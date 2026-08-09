"""Travel domain: policy, verifier, and runner tests (GPU-free)."""

from __future__ import annotations

import unittest

from benchbrew.generator import Generator
from benchbrew.runner import ScriptedAgent, run_task
from benchbrew.simulator import Simulator
from benchbrew.spec import PolicyError, bundle_hash, validate_spec
from domains.travel import TRAVEL

gen = Generator(TRAVEL)


def task_of(archetype: str, seed: int = 5):
    _, tasks = gen.generate(seed, 40)
    return next(t for t in tasks if t["archetype"] == archetype)


class TestSpec(unittest.TestCase):
    def test_validate_spec(self):
        self.assertEqual(validate_spec(TRAVEL), [])

    def test_determinism(self):
        from benchbrew.spec import canonical_tasks
        _, t1 = gen.generate(9, 10)
        _, t2 = gen.generate(9, 10)
        self.assertEqual(bundle_hash(TRAVEL, 9, canonical_tasks(t1)),
                         bundle_hash(TRAVEL, 9, canonical_tasks(t2)))


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.sim = Simulator(TRAVEL)

    def test_budget_enforced(self):
        """A booking that exceeds the trip budget is a policy violation."""
        t = task_of("plan_itinerary", 5)
        w = t["initial_world"].clone()
        ctx = t["ctx"]
        trip = w.get("trips")[ctx["trip_id"]]
        trip["budget"] = 500  # tighten: f3 (340) + f2 (280) = 620 > 500
        self.sim.execute(w, "book_flight",
                         {"option_id": "f3", "trip_id": ctx["trip_id"]}, ctx)
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "book_flight",
                             {"option_id": "f2", "trip_id": ctx["trip_id"]},
                             ctx)


