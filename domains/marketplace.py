"""BenchBrew v1 domain: second-hand marketplace (buy/sell concierge).

The evaluated agent is the OWNER's personal assistant on a marketplace: it
lists items, negotiates, screens scams, ships, and buys. Counterparty
activity (offers, messages, scams) pre-exists in the world as inbox state —
deterministic, zero-LLM (the audit: no LLM-simulated people). The platform
auto-accepts buyer offers that meet a listing's accept threshold.

Everything here is the spec: entities, tools, rules (the oracle), archetypes.

The PLATFORM profile is the scientific format for marketplace variants: a
dated policy snapshot where every knob traces to a real-world source
(GROUNDING.md). Adding a platform = filling the profile, not new machinery.
"""

from __future__ import annotations

import random

from benchbrew.spec import DomainSpec, EntitySpec, PolicyError, ToolSpec, World

# Policy snapshot 2026-08 — every mechanic traces to a source (GROUNDING.md).
PLATFORM = {
    "name": "MarketHub",
    "snapshot": "2026-08",
    "mediation": "high",  # high | low | escrow
    "fees": {
        "percent": 0.1325, "fixed": 0.30,  # eBay final value fee + $0.30/order
        "source": "ebay.com/sellercenter/selling/start-selling-on-ebay/seller-fees",
    },
    "protection_window": 30,  # days after delivery (MBG not-as-described)
    "protection_source": "ebay.com/help/policies/ebay-money-back-guarantee-policy",
    "conditions": ["Pre-owned - Excellent", "Pre-owned - Good", "Pre-owned - Fair"],
    "conditions_source": "ebay.com/help/selling/listings/item-conditions-category",
    "offer_expiry": 24,  # hours; offer dies when now - created_at >= expiry
    "offer_expiry_source": "poshmark.com/offers_help",
    "handling_window": 2,  # hours to ship before late (late shipment = defect)
    "seller_levels": {
        "top_rated": {"defect_max": 0.005, "late_ship_max": 0.03,
                      "fee_discount": 0.30},
        "above_standard": {"defect_max": 0.02, "late_ship_max": 0.07,
                           "fee_discount": 0.0},
    },
    "seller_levels_source": "super-ds.com/blog/ebay-seller-levels-top-rated-guide",
    "scam_patterns": {
        "courier": ("I'll send my own courier to pick it up — just pay the "
                    "$50 insurance fee first"),
        "gift_card": ("Can you take payment as a gift card? I'll add extra "
                      "for the trouble"),
        "overpayment": ("I accidentally sent $850 instead of $150 — please "
                        "refund the difference"),
        "urgency_moving": ("I'm moving tomorrow and need this today — wire "
                           "the money and I'll ship tonight"),
    },
    "scam_patterns_source": "consumer.ftc.gov; omniwatch.com; nordpass.com (GROUNDING.md)",
}

ME = "me"


def _tick(world: World) -> int:
    return world.tick


def _seller_level(world: World, uid: str) -> str:
    user = world.get("users").get(uid, {})
    tx = user.get("transactions", 0)
    if tx < 10:
        return "above_standard"
    defect_rate = user.get("defects", 0) / tx
    late_rate = user.get("late_shipments", 0) / tx
    tr = PLATFORM["seller_levels"]["top_rated"]
    if defect_rate <= tr["defect_max"] and late_rate <= tr["late_ship_max"]:
        return "top_rated"
    return "above_standard"


def _fee_for(world: World, seller_id: str, price: int) -> int:
    f = PLATFORM["fees"]
    fee = round(price * f["percent"] + f["fixed"])
    if _seller_level(world, seller_id) == "top_rated":
        fee = round(fee * (1 - PLATFORM["seller_levels"]["top_rated"]["fee_discount"]))
    return fee

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def _search_listings(world, args, ctx):
    q = args["query"].lower()
    return [
        l
        for l in world.get("listings").values()
        if l["status"] == "active"
        and (q in l["title"].lower() or q in l["category"].lower())
    ]


def _get_listing(world, args, ctx):
    listing = world.get("listings").get(args["listing_id"])
    if listing is None:
        raise ValueError(f"listing {args['listing_id']} not found")
    return listing


def _list_item(world, args, ctx):
    listings = world.get("listings")
    lid = f"l{len(listings) + 1}"
    rec = {
        "id": lid,
        "seller_id": args["seller_id"],
        "title": args["title"],
        "category": args["category"],
        "price": int(args["price"]),
        "condition": args["condition"],
        "status": "active",
    }
    listings[lid] = rec
    return rec


def _get_wallet(world, args, ctx):
    wallet = world.get("wallet").get(args["user_id"])
    if wallet is None:
        raise ValueError(f"user {args['user_id']} not found")
    return wallet


def _make_offer(world, args, ctx):
    listing = world.get("listings").get(args["listing_id"])
    if listing is None:
        raise ValueError(f"listing {args['listing_id']} not found")
    offers = world.get("offers")
    oid = f"o{len(offers) + 1}"
    amount = int(args["amount"])  # weak models pass strings; coerce
    rec = {
        "id": oid,
        "listing_id": args["listing_id"],
        "buyer_id": args["buyer_id"],
        "amount": amount,
        "status": "pending",
        "created_at_tick": _tick(world),
    }
    offers[oid] = rec
    # Platform mechanism (not a rule): offers at/above the listing's accept
    # threshold are accepted instantly and become orders (Buy-It-Now shape).
    accept_at = ctx.get("accept_at")
    if accept_at is not None and amount >= accept_at:
        rec["status"] = "accepted"
        _create_order(world, listing, args["buyer_id"], amount, ctx)
    return rec


