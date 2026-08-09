"""Runner: execute a generated bundle against an agent.

The agent is pluggable — an OpenAI-compatible HTTP client (any served
model) or a scripted agent (GPU-free tests). For each task: present the
prompt + inbox as context, let the agent act through the spec's tools
(via the simulator, policy enforced), cap steps, then run the spec-derived
verifier. Output: a receipt per task (success, calls, errors, termination,
wall clock) — the same shape the arena consumes.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.error import HTTPError

from .generator import Generator
from .simulator import Simulator
from .spec import DomainSpec, PolicyError, World
from .verifier import check


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


@dataclass
class AgentMessage:
    role: str  # system | user | assistant | tool
    content: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class BaseAgent:
    def respond(self, messages: list[AgentMessage], tools: list[dict]) -> AgentMessage:
        raise NotImplementedError


class ScriptedAgent(BaseAgent):
    """Deterministic agent: a scripted sequence of tool calls. For tests —
    proves the runner + verifier without any model."""

    def __init__(self, script: list[tuple[str, dict]], final: str = "Done."):
        self.script = list(script)
        self.final = final

    def respond(self, messages, tools):
        if self.script:
            name, args = self.script.pop(0)
            return AgentMessage(role="assistant", content=None,
                                tool_calls=[{"id": f"c{len(self.script)}",
                                             "type": "function",
                                             "function": {"name": name,
                                                          "arguments": json.dumps(args)}}])
        return AgentMessage(role="assistant", content=self.final)


class OpenAIClientAgent(BaseAgent):
    """Thin OpenAI-compatible chat client (stdlib only)."""

    def __init__(self, base_url: str, model: str, max_tokens: int = 512):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens

    def respond(self, messages, tools):
        body = {
            "model": self.model,
            "messages": [_to_api(m) for m in messages],
            "max_tokens": self.max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        m = data["choices"][0]["message"]
        return AgentMessage(
            role="assistant",
            content=m.get("content"),
            tool_calls=m.get("tool_calls"),
        )


def _to_api(m: AgentMessage) -> dict:
    if m.role == "tool":
        return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
    out = {"role": m.role, "content": m.content}
    if m.tool_calls:
        out["tool_calls"] = m.tool_calls
    return out


# ---------------------------------------------------------------------------
# Tool schema (spec -> OpenAI function schema)
# ---------------------------------------------------------------------------

_PY_TO_JSON = {int: "integer", str: "string", float: "number", bool: "boolean"}


def tool_schema(spec: DomainSpec) -> list[dict]:
    out = []
    for name, ts in spec.tools.items():
        props, required = {}, []
        for p, t in ts.params.items():
            props[p] = {"type": _PY_TO_JSON.get(t, "string")}
            if t is not None and not (hasattr(t, "__args__") and type(None) in t.__args__):
                required.append(p)
        out.append({"type": "function",
                    "function": {"name": name, "description": ts.desc,
                                 "parameters": {"type": "object",
                                                "properties": props,
                                                "required": required}}})
    return out


# ---------------------------------------------------------------------------
# The run loop
# ---------------------------------------------------------------------------


@dataclass
class TaskResult:
    task_id: str
    archetype: str
    success: bool
    reasons: list[str]
    tool_calls: int = 0
    tool_errors: int = 0
    termination: str = "agent_stop"
    wall_clock_s: float = 0.0


def run_bundle(spec: DomainSpec, agent: BaseAgent, seed: int = 42,
               n_tasks: int = 10, max_steps: int = 20,
               archetype: str | None = None) -> list[TaskResult]:
    _, tasks = Generator(spec).generate(seed, max(n_tasks * 4, 20))
    if archetype:
        tasks = [t for t in tasks if t["archetype"] == archetype][:n_tasks]
    else:
        tasks = tasks[:n_tasks]
    return [run_task(spec, agent, t, max_steps) for t in tasks]


def _render_event(e: dict, users: dict) -> str:
    def uname(uid: str) -> str:
        u = users.get(uid, {})
        return u.get("name", uid) if isinstance(u, dict) else uid

    if e["type"] == "order":
        return (f"Order {e['order_id']} ({e.get('status', '')}, placed "
                f"{e.get('placed_hours_ago', '?')}h ago)")
    if e["type"] == "offer":
        return (f"Offer {e['offer_id']} on listing {e['listing_id']} "
                f"from {uname(e['from'])}: ${e['amount']}"
                + (f" (expires in {e['expires_in_hours']}h)"
                   if e.get("expires_in_hours") else ""))
    return f"Message {e['message_id']} from {uname(e['from'])}: \"{e['text']}\""


def run_task(spec: DomainSpec, agent: BaseAgent, task: dict,
             max_steps: int = 20) -> TaskResult:
    sim = Simulator(spec)
    tools = tool_schema(spec)
    world: World = task["initial_world"].clone()
    ctx = dict(task["ctx"])
    start = time.time()
    messages: list[AgentMessage] = [
        AgentMessage(role="system", content=(
            "You are Alex's personal assistant on a second-hand marketplace. "
            "Your user id is 'me' (you act for Alex). "
            "ALWAYS perform actions with the provided tools — never describe an "
            "action you have not actually performed. If you need an identifier, "
            "find it with the read tools or the inbox below; do not invent ids.")),
        AgentMessage(role="user", content=task["prompt"]),
    ]
    if task["inbox"]:
        users = task["initial_world"].get("users")
        known = "\n".join(f"- {_render_event(e, users)}" for e in task["inbox"])
        messages.append(AgentMessage(role="user",
                                     content=f"Pending inbox:\n{known}"))

    calls, errors, termination = 0, 0, "agent_stop"
    fired: set[int] = set()
    for _ in range(max_steps):
        try:
            msg = agent.respond(messages, tools)
        except HTTPError as e:
            # the server rejected the model's (corrupt) tool arguments —
            # count it as a server error, never crash the bundle
            errors += 1
            termination = "server_error"
            messages.append(AgentMessage(
                role="tool", tool_call_id="srv",
                content=f"ERROR: server rejected request: {e.code} {e.reason}"))
            break
        if not msg.tool_calls:
            messages.append(AgentMessage(role="assistant", content=msg.content))
            break
        messages.append(msg)
        for tc in msg.tool_calls:
            fn = tc.get("function", {})
            name, raw_args = fn.get("name"), fn.get("arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}
            calls += 1
            try:
                result = sim.execute(world, name, args, ctx)
                text = json.dumps(result, default=str)
            except (PolicyError, ValueError, KeyError, TypeError) as e:
                errors += 1
                text = f"ERROR: {e}"
            messages.append(AgentMessage(role="tool", tool_call_id=tc.get("id"),
                                         content=text))
            # world time advances: 1 tick (hour) per tool call — offers expire,
            # handling windows close, protection windows elapse
            world.tick += 1
            # counterparty events: scripted responses fire after their trigger
            # tool runs (e.g. the seller counters your offer). Deterministic,
            # zero-LLM — the spec authors the other side's behavior.
            for ci, cp in enumerate(task.get("counterparty", [])):
                if ci not in fired and cp.get("after") == name:
                    fired.add(ci)
                    for coll, records in cp.get("add_to_world", {}).items():
                        world.get(coll).update(records)
                    messages.append(AgentMessage(
                        role="user",
                        content=f"New inbox:\n- {_render_event(cp['event'], world.get('users'))}"))
        if errors >= 3:
            termination = "too_many_errors"
            break
    else:
        termination = "max_steps"

    ok, reasons = check(task, world)
    return TaskResult(
        task_id=task["id"], archetype=task["archetype"], success=ok,
        reasons=reasons, tool_calls=calls, tool_errors=errors,
        termination=termination, wall_clock_s=round(time.time() - start, 2),
    )


def report(results: list[TaskResult]) -> dict:
    n = len(results)
    wins = sum(1 for r in results if r.success)
    calls = sum(r.tool_calls for r in results)
    errors = sum(r.tool_errors for r in results)
    terms: dict[str, int] = {}
    for r in results:
        terms[r.termination] = terms.get(r.termination, 0) + 1
    return {
        "n_tasks": n,
        "success_rate": round(wins / n, 3) if n else 0.0,
        "n_success": wins,
        "tool_calls_per_task": round(calls / n, 1) if n else 0.0,
        "tool_error_rate": round(errors / calls, 3) if calls else 0.0,
        "terminations": terms,
        "per_task": [
            {"id": r.task_id, "archetype": r.archetype, "success": r.success,
             "reasons": r.reasons, "tool_calls": r.tool_calls,
             "tool_errors": r.tool_errors, "termination": r.termination,
             "wall_clock_s": r.wall_clock_s}
            for r in results
        ],
    }
