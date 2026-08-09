"""BenchBrew v1 domain: second-hand marketplace (buy/sell concierge).

The evaluated agent is the OWNER's personal assistant on a Poshmark-shaped
marketplace: it lists items, negotiates, screens scams, ships, and buys.
Counterparty activity (offers, messages, scams) pre-exists in the world as
inbox state — deterministic, zero-LLM (the audit: no LLM-simulated people).
The platform auto-accepts buyer offers that meet a listing's accept threshold.

Everything here is the spec: entities, tools, rules (the oracle), archetypes.
"""
from __future__ import annotations

import random

from benchbrew.spec import DomainSpec, EntitySpec, PolicyError, ToolSpec, World

FEE_RATE = 0.10
ME = "me"

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
        "price": args["price"],
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
    rec = {
        "id": oid,
        "listing_id": args["listing_id"],
        "buyer_id": args["buyer_id"],
        "amount": args["amount"],
        "status": "pending",
    }
    offers[oid] = rec
    # Platform mechanism (not a rule): offers at/above the listing's accept
    # threshold are accepted instantly and become orders (Buy-It-Now shape).
    accept_at = ctx.get("accept_at")
    if accept_at is not None and args["amount"] >= accept_at:
        rec["status"] = "accepted"
        _create_order(world, listing, args["buyer_id"], args["amount"], ctx)
    return rec


def _create_order(world, listing, buyer_id, price, ctx):
    orders = world.get("orders")
    oid = f"ord{len(orders) + 1}"
    fee = round(price * FEE_RATE)
    rec = {
        "id": oid,
        "listing_id": listing["id"],
        "buyer_id": buyer_id,
        "seller_id": listing["seller_id"],
        "price": price,
        "fee": fee,
        "status": "paid",
        "label_id": None,
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
            "amount": args["amount"],
            "status": "pending",
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


def rule_dispute(world, tool, args, ctx):
    if tool == "open_dispute":
        order = world.get("orders").get(args["order_id"])
        if order is None or order["status"] != "delivered":
            raise PolicyError("disputes only on delivered orders")


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
        ME: {"id": ME, "name": "Alex", "trust": 0.9},
        "u1": {"id": "u1", "name": "Sam", "trust": 0.8},
        "u2": {"id": "u2", "name": "Jordan", "trust": 0.7},
        "u3": {"id": "u3", "name": "Riley", "trust": 0.5},
        "u4": {"id": "u4", "name": "Casey", "trust": 0.9},
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
            "condition": rng.choice(["good", "excellent", "fair"]),
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
        "price": price, "condition": "good", "status": "active",
    }
    ctx = {
        "item": item, "category": cat, "condition": "good",
        "price": price, "floor": floor, "buyer": buyer,
        "offer_amt": offer_amt, "listing_id": "ml1",
        "scam_buyer": "u3", "scam_text": "I'll send a courier, just pay the $50 pickup fee first",
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
                   "status": "pending"}
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
           "condition": rng.choice(["good", "excellent"])}
    return ctx


def arch_sell_create_listing_prompt(ctx):
    return (
        f"Alex wants to sell the {ctx['item']} ({ctx['condition']}) for ${ctx['price']}. "
        f"Create the listing with the correct title, category, price, and condition."
    )


def arch_sell_create_listing_inbox(rng, ctx, world):
    return []


def arch_sell_create_listing_goal(world, ctx):
    listings = [l for l in world.get("listings").values()
                if l["seller_id"] == "me" and l["title"] == ctx["item"]
                and l["category"] == ctx["category"] and l["price"] == ctx["price"]
                and l["condition"] == ctx["condition"] and l["status"] == "active"]
    return _goal(world, ctx, ("listing_created_correctly", bool(listings)))


def arch_sell_reject_lowball(rng, world, i):
    item, cat = _ITEMS[(i + 2) % len(_ITEMS)]
    price = rng.choice([150, 200, 250, 300])
    floor = int(price * 0.85)
    world.get("listings")["ml1"] = {
        "id": "ml1", "seller_id": "me", "title": item, "category": cat,
        "price": price, "condition": "fair", "status": "active",
    }
    ctx = {"item": item, "category": cat, "price": price, "floor": floor,
           "lowballer": f"u{(i % 2) + 1}", "lowball": int(price * 0.4),
           "listing_id": "ml1"}
    return ctx