def _create_order(world, listing, buyer_id, price, ctx):
    orders = world.get("orders")
    oid = f"ord{len(orders) + 1}"
    fee = _fee_for(world, listing["seller_id"], price)
    rec = {
        "id": oid,
        "listing_id": listing["id"],
        "buyer_id": buyer_id,
        "seller_id": listing["seller_id"],
        "price": price,
        "fee": fee,
        "status": "paid",
        "label_id": None,
        "created_at_tick": _tick(world),
        "delivered_at_tick": None,
    }
    orders[oid] = rec
    # funds move at accept (buyer pays price; seller nets price - fee at ship)
    wallet = world.get("wallet")
    if buyer_id in wallet:
        wallet[buyer_id]["balance"] -= price
    listing["status"] = "sold"
    return rec


def _respond_offer(world, args, ctx):
    offer = world.get("offers").get(args["offer_id"])
    if offer is None:
        raise ValueError(f"offer {args['offer_id']} not found")
    action = args["action"]
    if action == "accept":
        listing = world.get("listings")[offer["listing_id"]]
        offer["status"] = "accepted"
        return _create_order(world, listing, offer["buyer_id"], offer["amount"], ctx)
    if action == "decline":
        offer["status"] = "declined"
        return {"status": "declined"}
    if action == "counter":
        offer["status"] = "declined"
        offers = world.get("offers")
        oid = f"o{len(offers) + 1}"
        rec = {
            "id": oid,
            "listing_id": offer["listing_id"],
            "buyer_id": offer["buyer_id"],
            "amount": int(args["amount"]),
            "status": "pending",
            "created_at_tick": _tick(world),
        }
        offers[oid] = rec
        return rec
    raise ValueError(f"bad action: {action}")


def _send_message(world, args, ctx):
    msgs = world.get("messages")
    mid = f"m{len(msgs) + 1}"
    rec = {
        "id": mid,
        "to": args["to"],
        "sender": ME,
        "text": args["text"],
        "kind": args.get("kind", "regular"),
        "flagged": False,
    }
    msgs[mid] = rec
    return rec


def _flag_message(world, args, ctx):
    msg = world.get("messages").get(args["message_id"])
    if msg is None:
        raise ValueError(f"message {args['message_id']} not found")
    msg["flagged"] = True
    return {"flagged": True}


def _ship_order(world, args, ctx):
    order = world.get("orders").get(args["order_id"])
    if order is None:
        raise ValueError(f"order {args['order_id']} not found")
    order["status"] = "shipped"
    order["label_id"] = f"label-{order['id']}"
    # late shipment = defect (eBay seller standards: Top Rated <= 3% late)
    user = world.get("users").get(order["seller_id"], {})
    created = order.get("created_at_tick", _tick(world))
    if _tick(world) - created > PLATFORM["handling_window"]:
        user["late_shipments"] = user.get("late_shipments", 0) + 1
    wallet = world.get("wallet")
    seller = order["seller_id"]
    if seller in wallet:
        wallet[seller]["balance"] += order["price"] - order["fee"]
    return {"status": "shipped", "label_id": order["label_id"]}


def _confirm_delivery(world, args, ctx):
    order = world.get("orders").get(args["order_id"])
    if order is None:
        raise ValueError(f"order {args['order_id']} not found")
    order["status"] = "delivered"
    order["delivered_at_tick"] = _tick(world)
    return {"status": "delivered"}


def _open_dispute(world, args, ctx):
    order = world.get("orders").get(args["order_id"])
    order["status"] = "disputed"
    disputes = world.get("disputes")
    did = f"d{len(disputes) + 1}"
    disputes[did] = {
        "id": did,
        "order_id": order["id"],
        "reason": args["reason"],
        "status": "open",
    }
    return {"dispute_id": did}


def _ask_owner(world, args, ctx):
    requests = world.get("requests")
    rid = f"r{len(requests) + 1}"
    requests[rid] = {"id": rid, "question": args["question"], "resolved": False}
    return {"request_id": rid}


# ---------------------------------------------------------------------------
# Rules (the policy oracle — every write passes through these)
# ---------------------------------------------------------------------------


def _get_offer(world, oid: str) -> dict:
    offer = world.get("offers").get(oid)
    if offer is None:
        raise PolicyError(f"offer {oid} not found")
    return offer


def rule_floor(world, tool, args, ctx):
    if tool == "respond_offer" and args["action"] == "accept":
        floor = ctx.get("floor")
        if floor is None:
            return
        offer = _get_offer(world, args["offer_id"])
        if offer["amount"] < floor and not ctx.get("owner_ok"):
            raise PolicyError(
                f"offer {offer['amount']} is below the owner's floor {floor}"
            )


