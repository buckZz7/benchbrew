"""BenchBrew domain: coding — the execution-verified lane.

The evaluated agent is the owner's coding assistant in a tiny repo: it
reads files, writes code, and runs the VISIBLE test suite. The oracle is
the HIDDEN test suite inside the goal predicates: at evaluation, the
submitted code is executed against hidden tests in a restricted sandbox.
Pass/fail is deterministic — the strongest form of the factory's promise:
a king's score means capability, not memorization, because you cannot
memorize past a hidden test.

Hidden-test rule (the lane's one hard design constraint): hidden tests
live ONLY in the goal predicates (the spec), never in the agent's world.
The agent's run_tests tool exposes only the visible suite, so overfitting
the visible tests cannot pass the goal.

The oracle is an executable specification: unlike consumer-policy lanes
(Reg E, DOT), the source of truth here is the test contract itself,
authored deterministically in the spec and executed at evaluation —
execution-verified by construction. See GROUNDING.md domain 6.
"""

from __future__ import annotations

import builtins
import time

from benchbrew.spec import DomainSpec, EntitySpec, ToolSpec, World

# ---------------------------------------------------------------------------
# The sandbox: a restricted Python execution surface for submitted code.
# The code runs with a safe builtins allowlist and a timeout; anything else
# (imports, IO, network) is absent by construction. This is an eval harness,
# not a service — the blast radius is the single evaluation process.
# ---------------------------------------------------------------------------

_SAFE_BUILTINS = {n: getattr(builtins, n) for n in (
    "abs", "all", "any", "bool", "chr", "dict", "divmod", "enumerate",
    "float", "format", "frozenset", "int", "isinstance", "issubclass",
    "iter", "len", "list", "map", "max", "min", "next", "object", "ord",
    "pow", "print", "range", "repr", "reversed", "round", "set", "slice",
    "sorted", "str", "sum", "tuple", "zip",
    "Exception", "ArithmeticError", "LookupError", "ValueError",
    "IndexError", "KeyError", "TypeError", "ZeroDivisionError",
    "RuntimeError", "NameError", "AttributeError", "OverflowError",
    "StopIteration", "ImportError", "MemoryError", "NotImplementedError",
)}


def _run_code(code: str, test_fn: str, timeout_s: float = 3.0) -> bool:
    """Execute submitted code + a test function in the sandbox; return pass."""
    ns = {"__builtins__": dict(_SAFE_BUILTINS)}
    started = time.monotonic()
    try:
        exec(code, ns)  # noqa: S102 — the sandbox IS the eval harness
        if time.monotonic() - started > timeout_s:
            return False
        exec(test_fn, ns)  # noqa: S102 — defines test() -> bool
        return bool(ns["test"]())
    except Exception:
        return False


def _visible_results(world: World) -> dict:
    """Run the VISIBLE suite against the current main file."""
    code = world.get("files").get("main", {}).get("content", "")
    results = {}
    for tid, t in world.get("tests").items():
        results[t["name"]] = _run_code(code, t["fn"])
    return results


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def _list_files(world, args, ctx):
    return {"files": [f["name"] for f in world.get("files").values()]}


def _read_file(world, args, ctx):
    f = world.get("files").get(args["file_id"])
    if f is None:
        raise ValueError(f"file {args['file_id']} not found")
    return {"name": f["name"], "content": f["content"]}


def _list_tests(world, args, ctx):
    return {"tests": [t["name"] for t in world.get("tests").values()]}


def _write_code(world, args, ctx):
    f = world.get("files").get(args["file_id"])
    if f is None:
        raise ValueError(f"file {args['file_id']} not found")
    f["content"] = args["content"]
    return {"file_id": args["file_id"], "written": True}


def _run_tests(world, args, ctx):
    results = _visible_results(world)
    run_id = f"r{len(world.get('runs')) + 1}"
    world.get("runs")[run_id] = {
        "id": run_id, "status": "done", "results": results,
    }
    return {"run_id": run_id, "results": results}


def _get_failure(world, args, ctx):
    results = _visible_results(world)
    name = args.get("test_name")
    if name is not None:
        return {"test_name": name, "passed": bool(results.get(name))}
    failed = [n for n, ok in results.items() if not ok]
    return {"failed": failed}


