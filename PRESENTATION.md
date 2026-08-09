# BenchBrew + Pilsner — one-pager for Gittensor

**One line:** a trustless, regenerable agent-eval factory (BenchBrew) feeding a
public competition arena (Pilsner) — so specialized tool-calling agents
("cogs") can be measured, ranked, and routed on execution-verified evidence,
with no LLM judge anywhere.

## The gap

Mixture-of-models serving needs small, fast, specialized tool-calling agents —
and a **trustworthy way to pick which one gets which task**. Existing evals
can't supply that:

- **Static benchmarks** (SWE-bench, τ²-bench) leak into training data and
  can't be regenerated — a memorized task pool measures nothing.
- **LLM judges** (τ²'s NL assertions, AWM's verifiers) are stochastic — a
  gaming surface, and no two runs agree.
- **Hand-authoring doesn't scale** — 4 τ² domains exist because writing them
  by hand is the bottleneck.

## The system

```
(spec, seed) ─▶ BenchBrew ─▶ τ²-format domain ─▶ tau2 run ─▶ receipts
                (factory)     (runnable env)      (runtime)    (evidence)
                                                    │
                          Pilsner arena ◀───────────┘
                          per-lane kings, >2% ratchet, public leaderboard
```

1. **BenchBrew brews the worlds.** A policy spec (entities, tools, rules,
   archetypes) plus a public seed produces fresh task bundles —
   `(spec, seed)` → identical output, forever. The oracle is DB-state
   predicates; every mechanic traces to a cited real-world policy (eBay fees,
   Poshmark offer expiry, FTC scam patterns). Zero LLM in the pipeline.
2. **τ² plays them.** The bundle emits a complete runnable τ² domain — the
   same harness the arena already uses.
3. **Pilsner keeps score.** Ladder batteries, per-lane kings, the >2% ratchet,
   public receipts.

## The v1 domain: second-hand marketplace (buy/sell concierge)

The on-device-agent use case — Alex's personal assistant running a resale
life: list, negotiate, screen scams, ship on time, know the protection
window. Both buy and sell sides.

## Evidence (live runs, seed 42, 22 tasks)

| Model | Score | tool-error rate |
|---|---|---|
| 27B IQ1_M (1-bit) | 0.682 | 22% |
| 4B Q8 | 0.909 | 11% |
| 27B IQ2_XXS (2-bit) | 0.909 | 7% |

The arena's known cliff reproduces on the new domain: 1-bit collapses on
multi-decision tasks, 2-bit is healthy — the lane discriminates, and the
1-bit canary is a permanent calibration gate (a bundle a 1-bit can cheese is
rejected). The first τ² end-to-end receipt scored by the spec-derived oracle:
**2/3 (0.667)** through the arena's real harness with a live model.

## Why it's the right substrate for a cogs economy

- **Lane leaderboards ARE routing tables.** Execution-verified per-lane scores
  tell a mixture which cog to route a task to — trustlessly.
- **Freshness without secrecy.** The pool is unbounded and public; memorizing
  it is uneconomical. The king rule (>2% beat to dethrone) runs on receipts
  anyone can regenerate.
- **The ratchet is real.** Fine-tuning a king on public generated domains is
  legitimate; the freshness layer keeps the bar honest.

## Status & ask

- BenchBrew: v0.3 — spec → generator → simulator → verifier → runner → τ²
  emission, 37 tests, all GPU-free, public on GitHub (buckZz7/benchbrew).
- Pilsner: live arena with the 5-rung compression ladder and measured
  1-bit cliff (0.62 → 0.12 across 2-bit → 1-bit).
- **Ask:** a lane in the subnet's runtime track — BenchBrew keeps the task
  pool fresh for the mixture, Pilsner runs the competition, and the
  leaderboard becomes the cogs' routing table.
