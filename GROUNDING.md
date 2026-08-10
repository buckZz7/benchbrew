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

## Spec changes implemented (v0.3 → v0.5; recorded here as the decision trail)

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

## Domain 2: local services (TaskRabbit family) — snapshot 2026-08

Mechanics and their sources (the benchbrew-domain-authoring gate: every rule
traces to a real policy):

1. **Service fee**: clients pay a service fee computed as a percentage of the
   tasker's hourly rate, applied per hour worked; taskers receive 100% of
   their set rate. Source: TaskRabbit Support "What's the Taskrabbit Service
   Fee?" (support.taskrabbit.com/hc/en-us/articles/46260411872155) — the
   article confirms "calculated as a percentage of the hourly rate"; the
   commonly-reported rate is ~15% (TaskRabbit "How Pricing Works" blog:
   "you'll always get 100% of the hourly rate you set"). Sim: 15%.
2. **Cancellation window**: clients may cancel anytime, but pay a
   cancellation fee if the task is canceled within 24 hours of the scheduled
   start time, or the client is a no-show. NO fee if: the tasker did not show
   up, or the task was canceled within 5 minutes of booking. The fee equals
   1 hour at the tasker's hourly rate plus platform fees. Source: TaskRabbit
   Support "Cancellation Policy" (46260411471899, eff. 2025-05-07) and
   "No Show Cancellation Policy" (46260490243227, eff. 2024-09-24).
3. **Escrow / payment release**: the client's card is charged for the task;
   the tasker is paid only after the client confirms completion — payment is
   released within 24h of the tasker submitting the invoice, contingent on
   the client's confirmation. Source: TaskRabbit Support "How Do I Pay My
   Tasker?" (46260427597595) + "How Pricing Works" blog (step 3: "You
   complete the task — and confirm when it's done"). Sim: wallet holds the
   total at booking; confirm_completion releases it to the tasker.
4. **No-show asymmetry**: a tasker who fails to show up forfeits compensation
   and the client owes no cancellation fee (policy carve-out above). A client
   who is unavailable at the start time owes the 1-hour fee.
5. **Off-platform payment = policy violation**: requesting payment outside the
   platform (direct transfer, gift cards) is the services-flavored scam
   pattern — same FTC-documented off-platform payment pressure as
   marketplace scams. Source: TaskRabbit Global Terms of Service (platform
   holds funds; direct payments bypass protection) + FTC consumer fraud
   guidance on off-platform payment requests.

## Review gate (marketplace lane, pending)

### local_services calibration (v0.2, seed 42, 36 tasks — 18 archetypes × 2)

| Model | Score | calls/task | tool-error rate |
|---|---|---|---|
| Qwen3-4B Q8 (weak) | 0.528 | 0.7 | 7.7% |
| Qwen3.6-27B IQ2_XXS (strong) | 0.722 | 1.9 | 21.7% |

Gap 0.194 — the lane separates. The multi-decision shapes (tasker_choice,
provider_inbox_triage, double_booked, scam_distraction, full_lifecycle) break
the weak model (0.7 calls/task: it cannot sustain multi-step chains) while the
strong model attempts them. Gate: weak < strong with a real gap ✓.

### personal_finance calibration (v0.1, seed 42, 26 tasks — 13 archetypes x 2)

| Model | Score | calls/task | tool-error rate |
|---|---|---|---|
| Qwen3-4B Q8 (weak) | 0.346 | 0.6 | 12.5% |
| Qwen3.6-27B IQ2_XXS (strong) | 0.654 | 2.2 | 17.9% |

Gap 0.308 — the widest separation across lanes. The Reg E reporting clock
(freeze + report within the 2-day tier), escalation shapes (transfer_limit,
budget_check, price_hike), and the scam-contact rule (safe-account tell)
break the weak model (0.6 calls/task: it does not sustain multi-step chains)
while the strong model attempts them. Gate: weak < strong with a real gap ✓.

