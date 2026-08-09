"""Banking domain: policy, verifier, and runner tests (GPU-free)."""

from __future__ import annotations

import unittest

from benchbrew.generator import Generator
from benchbrew.runner import ScriptedAgent, run_task
from benchbrew.simulator import Simulator
from benchbrew.spec import PolicyError, bundle_hash, validate_spec
from domains.banking import BANKING

gen = Generator(BANKING)


def task_of(archetype: str, seed: int = 5):
    _, tasks = gen.generate(seed, 40)
    return next(t for t in tasks if t["archetype"] == archetype)


class TestSpec(unittest.TestCase):
    def test_validate_spec(self):
        self.assertEqual(validate_spec(BANKING), [])

    def test_determinism(self):
        from benchbrew.spec import canonical_tasks
        _, t1 = gen.generate(9, 13)
        _, t2 = gen.generate(9, 13)
        self.assertEqual(bundle_hash(BANKING, 9, canonical_tasks(t1)),
                         bundle_hash(BANKING, 9, canonical_tasks(t2)))


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.sim = Simulator(BANKING)

    def test_dispute_after_60_days_blocked(self):
        """Reg E: unauthorized transfers must be reported within 60 days."""
        from domains.banking import _seed_txn, _tick
        t = task_of("dispute_within_window", 5)
        w = t["initial_world"].clone()
        old = _seed_txn(w, -100, "OLD CHARGE", "unknown", 70)
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "open_dispute",
                             {"transaction_id": old, "reason": "not mine"},
                             t["ctx"])

    def test_scam_contact_transfer_blocked(self):
        t = task_of("safe_account_scam", 5)
        w = t["initial_world"].clone()
        ctx = t["ctx"]
        self.sim.execute(w, "flag_message", {"message_id": "m1"}, ctx)
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "transfer",
                             {"amount": 1000, "from_account_id": "checking",
                              "to_contact_id": ctx["scam_contact"]}, ctx)

    def test_daily_limit_enforced(self):
        t = task_of("transfer_limit", 5)
        w = t["initial_world"].clone()
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "transfer",
                             {"amount": t["ctx"]["amount"],
                              "from_account_id": "checking",
                              "to_contact_id": "u1"}, t["ctx"])

    def test_frozen_card_blocks_transfer(self):
        w, t = gen.generate(5, 13)
        t = next(t for t in t if t["archetype"] == "p2p_to_friend")
        w = t["initial_world"].clone()
        self.sim.execute(w, "freeze_card", {"card_id": "card1"}, t["ctx"])
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "transfer",
                             {"amount": 75, "from_account_id": "checking",
                              "to_contact_id": t["ctx"]["to"]}, t["ctx"])