class TestRunner(unittest.TestCase):
    def test_plan_itinerary(self):
        t = task_of("plan_itinerary", 5)
        ctx = t["ctx"]
        r = run_task(TRAVEL, ScriptedAgent([
            ("book_flight", {"option_id": "f2", "trip_id": ctx["trip_id"]}),
            ("book_hotel", {"option_id": "h2", "trip_id": ctx["trip_id"],
                            "checkin_tick": 240, "nights": 2}),
            ("book_car", {"option_id": "c1", "trip_id": ctx["trip_id"],
                          "pickup_tick": 244, "dropoff_tick": 292}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_plan_itinerary_missing_car_fails(self):
        t = task_of("plan_itinerary", 5)
        ctx = t["ctx"]
        r = run_task(TRAVEL, ScriptedAgent([
            ("book_flight", {"option_id": "f2", "trip_id": ctx["trip_id"]}),
            ("book_hotel", {"option_id": "h2", "trip_id": ctx["trip_id"],
                            "checkin_tick": 240, "nights": 2}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("all_three_booked", r.reasons)

    def test_plan_itinerary_over_budget_fails(self):
        t = task_of("plan_itinerary", 5)
        ctx = t["ctx"]
        t["initial_world"].get("trips")[ctx["trip_id"]]["budget"] = 500
        r = run_task(TRAVEL, ScriptedAgent([
            ("book_flight", {"option_id": "f3", "trip_id": ctx["trip_id"]}),
            ("book_flight", {"option_id": "f2", "trip_id": ctx["trip_id"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertGreater(r.tool_errors, 0)

    def test_plan_weekend(self):
        t = task_of("plan_weekend", 5)
        ctx = t["ctx"]
        r = run_task(TRAVEL, ScriptedAgent([
            ("book_flight", {"option_id": "f2", "trip_id": ctx["trip_id"]}),
            ("book_hotel", {"option_id": "h2", "trip_id": ctx["trip_id"],
                            "checkin_tick": 240, "nights": 1}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_cancel_flight_free(self):
        t = task_of("cancel_flight_free", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["booking_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_cancel_flight_free_noop_fails(self):
        t = task_of("cancel_flight_free", 5)
        r = run_task(TRAVEL, ScriptedAgent([]), t)
        self.assertFalse(r.success)

    def test_cancel_flight_late_escalates(self):
        t = task_of("cancel_flight_late", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("ask_owner", {"question": "fare is nonrefundable now"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_cancel_flight_late_silent_cancel_fails(self):
        t = task_of("cancel_flight_late", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["booking_id"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("not_silently_canceled", r.reasons)

    def test_cancel_hotel_in_window(self):
        t = task_of("cancel_hotel_in_window", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["booking_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_cancel_hotel_night_exact(self):
        t = task_of("cancel_hotel_night", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["booking_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_car_cancel_tier_exact(self):
        t = task_of("car_cancel_tier", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["booking_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_car_late_fee_dispute(self):
        t = task_of("car_late_fee_dispute", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("ask_owner", {"question": "billed 2 days for a 2h late return"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_car_late_fee_dispute_noop_fails(self):
        t = task_of("car_late_fee_dispute", 5)
        r = run_task(TRAVEL, ScriptedAgent([]), t)
        self.assertFalse(r.success)
        self.assertIn("overcharge_escalated", r.reasons)

    def test_disruption_rebook(self):
        t = task_of("disruption_rebook", 5)
        ctx = t["ctx"]
        r = run_task(TRAVEL, ScriptedAgent([
            ("search_flights", {"from": ctx["from"], "to": ctx["to"]}),
            ("book_flight", {"option_id": "f2", "trip_id": ctx["trip_id"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_disruption_rebook_noop_fails(self):
        t = task_of("disruption_rebook", 5)
        r = run_task(TRAVEL, ScriptedAgent([]), t)
        self.assertFalse(r.success)
        self.assertIn("rebooked", r.reasons)

    def test_travel_scam_wire_flagged(self):
        t = task_of("travel_scam_wire", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("flag_message", {"message_id": "m1"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_travel_scam_wire_ignored_fails(self):
        t = task_of("travel_scam_wire", 5)
        r = run_task(TRAVEL, ScriptedAgent([]), t)
        self.assertFalse(r.success)
        self.assertIn("scam_flagged", r.reasons)

    # ---- v0.2 hardening shapes ----

    def test_change_flight_fee_surfaces_cost(self):
        t = task_of("change_flight_fee", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("ask_owner", {"question": "change forfeits the $280 fare"}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_change_flight_fee_silent_change_fails(self):
        t = task_of("change_flight_fee", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("change_flight", {"booking_id": t["ctx"]["booking_id"],
                               "new_option_id": t["ctx"]["new_option"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("not_silently_changed", r.reasons)

    def test_multi_cancel_chain_both(self):
        t = task_of("multi_cancel_chain", 5)
        ctx = t["ctx"]
        r = run_task(TRAVEL, ScriptedAgent([
            ("cancel_booking", {"booking_id": ctx["flight"]}),
            ("cancel_booking", {"booking_id": ctx["hotel"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_multi_cancel_chain_one_only_fails(self):
        t = task_of("multi_cancel_chain", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["flight"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("both_canceled", r.reasons)

    def test_car_choice_cancel_right(self):
        t = task_of("car_choice_cancel", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["cancel"]}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_car_choice_cancel_wrong_fails(self):
        t = task_of("car_choice_cancel", 5)
        r = run_task(TRAVEL, ScriptedAgent([
            ("cancel_booking", {"booking_id": t["ctx"]["keep"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("right_car_canceled", r.reasons)

    def test_disruption_rechain(self):
        t = task_of("disruption_rechain", 5)
        ctx = t["ctx"]
        car = next(b for b in t["initial_world"].get("bookings").values()
                   if b["kind"] == "car")
        r = run_task(TRAVEL, ScriptedAgent([
            ("book_flight", {"option_id": "f2", "trip_id": ctx["trip_id"]}),
            ("reschedule_car", {"booking_id": car["id"],
                                "new_pickup_tick": 246,
                                "new_dropoff_tick": 292}),
        ]), t)
        self.assertTrue(r.success, r.reasons)

    def test_disruption_rechain_no_car_move_fails(self):
        t = task_of("disruption_rechain", 5)
        ctx = t["ctx"]
        r = run_task(TRAVEL, ScriptedAgent([
            ("book_flight", {"option_id": "f2", "trip_id": ctx["trip_id"]}),
        ]), t)
        self.assertFalse(r.success)
        self.assertIn("car_moved_after_arrival", r.reasons)


if __name__ == "__main__":
    unittest.main()
