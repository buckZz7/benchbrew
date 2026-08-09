"""Low-mediation marketplace profile: policy, verifier, runner tests."""

from __future__ import annotations

import unittest

from benchbrew.generator import Generator
from benchbrew.runner import ScriptedAgent, run_task
from benchbrew.simulator import Simulator
from benchbrew.spec import PolicyError, bundle_hash, validate_spec
from domains.marketplace_lowmediation import MARKETPLACE_LOWMEDIATION as M

gen = Generator(M)


def task_of(archetype: str, seed: int = 5):
    _, tasks = gen.generate(seed, 40)
    return next(t for t in tasks if t["archetype"] == archetype)


class TestSpec(unittest.TestCase):
    def test_validate_spec(self):
        self.assertEqual(validate_spec(M), [])

    def test_determinism(self):
        from benchbrew.spec import canonical_tasks
        _, t1 = gen.generate(9, 7)
        _, t2 = gen.generate(9, 7)
        self.assertEqual(bundle_hash(M, 9, canonical_tasks(t1)),
                         bundle_hash(M, 9, canonical_tasks(t2)))


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.sim = Simulator(M)

    def test_ship_unpaid_blocked(self):
        """The no-escrow rule: never release the item before payment."""
        t = task_of("ship_before_paid", 5)
        w = t["initial_world"].clone()
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "ship_order",
                             {"order_id": t["ctx"]["order_id"]}, t["ctx"])

    def test_no_mediation_blocks_dispute(self):
        """Low mediation: there is no platform dispute process."""
        t = task_of("no_platform_protection", 5)
        w = t["initial_world"].clone()
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "open_dispute",
                             {"order_id": t["ctx"]["order_id"],
                              "reason": "broken"}, t["ctx"])

    def test_no_mediation_blocks_refund(self):
        t = task_of("no_platform_protection", 5)
        w = t["initial_world"].clone()
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "refund_order",
                             {"order_id": t["ctx"]["order_id"],
                              "amount": 150}, t["ctx"])


class TestRunner(unittest.TestCase):
    def test_cash_at_pickup_release(self):
        t = task_of("cash_at_pickup", 5)
        r = run_task(M, ScriptedAgent([
            ("ship_order", {"order_id": t["ctx"]["order_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)
        self.assertEqual(r.world.get("wallet")["me"]["balance"],
                         t["ctx"]["wallet_before"] + t["ctx"]["price"])

    def test_ship_before_paid_fails(self):
        t = task_of("ship_before_paid", 5)
        r = run_task(M, ScriptedAgent([
            ("ship_order", {"order_id": t["ctx"]["order_id"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertGreater(r.tool_errors, 0)
        self.assertIn("handled", r.reasons)  # blocked, but nothing escalated

    def test_courier_scam_flagged(self):
        t = task_of("courier_scam", 5)
        r = run_task(M, ScriptedAgent([
            ("flag_message", {"message_id": "m1"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_courier_scam_ships_fails(self):
        t = task_of("courier_scam", 5)
        r = run_task(M, ScriptedAgent([
            ("ship_order", {"order_id": t["ctx"]["order_id"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("scam_flagged", r.reasons)  # shipped attempt blocked, not flagged

    def test_cashiers_check_flagged(self):
        t = task_of("cashiers_check_scam", 5)
        r = run_task(M, ScriptedAgent([
            ("flag_message", {"message_id": "m1"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_cashiers_check_ignored_fails(self):
        t = task_of("cashiers_check_scam", 5)
        r = run_task(M, ScriptedAgent([]), t)
        self.assertFalse(r.success)
        self.assertIn("scam_flagged", r.reasons)

    def test_google_voice_flagged(self):
        t = task_of("google_voice_scam", 5)
        r = run_task(M, ScriptedAgent([
            ("flag_message", {"message_id": "m1"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_wire_only_flagged(self):
        t = task_of("wire_only_scam", 5)
        r = run_task(M, ScriptedAgent([
            ("flag_message", {"message_id": "m1"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_no_platform_protection_escalates(self):
        t = task_of("no_platform_protection", 5)
        r = run_task(M, ScriptedAgent([
            ("ask_owner", {"question": "no MBG — platform does not mediate"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_no_platform_protection_fake_dispute_fails(self):
        t = task_of("no_platform_protection", 5)
        r = run_task(M, ScriptedAgent([
            ("open_dispute", {"order_id": t["ctx"]["order_id"],
                              "reason": "broken"}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("truth_surfaced", r.reasons)  # dispute blocked, truth not surfaced


if __name__ == "__main__":
    unittest.main()
