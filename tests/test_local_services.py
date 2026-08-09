"""Local-services domain: policy, verifier, and runner tests (GPU-free)."""

from __future__ import annotations

import unittest

from benchbrew.generator import Generator
from benchbrew.runner import ScriptedAgent, run_task
from benchbrew.simulator import Simulator
from benchbrew.spec import PolicyError, bundle_hash, validate_spec
from benchbrew.verifier import check
from domains.local_services import LOCAL_SERVICES

gen = Generator(LOCAL_SERVICES)


def task_of(archetype: str, seed: int = 3):
    _, tasks = gen.generate(seed, 40)
    return next(t for t in tasks if t["archetype"] == archetype)


class TestSpec(unittest.TestCase):
    def test_validate_spec(self):
        self.assertEqual(validate_spec(LOCAL_SERVICES), [])

    def test_determinism(self):
        from benchbrew.spec import canonical_tasks
        _, t1 = gen.generate(11, 8)
        _, t2 = gen.generate(11, 8)
        self.assertEqual(bundle_hash(LOCAL_SERVICES, 11, canonical_tasks(t1)),
                         bundle_hash(LOCAL_SERVICES, 11, canonical_tasks(t2)))


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.sim = Simulator(LOCAL_SERVICES)

    def test_confirm_before_invoice_blocked(self):
        """Escrow rule: payment cannot release before the tasker invoiced."""
        t = task_of("pay_invoice_early", 3)
        w = t["initial_world"].clone()
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "confirm_completion",
                             {"booking_id": t["ctx"]["booking_id"]}, t["ctx"])

    def test_request_funds_rule(self):
        t = task_of("book_within_budget", 3)
        w = t["initial_world"].clone()
        ctx = t["ctx"]
        taskers = [u for u in w.get("users").values()
                   if ctx["category"] in u.get("categories", [])]
        w.get("wallet")["me"]["balance"] = 5  # broke
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "request_booking",
                             {"tasker_id": taskers[0]["id"],
                              "service_id": ctx["service_id"],
                              "scheduled_at_tick": 48, "hours": 2}, ctx)

    def test_scam_tasker_blocked(self):
        t = task_of("scam_direct_pay", 3)
        w = t["initial_world"].clone()
        ctx = t["ctx"]
        # flag the scam message -> the tasker can no longer be transacted with
        mid = next(e["message_id"] for e in t["inbox"] if e["type"] == "message")
        self.sim.execute(w, "flag_message", {"message_id": mid}, ctx)
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "request_booking",
                             {"tasker_id": ctx["tasker_id"],
                              "service_id": "s1", "scheduled_at_tick": 48,
                              "hours": 1}, ctx)


