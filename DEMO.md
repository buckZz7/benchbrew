# Demo: the full BenchBrew loop

Three paths, from cheapest to most complete. Everything is GPU-free except
path 3's live model.

## 1. Generate a deterministic bundle (no GPU, no deps)

```bash
cd benchbrew
python3 -m benchbrew --seed 42 --tasks 12
# -> outputs/tasks.json (τ²-schema), checks.py (spec-derived verifier),
#    manifest.json (spec hash + seed + bundle hash)
# prints: DETERMINISTIC sha256=... — regenerate with the same seed, same hash
```

## 2. Prove the loop with a scripted agent (no GPU, no deps, no model)

```bash
python3 -m unittest discover -s tests -v   # 37 tests, ~0.1s
```

Scripted agents play correct and wrong trajectories through the simulator;
the verifier must agree. This is how the harness is validated without any LLM.

## 3. Run a live model through the arena's harness (needs an endpoint)

```bash
# a) emit the τ²-runnable domain
python3 -c "
from benchbrew.generator import Generator
from benchbrew.emitter_tau2 import emit_tau2_domain
from domains.marketplace import MARKETPLACE
w, t = Generator(MARKETPLACE).generate(42, 16)
emit_tau2_domain(MARKETPLACE, 42, t, w, '/path/to/tau2-bench')
"

# b) run it with the arena's official CLI (any OpenAI-compatible endpoint)
cd /path/to/tau2-bench
OPENAI_API_KEY=sk-dummy uv run tau2 run \
  --domain marketplace \
  --agent-llm openai/<model> \
  --agent-llm-args '{"api_base": "http://<host>:<port>/v1", "temperature": 0.0}' \
  --user-llm openai/<model> \
  --user-llm-args '{"api_base": "http://<host>:<port>/v1", "temperature": 0.0}' \
  --num-trials 1 --num-tasks 16 --task-split-name base --max-steps 25
```

The receipt scores tasks with the spec-derived oracle (`ENV_ASSERTION`),
reported per task with reward + termination reason.

## Or the zero-dep runner (same bundle, our own harness)

```bash
BENCHBREW_BASE_URL=http://<host>:<port>/v1 BENCHBREW_MODEL=<model> python3 - <<'EOF'
import json, os
from benchbrew.runner import OpenAIClientAgent, run_bundle, report
from domains.marketplace import MARKETPLACE
rep = report(run_bundle(MARKETPLACE, OpenAIClientAgent(
    os.environ['BENCHBREW_BASE_URL'], os.environ['BENCHBREW_MODEL']),
    seed=42, n_tasks=22))
print(json.dumps(rep, indent=2))
EOF
```