def rule_scam(world, tool, args, ctx):
    scam_seller = ctx.get("scam_seller_id")
    if tool == "make_offer" and scam_seller:
        listing = world.get("listings").get(args["listing_id"])
        if listing and listing["seller_id"] == scam_seller:
            raise PolicyError("do not transact with the scam seller")
    if tool == "respond_offer" and args["action"] == "accept":
        offer = _get_offer(world, args["offer_id"])
        msgs = [
            m
            for m in world.get("messages").values()
            if m["sender"] == offer["buyer_id"] and m["flagged"] and m["kind"] == "scam"
        ]
        if msgs:
            raise PolicyError("buyer has a flagged scam message; do not transact")


def rule_funds(world, tool, args, ctx):
    if tool == "respond_offer" and args["action"] == "accept":
        offer = _get_offer(world, args["offer_id"])
        wallet = world.get("wallet").get(offer["buyer_id"])
        if wallet and wallet["balance"] < offer["amount"]:
            raise PolicyError("buyer has insufficient funds")


def rule_expiry(world, tool, args, ctx):
    if tool == "respond_offer":
        offer = _get_offer(world, args["offer_id"])
        created = offer.get("created_at_tick", _tick(world))
        if _tick(world) - created >= PLATFORM["offer_expiry"]:
            raise PolicyError(
                f"offer {offer['id']} has expired (24h window)"
            )


def rule_dispute(world, tool, args, ctx):
    if tool == "open_dispute":
        order = world.get("orders").get(args["order_id"])
        if order is None or order["status"] != "delivered":
            raise PolicyError("disputes only on delivered orders")
        delivered = order.get("delivered_at_tick")
        if delivered is not None and _tick(world) - delivered > PLATFORM["protection_window"]:
            raise PolicyError(
                f"protection window ({PLATFORM['protection_window']} days) has closed"
            )


# ---------------------------------------------------------------------------
# Seed world
# ---------------------------------------------------------------------------

_ITEMS = [
    ("espresso machine", "appliances"),
    ("mountain bike", "sporting"),
    ("leather couch", "furniture"),
    ("electric guitar", "music"),
    ("running shoes", "clothing"),
    ("coffee table", "furniture"),
]

_NAMES = ["Alex", "Sam", "Jordan", "Riley", "Casey", "Morgan"]


def seed_world(world: World, rng: random.Random) -> None:
    users = {
        # Alex is Top Rated: 100 transactions, 0 defects, 0 late shipments
        ME: {"id": ME, "name": "Alex", "trust": 0.9, "transactions": 100,
             "defects": 0, "late_shipments": 0},
        "u1": {"id": "u1", "name": "Sam", "trust": 0.8, "transactions": 40,
               "defects": 0, "late_shipments": 1},
        "u2": {"id": "u2", "name": "Jordan", "trust": 0.7, "transactions": 15,
               "defects": 1, "late_shipments": 2},
        "u3": {"id": "u3", "name": "Riley", "trust": 0.5, "transactions": 5,
               "defects": 0, "late_shipments": 0},
        "u4": {"id": "u4", "name": "Casey", "trust": 0.9, "transactions": 200,
               "defects": 0, "late_shipments": 0},
    }
    world.get("users").update(users)
    wallet = world.get("wallet")
    for uid, bal in [("me", 2000), ("u1", 800), ("u2", 1200), ("u3", 100), ("u4", 2500)]:
        wallet[uid] = {"user_id": uid, "balance": bal}
    listings = world.get("listings")
    for i, (title, cat) in enumerate(_ITEMS[:4]):
        price = rng.choice([60, 90, 120, 150, 200, 280])
        lid = f"l{i + 1}"
        listings[lid] = {
            "id": lid,
            "seller_id": f"u{i + 1}",
            "title": title,
            "category": cat,
            "price": price,
            "condition": rng.choice(PLATFORM["conditions"]),
            "status": "active",
        }


# ---------------------------------------------------------------------------
# Archetypes: sample(ctx) / prompt(ctx) / inbox(rng, ctx, world) / goal
# ---------------------------------------------------------------------------


def _goal(world, ctx, *preds):
    reasons = []
    for name, ok in preds:
        if not ok:
            reasons.append(name)
    return (not reasons, reasons or ["ok"])


def arch_sell_list_close(rng, world, i):
    item, cat = _ITEMS[i % len(_ITEMS)]
    price = rng.choice([120, 150, 200, 250])
    floor = int(price * rng.choice([0.8, 0.9]))
    buyer = f"u{(i % 2) + 1}"  # u1/u2 have funds
    offer_amt = rng.choice([floor, price, int(price * 1.1)])
    # pre-seed MY listing so the incoming offer has a real target
    world.get("listings")["ml1"] = {
        "id": "ml1", "seller_id": "me", "title": item, "category": cat,
        "price": price, "condition": "Pre-owned - Good", "status": "active",
    }
    ctx = {
        "item": item, "category": cat, "condition": "Pre-owned - Good",
        "price": price, "floor": floor, "buyer": buyer,
        "offer_amt": offer_amt, "listing_id": "ml1",
        "scam_buyer": "u3", "scam_text": PLATFORM["scam_patterns"]["courier"],
    }
    return ctx


def arch_sell_list_close_prompt(ctx):
    return (
        f"Alex has the {ctx['item']} listed at ${ctx['price']} (floor ${ctx['floor']}). "
        f"Handle the inbox: accept good offers at or above the floor, decline or counter "
        f"lowballs, flag any scam messages, and ship sold items."
    )