## Domain 4: travel (itinerary concierge, TripHub) — snapshot 2026-08

Mechanics and their sources:
- **Flights — DOT 24-hour rule**: free cancellation or 24h hold within 24
  hours of booking IF booked at least 7 days before departure (direct with
  the airline, US-originating). The clock runs FROM BOOKING — a different
  axis than arrival-side windows. Source: transportation.gov (Refunds page,
  aviation consumer protection).
- **Hotels — Hilton flexible rate**: free cancellation up to 48 hours before
  check-in; within 48h the first night is charged. Source: hilton.com help
  center + pointscrowd.com (Hilton cancellation policy).
- **Cars — Hertz prepaid**: free cancellation within 24 hours of booking;
  cancel >24h before pickup -> $100 fee; <=24h before pickup -> $200 fee
  (fee never exceeds the prepaid total). Late returns: 30-min grace, 30+ min
  -> hourly charges, 1.5h+ -> a full day's rental. Source: hertz.com
  reservation policy + early/late support pages.
- **Travel scams**: wire-transfer/gift-card/payment-app-only payment is the
  tell ("that's a scam, every time"); fake cancellations demanding card
  confirmation. Source: consumer.ftc.gov/articles/avoid-scams-when-you-travel.

### travel calibration (v0.1, seed 42, 20 tasks — 10 archetypes x 2)

| Model | Score | calls/task | tool-error rate |
|---|---|---|---|
| Qwen3-4B Q8 (weak) | 0.25 | 0.5 | 0.0% |
| Qwen3.6-27B IQ2_XXS (strong) | 0.95 | 3.4 | 2.9% |

Gap 0.70 — the widest across lanes. The weak model floors (0.5 calls/task:
it does not attempt the search->book chains or the policy-clock math), the
strong model works the full itinerary. CAVEAT: 0.95 is near-ceiling for the
strong model — v0.2 should add change-fee math, multi-booking cancellation
chains, and hotel no-show shapes to pull it to ~0.85 and leave dethrone
headroom (same hardening arc as marketplace v0.3->v0.5).

### marketplace calibration (v0.5 RE-MEASUREMENT, seed 42, 26 tasks — 13 archetypes x 2)

| Model | Score | calls/task | tool-error rate |
|---|---|---|---|
| Qwen3-4B Q8 (weak) | 0.231 | 0.7 | 11.8% |
| Qwen3.6-27B IQ2_XXS (strong) | 0.923 | 2.5 | 6.2% |

Gap 0.69 — the historical 0.91/0.91 compression was v0.3-era data; the
v0.4/v0.5 hardening (counterparty events, scam variants, refund math,
full-inbox triage, actor binding) resolved it. Weak collapsed 0.909 -> 0.231
while strong held. Lane is IN WINDOW; no further hardening planned
(lesson: re-measure before building — the trigger is the measurement).

### travel calibration (v0.2, seed 42, 28 tasks — 14 archetypes x 2)

| Model | Score | calls/task | tool-error rate |
|---|---|---|---|
| Qwen3-4B Q8 (weak) | 0.107 | 0.2 | 50.0% |
| Qwen3.6-27B IQ2_XXS (strong) | 0.75 | 3.6 | 2.0% |

Gap 0.64. The v0.2 hardening pulled the strong model off the ceiling
(0.95 -> 0.75) with change-fee / multi-cancel / car-choice / re-orchestration
shapes — real dethrone headroom restored. Weak floors (0.11, barely acts;
50% error when it tries) — acceptable: proves the lane is non-trivial, and
the strong clears it decisively. Lane IN WINDOW (strong slightly below the
~0.85 guide; accepting — over-tuning to hit a number is overfitting the
ruler to the calibration models).

## Domain 5: marketplace_lowmediation profile (agent-as-safety-net) — 2026-08