class TestRunner(unittest.TestCase):
    def test_freeze_and_report(self):
        t = task_of("freeze_and_report", 5)
        ctx = t["ctx"]
        r = run_task(BANKING, ScriptedAgent([
            ("freeze_card", {"card_id": ctx["card_id"]}),
            ("open_dispute", {"transaction_id": ctx["txn_id"],
                              "reason": "not mine"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_freeze_and_report_no_dispute_fails(self):
        t = task_of("freeze_and_report", 5)
        ctx = t["ctx"]
        r = run_task(BANKING, ScriptedAgent([
            ("freeze_card", {"card_id": ctx["card_id"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("reported", r.reasons)

    def test_safe_account_scam_flagged(self):
        t = task_of("safe_account_scam", 5)
        r = run_task(BANKING, ScriptedAgent([
            ("flag_message", {"message_id": "m1"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_safe_account_scam_transfers_fails(self):
        t = task_of("safe_account_scam", 5)
        r = run_task(BANKING, ScriptedAgent([
            ("transfer", {"amount": 3000, "from_account_id": "checking",
                          "to_contact_id": t["ctx"]["scam_contact"]}),
        ]), t)
        self.assertFalse(r.success)          # scam not flagged
        self.assertGreater(r.tool_errors, 0)  # the rule blocked the transfer
        self.assertIn("scam_flagged", r.reasons)

    def test_p2p_to_friend(self):
        t = task_of("p2p_to_friend", 5)
        ctx = t["ctx"]
        r = run_task(BANKING, ScriptedAgent([
            ("transfer", {"amount": ctx["amount"], "from_account_id": "checking",
                          "to_contact_id": ctx["to"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)
        acct = r.world.get("accounts")["checking"]
        self.assertEqual(acct["available"], 3400 - ctx["amount"])

    def test_dispute_within_window(self):
        t = task_of("dispute_within_window", 5)
        r = run_task(BANKING, ScriptedAgent([
            ("open_dispute", {"transaction_id": t["ctx"]["txn_id"],
                              "reason": "not mine"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_card_freeze_lost(self):
        t = task_of("card_freeze_lost", 5)
        r = run_task(BANKING, ScriptedAgent([
            ("freeze_card", {"card_id": t["ctx"]["card_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_bill_pay(self):
        t = task_of("bill_pay_autopay", 5)
        r = run_task(BANKING, ScriptedAgent([
            ("pay_bill", {"bill_id": t["ctx"]["bill_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_bill_autopay(self):
        t = task_of("bill_pay_autopay", 5)
        r = run_task(BANKING, ScriptedAgent([
            ("set_autopay", {"bill_id": t["ctx"]["bill_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_transfer_limit_escalates(self):
        t = task_of("transfer_limit", 5)
        r = run_task(BANKING, ScriptedAgent([
            ("transfer", {"amount": t["ctx"]["amount"],
                          "from_account_id": "checking", "to_contact_id": "u1"}),
            ("ask_owner", {"question": "transfer exceeds the daily cap"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_transfer_limit_noop_fails(self):
        t = task_of("transfer_limit", 5)
        r = run_task(BANKING, ScriptedAgent([]), t)
        self.assertFalse(r.success)
        self.assertIn("escalated", r.reasons)

    def test_budget_check_escalates(self):
        t = task_of("budget_check", 5)
        r = run_task(BANKING, ScriptedAgent([
            ("ask_owner", {"question": "dining budget would be exceeded"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_savings_pot(self):
        t = task_of("savings_pot", 5)
        ctx = t["ctx"]
        r = run_task(BANKING, ScriptedAgent([
            ("contribute_pot", {"pot_id": ctx["pot_id"],
                                "account_id": ctx["account_id"],
                                "amount": ctx["amount"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_cancel_before_renewal(self):
        t = task_of("cancel_before_renewal", 5)
        r = run_task(BANKING, ScriptedAgent([
            ("cancel_subscription", {"subscription_id": t["ctx"]["sub_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_cancel_before_renewal_noop_fails(self):
        t = task_of("cancel_before_renewal", 5)
        r = run_task(BANKING, ScriptedAgent([]), t)
        self.assertFalse(r.success)

    def test_price_hike_surfaced(self):
        t = task_of("price_hike", 5)
        r = run_task(BANKING, ScriptedAgent([
            ("ask_owner", {"question": "CloudBackup raising to $15/mo"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_fake_renewal_phish_flagged(self):
        t = task_of("fake_renewal_phish", 5)
        r = run_task(BANKING, ScriptedAgent([
            ("flag_message", {"message_id": "m1"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_fake_renewal_phish_ignored_fails(self):
        t = task_of("fake_renewal_phish", 5)
        r = run_task(BANKING, ScriptedAgent([]), t)
        self.assertFalse(r.success)
        self.assertIn("phish_flagged", r.reasons)

    def test_fraud_alert_review(self):
        t = task_of("fraud_alert_review", 5)
        r = run_task(BANKING, ScriptedAgent([
            ("freeze_card", {"card_id": "card1"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)


if __name__ == "__main__":
    unittest.main()
