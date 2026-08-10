"""coding domain: generator, verifier, runner tests.

The core claim: the goal (hidden suite) executes the artifact — visible-passing
code that misses hidden edges must FAIL, and the sandbox must reject unsafe
code without crashing the harness.
"""

from __future__ import annotations

import unittest

from benchbrew.generator import Generator
from benchbrew.runner import ScriptedAgent, run_task
from benchbrew.spec import validate_spec
from domains.coding import (
    CODING, _BUGGY_MIN_INDEX, _CRASHY_PARSE, _run_code, _visible_results,
)


class TestSpec(unittest.TestCase):
    def test_spec_validates(self):
        self.assertEqual(validate_spec(CODING), [])

    def test_generation_is_deterministic(self):
        g = Generator(CODING)
        w1, t1 = g.generate(42, 14)
        w2, t2 = g.generate(42, 14)
        self.assertEqual(
            [t["ctx"] for t in t1], [t["ctx"] for t in t2])
        self.assertEqual(
            [t["prompt"] for t in t1], [t["prompt"] for t in t2])

    def test_hidden_tests_never_in_world(self):
        g = Generator(CODING)
        _, tasks = g.generate(42, 7)
        for t in tasks:
            tests = t["initial_world"].get("tests")
            self.assertTrue(all(tt["visible"] for tt in tests.values()),
                            "world leaked a hidden test")


class TestSandbox(unittest.TestCase):
    def test_correct_code_passes(self):
        code = "def fizzbuzz(n):\n    out = []\n    for i in range(1, n + 1):\n        if i % 15 == 0: out.append('FizzBuzz')\n        elif i % 3 == 0: out.append('Fizz')\n        elif i % 5 == 0: out.append('Buzz')\n        else: out.append(str(i))\n    return ' '.join(out)\n"
        test = ("def test():\n"
                '    return fizzbuzz(15) == "1 2 Fizz 4 Buzz Fizz 7 8 Fizz '
                'Buzz 11 Fizz 13 14 FizzBuzz"\n')
        self.assertTrue(_run_code(code, test))

    def test_unsafe_code_does_not_crash(self):
        # import/open/network must be impossible; the goal returns False
        code = "import os\n"
        test = "def test():\n    return True\n"
        self.assertFalse(_run_code(code, test))
        code2 = "open('/etc/passwd')\n"
        self.assertFalse(_run_code(code2, test))


class TestArchetypes(unittest.TestCase):
    def _goal(self, arch_name, idx, code):
        t = [x for x in Generator(CODING).generate(42, 14)[1]
             if x["archetype"] == arch_name][idx]
        world = t["initial_world"]
        world.get("files")["main"]["content"] = code
        ok, _ = t["goal"](world, t["ctx"])
        return ok

    # --- implement family ---
    def test_implement_fizzbuzz_correct(self):
        code = (
            "def fizzbuzz(n):\n"
            "    out = []\n"
            "    for i in range(1, n + 1):\n"
            "        if i % 15 == 0: out.append('FizzBuzz')\n"
            "        elif i % 3 == 0: out.append('Fizz')\n"
            "        elif i % 5 == 0: out.append('Buzz')\n"
            "        else: out.append(str(i))\n"
            "    return ' '.join(out)\n"
        )
        self.assertTrue(self._goal("implement_fizzbuzz", 0, code))

    def test_implement_fizzbuzz_wrong(self):
        code = "def fizzbuzz(n):\n    return 'wrong'\n"
        self.assertFalse(self._goal("implement_fizzbuzz", 0, code))

    def test_implement_cart_total_correct(self):
        code = (
            "def cart_total(cart):\n"
            "    return sum(p * q for p, q in cart)\n"
        )
        self.assertTrue(self._goal("implement_cart_total", 0, code))

    def test_implement_cart_total_wrong(self):
        code = "def cart_total(cart):\n    return 0\n"
        self.assertFalse(self._goal("implement_cart_total", 0, code))

    # --- fix-bug family ---
    def test_fix_bug_is_even_fixed(self):
        code = "def is_even(n):\n    return n % 2 == 0\n"
        self.assertTrue(self._goal("fix_bug_is_even", 0, code))

    def test_fix_bug_is_even_unfixed(self):
        code = "def is_even(n):\n    return n % 2 == 1\n"
        self.assertFalse(self._goal("fix_bug_is_even", 0, code))

    def test_fix_bug_min_index_fixed(self):
        code = (
            "def min_index(nums):\n"
            "    if not nums:\n"
            "        return -1\n"
            "    return nums.index(min(nums))\n"
        )
        self.assertTrue(self._goal("fix_bug_min_index", 0, code))

    def test_fix_bug_min_index_unfixed(self):
        self.assertFalse(self._goal("fix_bug_min_index", 0, _BUGGY_MIN_INDEX))

    # --- edge-case family: visible passes, hidden edge must bite ---
    def test_edge_divide_guarded(self):
        code = (
            "def safe_divide(a, b):\n"
            "    return a / b if b != 0 else 0.0\n"
        )
        self.assertTrue(self._goal("edge_divide", 0, code))

    def test_edge_divide_unguarded(self):
        # passes the visible test, fails the hidden zero case
        code = "def safe_divide(a, b):\n    return a / b\n"
        self.assertFalse(self._goal("edge_divide", 0, code))

    def test_edge_empty_guarded(self):
        code = (
            "def first_word(s):\n"
            "    return s.split(' ')[0] if s.strip() else ''\n"
        )
        self.assertTrue(self._goal("edge_empty", 0, code))

    def test_edge_empty_unguarded(self):
        code = "def first_word(s):\n    return s[:s.index(' ')]\n"
        self.assertFalse(self._goal("edge_empty", 0, code))

    # --- diagnosis family ---
    def test_read_error_fixed(self):
        code = (
            "def parse_row(line):\n"
            "    parts = line.split(',')\n"
            "    try:\n"
            "        qty = int(parts[1])\n"
            "    except (IndexError, ValueError):\n"
            "        qty = 0\n"
            "    return {'name': parts[0], 'qty': qty}\n"
        )
        self.assertTrue(self._goal("read_error_fix", 0, code))

    def test_read_error_unfixed(self):
        self.assertFalse(self._goal("read_error_fix", 0, _CRASHY_PARSE))


class TestRunner(unittest.TestCase):
    def test_scripted_agent_fixes_bug(self):
        t = [x for x in Generator(CODING).generate(42, 14)[1]
             if x["archetype"] == "fix_bug_is_even"][0]
        agent = ScriptedAgent([
            ("read_file", {"file_id": "main"}),
            ("run_tests", {}),
            ("write_code", {"file_id": "main",
                            "content": "def is_even(n):\n    return n % 2 == 0\n"}),
            ("run_tests", {}),
        ])
        r = run_task(CODING, agent, t)
        self.assertTrue(r.success, r.reasons)

    def test_scripted_agent_leaves_bug_fails(self):
        t = [x for x in Generator(CODING).generate(42, 14)[1]
             if x["archetype"] == "fix_bug_is_even"][0]
        agent = ScriptedAgent([
            ("read_file", {"file_id": "main"}),
            ("run_tests", {}),
        ])
        r = run_task(CODING, agent, t)
        self.assertFalse(r.success)

    def test_runner_visible_tests_reflect_world(self):
        t = [x for x in Generator(CODING).generate(42, 14)[1]
             if x["archetype"] == "fix_bug_is_even"][0]
        world = t["initial_world"]
        res = _visible_results(world)
        # the planted bug fails the visible suite too
        self.assertFalse(all(res.values()))


if __name__ == "__main__":
    unittest.main()
