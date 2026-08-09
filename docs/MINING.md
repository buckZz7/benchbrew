# Mining BenchBrew

Welcome. BenchBrew is a spec-driven agent-eval factory: a public spec (the
marketplace domain) generates fresh, deterministic, LLM-free evaluation
bundles. Your PRs improve the factory. No servers, no API keys — just
GitHub PRs, scored on merged, source-code-bearing work.

## How scoring works here (the realities)

- Validators score **merged PRs** via AST token analysis. **Source code is the
  weight; docs and tests are light (0.05x).** Write real code.
- You need ≥3 merged PRs and ≥80% credibility (merged/(merged+closed)) in
  this repo before earning — so pick small, scoped issues and read the
  acceptance criteria carefully. Rejections are rare if you follow them.
- Maintainer PRs don't earn. Issues are seeded small on purpose — one issue,
  one PR.

## What's worth mining

The factory lives in `benchbrew/` (engine) and `domains/marketplace.py`
(the spec: entities, tools, rules-as-code, archetypes). High-value work:

1. **New archetypes** — task shapes that test agent behavior the current
   set misses (e.g. multi-round negotiation, bundled orders, partial
   fulfillment). Each archetype needs `sample/prompt/inbox/goal` + a
   scripted-agent test, and must pass the calibration gate (weak model
   scores below strong; a 1-bit canary must fail it).
2. **Platform profiles** — the marketplace family is one spec at different
   knob settings (GROUNDING.md). A Depop/Vinted/FB-Marketplace profile is a
   config + mechanics, not new machinery. Every rule needs a cited source.
3. **Tool & oracle coverage** — more tools, more assertion predicates,
   deeper edge cases (scam variants, window edges, fee math). Every tool
   needs a description; every rule needs a `rule_sources` entry
   (`validate_spec` refuses unsourced rules).
4. **The τ² emitter** — `benchbrew/emitter_tau2.py` generates the runnable
   τ² domain package; improvements here make the arena integration better.

## Getting started

```bash
git clone https://github.com/buckZz7/benchbrew
cd benchbrew
python3 -m unittest discover -s tests -v   # 37 tests, GPU-free, zero deps
python3 -m benchbrew --seed 42 --tasks 12  # generate a deterministic bundle
```

Then read `GROUNDING.md` (every mechanic must trace to a real source) and
pick a seeded issue. CI runs the tests + spec gate on every PR.

## Quality bar (the audit)

- Zero LLM in the pipeline — no LLM judges, no LLM-generated tasks.
- Deterministic: `(spec, seed)` → identical bundle hash.
- Grounded: every rule carries a source URL.
- Calibrated: the bundle must separate a weak model from a strong one.

If a PR adds a mechanic without a source, or an archetype without a test, it
will not merge. That's the point.
