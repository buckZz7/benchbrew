# BenchBrew

**Spec-derived, zero-LLM agent evaluation environments — a factory that brews
fresh, deterministic, execution-verified task bundles from a public spec and a
seed. Anyone can regenerate the exact same tasks. No LLM judge anywhere.**

```
      (policy spec, public seed)
                  │
   BenchBrew ────▶ τ²-format domain ────▶ tau2 run ────▶ receipts
   (factory)        (runnable env)         (runtime)      (evidence)
                  │
                  └──▶ Pilsner arena: per-lane kings, >2% rule, leaderboard
```

## The problem

Agent evals need environments, and the 2026 generation has three failure
modes:

1. **Static and contaminable** — SWE-bench's tasks leak into training data;
   nobody can regenerate them.
2. **LLM judges in the loop** — τ²-bench ships an LLM-judged evaluator; AWM
   (ICML 2026) generates environments *and* verifiers with LLMs. A stochastic
   judge is a gaming surface and breaks comparability.
3. **Hand-authored, so they don't scale** — τ² has 4 domains because
   authoring is the bottleneck.

BenchBrew is the third corner: **the policy spec is the oracle.** Entities,
tools, rules, and task archetypes are declared in a spec; the simulator, the
tasks, and the verifier all derive from it deterministically. No LLM anywhere
in the pipeline. `(spec, seed)` → identical bundle, forever. Freshness without
secrecy; the pool is unbounded, so memorizing it is uneconomical.

## Trust properties (the audit)

- **Zero-LLM in generation, simulation, and verification** — the oracle is
  DB-state predicates (`ENV_ASSERTION` in τ² terms), never a judge.
- **Deterministic regeneration** — `(spec, seed)` → identical bundle hash;
  nothing hidden, re-runnable by anyone.
- **Grounded mechanics** — every rule traces to a real, citable policy
  (GROUNDING.md): eBay fees (13.25% + $0.30), 30-day Money Back Guarantee,
  Poshmark's 24h offer expiry, seller-level thresholds, FTC-documented scam
  patterns. Policy drift is versioned via the spec hash, never silent.
- **Storage- and runner-agnostic** — world state is plain dicts; the bundle
  runs on our zero-dependency runner OR emits a complete runnable τ² domain
  (the arena's official harness).

## The lanes (all generated from specs — new lanes are new specs, not machinery)

| Lane | What it measures | Weak (4B) | Strong (27B IQ2) | Gap |
|---|---|---|---|---|
| marketplace v0.5 | two-sided commerce: negotiate, escrow math, scam screens | 0.23 | 0.92 | 0.69 |
| local_services v0.2 | booking lifecycle: escrow release, cancellation windows, provider standing | 0.53 | 0.72 | 0.19 |
| personal_finance v0.1 | the money agent: Reg E reporting clock, budgets, subscriptions, fraud | 0.35 | 0.65 | 0.31 |
| travel v0.2 | itinerary orchestration: DOT booking clock, hotel/car windows, disruption rebook | 0.11 | 0.75 | 0.64 |
| marketplace_lowmediation v0.1 | agent-as-safety-net profile — measured, gap 0.07 (compressed), DROPPED as a lane; kept as a profile variant | 0.43 | 0.50 | 0.07 |

Every lane hits a calibration window (weak ~0.3-0.5, strong ~0.85, gap >= 0.15):
compression (weak ~= strong) is the worst failure — the ruler is blind; saturation
(strong >= 0.95) stalls the ladder. Hardening is triggered by MEASUREMENT, never
a schedule: re-calibrate on any spec change, harden worst-deviation-first.

## The spec pipeline (generic by construction)

A domain is a spec: entities, actor-bound tools, rules (the oracle, every rule
sourced in GROUNDING.md), and archetypes (sample -> world, prompt, goal
predicates). The τ² emitter (emitter_tau2.py) is SPEC-DRIVEN — it embeds the
spec module itself and generates the adapter, so ANY spec emits a runnable τ²
domain. Proven live: marketplace, local_services, personal_finance, and travel
all emit, register, and score through `tau2 run` with the spec's own goal
functions as env assertions.

Counterparty activity is deterministic world state + scripted mid-run events
(the seller counters your offer, the airline cancels the flight) — no
LLM-simulated people.

## Measured so far

Calibration (standalone runner, seed 42, live models) — full evidence in
GROUNDING.md, refreshed on every spec change:

- marketplace v0.5: **0.23 vs 0.92** (the historical 0.91/0.91 was stale v0.3 data)
- local_services v0.2: **0.53 vs 0.72**
- personal_finance v0.1: **0.35 vs 0.65**
- travel v0.2: **0.11 vs 0.75** (v0.1 was 0.25 vs 0.95 — ceiling hardening worked)

The 1-bit canary (IQ1_M ~0.3 on marketplace) is part of the calibration gate:
a lane must separate weak from strong.

**Pilsner plug-in (the integration):** the same bundle emits a complete
runnable τ² domain — registered, per-task worlds applied, oracle enforced
through τ²'s own evaluator. Receipts carry full provenance (spec sha, seed,
bundle sha) and are replay-verified through the DOMAIN THAT PRODUCED THE SIM
before the board admits them. The arena loop: fresh public seed -> emit ->
`tau2 run` -> verified receipt -> board king.