def _ask_owner(world, args, ctx):
    req_id = str(len(world.get("requests")) + 1)
    world.get("requests")[req_id] = {
        "id": req_id, "question": args["question"], "answered": False,
    }
    return {"request_id": req_id}


# ---------------------------------------------------------------------------
# Archetypes — every task carries its hidden suite inside the goal fn.
# ---------------------------------------------------------------------------

def _seed(world: World, starter: str, visible_tests: dict) -> None:
    world.get("files")["main"] = {
        "id": "main", "name": "main.py", "content": starter,
    }
    for tid, (tname, fn) in enumerate(visible_tests.items(), 1):
        world.get("tests")[f"t{tid}"] = {
            "id": f"t{tid}", "name": tname, "visible": True, "fn": fn,
        }
    world.get("runs")
    world.get("requests")


# --- implement family -------------------------------------------------------

# --- implement family (minimal numeric shapes: one expression, no strings) ---

def arch_implement_add(rng, world, i):
    _seed(world, "", {
        "small": "def test():\n    return add(2, 3) == 5\n",
    })
    return {"file_id": "main", "task": "implement_add"}


def arch_implement_add_prompt(ctx):
    return (
        "Alex needs a function `add(a, b) -> int` that returns a + b. "
        "Write it in main.py and run the tests until they pass."
    )


def arch_implement_add_goal(world: World, ctx) -> bool:
    code = world.get("files").get("main", {}).get("content", "")
    hidden = (
        'def test():\n'
        '    if add(0, 0) != 0: return False\n'
        '    if add(-1, 1) != 0: return False\n'
        '    return add(10, 32) == 42\n'
    )
    ok = _run_code(code, hidden)
    return ok, [] if ok else ["hidden_suite_failed"]


def arch_implement_cart_total(rng, world, i):
    _seed(world, "", {
        "small": "def test():\n    return cart_total([(2.0, 3)]) == 6.0\n",
    })
    return {"file_id": "main", "task": "implement_cart_total"}


def arch_implement_cart_total_prompt(ctx):
    return (
        "Alex needs a function `cart_total(cart: list) -> float` where cart is "
        "a list of (price, quantity) tuples; it returns the sum of price*quantity. "
        "Write it in main.py and run the tests until they pass."
    )


def arch_implement_cart_total_goal(world: World, ctx) -> bool:
    code = world.get("files").get("main", {}).get("content", "")
    hidden = (
        'def test():\n'
        '    t = cart_total([(3.5, 2), (1.0, 5), (0.5, 10)])\n'
        '    if abs(t - 17.0) > 1e-9: return False\n'
        '    return cart_total([]) == 0.0\n'
    )
    ok = _run_code(code, hidden)
    return ok, [] if ok else ["hidden_suite_failed"]


# --- fix-bug family ---------------------------------------------------------

_BUGGY_IS_EVEN = (
    "def is_even(n: int) -> bool:\n"
    "    return n % 2 == 1\n"
)


def arch_fix_bug_is_even(rng, world, i):
    _seed(world, _BUGGY_IS_EVEN, {
        "even_returns_true": "def test():\n    return is_even(4) is True\n",
        "odd_returns_false": "def test():\n    return is_even(3) is False\n",
    })
    return {"file_id": "main", "task": "fix_bug_is_even"}


def arch_fix_bug_is_even_prompt(ctx):
    return (
        "Alex's function `is_even(n)` is wrong: it returns the opposite of what "
        "it should. The tests are failing. Read the code, fix the bug, and get "
        "the tests green. (Do not change the function name or signature.)"
    )


def arch_fix_bug_is_even_goal(world: World, ctx) -> bool:
    code = world.get("files").get("main", {}).get("content", "")
    hidden = (
        'def test():\n'
        '    if not is_even(0): return False\n'
        '    if not is_even(-4): return False\n'
        '    if is_even(7): return False\n'
        '    return is_even(10) is True\n'
    )
    ok = _run_code(code, hidden)
    return ok, [] if ok else ["hidden_suite_failed"]