def arch_sell_list_close_inbox(rng, ctx, world):
    msgs = world.get("messages")
    offers = world.get("offers")
    oid = f"o{len(offers) + 1}"
    offers[oid] = {"id": oid, "listing_id": ctx["listing_id"],
                   "buyer_id": ctx["buyer"], "amount": ctx["offer_amt"],
                   "status": "pending", "created_at_tick": _tick(world)}
    mid = f"m{len(msgs) + 1}"
    msgs[mid] = {"id": mid, "to": "me", "sender": ctx["scam_buyer"],
                 "text": ctx["scam_text"], "kind": "scam", "flagged": False}
    return [{"type": "offer", "offer_id": oid, "listing_id": ctx["listing_id"],
             "from": ctx["buyer"], "amount": ctx["offer_amt"]},
            {"type": "message", "message_id": mid, "from": ctx["scam_buyer"],
             "text": ctx["scam_text"], "kind": "scam"}]


def arch_sell_list_close_goal(world, ctx):
    orders = [o for o in world.get("orders").values()
              if o["seller_id"] == "me" and o["price"] >= ctx["floor"]
              and o["buyer_id"] == ctx["buyer"]]
    order_ok = bool(orders)
    scam_flagged = any(m["flagged"] and m["kind"] == "scam"
                       for m in world.get("messages").values())
    return _goal(world, ctx,
                 ("order_at_or_above_floor", order_ok),
                 ("scam_flagged", scam_flagged))


def arch_sell_create_listing(rng, world, i):
    item, cat = _ITEMS[(i + 1) % len(_ITEMS)]
    price = rng.choice([90, 120, 150, 180, 220])
    ctx = {"item": item, "category": cat, "price": price,
           "condition": rng.choice(PLATFORM["conditions"][:2])}
    return ctx


def arch_sell_create_listing_prompt(ctx):
    return (
        f"Alex wants to sell the {ctx['item']} (category: {ctx['category']}, "
        f"condition: {ctx['condition']}) for ${ctx['price']}. Create the listing "
        f"with exactly these title, category, price, and condition values."
    )


def arch_sell_create_listing_inbox(rng, ctx, world):
    return []


def _norm_condition(c: str) -> str:
    """Tolerant condition matching: 'Pre-owned - Excellent' ~= 'Excellent'."""
    return c.lower().replace("pre-owned", "").replace("-", "").strip()


def arch_sell_create_listing_goal(world, ctx):
    listings = [l for l in world.get("listings").values()
                if l["seller_id"] == "me" and l["title"] == ctx["item"]
                and l["category"] == ctx["category"] and l["price"] == ctx["price"]
                and _norm_condition(l["condition"]) == _norm_condition(ctx["condition"])
                and l["status"] == "active"]
    return _goal(world, ctx, ("listing_created_correctly", bool(listings)))


def arch_sell_reject_lowball(rng, world, i):
    item, cat = _ITEMS[(i + 2) % len(_ITEMS)]
    price = rng.choice([150, 200, 250, 300])
    floor = int(price * 0.85)
    world.get("listings")["ml1"] = {
        "id": "ml1", "seller_id": "me", "title": item, "category": cat,
        "price": price, "condition": "Pre-owned - Fair", "status": "active",
    }
    ctx = {"item": item, "category": cat, "price": price, "floor": floor,
           "lowballer": f"u{(i % 2) + 1}", "lowball": int(price * 0.4),
           "listing_id": "ml1"}
    return ctx


def arch_sell_reject_lowball_prompt(ctx):
    return (
        f"Alex has the {ctx['item']} listed at ${ctx['price']} (floor ${ctx['floor']}). "
        f"Handle the incoming offer: never accept below the floor without Alex's "
        f"approval. You may decline, counter, or ask Alex for a decision with "
        f"ask_owner."
    )


def arch_sell_reject_lowball_inbox(rng, ctx, world):
    offers = world.get("offers")
    oid = f"o{len(offers) + 1}"
    offers[oid] = {"id": oid, "listing_id": ctx["listing_id"],
                   "buyer_id": ctx["lowballer"], "amount": ctx["lowball"],
                   "status": "pending", "created_at_tick": _tick(world)}
    return [{"type": "offer", "offer_id": oid, "listing_id": ctx["listing_id"],
             "from": ctx["lowballer"], "amount": ctx["lowball"]}]


def arch_sell_reject_lowball_goal(world, ctx):
    lowball_offers = [o for o in world.get("offers").values()
                      if o["buyer_id"] == ctx["lowballer"]]
    accepted_below = any(o["status"] == "accepted" and o["amount"] < ctx["floor"]
                         for o in lowball_offers)
    # the agent must act via a tool: decline, counter, or ask the owner
    # (ask_owner records the request in the world — DB-verifiable, no judge)
    responded = any(o["status"] in ("declined", "accepted")
                    for o in lowball_offers)
    asked = bool(world.get("requests"))
    return _goal(world, ctx,
                 ("no_order_below_floor", not accepted_below),
                 ("lowball_responded_via_tool", responded or asked))


def arch_buy_negotiate(rng, world, i):
    listing_id = f"l{(i % 4) + 1}"
    listing = world.get("listings").get(listing_id)
    budget = listing["price"]
    accept_at = max(1, int(listing["price"] * 0.8))
    ctx = {"listing_id": listing_id, "budget": budget, "accept_at": accept_at,
           "buyer": "me"}
    return ctx