The marketplace machinery with LOW-mediation policy. Sources:
- **No platform fee, no buyer protection, no seller levels, no offer
  mechanism**: craigslist.org (local classifieds: free postings, "deals with
  strangers can lead to trouble", anonymous sellers, direct negotiation).
- **Payment is cash at pickup; never release before payment in hand**:
  craigslist.org/about/scams (local meet-ups, cash preferred).
- **Scam tells (all sourced)**: courier pickup + "payment already wired"
  (craigslist.org/about/scams); cashier's-check overpayment + refund the
  difference (consumer.ftc.gov/articles/how-avoid-scams-using-marketplaces);
  Google Voice verification-code request (consumer.ftc.gov articles on
  Google Voice scams); wire-only payment pressure (FTC: "that's a scam,
  every time" — avoid-scams-when-you-travel + marketplaces articles).
- **No platform mediation**: the platform does not mediate disputes or
  refunds — the agent surfaces the truth to Alex instead of filing
  nonexistent claims.

### marketplace_lowmediation calibration (v0.1, seed 42, 28 tasks — 7 archetypes x 4) + DROP decision

| Model | Score | calls/task | tool-error rate |
|---|---|---|---|
| Qwen3-4B (weak) | 0.429 | 0.6 | 11.1% |
| Qwen3.6-27B IQ2 (strong) | 0.5 | 1.1 | 9.4% |

**Verdict: DROPPED as a lane (2026-08-09).** Gap 0.071 < 0.15 (compressed) AND
strong 0.5 >= marketplace's 0.40 honest score. The archetypes are single-decision
scam-detection tasks that the weak model passes at parity — the axis is already
measured by marketplace (detection) and local_services (payment-gated release).
Retained in the repo as a documented PLATFORM profile variant (the machinery
demonstrates the profile concept; the calibration proves it is not a lane).

## Domain 6: coding (the execution-verified lane) — 2026-08

The oracle is an EXECUTABLE specification: submitted code is executed in a
restricted sandbox against a hidden test suite; pass/fail is deterministic.
Unlike consumer-policy lanes (Reg E, DOT), the source of truth is the test
contract itself, authored in the spec — execution-verified by construction.

- **Hidden-test rule**: hidden tests live ONLY in the goal predicates,
  never in the agent's world. The agent's `run_tests` tool runs only the
  visible suite, so overfitting the visible tests cannot pass the goal.
- **Sandbox**: restricted builtins allowlist (no imports/IO/network) + a
  3s timeout; unsafe code returns False without crashing the harness.
- **Mechanic sources**: the test contracts define the behavior (self-authored
  problem specs — the equivalent of the archetype samples in other lanes);
  the sandbox pattern follows the standard restricted-exec approach used by
  eval harnesses (safe-builtins exec). The lane's policy surface IS the
  executable contract.

### coding calibration (v0.1, v0.1.1, v0.2 — all floored) + PARK decision

| Version | Model | Score | calls/task | tool-error rate |
|---|---|---|---|---|
| v0.1 (no visible tests) | 4B / IQ2 | 0.0 / 0.0 | 0.5 / 6.9 | 64% / 44% |
| v0.1.1 (+visible tests) | 4B / IQ2 | 0.0 / 0.107 | 0.6 / 7.1 | 50% / 41% |
| v0.2 (minimal shapes) | 4B / IQ2 | 0.0 / 0.0 | 0.4 / 7.6 | 46% / 39% |

**Verdict: PARKED as a frontier lane (2026-08-10).** The ~39-44% tool-error
rate persists across every shape at 7+ calls/task — the binding constraint
is the INTERFACE WALL: emitting a long token-exact code string through the
tool-call JSON interface exceeds the low-precision model class (the same
exact-token ceiling as the 1-bit entity-derivation finding, in extreme
form). The lane stays in the repo, fully built/tested/emitted — the first
ruler that measures beyond the current field. A challenger that can clear
it becomes its king by construction.
