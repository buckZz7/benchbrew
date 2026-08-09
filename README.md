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

## The v1 domain: second-hand marketplace (buy/sell concierge)

The evaluated agent is **Alex's personal assistant on a marketplace** — the
on-device-agent use case. Both sides:

- **sell**: list items, accept offers at/above the floor, decline lowballs,
  flag scams, ship on time (or lose Top Rated)
- **buy**: negotiate within budget, avoid scam sellers, know the protection
  window

Counterparty activity is deterministic world state + scripted mid-run events
(the seller counters your offer) — no LLM-simulated people.

## Measured so far

Standalone runner (benchbrew/runner.py), 22-task bundle, seed 42, live models:

| Model | Score | calls/task | tool-error rate |
|---|---|---|---|
| Qwen3.6-27B IQ1_M (1-bit) | 0.682 (15/22) | 3.7 | 22.2% |
| Qwen3-4B Q8 | 0.909 (20/22) | 2.1 | 10.6% |
| Qwen3.6-27B IQ2_XXS (2-bit) | 0.909 (20/22) | 2.5 | 7.3% |

The ordering reproduces the Pilsner arena's known cliff: 1-bit collapses on
multi-decision orchestration (fails `sell_full_inbox` outright), 2-bit and 4B
are healthy. The multi-decision archetypes exist precisely to make the lane
discriminate — the 1-bit canary is part of the calibration gate.

**Pilsner plug-in (the integration):** the same bundle emits a complete
runnable τ² domain — registered, per-task worlds applied, oracle enforced
through τ²'s own evaluator. End-to-end receipts through the arena's real
harness (`tau2 run --domain marketplace`, live model):

```
3-task run:  Average Reward 0.667 (2/3)
8-task run:  Average Reward 0.375 (3/8), after adding get_inbox
```

The τ² path scores lower than the standalone runner (0.909) because τ²'s
LLM user-sim drives the conversation and the agent must discover its inbox
via `get_inbox` — world state, not a prompt handout. That gap is the arena's
operating point, not a harness bug: receipts are produced, scored by the
spec-derived oracle, and analyzable per task (reward + termination).

## Quick start

```bash
# generate + emit a deterministic bundle
python3 -m benchbrew --seed 42 --tasks 12

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