## Quick start

```bash
# generate + emit a deterministic bundle (any spec: --domain local_services,
# personal_finance, travel, marketplace_lowmediation)
python3 -m benchbrew --seed 42 --tasks 12 --domain marketplace

# run it against any OpenAI-compatible endpoint (our zero-dep runner)
BENCHBREW_BASE_URL=... BENCHBREW_MODEL=... python3 - <<'EOF'
from benchbrew.runner import OpenAIClientAgent, run_bundle, report
from domains.marketplace import MARKETPLACE
print(report(run_bundle(MARKETPLACE, OpenAIClientAgent(
    os.environ['BENCHBREW_BASE_URL'], os.environ['BENCHBREW_MODEL']),
    seed=42, n_tasks=22)))
EOF

# emit a τ²-runnable domain and run it through the arena's harness
python3 -c "from benchbrew.generator import Generator; from benchbrew.emitter_tau2 import emit_tau2_domain; from domains.marketplace import MARKETPLACE; w,t=Generator(MARKETPLACE).generate(42,16); emit_tau2_domain(MARKETPLACE,42,t,w,'/path/to/tau2-bench')"
cd /path/to/tau2-bench && tau2 run --domain marketplace --agent-llm ... 
```

37 tests, GPU-free (scripted agents prove the loop without any model).

## Freshness (the anti-memorization protocol)

A lane's task pool is regenerated per eval, not fixed. Pilsner's runner
takes a public seed (`PILSNER_BENCHBREW_SEED`), re-emits the domain bundle
from `(spec, seed)` before each battery, and records the provenance in the
receipt: spec version + hash, seed, and the bundle sha256, alongside the
sampled task ids. Anyone can run `python3 -m benchbrew --seed N --tasks M
--quiet` and regenerate the exact tasks a model was scored on — nothing
hidden, everything verifiable. Because the pool is unbounded (archetypes ×
seeds), memorizing one bundle buys nothing for the next: freshness without
secrecy.

## Adding a platform or domain

Follow the gated procedure in the `benchbrew-domain-authoring` skill: research
the real policies with sources → fill the PLATFORM profile (fees, protection
window, conditions, offer expiry, seller levels, scam patterns, mediation
level) → wire mechanics → archetypes → tests → **calibration gate** (weak
model must score below strong; a 1-bit canary must fail) → practitioner review.
`validate_spec` refuses any rule without a source. The platform spectrum
(Craigslist → FB Marketplace → OfferUp → Depop → Mercari → Vinted → Poshmark
→ eBay → Mercado Libre escrow) is one world family at different knob settings
— a new platform is a config, not new machinery.

## Why this matters for Gittensor

On-device and mixture-of-models serving need **cheap, fast, specialized
tool-calling agents** ("cogs") — and a way to know which cog to route a task
to. BenchBrew produces the rulers: execution-verified, trustless, per-lane
scores that any mixture can use as its routing table. Pilsner runs the
competition (kings, the >2% ratchet, public receipts); BenchBrew keeps the
task pool fresh so the ruler can't be memorized. The whole loop is public,
deterministic, and LLM-free.

## Repos

- **benchbrew** — this factory: spec → bundles → runners → τ² emission
- **pilsner** — the arena: ladder batteries, per-lane kings, leaderboard
  (consumes BenchBrew evals it didn't write)
