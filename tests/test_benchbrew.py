"""BenchBrew v0 tests: determinism, policy rules, verifier, emitter."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchbrew.generator import Generator
from benchbrew.simulator import Simulator
from benchbrew.spec import PolicyError, World, bundle_hash, validate_spec
from benchbrew.verifier import check
from domains.marketplace import MARKETPLACE, PLATFORM, _fee_for, _seller_level


def stripped(tasks):
    from benchbrew.spec import canonical_tasks
    return canonical_tasks(tasks)


class TestDeterminism(unittest.TestCase):
    def test_same_seed_identical_bundle(self):
        g = Generator(MARKETPLACE)
        _, t1 = g.generate(42, 12)
        _, t2 = g.generate(42, 12)
        self.assertEqual(bundle_hash(MARKETPLACE, 42, stripped(t1)),
                         bundle_hash(MARKETPLACE, 42, stripped(t2)))

    def test_different_seeds_differ(self):
        g = Generator(MARKETPLACE)
        _, t1 = g.generate(42, 12)
        _, t2 = g.generate(43, 12)
        self.assertNotEqual(bundle_hash(MARKETPLACE, 42, stripped(t1)),
                            bundle_hash(MARKETPLACE, 43, stripped(t2)))

    def test_world_canonical_deterministic(self):
        g = Generator(MARKETPLACE)
        w1, _ = g.generate(7, 4)
        w2, _ = g.generate(7, 4)
        self.assertEqual(w1.canonical(), w2.canonical())


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.sim = Simulator(MARKETPLACE)
        self.gen = Generator(MARKETPLACE)

    def task_of(self, archetype: str, seed: int = 1) -> tuple["World", dict]:
        _, tasks = self.gen.generate(seed, 20)
        for t in tasks:
            if t["archetype"] == archetype:
                return t["initial_world"], t
        self.fail(f"no {archetype} task generated")

    def test_spec_validates(self):
        self.assertEqual(validate_spec(MARKETPLACE), [])

    def test_grounded_fees(self):
        w, _ = self.gen.generate(1, 1)
        # eBay 13.25% + $0.30; Alex is Top Rated -> 30% fee discount
        self.assertEqual(_fee_for(w, "me", 100), round(round(100 * 0.1325 + 0.30) * 0.7))
        self.assertEqual(_fee_for(w, "u3", 100), round(100 * 0.1325 + 0.30))
        self.assertLess(_fee_for(w, "me", 100), _fee_for(w, "u3", 100))
        self.assertEqual(_seller_level(w, "me"), "top_rated")

    def test_offer_expiry_blocks_late_response(self):
        w, t = self.task_of("sell_list_close")
        offer = next(v for v in t["inbox"] if v["type"] == "offer")
        # 25 hours old -> expired (24h window)
        w.get("offers")[offer["offer_id"]]["created_at_tick"] = -25
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "respond_offer",
                             {"offer_id": offer["offer_id"], "action": "accept"}, t["ctx"])

    def test_dispute_window_closed(self):
        w, t = self.task_of("buy_late_dispute")
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "open_dispute",
                             {"order_id": "ord0", "reason": "not as described"}, t["ctx"])

    def test_floor_blocks_below_floor_accept(self):
        w, t = self.task_of("sell_list_close")
        ctx = dict(t["ctx"], owner_ok=False)
        # craft a below-floor offer (the generator's offers are at/above floor)
        offers = w.get("offers")
        oid = f"o{len(offers) + 1}"
        offers[oid] = {"id": oid, "listing_id": ctx["listing_id"],
                       "buyer_id": ctx["buyer"], "amount": ctx["floor"] - 10,
                       "status": "pending"}
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "respond_offer",
                             {"offer_id": oid, "action": "accept"}, ctx)
        # at/above floor is fine
        offers[oid]["amount"] = ctx["floor"]
        self.sim.execute(w, "respond_offer",
                         {"offer_id": oid, "action": "accept"}, ctx)
        self.assertTrue(w.get("orders"))

    def test_floor_allows_at_or_above_floor(self):
        w, t = self.task_of("sell_list_close", 3)
        ctx = t["ctx"]
        offer = next(v for v in t["inbox"] if v["type"] == "offer")
        self.assertGreaterEqual(offer["amount"], ctx["floor"])
        self.sim.execute(w, "respond_offer",
                         {"offer_id": offer["offer_id"], "action": "accept"}, ctx)
        self.assertTrue(w.get("orders"))

    def test_scam_buyer_cannot_transact(self):
        # the scam sender (u3) sends a scam message; if they also had an
        # offer, accepting it after the message is flagged must be blocked
        w, t = self.task_of("sell_list_close", 5)
        ctx = t["ctx"]
        scam = next(v for v in t["inbox"] if v["type"] == "message")
        self.sim.execute(w, "flag_message",
                         {"message_id": scam["message_id"]}, ctx)
        offers = w.get("offers")
        oid = f"o{len(offers) + 1}"
        offers[oid] = {"id": oid, "listing_id": ctx["listing_id"],
                       "buyer_id": ctx["scam_buyer"], "amount": ctx["offer_amt"],
                       "status": "pending"}
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "respond_offer",
                             {"offer_id": oid, "action": "accept"}, ctx)

    def test_dispute_only_after_delivery(self):
        _, tasks = self.gen.generate(1, 1)
        w = tasks[0]["initial_world"].clone()
        self.sim.execute(w, "list_item",
                         {"seller_id": "me", "title": "x", "category": "c",
                          "price": 10, "condition": "good"}, {})
        # no delivered order exists -> any dispute attempt fails
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "open_dispute",
                             {"order_id": "ord1", "reason": "broken"}, {})


class TestVerifier(unittest.TestCase):
    def setUp(self):
        self.sim = Simulator(MARKETPLACE)
        self.gen = Generator(MARKETPLACE)

    def task_of(self, archetype: str, seed: int = 1) -> tuple["World", dict]:
        """Generate a bundle and return (initial_world, task) for an archetype."""
        _, tasks = self.gen.generate(seed, 20)
        for t in tasks:
            if t["archetype"] == archetype:
                return t["initial_world"], t
        self.fail(f"no {archetype} task generated")

    def test_correct_sell_flow_passes(self):
        w, t = self.task_of("sell_list_close")
        ctx = t["ctx"]
        offer = next(v for v in t["inbox"] if v["type"] == "offer")
        scam = next(v for v in t["inbox"] if v["type"] == "message")
        # accept the legit offer (it's at/above floor by construction)
        self.sim.execute(w, "respond_offer",
                         {"offer_id": offer["offer_id"], "action": "accept"}, ctx)
        order = next(iter(w.get("orders").values()))
        self.sim.execute(w, "ship_order", {"order_id": order["id"]}, ctx)
        self.sim.execute(w, "flag_message", {"message_id": scam["message_id"]}, ctx)
        ok, reasons = check(t, w)
        self.assertTrue(ok, reasons)

    def test_scam_engagement_fails(self):
        w, t = self.task_of("sell_list_close", 3)
        ctx = t["ctx"]
        # agent accepts the legit offer but never flags the scam
        offer = next(v for v in t["inbox"] if v["type"] == "offer")
        self.sim.execute(w, "respond_offer",
                         {"offer_id": offer["offer_id"], "action": "accept"}, ctx)
        ok, reasons = check(t, w)
        self.assertFalse(ok)
        self.assertIn("scam_flagged", reasons)

    def test_buy_negotiate_within_budget(self):
        w, t = self.task_of("buy_negotiate", 2)
        ctx = t["ctx"]
        # offer exactly the accept threshold (<= budget by construction)
        self.sim.execute(w, "make_offer",
                         {"listing_id": ctx["listing_id"], "buyer_id": "me",
                          "amount": ctx["accept_at"]}, ctx)
        ok, reasons = check(t, w)
        self.assertTrue(ok, reasons)

    def test_buy_avoid_scam(self):
        w, t = self.task_of("buy_avoid_scam", 5)
        ctx = t["ctx"]
        scam = next(v for v in t["inbox"] if v["type"] == "message")
        # flag and walk away: no order
        self.sim.execute(w, "flag_message", {"message_id": scam["message_id"]}, ctx)
        ok, reasons = check(t, w)
        self.assertTrue(ok, reasons)
        # engaging the scammer is blocked by policy
        with self.assertRaises(PolicyError):
            self.sim.execute(w, "make_offer",
                             {"listing_id": ctx["listing_id"], "buyer_id": "me",
                              "amount": 5}, ctx)


class TestEmitter(unittest.TestCase):
    def test_emits_tau2_shape(self):
        from benchbrew.emitter import emit
        import tempfile
        g = Generator(MARKETPLACE)
        w, tasks = g.generate(42, 4)
        with tempfile.TemporaryDirectory() as d:
            out = emit(MARKETPLACE, 42, tasks, w, d)
            tj = json.loads((out / "tasks.json").read_text())
            self.assertEqual(len(tj), 4)
            first = tj[0]
            for key in ("id", "description", "user_scenario", "evaluation_criteria"):
                self.assertIn(key, first)
            self.assertEqual(first["evaluation_criteria"]["reward_basis"], ["DB"])
            self.assertEqual(first["evaluation_criteria"]["nl_assertions"], [])
            self.assertIn("bundle_hash", json.loads((out / "manifest.json").read_text()))
            self.assertTrue((out / "checks.py").exists())

    def test_emits_tau2_domain_package(self):
        """The τ²-domain emitter writes a complete, registered domain package."""
        from benchbrew.emitter_tau2 import emit_tau2_domain
        import tempfile
        g = Generator(MARKETPLACE)
        w, tasks = g.generate(42, 4)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            # fake the tau2 layout: src/tau2/registry.py + data/
            reg = root / "src" / "tau2" / "registry.py"
            reg.parent.mkdir(parents=True)
            reg.write_text("from tau2.registry import registry\n")
            src = emit_tau2_domain(MARKETPLACE, 42, tasks, w, root)
            for f in ("data_model.py", "tools.py", "environment.py", "utils.py",
                      "__init__.py"):
                self.assertTrue((src / f).exists(), f)
            data = root / "data" / "tau2" / "domains" / "marketplace"
            for f in ("tasks.json", "db.json", "split_tasks.json", "policy.md"):
                self.assertTrue((data / f).exists(), f)
            self.assertIn("_bb_marketplace_get_environment", reg.read_text())
            tj = json.loads((data / "tasks.json").read_text())
            self.assertEqual(len(tj), 4)
            self.assertIn("initialization_data", tj[0]["initial_state"])
            self.assertIn("seller_floor", json.dumps(tj))


if __name__ == "__main__":
    unittest.main()