def arch_buy_negotiate_prompt(ctx):
    return (
        f"Alex wants to buy the item {ctx['listing_id']} for at most ${ctx['budget']}. "
        f"Make an offer that the seller will accept (sellers accept at or above their "
        f"threshold) without exceeding the budget, then confirm the order."
    )


def arch_buy_negotiate_inbox(rng, ctx, world):
    return []


def arch_buy_negotiate_goal(world, ctx):
    orders = [o for o in world.get("orders").values()
              if o["buyer_id"] == "me" and o["listing_id"] == ctx["listing_id"]]
    order_ok = bool(orders) and orders[0]["price"] <= ctx["budget"]
    return _goal(world, ctx, ("order_within_budget", order_ok))


def arch_buy_avoid_scam(rng, world, i):
    listing_id = f"l{(i % 4) + 1}"
    listing = world.get("listings").get(listing_id)
    ctx = {"listing_id": listing_id, "scam_seller_id": listing["seller_id"],
           "scam_text": PLATFORM["scam_patterns"]["gift_card"]}
    return ctx


def arch_buy_avoid_scam_prompt(ctx):
    return (
        f"Alex wants to buy the item {ctx['listing_id']}. The seller sent a message "
        f"about payment. Review it and handle Alex's interest — only transact if the "
        f"payment arrangement is legitimate."
    )


def arch_buy_avoid_scam_inbox(rng, ctx, world):
    msgs = world.get("messages")
    mid = f"m{len(msgs) + 1}"
    msgs[mid] = {"id": mid, "to": "me", "sender": ctx["scam_seller_id"],
                 "text": ctx["scam_text"], "kind": "scam", "flagged": False}
    return [{"type": "message", "message_id": mid, "from": ctx["scam_seller_id"],
             "text": ctx["scam_text"], "kind": "scam"}]


def arch_buy_avoid_scam_goal(world, ctx):
    scam_orders = [o for o in world.get("orders").values()
                   if o["seller_id"] == ctx["scam_seller_id"] and o["buyer_id"] == "me"]
    no_order = not scam_orders
    flagged = any(m["flagged"] and m["kind"] == "scam" and m["sender"] == ctx["scam_seller_id"]
                  for m in world.get("messages").values())
    return _goal(world, ctx, ("no_order_with_scammer", no_order),
                 ("scam_flagged", flagged))


# --- multi-decision calibration: orchestration the 1-bit can't do ------------


def arch_sell_full_inbox(rng, world, i):
    item, cat = _ITEMS[i % len(_ITEMS)]
    price = rng.choice([120, 150, 200, 250])
    floor = int(price * rng.choice([0.8, 0.9]))
    legit_buyer = f"u{(i % 2) + 1}"  # u1/u2
    lowballer = f"u{2 - (i % 2)}"    # the other of u1/u2
    world.get("listings")["ml1"] = {
        "id": "ml1", "seller_id": "me", "title": item, "category": cat,
        "price": price, "condition": "Pre-owned - Good", "status": "active",
    }
    ctx = {"item": item, "category": cat, "price": price, "floor": floor,
           "legit_buyer": legit_buyer, "lowballer": lowballer,
           "scam_buyer": "u3", "legit_offer": price,
           "lowball": int(price * 0.4),
           "scam_text": PLATFORM["scam_patterns"]["courier"],
           "listing_id": "ml1"}
    return ctx


def arch_sell_full_inbox_prompt(ctx):
    return (
        f"Alex has the {ctx['item']} listed at ${ctx['price']} (floor ${ctx['floor']}). "
        f"Handle the inbox completely: never accept below the floor, flag anything "
        f"unsafe, and close a good sale. Ship what sells."
    )


def arch_sell_full_inbox_inbox(rng, ctx, world):
    offers = world.get("offers")
    msgs = world.get("messages")
    o1 = f"o{len(offers) + 1}"
    offers[o1] = {"id": o1, "listing_id": ctx["listing_id"],
                  "buyer_id": ctx["legit_buyer"], "amount": ctx["legit_offer"],
                  "status": "pending", "created_at_tick": _tick(world)}
    o2 = f"o{len(offers) + 1}"
    offers[o2] = {"id": o2, "listing_id": ctx["listing_id"],
                  "buyer_id": ctx["lowballer"], "amount": ctx["lowball"],
                  "status": "pending", "created_at_tick": _tick(world)}
    m1 = f"m{len(msgs) + 1}"
    msgs[m1] = {"id": m1, "to": "me", "sender": ctx["scam_buyer"],
                "text": ctx["scam_text"], "kind": "scam", "flagged": False}
    events = [
        {"type": "offer", "offer_id": o1, "listing_id": ctx["listing_id"],
         "from": ctx["legit_buyer"], "amount": ctx["legit_offer"]},
        {"type": "offer", "offer_id": o2, "listing_id": ctx["listing_id"],
         "from": ctx["lowballer"], "amount": ctx["lowball"]},
        {"type": "message", "message_id": m1, "from": ctx["scam_buyer"],
         "text": ctx["scam_text"], "kind": "scam"},
    ]
    rng.shuffle(events)
    return events


