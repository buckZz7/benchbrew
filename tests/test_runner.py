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

    def test_tool_schema_shape(self):
        schema = {s["function"]["name"]: s for s in tool_schema(MARKETPLACE)}
        self.assertIn("respond_offer", schema)
        params = schema["respond_offer"]["function"]["parameters"]
        # optional (None-able) params are not required
        self.assertNotIn("amount", params["required"])
        self.assertIn("offer_id", params["required"])

    def test_run_bundle_archetype_filter_and_report(self):
        results = run_bundle(MARKETPLACE, ScriptedAgent([]), seed=1, n_tasks=3,
                             archetype="sell_create_listing", max_steps=1)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.archetype == "sell_create_listing" for r in results))
        rep = report(results)
        self.assertIn("success_rate", rep)
        self.assertEqual(rep["n_tasks"], 3)


if __name__ == "__main__":
    unittest.main()
