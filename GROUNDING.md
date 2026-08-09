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

## Platform spectrum: one world family, different knob settings

The second-hand marketplace family spans a **mediation axis** — from "no
platform at all" (Craigslist) to "platform is the escrow" (Mercado
Libre/MercadoPago). Every platform is the same entity/tool/rules family at
different settings of: fee structure, buyer-protection window, fulfillment
(local vs shipped), condition structure, negotiation shape, seller levels.

| Platform | Seller fee | Buyer protection | Fulfillment | Notes | Source |
|---|---|---|---|---|---|
| Craigslist | 0 | **none** | local, cash | anonymous relay; scam surface maximal (Western Union, fake cashier's checks) | craigslist.org |
| Facebook Marketplace (local) | 0 | **none** for cash/meetup | local pickup | free; "never pay upfront to hold or for delivery fees"; check account age | facebook.com/policies/purchase_protection; FB Help |
| Facebook Marketplace (shipped) | 0 | Purchase Protection, **max $500** covered | shipping | protection only on shipped checkout; claim → full refund + shipping | facebook.com/policies/purchase_protection |
| OfferUp (local) | 0 | none (local) | local pickup | local = free | marketplacefee.com/offerup-fees |
| OfferUp (shipped) | **12.9%, min $1.99** | claim if not as described | shipping | buyer service fee at checkout | marketplacefee.com/offerup-fees; cluzy.app |
| Depop | **10%** + 3.3% + $0.45 processing | platform payments; dispute process | shipping (label optional) / local | fee on sale price incl. shipping if no label | depophelp.zendesk.com (Seller fees); nifty.ai |
| Mercari | 10% | Buyer Protection fee **3.6%** (buyer pays); **72h after delivery to report**; return ships back within 3 days | shipping / local | protection window is the shortest of the big platforms | mercari.com/us/help_center/article/235, /169 |
| Vinted | **0** (sellers) | mandatory Buyer Protection fee (buyer pays); **~48h seller response** to issue reports | shipping | bundle offers; seller-paid-fee model is the outlier | vinted.com/help/3/550-buyer-protection |
| Poshmark (2026) | 5.99% + tiered $1–3 | 5.99% buyer protection fee | shipping (flat label ~$7.97) | restructured mid-2025 | voolist.com; modernretail.co |
| eBay | **13.25% + $0.30** | MBG: 30 days after delivery (not-as-described); courier pickup NOT covered | shipping / local | seller levels (Top Rated ≤0.5% defect) | ebay.com sellercenter; super-ds.com |
| Mercado Libre (LatAm) | ~13% + processing | **escrow via MercadoPago** (funds held until delivery confirmed) | shipping | the escrow end of the spectrum | (to source) |

### What the spectrum means for the spec

1. **Mediation level is a first-class knob.** At low mediation
   (Craigslist/FB local) the platform provides no protection and the agent
   IS the safety net — scam screening, meetup logistics, payment
   verification. At high mediation (eBay/Poshmark) the agent navigates
   platform policy — windows, fees, dispute process. Different skills,
   same world family.
2. **The phone-agent story skews LOW-mediation.** Facebook Marketplace is
   where ordinary people buy/sell on their phones, and it has the weakest
   platform safety net — so a local agent adds the most value there (and
   the eval has the most to measure). The current spec is eBay/Poshmark-
   shaped (high mediation); a low-mediation variant (FB/Craigslist-shaped:
   free-form messaging, meetup, cash, no protection) is the natural second
   variant — the phone story made concrete.
3. **Protection windows vary by platform** (Mercari 72h, Vinted ~48h
   response, eBay 30d, FB shipped ≤$500). The dispute-window rule is a
   per-platform config, not a fixed constant — another knob.
4. **Fees span 0% → 13.25%+** (Vinted/OfferUp-local/FB-local at zero;
   eBay highest). The fee rule is a per-platform config.

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