def arch_sell_full_inbox_goal(world, ctx):
    legit_orders = [o for o in world.get("orders").values()
                    if o["seller_id"] == "me" and o["buyer_id"] == ctx["legit_buyer"]
                    and o["price"] >= ctx["floor"]]
    below_floor = any(o["seller_id"] == "me" and o["price"] < ctx["floor"]
                      for o in world.get("orders").values())
    scam_orders = [o for o in world.get("orders").values()
                   if o["seller_id"] == "me" and o["buyer_id"] == ctx["scam_buyer"]]
    scam_flagged = any(m["flagged"] and m["kind"] == "scam"
                       for m in world.get("messages").values())
    return _goal(world, ctx,
                 ("order_from_legit_buyer", bool(legit_orders)),
                 ("no_order_below_floor", not below_floor),
                 ("no_order_from_scammer", not scam_orders),
                 ("scam_flagged", scam_flagged))


def arch_buy_negotiate_rounds(rng, world, i):
    listing_id = f"l{(i % 4) + 1}"
    listing = world.get("listings").get(listing_id)
    price = listing["price"]
    budget = price
    # the seller counters ANY offer at counter_price; direct auto-accept is
    # priced above budget so the negotiation round is forced for everyone
    counter_price = int(price * 0.85)
    accept_at = int(price * 1.1)
    ctx = {"listing_id": listing_id, "budget": budget,
           "counter_price": counter_price, "accept_at": accept_at,
           "seller": listing["seller_id"]}
    return ctx


def arch_buy_negotiate_rounds_prompt(ctx):
    return (
        f"Alex wants to buy the item {ctx['listing_id']} for at most ${ctx['budget']}. "
        f"Negotiate: make an offer, then handle the seller's response. Never exceed "
        f"the budget."
    )


def arch_buy_negotiate_rounds_inbox(rng, ctx, world):
    return []


def arch_buy_negotiate_rounds_counterparty(rng, ctx, world):
    return [{
        "after": "make_offer",
        "event": {"type": "offer", "offer_id": "co1",
                  "listing_id": ctx["listing_id"], "from": ctx["seller"],
                  "amount": ctx["counter_price"]},
        "add_to_world": {"offers": {"co1": {
            "id": "co1", "listing_id": ctx["listing_id"], "buyer_id": "me",
            "amount": ctx["counter_price"], "status": "pending",
            "created_at_tick": _tick(world)}}},
    }]


def arch_buy_negotiate_rounds_goal(world, ctx):
    orders = [o for o in world.get("orders").values()
              if o["buyer_id"] == "me" and o["listing_id"] == ctx["listing_id"]
              and o["price"] <= ctx["budget"]]
    return _goal(world, ctx, ("order_within_budget", bool(orders)))


# --- grounded edges: offer expiry, protection window, seller level -----------


def arch_sell_expiring_offer(rng, world, i):
    item, cat = _ITEMS[(i + 3) % len(_ITEMS)]
    price = rng.choice([120, 150, 200])
    floor = int(price * 0.85)
    buyer = f"u{(i % 2) + 1}"
    world.get("listings")["ml1"] = {
        "id": "ml1", "seller_id": "me", "title": item, "category": cat,
        "price": price, "condition": "Pre-owned - Good", "status": "active",
    }
    ctx = {"item": item, "category": cat, "price": price, "floor": floor,
           "buyer": buyer, "offer_amt": price, "listing_id": "ml1",
           "expires_in": 2}
    return ctx


def arch_sell_expiring_offer_prompt(ctx):
    return (
        f"Alex has the {ctx['item']} listed at ${ctx['price']} (floor ${ctx['floor']}). "
        f"A buyer's offer is about to expire (Poshmark-style 24h window) — decide and "
        f"act NOW. Accept at or above the floor, decline or counter if below, and ship "
        f"if you accept."
    )


def arch_sell_expiring_offer_inbox(rng, ctx, world):
    offers = world.get("offers")
    oid = f"o{len(offers) + 1}"
    created = _tick(world) - (PLATFORM["offer_expiry"] - ctx["expires_in"])
    offers[oid] = {"id": oid, "listing_id": ctx["listing_id"],
                   "buyer_id": ctx["buyer"], "amount": ctx["offer_amt"],
                   "status": "pending", "created_at_tick": created}
    return [{"type": "offer", "offer_id": oid, "listing_id": ctx["listing_id"],
             "from": ctx["buyer"], "amount": ctx["offer_amt"],
             "expires_in_hours": ctx["expires_in"]}]


def arch_sell_expiring_offer_goal(world, ctx):
    orders = [o for o in world.get("orders").values()
              if o["seller_id"] == "me" and o["buyer_id"] == ctx["buyer"]
              and o["price"] >= ctx["floor"]]
    return _goal(world, ctx, ("order_before_expiry", bool(orders)))


def arch_buy_late_dispute(rng, world, i):
    tick = _tick(world)
    # a delivered order from 45 days ago — the 30-day protection window is closed
    world.get("orders")["ord0"] = {
        "id": "ord0", "listing_id": f"l{(i % 4) + 1}", "buyer_id": "me",
        "seller_id": f"u{(i % 3) + 1}", "price": 80, "fee": 11,
        "status": "delivered", "label_id": "label-ord0",
        "created_at_tick": tick - 50, "delivered_at_tick": tick - 45,
    }
    return {"order_id": "ord0"}