_BUGGY_MIN_INDEX = (
    "def min_index(nums: list) -> int:\n"
    "    if not nums:\n"
    "        return -1\n"
    "    m = nums[0]\n"
    "    idx = 0\n"
    "    for i, v in enumerate(nums):\n"
    "        if v < m:\n"
    "            m = v\n"
    "            idx = i + 1\n"
    "    return idx\n"
)


def arch_fix_bug_min_index(rng, world, i):
    _seed(world, _BUGGY_MIN_INDEX, {
        "min_of_three": "def test():\n    return min_index([3, 1, 2]) == 1\n",
    })
    return {"file_id": "main", "task": "fix_bug_min_index"}


def arch_fix_bug_min_index_prompt(ctx):
    return (
        "Alex's `min_index(nums)` should return the index of the smallest value "
        "but has an off-by-one bug. The test is failing. Fix it without changing "
        "the name or signature, and get the tests green."
    )


def arch_fix_bug_min_index_goal(world: World, ctx) -> bool:
    code = world.get("files").get("main", {}).get("content", "")
    hidden = (
        'def test():\n'
        '    if min_index([5]) != 0: return False\n'
        '    if min_index([3, 1, 2]) != 1: return False\n'
        '    if min_index([7, 8, 6, 9]) != 2: return False\n'
        '    return min_index([]) == -1\n'
    )
    ok = _run_code(code, hidden)
    return ok, [] if ok else ["hidden_suite_failed"]


# --- edge-case family (visible passes, hidden edge bites) --------------------

_EDGE_DIVIDE = (
    "def safe_divide(a: float, b: float) -> float:\n"
    "    return a / b\n"
)


def arch_edge_divide(rng, world, i):
    _seed(world, _EDGE_DIVIDE, {
        "normal": "def test():\n    return safe_divide(10, 2) == 5.0\n",
    })
    return {"file_id": "main", "task": "edge_divide"}


def arch_edge_divide_prompt(ctx):
    return (
        "Alex needs `safe_divide(a, b)` to never raise: when b is zero it should "
        "return 0.0. The visible test passes, but the hidden suite checks the "
        "zero case. Update the code so every input is safe."
    )


def arch_edge_divide_goal(world: World, ctx) -> bool:
    code = world.get("files").get("main", {}).get("content", "")
    hidden = (
        'def test():\n'
        '    if safe_divide(10, 0) != 0.0: return False\n'
        '    if safe_divide(-6, 2) != -3.0: return False\n'
        '    return safe_divide(0, 0) == 0.0\n'
    )
    ok = _run_code(code, hidden)
    return ok, [] if ok else ["hidden_suite_failed"]


_EDGE_EMPTY = (
    "def first_word(s: str) -> str:\n"
    "    return s[:s.index(' ')]\n"
)


def arch_edge_empty(rng, world, i):
    _seed(world, _EDGE_EMPTY, {
        "normal": "def test():\n    return first_word('hello world') == 'hello'\n",
    })
    return {"file_id": "main", "task": "edge_empty"}


def arch_edge_empty_prompt(ctx):
    return (
        "Alex needs `first_word(s)` to return the first word of a space-separated "
        "string, and return '' for an empty string (the current code raises). The "
        "visible test passes; the hidden suite checks the empty input. Make it "
        "safe for every input."
    )


def arch_edge_empty_goal(world: World, ctx) -> bool:
    code = world.get("files").get("main", {}).get("content", "")
    hidden = (
        'def test():\n'
        '    if first_word("") != "": return False\n'
        '    if first_word("single") != "single": return False\n'
        '    if first_word("hello world") != "hello": return False\n'
        '    return first_word("  ") == ""\n'
    )
    ok = _run_code(code, hidden)
    return ok, [] if ok else ["hidden_suite_failed"]


# --- diagnosis family --------------------------------------------------------

_CRASHY_PARSE = (
    "def parse_row(line: str) -> dict:\n"
    "    parts = line.split(',')\n"
    "    return {'name': parts[0], 'qty': int(parts[1])}\n"
)


