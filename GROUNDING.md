# Grounding: where the marketplace spec's mechanics come from

Every mechanic in `domains/marketplace.py` must trace to a real, citable
policy. That is how the invented world "translates to real life" without
us being marketplace operators: we borrow the world's existing objective
structures (the same move SWE-bench made by mining real repos, and τ² made
by having practitioners author domains). Auditability of the domain content
is part of the trustless property: anyone can check a mechanic against its
source.

## Mechanic → source map (complete)

| Spec mechanic (current) | Real-world policy | Source |
|---|---|---|
| Flat 10% marketplace fee on orders | eBay: **13.25% final value fee + $0.30/order** in most categories (2.35% on portion over $7,500); one 2026 guide reports the base rising to 13.6%. Poshmark (2026): 5.99% seller + 5.99% buyer protection fee + $1/$2/$3 tiered + shipping from $7.97. Poshmark (older): 20% over $15, $2.95 under $15 | ebay.com/sellercenter/selling/start-selling-on-ebay/seller-fees; super-ds.com/blog/how-much-ebay-charges-for-selling-in-2026; voolist.com/blog/marketplace-fees-comparison-2026 |
| `dispute_window`: disputes only on delivered orders | eBay Money Back Guarantee: "not as described" return request up to **30 calendar days after delivery** (wrong item / damaged / faulty). Exclusions: third-party/buyer-arranged courier pickup = **NOT covered**; trading cards = 3 days. **Conflict noted:** a real platform DOES allow pre-delivery issue reports — the spec's "delivered-only" rule should become "within 30 days of delivery" | ebay.com/help/policies/ebay-money-back-guarantee-policy |
| Condition grading: good / excellent / fair | eBay clothing/electronics condition options: **Pre-owned - Excellent** (gently used, few signs of wear), **Pre-owned - Good** (gently used, imperfections described), **Pre-owned - Fair** (significantly visible imperfections — scratches, dents, broken/missing parts). Spec should adopt these exact labels | ebay.com/help/selling/listings/creating-managing-listings/item-conditions-category; ebay sellercenter 2025-01 "New item conditions" update |
| Offer flow: offers exist, accept/decline/counter | Poshmark: both sides make offers; buyer-initiated offers **expire after 24h with no action** (platform help page; one guide says 48h — pinned to platform page); counters are the negotiation loop; opening offers ~20–30% below asking are the norm | poshmark.com/offers_help; nifty.ai/post/poshmark-offer-guide; blog.vendoo.co (offer etiquette) |
| Scam: courier-fee ("I'll send a courier, pay the pickup fee first") | Courier-pickup scams are a documented seller-targeted pattern: "buyer insists they'll send their own courier" is a red flag — legitimate buyers don't have private couriers on standby; platform protection explicitly excludes buyer-arranged courier pickup | omniwatch.com/blog/facebook-marketplace-scams/ (scam #4); ebay MBG exclusions |
| Scam: gift-card / off-platform payment | FTC: gift-card payment requests are a scam signal; unusual, hard-to-reverse payment methods = red flag; scammers push moving off-platform | consumer.ftc.gov/articles/avoiding-and-reporting-gift-card-scams; kentpolicedepartment (FB) |
| Scam: overpayment ("accidentally" overpaid, refund the excess) | Overpayment scam: buyer overpays with fraudulent funds, asks seller to refund the excess; when the original payment fails to clear, the seller loses both refund and item | nordpass.com/blog/facebook-marketplace-scams/; AARP FB Marketplace guide |
| Scam: urgency / "moving" / deployed excuses | Scammers pressure for speed (rushed communication) and use "moving to a new location / deployed" sob stories to push off-platform or unusual payment | kentpolicedepartment (FB); BBB warning via WHSV; coveron.com 16 scams |
| Seller performance (NOT yet in spec — proposed edge) | eBay seller levels: **Top Rated** = defect rate ≤ 0.5%, late shipment ≤ 3%, 100+ transactions; **Above Standard** = defect ≤ 2%, late shipment ≤ 7%; **Below Standard** = above those. Defects = cases closed without seller resolution + out-of-stock cancellations. Top Rated = lower fees | super-ds.com/blog/ebay-seller-levels-top-rated-guide; export.ebay.com/en/growth/seller-performance/seller-levels |
| Shipping label mechanics | Platform-generated prepaid labels (Poshmark flat $7.67–7.97, buyer pays); label = platform's own shipping contract (grounds why "own courier" is abnormal) | voolist Poshmark fees guide; Poshmark shipping help |

## Policy snapshot principle

Marketplace policies CHANGE (Poshmark restructured fees in 2025 — sellers
were "irate"; eBay's base fee reportedly moved 13.25%→13.6% for 2026;
eBay introduced new item conditions Jan 2025). So the spec pins a **dated
policy snapshot**: every rule carries `source` (URL + policy name) and the
snapshot date lives in the spec version. A new snapshot = a new spec
version = a new `spec_hash` — already supported by the generator
(`spec_hash` gates bundle identity), so policy drift is explicit and
versioned, never silent.

**Snapshot pin:** `2026-08` (fees: eBay 13.25%+$0.30; conditions:
Pre-owned Excellent/Good/Fair; offers: 24h expiry; protection: 30-day MBG).

## Spec changes implied by the map (proposed)

1. **Fee**: 10% flat → 13.25% + $0.30 (eBay-style, snapshot-pinned) — order
   math + wallet checks updated; fee value becomes a named constant with
   `source`.
2. **Dispute window**: "delivered-only" → "within 30 days of delivery"
   (order carries a `delivered_at` tick; dispute rule checks the window).
3. **Conditions**: `good/excellent/fair` → `Pre-owned - Excellent / Good /
   Fair` (exact eBay labels; prompts + goals updated).
4. **Offer expiry**: offers expire after 24h of in-world ticks — the
   real Poshmark mechanic (adds a time dimension; the agent must act
   before expiry, or a good offer dies — a real discrimination edge).
5. **Seller level** (new edge): users carry defect/late-shipment counters;
   thresholds from eBay's table; agent actions (on-time shipping, case
   resolution) move the level; new archetype where protecting seller level
   is the goal. Top Rated = lower fee.
6. **Scam taxonomy**: texts swapped to the sourced patterns (courier,
   gift-card, overpayment, urgency/moving) — the tell stays in the text,
   never a label (detection, not classification).

## Review gate

Before the marketplace lane is defended in Pilsner: one practitioner
(active resale-platform user or marketplace operator) reviews a sample
bundle — the human-validation pass SWE-bench did with Verified. The
bundle's task set must read as "yes, this is what resale looks like."
