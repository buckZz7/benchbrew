"""Runner tests (GPU-free): scripted agents prove the run loop + verifier."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchbrew.generator import Generator
from benchbrew.runner import (ScriptedAgent, run_bundle, run_task, report,
                              tool_schema)
from domains.marketplace import MARKETPLACE

GEN = Generator(MARKETPLACE)


def task_of(archetype: str, seed: int = 1) -> dict:
    _, tasks = GEN.generate(seed, 20)
    for t in tasks:
        if t["archetype"] == archetype:
            return t
    raise AssertionError(f"no {archetype} task")


class TestRunner(unittest.TestCase):
    def test_correct_sell_flow_passes(self):
        t = task_of("sell_list_close", 1)
        offer = next(e for e in t["inbox"] if e["type"] == "offer")
        scam = next(e for e in t["inbox"] if e["type"] == "message")
        agent = ScriptedAgent([
            ("respond_offer", {"offer_id": offer["offer_id"], "action": "accept"}),
            ("ship_order", {"order_id": "ord1"}),
            ("flag_message", {"message_id": scam["message_id"]}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertTrue(r.success, r.reasons)
        self.assertEqual(r.termination, "agent_stop")
        self.assertEqual(r.tool_errors, 0)

    def test_missing_scam_flag_fails(self):
        t = task_of("sell_list_close", 1)
        offer = next(e for e in t["inbox"] if e["type"] == "offer")
        agent = ScriptedAgent([
            ("respond_offer", {"offer_id": offer["offer_id"], "action": "accept"}),
            ("ship_order", {"order_id": "ord1"}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertFalse(r.success)
        self.assertIn("scam_flagged", r.reasons)

    def test_below_floor_accept_counts_as_error(self):
        t = task_of("sell_list_close", 3)
        offer = next(e for e in t["inbox"] if e["type"] == "offer")
        # make the recorded offer below the owner's floor
        t["initial_world"].get("offers")[offer["offer_id"]]["amount"] = \
            t["ctx"]["floor"] - 10
        agent = ScriptedAgent([
            ("respond_offer", {"offer_id": offer["offer_id"], "action": "accept"}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertEqual(r.tool_errors, 1)
        self.assertFalse(r.success)

    def test_buy_negotiate_passes(self):
        t = task_of("buy_negotiate", 2)
        ctx = t["ctx"]
        agent = ScriptedAgent([
            ("make_offer", {"listing_id": ctx["listing_id"], "buyer_id": "me",
                            "amount": ctx["accept_at"]}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertTrue(r.success, r.reasons)

    def test_buy_avoid_scam_passes(self):
        t = task_of("buy_avoid_scam", 5)
        scam = next(e for e in t["inbox"] if e["type"] == "message")
        agent = ScriptedAgent([
            ("flag_message", {"message_id": scam["message_id"]}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertTrue(r.success, r.reasons)

    def test_lowball_requires_tool_response(self):
        t = task_of("sell_reject_lowball", 4)
        offer = next(e for e in t["inbox"] if e["type"] == "offer")
        # narrating a decision in text (no tool call) leaves the offer pending
        r = run_task(MARKETPLACE, ScriptedAgent([]), t)
        self.assertFalse(r.success)
        self.assertIn("lowball_responded_via_tool", r.reasons)
        # declining via the tool passes
        agent = ScriptedAgent([("respond_offer", {"offer_id": offer["offer_id"],
                                                  "action": "decline"})])
        r2 = run_task(MARKETPLACE, agent, t)
        self.assertTrue(r2.success, r2.reasons)
        # asking the owner via the ask_owner tool also passes (DB-verifiable)
        agent3 = ScriptedAgent([("ask_owner", {"question": "counter at floor?"})])
        r3 = run_task(MARKETPLACE, agent3, t)
        self.assertTrue(r3.success, r3.reasons)

    def test_step_cap_terminates(self):
        t = task_of("sell_reject_lowball", 4)
        # agent keeps making offers forever -> capped
        agent = ScriptedAgent([("make_offer", {"listing_id": t["ctx"]["listing_id"],
                                               "buyer_id": "me", "amount": 1})] * 50)
        r = run_task(MARKETPLACE, agent, t, max_steps=5)
        self.assertEqual(r.termination, "max_steps")
        self.assertEqual(r.tool_calls, 5)

    def test_expiring_offer_accept_now(self):
        t = task_of("sell_expiring_offer", 1)
        offer = next(e for e in t["inbox"] if e["type"] == "offer")
        # act immediately -> passes before the 24h window closes
        agent = ScriptedAgent([("respond_offer", {"offer_id": offer["offer_id"],
                                                  "action": "accept"})])
        r = run_task(MARKETPLACE, agent, t)
        self.assertTrue(r.success, r.reasons)

    def test_expiring_offer_dawdle_fails(self):
        t = task_of("sell_expiring_offer", 3)
        offer = next(e for e in t["inbox"] if e["type"] == "offer")
        # waste 3 steps first -> offer expired by the time we accept
        agent = ScriptedAgent([("get_listing", {"listing_id": "ml1"}),
                               ("get_wallet", {"user_id": "me"}),
                               ("get_listing", {"listing_id": "ml1"}),
                               ("respond_offer", {"offer_id": offer["offer_id"],
                                                  "action": "accept"})])
        r = run_task(MARKETPLACE, agent, t)
        self.assertFalse(r.success)
        self.assertGreater(r.tool_errors, 0)

    def test_late_dispute_no_op_passes(self):
        t = task_of("buy_late_dispute", 5)
        r = run_task(MARKETPLACE, ScriptedAgent([]), t)
        self.assertTrue(r.success, r.reasons)

    def test_ship_on_time_both_immediately(self):
        t = task_of("sell_ship_on_time", 2)
        agent = ScriptedAgent([("ship_order", {"order_id": "ord1"}),
                               ("ship_order", {"order_id": "ord2"})])
        r = run_task(MARKETPLACE, agent, t)
        self.assertTrue(r.success, r.reasons)

    def test_ship_on_time_dawdle_loses_rating(self):
        t = task_of("sell_ship_on_time", 4)
        # a read before shipping pushes the second order past the window
        agent = ScriptedAgent([("get_wallet", {"user_id": "me"}),
                               ("ship_order", {"order_id": "ord1"}),
                               ("ship_order", {"order_id": "ord2"})])
        r = run_task(MARKETPLACE, agent, t)
        self.assertFalse(r.success)
        self.assertIn("top_rated_kept", r.reasons)

    def test_full_inbox_correct_path(self):
        t = task_of("sell_full_inbox", 1)
        offers = [e for e in t["inbox"] if e["type"] == "offer"]
        scam = next(e for e in t["inbox"] if e["type"] == "message")
        legit = next(e for e in offers if e["amount"] >= t["ctx"]["floor"])
        lowball = next(e for e in offers if e["amount"] < t["ctx"]["floor"])
        agent = ScriptedAgent([
            ("respond_offer", {"offer_id": legit["offer_id"], "action": "accept"}),
            ("respond_offer", {"offer_id": lowball["offer_id"], "action": "decline"}),
            ("flag_message", {"message_id": scam["message_id"]}),
            ("ship_order", {"order_id": "ord1"}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertTrue(r.success, r.reasons)

    def test_full_inbox_missing_scam_flag_fails(self):
        t = task_of("sell_full_inbox", 3)
        offers = [e for e in t["inbox"] if e["type"] == "offer"]
        legit = next(e for e in offers if e["amount"] >= t["ctx"]["floor"])
        lowball = next(e for e in offers if e["amount"] < t["ctx"]["floor"])
        agent = ScriptedAgent([
            ("respond_offer", {"offer_id": legit["offer_id"], "action": "accept"}),
            ("respond_offer", {"offer_id": lowball["offer_id"], "action": "decline"}),
            ("ship_order", {"order_id": "ord1"}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertFalse(r.success)
        self.assertIn("scam_flagged", r.reasons)

    def test_scam_variant_detected(self):
        t = task_of("sell_scam_variant", 4)
        mid = next(e["message_id"] for e in t["inbox"] if e["type"] == "message")
        oid = next(e["offer_id"] for e in t["inbox"] if e["type"] == "offer")
        agent = ScriptedAgent([
            ("flag_message", {"message_id": mid}),
            ("respond_offer", {"offer_id": oid, "action": "decline"}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertTrue(r.success, r.reasons)

    def test_scam_variant_accepts_overpay_fails(self):
        """The overpayment offer is ABOVE floor — no rule blocks it. Only
        detection stops the agent from accepting it."""
        t = task_of("sell_scam_variant", 4)
        oid = next(e["offer_id"] for e in t["inbox"] if e["type"] == "offer")
        agent = ScriptedAgent([
            ("respond_offer", {"offer_id": oid, "action": "accept"}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertFalse(r.success)
        self.assertIn("no_order_with_scammer", r.reasons)

    def test_refund_math_full(self):
        t = task_of("sell_refund_math", 4)
        agent = ScriptedAgent([
            ("refund_order", {"order_id": t["ctx"]["order_id"],
                              "amount": t["ctx"]["price"]}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertTrue(r.success, r.reasons)

    def test_refund_math_shortchanges_buyer_fails(self):
        """Refunding price - fee (as if the platform kept the fee) shortchanges
        the buyer — exact arithmetic is the discriminator."""
        t = task_of("sell_refund_math", 4)
        agent = ScriptedAgent([
            ("refund_order", {"order_id": t["ctx"]["order_id"],
                              "amount": t["ctx"]["price"] - t["ctx"]["fee"]}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertFalse(r.success)
        self.assertIn("buyer_full_refund", r.reasons)

    def test_refund_math_over_pay_fails(self):
        t = task_of("sell_refund_math", 4)
        agent = ScriptedAgent([
            ("refund_order", {"order_id": t["ctx"]["order_id"],
                              "amount": t["ctx"]["price"] + 1}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertFalse(r.success)

    def test_negotiate_rounds_complete(self):
        t = task_of("buy_negotiate_rounds", 2)
        ctx = t["ctx"]
        # make an offer within budget -> seller counters -> accept the counter
        agent = ScriptedAgent([
            ("make_offer", {"listing_id": ctx["listing_id"], "buyer_id": "me",
                            "amount": int(ctx["budget"] * 0.7)}),
            ("respond_offer", {"offer_id": "co1", "action": "accept"}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertTrue(r.success, r.reasons)
        self.assertEqual(r.tool_calls, 2)

    def test_negotiate_rounds_no_response_fails(self):
        t = task_of("buy_negotiate_rounds", 4)
        ctx = t["ctx"]
        # offer made, counter ignored -> no order
        agent = ScriptedAgent([
            ("make_offer", {"listing_id": ctx["listing_id"], "buyer_id": "me",
                            "amount": int(ctx["budget"] * 0.7)}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertFalse(r.success)
        self.assertIn("order_within_budget", r.reasons)

    def test_negotiate_rounds_over_budget_fails(self):
        t = task_of("buy_negotiate_rounds", 5)
        ctx = t["ctx"]
        # offering above budget auto-accepts at a price over budget
        agent = ScriptedAgent([
            ("make_offer", {"listing_id": ctx["listing_id"], "buyer_id": "me",
                            "amount": ctx["budget"] + 50}),
        ])
        r = run_task(MARKETPLACE, agent, t)
        self.assertFalse(r.success)

    def test_counterparty_event_lands_in_world(self):
        t = task_of("buy_negotiate_rounds", 2)
        self.assertTrue(t["counterparty"])
        self.assertEqual(t["counterparty"][0]["after"], "make_offer")
        self.assertEqual(t["counterparty"][0]["event"]["offer_id"], "co1")

    def test_tool_schema_shape(self):
        schema = {s["function"]["name"]: s for s in tool_schema(MARKETPLACE)}
        self.assertIn("respond_offer", schema)
        params = schema["respond_offer"]["function"]["parameters"]
        # optional (None-able) params are not required
        self.assertNotIn("amount", params["required"])
        self.assertIn("offer_id", params["required"])

    def test_run_bundle_archetype_filter_and_report(self):
        results = run_bundle(MARKETPLACE, ScriptedAgent([]), seed=1, n_tasks=2,
                             archetype="sell_create_listing", max_steps=1)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.archetype == "sell_create_listing" for r in results))
        rep = report(results)
        self.assertIn("success_rate", rep)
        self.assertEqual(rep["n_tasks"], 2)


if __name__ == "__main__":
    unittest.main()