class TestRunner(unittest.TestCase):
    def test_book_within_budget(self):
        t = task_of("book_within_budget", 3)
        ctx = t["ctx"]
        taskers = [u for u in t["initial_world"].get("users").values()
                   if ctx["category"] in u.get("categories", [])]
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("request_booking", {"tasker_id": taskers[0]["id"],
                                 "service_id": ctx["service_id"],
                                 "scheduled_at_tick": 48, "hours": ctx["hours"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_book_wrong_category_fails(self):
        t = task_of("book_within_budget", 3)
        ctx = t["ctx"]
        # a tasker who does NOT serve the category -> tool error, goal fails
        taskers = [u for u in t["initial_world"].get("users").values()
                   if ctx["category"] not in u.get("categories", [])]
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("request_booking", {"tasker_id": taskers[0]["id"],
                                 "service_id": ctx["service_id"],
                                 "scheduled_at_tick": 48, "hours": ctx["hours"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertGreater(r.tool_errors, 0)

    def test_cancel_before_deadline_free(self):
        t = task_of("cancel_before_deadline", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["booking_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_cancel_late_decision_cancel_pays_fee(self):
        t = task_of("cancel_late_decision", 3)
        b = t["initial_world"].get("bookings")[t["ctx"]["booking_id"]]
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["booking_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)
        # exact money: refunded total minus exactly one hour at the rate
        fee = b["hourly_rate"] * 1
        bal = r.world.get("wallet")["me"]["balance"]
        self.assertEqual(bal, t["ctx"]["wallet_before"] + b["total"] - fee)

    def test_cancel_late_decision_reschedule_free(self):
        t = task_of("cancel_late_decision", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("reschedule_booking", {"booking_id": t["ctx"]["booking_id"],
                                    "new_scheduled_at_tick": 48}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_cancel_late_decision_noop_fails(self):
        t = task_of("cancel_late_decision", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([]), t)
        self.assertFalse(r.success)

    def test_tasker_noshow_free_cancel(self):
        t = task_of("tasker_noshow", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["booking_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_confirm_release_pays_tasker_exact(self):
        t = task_of("confirm_release", 3)
        ctx = t["ctx"]
        b = t["initial_world"].get("bookings")[ctx["booking_id"]]
        tasker_before = t["initial_world"].get("wallet")[ctx["tasker_id"]]["balance"]
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("confirm_completion", {"booking_id": ctx["booking_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)
        w = r.world
        paid = w.get("bookings")[ctx["booking_id"]]["status"] == "paid"
        exact = w.get("wallet")[ctx["tasker_id"]]["balance"] == tasker_before + b["tasker_net"]
        self.assertTrue(paid and exact)

    def test_dispute_wrong_work_correct(self):
        t = task_of("dispute_wrong_work", 3)
        ctx = t["ctx"]
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("open_dispute", {"booking_id": ctx["booking_id"],
                              "reason": "work not as described"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_dispute_wrong_work_confirm_fails(self):
        t = task_of("dispute_wrong_work", 3)
        ctx = t["ctx"]
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("confirm_completion", {"booking_id": ctx["booking_id"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("disputed_not_paid", r.reasons)

    def test_pay_invoice_early_flagged(self):
        t = task_of("pay_invoice_early", 3)
        mid = next(e["message_id"] for e in t["inbox"] if e["type"] == "message")
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("flag_message", {"message_id": mid}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_pay_invoice_early_confirm_blocked(self):
        t = task_of("pay_invoice_early", 3)
        ctx = t["ctx"]
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("confirm_completion", {"booking_id": ctx["booking_id"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertGreater(r.tool_errors, 0)  # escrow rule blocks the release

    def test_scam_direct_pay_flagged(self):
        t = task_of("scam_direct_pay", 3)
        mid = next(e["message_id"] for e in t["inbox"] if e["type"] == "message")
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("flag_message", {"message_id": mid}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_scam_direct_pay_ignored_fails(self):
        t = task_of("scam_direct_pay", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([]), t)
        self.assertFalse(r.success)
        self.assertIn("scam_flagged", r.reasons)

    # ---- provider side ----

    def test_accept_request(self):
        t = task_of("accept_request", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("accept_booking_request", {"booking_id": t["ctx"]["booking_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_accept_request_ignore_fails(self):
        t = task_of("accept_request", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([]), t)
        self.assertFalse(r.success)

    def test_invoice_after_job_exact_hours(self):
        t = task_of("invoice_after_job", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("submit_invoice", {"booking_id": t["ctx"]["booking_id"],
                                "hours_worked": t["ctx"]["hours"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_invoice_after_job_underbills_fails(self):
        t = task_of("invoice_after_job", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("submit_invoice", {"booking_id": t["ctx"]["booking_id"],
                                "hours_worked": 1}),  # underbilled
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("exact_hours", r.reasons)

    def test_client_noshow_compensated(self):
        t = task_of("client_noshow_fee", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["booking_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_provider_rating_risk_cancel_in_time(self):
        t = task_of("provider_rating_risk", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["booking_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_provider_rating_risk_noop_fails(self):
        t = task_of("provider_rating_risk", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([]), t)
        self.assertFalse(r.success)
        self.assertIn("canceled_in_time", r.reasons)

    def test_decline_scam_client_flagged(self):
        t = task_of("decline_scam_client", 3)
        mid = next(e["message_id"] for e in t["inbox"] if e["type"] == "message")
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("flag_message", {"message_id": mid}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_decline_scam_client_ignored_fails(self):
        t = task_of("decline_scam_client", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([]), t)
        self.assertFalse(r.success)
        self.assertIn("scam_flagged", r.reasons)

    # ---- v0.2 hardening shapes ----

    def test_tasker_choice_right(self):
        t = task_of("tasker_choice", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("request_booking", {"tasker_id": t["ctx"]["right_tasker"],
                                 "service_id": t["ctx"]["service_id"],
                                 "scheduled_at_tick": 48,
                                 "hours": t["ctx"]["hours"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_tasker_choice_over_budget_fails(self):
        t = task_of("tasker_choice", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("request_booking", {"tasker_id": "u5",  # $45/h -> over budget
                                 "service_id": t["ctx"]["service_id"],
                                 "scheduled_at_tick": 48,
                                 "hours": t["ctx"]["hours"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("right_tasker_booked", r.reasons)

    def test_double_booked_resolved(self):
        t = task_of("double_booked", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("reschedule_booking", {"booking_id": t["ctx"]["booking_ids"][0],
                                    "new_scheduled_at_tick": 48}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_double_booked_noop_fails(self):
        t = task_of("double_booked", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([]), t)
        self.assertFalse(r.success)
        self.assertIn("no_conflict", r.reasons)

    def test_scam_distraction_both_actions(self):
        t = task_of("scam_distraction", 3)
        mid = next(e["message_id"] for e in t["inbox"] if e["type"] == "message")
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["booking_id"]}),
            ("flag_message", {"message_id": mid}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_scam_distraction_only_cancel_fails(self):
        t = task_of("scam_distraction", 3)
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["booking_id"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("scam_flagged", r.reasons)

    def test_provider_inbox_triage_correct(self):
        t = task_of("provider_inbox_triage", 3)
        mid = next(e["message_id"] for e in t["inbox"] if e["type"] == "message")
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("accept_booking_request", {"booking_id": t["ctx"]["good"]}),
            ("flag_message", {"message_id": mid}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_provider_inbox_triage_accepts_scam_client_fails(self):
        t = task_of("provider_inbox_triage", 3)
        mid = next(e["message_id"] for e in t["inbox"] if e["type"] == "message")
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("accept_booking_request", {"booking_id": t["ctx"]["good"]}),
            ("accept_booking_request", {"booking_id": t["ctx"]["bad"]}),
            ("flag_message", {"message_id": mid}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("scam_client_not_accepted", r.reasons)

    def test_full_lifecycle_complete(self):
        t = task_of("full_lifecycle", 3)
        ctx = t["ctx"]
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("accept_booking_request", {"booking_id": ctx["booking_id"]}),
            ("submit_invoice", {"booking_id": ctx["booking_id"],
                                "hours_worked": ctx["hours"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_full_lifecycle_stops_after_accept_fails(self):
        t = task_of("full_lifecycle", 3)
        ctx = t["ctx"]
        r = run_task(LOCAL_SERVICES, ScriptedAgent([
            ("accept_booking_request", {"booking_id": ctx["booking_id"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("invoiced", r.reasons)


if __name__ == "__main__":
    unittest.main()