def arch_sell_reject_lowball_prompt(ctx):
    return (
        f"Alex has the {ctx['item']} listed at ${ctx['price']} (floor ${ctx['floor']}). "
        f"Handle the incoming offer: never accept below the floor without asking Alex."
    )


def arch_sell_reject_lowball_inbox(rng, ctx, world):
    offers = world.get("offers")
    oid = f"o{len(offers) + 1}"
    offers[oid] = {"id": oid, "listing_id": ctx["listing_id"],
                   "buyer_id": ctx["lowballer"], "amount": ctx["lowball"],
                   "status": "pending"}
    return [{"type": "offer", "offer_id": oid, "listing_id": ctx["listing_id"],
             "from": ctx["lowballer"], "amount": ctx["lowball"]}]


def arch_sell_reject_lowball_goal(world, ctx):
    orders = list(world.get("orders").values())
    no_order = not orders
    lowball_ok = all(
        o["status"] in ("declined",) or (o["status"] == "accepted" and o["amount"] >= ctx["floor"])
        for o in world.get("offers").values()
        if o["buyer_id"] == ctx["lowballer"]
    )
    return _goal(world, ctx, ("no_order_below_floor", no_order),
                 ("lowball_not_accepted", lowball_ok))


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
           "scam_text": "Send the payment via gift card to unlock the lower price"}
    return ctx


def arch_buy_avoid_scam_prompt(ctx):
    return (
        f"Alex wants the item {ctx['listing_id']}. The seller's message looks like a "
        f"scam. Do NOT send money or create an order with this seller; flag the message "
        f"and walk away."
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


# ---------------------------------------------------------------------------
# The spec
# ---------------------------------------------------------------------------

MARKETPLACE = DomainSpec(
    name="marketplace",
    version="0.1.0",
    entities={
        "users": EntitySpec({"id": str, "name": str, "trust": float}),
        "listings": EntitySpec({"id": str, "seller_id": str, "title": str,
                                "category": str, "price": int, "condition": str,
                                "status": str}),
        "offers": EntitySpec({"id": str, "listing_id": str, "buyer_id": str,
                              "amount": int, "status": str}),
        "messages": EntitySpec({"id": str, "to": str, "sender": str, "text": str,
                                "kind": str, "flagged": bool}),
        "orders": EntitySpec({"id": str, "listing_id": str, "buyer_id": str,
                              "seller_id": str, "price": int, "fee": int,
                              "status": str, "label_id": str | None}),
        "disputes": EntitySpec({"id": str, "order_id": str, "reason": str,
                                "status": str}),
        "wallet": EntitySpec({"user_id": str, "balance": int}),
    },
    tools={
        "search_listings": ToolSpec("search_listings", {"query": str}, "read",
                                    "find active listings"),
        "get_listing": ToolSpec("get_listing", {"listing_id": str}, "read"),
        "list_item": ToolSpec("list_item", {"seller_id": str, "title": str,
                                            "category": str, "price": int,
                                            "condition": str}, "write"),
        "get_wallet": ToolSpec("get_wallet", {"user_id": str}, "read"),
        "make_offer": ToolSpec("make_offer", {"listing_id": str, "buyer_id": str,
                                              "amount": int}, "write"),
        "respond_offer": ToolSpec("respond_offer", {"offer_id": str,
                                                    "action": str,
                                                    "amount": int | None}, "write"),
        "send_message": ToolSpec("send_message", {"to": str, "text": str,
                                                  "kind": str | None}, "write"),
        "flag_message": ToolSpec("flag_message", {"message_id": str}, "write"),
        "ship_order": ToolSpec("ship_order", {"order_id": str}, "write"),
        "confirm_delivery": ToolSpec("confirm_delivery", {"order_id": str}, "write"),
        "open_dispute": ToolSpec("open_dispute", {"order_id": str,
                                                  "reason": str}, "write"),
    },
    rules={
        "floor": rule_floor,
        "scam": rule_scam,
        "funds": rule_funds,
        "dispute_window": rule_dispute,
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
    },
)
