# Grounding: where the marketplace spec's mechanics come from

Every mechanic in `domains/marketplace.py` must trace to a real, citable
policy. That is how the invented world "translates to real life" without
us being marketplace operators: we borrow the world's existing objective
structures (the same move SWE-bench made by mining real repos, and τ² made
by having practitioners author domains). Auditability of the domain content
is part of the trustless property: anyone can check a mechanic against its
source.

## Mechanic → source map

| Spec mechanic (current) | Real-world policy | Source |
|---|---|---|
| Flat 10% marketplace fee on orders | Poshmark (2026): 5.99% seller fee + 5.99% buyer protection fee + $1/$2/$3 tiered fee (under $15 / $15–50 / $50+) + shipping from $7.97 (buyer pays). Older structure: 20% on sales ≥ $15, flat $2.95 under $15. eBay: ~13.25% + $0.30 (to verify) | voolist.com/blog/marketplace-fees-comparison-2026; modernretail.co (Poshmark fee restructure, Jun 2025); resellbot.com/poshmark-fee-calculator |
| `dispute_window`: disputes only on delivered orders | eBay Money Back Guarantee: buyer may request a "not as described" return up to **30 calendar days after delivery** (wrong item / damaged / faulty). Exclusions: item collected by a third party on the buyer's behalf or buyer-arranged courier pickup = **NOT covered**; trading cards = 3 days | ebay.com/help/policies/ebay-money-back-guarantee-policy |
| Scam: courier-fee ("I'll send a courier, pay the pickup fee first") | Courier/escrow-pickup scams are a documented P2P pattern; platform protection explicitly does **not** cover buyer-arranged courier pickup (see MBG exclusion) — which is why scammers push it | AARP FB Marketplace guide; ebay MBG exclusions |
| Scam: gift-card / off-platform payment | FTC: gift-card payment requests are a scam signal ("That's a scam"); unusual, hard-to-reverse payment methods = red flag | consumer.ftc.gov/articles/avoiding-and-reporting-gift-card-scams |
| Scam: overpayment (to encode — buyer "overpays" with fraudulent funds, asks refund of the excess) | Overpayment scam: buyer "accidentally" overpays using a fraudulent source, then asks the seller to refund the excess; when the original payment fails to clear the seller loses both the refund and the item | nordpass.com/blog/facebook-marketplace-scams/; AARP FB Marketplace guide |
| Condition grading: good / excellent / fair | eBay item conditions: New, Like New, Good, Fair, Poor (to verify + map) | ebay.com (to source) |
| Offers / negotiation flow | Poshmark offer + counter-offer mechanics; offer expiry (to verify) | poshmark.com (to source) |
| Seller performance standards | eBay seller standards: defect rate / late-shipment rate thresholds, Top Rated Seller status (to encode as an edge) | ebay.com seller standards (to source) |
| Shipping label mechanics | Platform-generated prepaid labels (Poshmark $7.67–7.97 flat); label = platform's own shipping contract | voolist (Poshmark fees guide) |

## Policy snapshot principle

Marketplace policies CHANGE (Poshmark restructured fees in 2025 — sellers
were "irate"). So the spec pins a **dated policy snapshot**: every rule
carries `source` (URL + policy name) and the snapshot date lives in the
spec version. A new snapshot = a new spec version = a new `spec_hash` —
already supported by the generator (`spec_hash` gates bundle identity), so
policy drift is explicit and versioned, never silent.

## Grounding gaps to close (next research pass)

1. eBay fee structure exact numbers + final-value fee tiers
2. eBay item condition definitions (New/Like New/Good/Fair/Poor)
3. Poshmark offer mechanics: counter limits, offer expiry, minimum offer %
4. Seller performance standards (eBay: defect rate, late shipment, Top Rated)
5. FTC/AARP: the full scam taxonomy (overpayment, courier, gift card, fake
   escrow, "moving" sellers) with sources for each pattern the spec encodes

## Review gate

Before the marketplace lane is defended in Pilsner: one practitioner
(active resale-platform user or marketplace operator) reviews a sample
bundle — the human-validation pass SWE-bench did with Verified. The
bundle's task set must read as "yes, this is what resale looks like."