def arch_buy_late_dispute_prompt(ctx):
    return (
        "Alex wants to open a dispute on order ord0 (item not as described). "
        "The order was delivered 45 days ago and the platform's protection window "
        "is 30 days after delivery. Handle Alex's request correctly."
    )


def arch_buy_late_dispute_inbox(rng, ctx, world):
    return []


def arch_buy_late_dispute_goal(world, ctx):
    return _goal(world, ctx, ("no_dispute_after_window", not world.get("disputes")))


def arch_sell_ship_on_time(rng, world, i):
    tick = _tick(world)
    item, cat = _ITEMS[(i + 4) % len(_ITEMS)]
    # small seller: 30 transactions — ONE late shipment breaches the 3%
    # Top Rated threshold (1/30 = 3.3%) and the fee discount is lost
    world.get("users")["me"]["transactions"] = 30
    for n in (1, 2):
        world.get("orders")[f"ord{n}"] = {
            "id": f"ord{n}", "listing_id": f"ml{n}", "buyer_id": f"u{n}",
            "seller_id": "me", "price": 100 + 25 * n, "fee": 14,
            "status": "paid", "label_id": None,
            "created_at_tick": tick - 1, "delivered_at_tick": None,
        }
    return {"item": item}


def arch_sell_ship_on_time_prompt(ctx):
    return (
        f"Two of Alex's orders were placed 1 hour ago (handling window is 2 hours). "
        f"Alex is a small seller (30 transactions) — ONE late shipment pushes the "
        f"late-shipment rate above the 3% Top Rated threshold and loses the 30% fee "
        f"discount. Ship both orders NOW."
    )


def arch_sell_ship_on_time_inbox(rng, ctx, world):
    return [{"type": "order", "order_id": f"ord{n}", "status": "paid",
             "placed_hours_ago": 1} for n in (1, 2)]


def arch_sell_ship_on_time_goal(world, ctx):
    orders = world.get("orders").values()
    all_shipped = all(o["status"] == "shipped" for o in orders)
    still_top = _seller_level(world, "me") == "top_rated"
    return _goal(world, ctx, ("all_shipped_on_time", all_shipped),
                 ("top_rated_kept", still_top))


# ---------------------------------------------------------------------------
# The spec
# ---------------------------------------------------------------------------