def arch_read_error_fix(rng, world, i):
    _seed(world, _CRASHY_PARSE, {
        "normal": "def test():\n    return parse_row('a,2') == {'name': 'a', 'qty': 2}\n",
    })
    return {"file_id": "main", "task": "read_error_fix"}


def arch_read_error_fix_prompt(ctx):
    return (
        "Alex ran parse_row('widget,') and it crashed with a ValueError "
        "(int() got an empty string). The function should treat a missing "
        "quantity as 0. Fix it so no input crashes, and the tests stay green."
    )


def arch_read_error_fix_goal(world: World, ctx) -> bool:
    code = world.get("files").get("main", {}).get("content", "")
    hidden = (
        'def test():\n'
        "    if parse_row('widget,') != {'name': 'widget', 'qty': 0}: return False\n"
        "    if parse_row('x,7') != {'name': 'x', 'qty': 7}: return False\n"
        "    return parse_row(',') == {'name': '', 'qty': 0}\n"
    )
    ok = _run_code(code, hidden)
    return ok, [] if ok else ["hidden_suite_failed"]


# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------

def _empty_inbox(rng, ctx, world):
    return {}


CODING = DomainSpec(
    name="coding",
    version="0.2.0",
    entities={
        "files": EntitySpec({"id": str, "name": str, "content": str}),
        "tests": EntitySpec({"id": str, "name": str, "visible": bool, "fn": str}),
        "runs": EntitySpec({"id": str, "status": str, "results": dict}),
        "requests": EntitySpec({"id": str, "question": str, "answered": bool}),
    },
    tools={
        "list_files": ToolSpec("list_files", {}, "read", "list the repo files"),
        "read_file": ToolSpec("read_file", {"file_id": str}, "read", "read a file"),
        "list_tests": ToolSpec("list_tests", {}, "read", "list the visible tests"),
        "write_code": ToolSpec("write_code", {"file_id": str, "content": str},
                               "write", "write code to a file"),
        "run_tests": ToolSpec("run_tests", {}, "write", "run the visible suite"),
        "get_failure": ToolSpec("get_failure", {"test_name": str}, "read",
                                "check a test's result"),
        "ask_owner": ToolSpec("ask_owner", {"question": str}, "write",
                              "ask Alex a question"),
    },
    tool_impls={
        "list_files": _list_files,
        "read_file": _read_file,
        "list_tests": _list_tests,
        "write_code": _write_code,
        "run_tests": _run_tests,
        "get_failure": _get_failure,
        "ask_owner": _ask_owner,
    },
    rules={},
    rule_sources={},
    archetypes={
        "implement_add": {
            "role": "write", "sample": arch_implement_add,
            "prompt": arch_implement_add_prompt, "inbox": _empty_inbox,
            "goal": arch_implement_add_goal,
        },
        "implement_cart_total": {
            "role": "write", "sample": arch_implement_cart_total,
            "prompt": arch_implement_cart_total_prompt, "inbox": _empty_inbox,
            "goal": arch_implement_cart_total_goal,
        },
        "fix_bug_is_even": {
            "role": "write", "sample": arch_fix_bug_is_even,
            "prompt": arch_fix_bug_is_even_prompt, "inbox": _empty_inbox,
            "goal": arch_fix_bug_is_even_goal,
        },
        "fix_bug_min_index": {
            "role": "write", "sample": arch_fix_bug_min_index,
            "prompt": arch_fix_bug_min_index_prompt, "inbox": _empty_inbox,
            "goal": arch_fix_bug_min_index_goal,
        },
        "edge_divide": {
            "role": "write", "sample": arch_edge_divide,
            "prompt": arch_edge_divide_prompt, "inbox": _empty_inbox,
            "goal": arch_edge_divide_goal,
        },
        "edge_empty": {
            "role": "write", "sample": arch_edge_empty,
            "prompt": arch_edge_empty_prompt, "inbox": _empty_inbox,
            "goal": arch_edge_empty_goal,
        },
        "read_error_fix": {
            "role": "write", "sample": arch_read_error_fix,
            "prompt": arch_read_error_fix_prompt, "inbox": _empty_inbox,
            "goal": arch_read_error_fix_goal,
        },
    },
    seed_world=lambda rng, world: world,
)
