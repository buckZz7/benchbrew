# BenchBrew

Spec-derived, zero-LLM agent evaluation environments. Describe a world —
the generator pours out fresh, deterministic, execution-verified task
bundles. Same `(spec, seed)` in, identical bundle out, forever.

**The trust model in one line:** public spec + public seed = anyone
regenerates the exact same tasks. Freshness without secrecy; the pool is
unbounded, so memorizing the distribution is what gets expensive.

## Why it exists

Agent evals need environments. Building them by hand doesn't scale (the
τ²-bench domains are hand-authored), and the 2026 generation pipelines
(AWM, WebArena-Infinity) author environments with LLMs — which relocates
trust into a stochastic process no one can re-run. BenchBrew is the third
corner: **the policy spec is the oracle** — entities, tools, rules, and
task archetypes — and everything (simulator, tasks, verifier) derives from
it deterministically. No LLM anywhere in the pipeline.

## v0 contents

```
benchbrew/
  spec.py       DomainSpec, World (storage-agnostic), canonical hashing
  generator.py  (spec, seed) -> baseline world + per-task worlds + tasks
  simulator.py  tool dispatch + policy rules (PolicyError on violation)
  verifier.py   valid-outcome-set predicates (DB state only, no judge)
  emitter.py    tau2-format tasks.json + checks.py + manifest.json
domains/
  marketplace.py  v1 domain: second-hand marketplace (buy/sell concierge)
tests/
  test_benchbrew.py  determinism, policy, verifier, emitter (12 tests)
```

## Use

```bash
python3 -m unittest discover -s tests -v     # 12 tests, GPU-free
python3 -m benchbrew --seed 42 --tasks 12    # generate + emit a bundle
```

The bundle (`outputs/`) is the artifact: `tasks.json` in τ²-bench schema
(`reward_basis: DB`, zero NL assertions), `checks.py` with the spec-derived
verifier predicates, `manifest.json` binding spec hash + seed + bundle hash.

## v1 domain: marketplace

The evaluated agent is the owner's personal assistant on a Poshmark-shaped
marketplace — the on-device-agent use case. Both sides:

- **sell**: list an item, accept good offers (floor-enforced), decline
  lowballs, flag scams, ship
- **buy**: negotiate within budget, avoid scam sellers

Policy rules (the oracle): owner floor, scam-actor transaction block,
buyer funds, dispute-only-after-delivery, platform auto-accept at the
listing's threshold. Counterparty activity pre-exists as deterministic
world state — no LLM-simulated people.

## Design constraints (the audit)

- Zero-LLM: no LLM in generation, simulation, or verification
- Deterministic regeneration: `(spec, seed)` -> identical bundle hash
- Execution-verified: DB-state predicates only, no judge
- Storage-agnostic world (Pydantic-style state; swappable backend)
- Rules-as-code for v0; a declarative DSL (YAML) is the next layer

## Roadmap (short)

1. Runner: execute bundles against an OpenAI-compatible endpoint (the
   arena loop — serve, run, receipt)
2. τ²-runnable evaluator module (their EnvironmentEvaluator contract)
3. Gold-trajectory emission (training data from the same oracle)
4. Declarative spec format (the "describe a world" ergonomics layer)
5. More variants: rentals, tickets, services (same spec family)