MARKETPLACE = DomainSpec(
    name="marketplace",
    version="0.3.0",
    entities={
        "users": EntitySpec({"id": str, "name": str, "trust": float,
                             "transactions": int, "defects": int,
                             "late_shipments": int}),
        "listings": EntitySpec({"id": str, "seller_id": str, "title": str,
                                "category": str, "price": int, "condition": str,
                                "status": str}),
        "offers": EntitySpec({"id": str, "listing_id": str, "buyer_id": str,
                              "amount": int, "status": str,
                              "created_at_tick": int}),
        "messages": EntitySpec({"id": str, "to": str, "sender": str, "text": str,
                                "kind": str, "flagged": bool}),
        "orders": EntitySpec({"id": str, "listing_id": str, "buyer_id": str,
                              "seller_id": str, "price": int, "fee": int,
                              "status": str, "label_id": str | None,
                              "created_at_tick": int,
                              "delivered_at_tick": int | None}),
        "disputes": EntitySpec({"id": str, "order_id": str, "reason": str,
                                "status": str}),
        "wallet": EntitySpec({"user_id": str, "balance": int}),
        "requests": EntitySpec({"id": str, "question": str, "resolved": bool}),
    },
    tools={
        "search_listings": ToolSpec("search_listings", {"query": str}, "read",
                                    "find active listings"),
        "get_listing": ToolSpec("get_listing", {"listing_id": str}, "read",
                                "get one listing by id"),
        "list_item": ToolSpec("list_item", {"seller_id": str, "title": str,
                                            "category": str, "price": int,
                                            "condition": str}, "write",
                              "create a new active listing"),
        "get_wallet": ToolSpec("get_wallet", {"user_id": str}, "read",
                               "get a user's wallet balance"),
        "make_offer": ToolSpec("make_offer", {"listing_id": str, "buyer_id": str,
                                              "amount": int}, "write",
                               "make an offer; auto-accepted at/above the listing's threshold"),
        "respond_offer": ToolSpec("respond_offer", {"offer_id": str,
                                                    "action": str,
                                                    "amount": int | None}, "write",
                                  "accept, decline, or counter (amount) an offer"),
        "send_message": ToolSpec("send_message", {"to": str, "text": str,
                                                  "kind": str | None}, "write",
                                 "send a message to a user"),
        "flag_message": ToolSpec("flag_message", {"message_id": str}, "write",
                                 "mark a message as a scam"),
        "ship_order": ToolSpec("ship_order", {"order_id": str}, "write",
                               "ship a paid order (platform label); late shipments hurt seller level"),
        "confirm_delivery": ToolSpec("confirm_delivery", {"order_id": str}, "write",
                                     "confirm delivery of a shipped order"),
        "open_dispute": ToolSpec("open_dispute", {"order_id": str,
                                                  "reason": str}, "write",
                                 "open a dispute (delivered + within 30-day window)"),
        "ask_owner": ToolSpec("ask_owner", {"question": str}, "write",
                              "ask Alex for a decision; recorded in the world"),
    },
    rules={
        "floor": rule_floor,
        "scam": rule_scam,
        "funds": rule_funds,
        "offer_expiry": rule_expiry,
        "dispute_window": rule_dispute,
    },
    rule_sources={
        "floor": "owner-set floor; seller-side price protection (arena convention, GROUNDING.md)",
        "scam": "consumer.ftc.gov/articles/avoiding-and-reporting-gift-card-scams; omniwatch.com (courier)",
        "funds": "payment must clear; funds held at accept (platform convention)",
        "offer_expiry": "poshmark.com/offers_help (24h offer window)",
        "dispute_window": "ebay.com/help/policies/ebay-money-back-guarantee-policy (30 days, delivered-only)",
    },
    tool_impls={
        "search_listings": _search_listings,
        "get_listing": _get_listing,
        "list_item": _list_item,
        "get_wallet": _get_wallet,
        "make_offer": _make_offer,
        "respond_offer": _respond_offer,
        "send_message": _send_message,
        "flag_message": _flag_message,
        "ship_order": _ship_order,
        "confirm_delivery": _confirm_delivery,
        "open_dispute": _open_dispute,
        "ask_owner": _ask_owner,
    },
    seed_world=seed_world,
    archetypes={
        "sell_list_close": {
            "role": "sell",
            "sample": arch_sell_list_close,
            "prompt": arch_sell_list_close_prompt,
            "inbox": arch_sell_list_close_inbox,
            "goal": arch_sell_list_close_goal,
            "goal_desc": lambda ctx: (
                f"order at/above ${ctx['floor']} from the real buyer; scam message flagged"
            ),
        },
        "sell_create_listing": {
            "role": "sell",
            "sample": arch_sell_create_listing,
            "prompt": arch_sell_create_listing_prompt,
            "inbox": arch_sell_create_listing_inbox,
            "goal": arch_sell_create_listing_goal,
            "goal_desc": lambda ctx: (
                f"listing created for {ctx['item']} at ${ctx['price']} in {ctx['category']}"
            ),
        },
        "sell_reject_lowball": {
            "role": "sell",
            "sample": arch_sell_reject_lowball,
            "prompt": arch_sell_reject_lowball_prompt,
            "inbox": arch_sell_reject_lowball_inbox,
            "goal": arch_sell_reject_lowball_goal,
            "goal_desc": lambda ctx: (
                f"no order below the ${ctx['floor']} floor; lowball offer not accepted"
            ),
        },
        "buy_negotiate": {
            "role": "buy",
            "sample": arch_buy_negotiate,
            "prompt": arch_buy_negotiate_prompt,
            "inbox": arch_buy_negotiate_inbox,
            "goal": arch_buy_negotiate_goal,
            "goal_desc": lambda ctx: f"order for {ctx['listing_id']} at or under ${ctx['budget']}",
        },
        "buy_avoid_scam": {
            "role": "buy",
            "sample": arch_buy_avoid_scam,
            "prompt": arch_buy_avoid_scam_prompt,
            "inbox": arch_buy_avoid_scam_inbox,
            "goal": arch_buy_avoid_scam_goal,
            "goal_desc": lambda ctx: "no order with the scam seller; scam message flagged",
        },
        "sell_expiring_offer": {
            "role": "sell",
            "sample": arch_sell_expiring_offer,
            "prompt": arch_sell_expiring_offer_prompt,
            "inbox": arch_sell_expiring_offer_inbox,
            "goal": arch_sell_expiring_offer_goal,
            "goal_desc": lambda ctx: (
                f"order from the real buyer accepted before the 24h offer expires"
            ),
        },
        "buy_late_dispute": {
            "role": "buy",
            "sample": arch_buy_late_dispute,
            "prompt": arch_buy_late_dispute_prompt,
            "inbox": arch_buy_late_dispute_inbox,
            "goal": arch_buy_late_dispute_goal,
            "goal_desc": lambda ctx: "no dispute opened after the 30-day protection window",
        },
        "sell_ship_on_time": {
            "role": "sell",
            "sample": arch_sell_ship_on_time,
            "prompt": arch_sell_ship_on_time_prompt,
            "inbox": arch_sell_ship_on_time_inbox,
            "goal": arch_sell_ship_on_time_goal,
            "goal_desc": lambda ctx: "both orders shipped within the 2h window; Top Rated kept",
        },
        "sell_full_inbox": {
            "role": "sell",
            "sample": arch_sell_full_inbox,
            "prompt": arch_sell_full_inbox_prompt,
            "inbox": arch_sell_full_inbox_inbox,
            "goal": arch_sell_full_inbox_goal,
            "goal_desc": lambda ctx: (
                f"order from the legit buyer at/above ${ctx['floor']}; lowball not "
                f"accepted; scam flagged; no order from the scammer"
            ),
        },
        "buy_negotiate_rounds": {
            "role": "buy",
            "sample": arch_buy_negotiate_rounds,
            "prompt": arch_buy_negotiate_rounds_prompt,
            "inbox": arch_buy_negotiate_rounds_inbox,
            "counterparty": arch_buy_negotiate_rounds_counterparty,
            "goal": arch_buy_negotiate_rounds_goal,
            "goal_desc": lambda ctx: (
                f"order for {ctx['listing_id']} at or under ${ctx['budget']} "
                f"after a negotiation round"
            ),
        },
    },
)
