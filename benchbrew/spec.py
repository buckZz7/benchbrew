"""BenchBrew core: domain spec types + world state.

v0 rules-as-code: a DomainSpec declares entities/tools (data) and rule/goal
functions (deterministic Python). The DSL-as-data ergonomics layer comes later;
the trust contract is already here: everything derives from the spec, nothing
from an LLM.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable

# ---------------------------------------------------------------------------
# World: generic entity collections (id -> record dict). Storage-agnostic by
# design (the audit: Pydantic v1, swappable behind the tool interface).
# ---------------------------------------------------------------------------


class World:
    def __init__(self, collections: dict[str, dict[str, dict]] | None = None):
        self.collections = collections or {}

    def get(self, name: str) -> dict[str, dict]:
        return self.collections.setdefault(name, {})

    def clone(self) -> "World":
        return World(
            {k: {i: dict(r) for i, r in v.items()} for k, v in self.collections.items()}
        )

    def canonical(self) -> str:
        return json.dumps(self.collections, sort_keys=True, separators=(",", ":"))


class PolicyError(Exception):
    """A policy rule rejected the tool call."""


# ---------------------------------------------------------------------------
# Spec types
# ---------------------------------------------------------------------------


@dataclass
class EntitySpec:
    fields: dict[str, type]
    desc: str = ""


@dataclass
class ToolSpec:
    name: str
    params: dict[str, type]
    kind: str = "write"  # read | write
    desc: str = ""


@dataclass
class DomainSpec:
    name: str
    entities: dict[str, EntitySpec]
    tools: dict[str, ToolSpec]
    # rule: fn(world, tool_name, args, ctx) -> None; raises PolicyError on violation
    rules: dict[str, Callable] = field(default_factory=dict)
    # tool impl: fn(world, args, ctx) -> dict (the tool's return value)
    tool_impls: dict[str, Callable] = field(default_factory=dict)
    # seed_world: fn(world, rng) -> None  (baseline world population)
    seed_world: Callable | None = None
    # archetype: {name: {role, sample: fn(rng, world) -> ctx,
    #                    goal: fn(world, ctx) -> (bool, [reasons]),
    #                    prompt: fn(ctx) -> str (owner instruction),
    #                    inbox: fn(rng, ctx, world) -> [events]}}
    archetypes: dict[str, dict] = field(default_factory=dict)
    version: str = "0.1.0"

    def spec_hash(self) -> str:
        blob = json.dumps(
            {
                "name": self.name,
                "version": self.version,
                "entities": {k: sorted(v.fields) for k, v in self.entities.items()},
                "tools": {k: sorted(v.params) for k, v in self.tools.items()},
                "rules": sorted(self.rules),
                "archetypes": sorted(self.archetypes),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Bundle: the deterministic output of (spec, seed)
# ---------------------------------------------------------------------------


def bundle_hash(spec: DomainSpec, seed: int, tasks: list[dict]) -> str:
    blob = json.dumps(
        {"spec": spec.spec_hash(), "seed": seed, "tasks": tasks},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def canonical_tasks(tasks: list[dict]) -> list[dict]:
    """Hashable/serializable task form: goal fns and world objects replaced
    by their deterministic representations. THE canonicalization for bundle
    hashes — used by the CLI determinism check, the emitter manifest, and
    tests, so every hash is computed the same way."""
    out = []
    for t in tasks:
        d = {k: v for k, v in t.items() if k not in ("goal", "initial_world")}
        d["goal"] = t["goal_desc"](t["ctx"])
        d["initial_world"] = t["initial_world"].canonical()
        out.append(d)
    return out


def deepcopy(x: Any) -> Any:
    return copy.deepcopy(x)
