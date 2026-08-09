"""BenchBrew CLI: python -m benchbrew --seed 42 --tasks 12 [--out outputs]

Generate a deterministic task bundle from the marketplace spec, verify
determinism (regenerate + hash compare), and emit the tau2-format bundle.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from benchbrew.generator import Generator
from benchbrew.spec import bundle_hash

REPO = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    seed = 42
    n_tasks = 12
    out_dir = "outputs"
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--seed":
            seed = int(args[i + 1]); i += 2
        elif a == "--tasks":
            n_tasks = int(args[i + 1]); i += 2
        elif a == "--out":
            out_dir = args[i + 1]; i += 2
        else:
            print(f"unknown arg: {a}"); return 2

    sys.path.insert(0, str(REPO))
    from domains.marketplace import MARKETPLACE

    from benchbrew.spec import validate_spec
    problems = validate_spec(MARKETPLACE)
    if problems:
        print("SPEC INVALID — refusing to emit:")
        for p in problems:
            print(f"  - {p}")
        return 3

    gen = Generator(MARKETPLACE)
    world, tasks = gen.generate(seed, n_tasks)
    h1 = bundle_hash(MARKETPLACE, seed, _stripped(tasks))

    # determinism check: regenerate and compare hashes
    _, tasks2 = gen.generate(seed, n_tasks)
    h2 = bundle_hash(MARKETPLACE, seed, _stripped(tasks2))
    det = "DETERMINISTIC" if h1 == h2 else "NON-DETERMINISTIC (BUG)"

    from benchbrew.emitter import emit
    out = emit(MARKETPLACE, seed, tasks, world, out_dir)

    print(f"domain:     {MARKETPLACE.name} v{MARKETPLACE.version}")
    print(f"spec hash:  {MARKETPLACE.spec_hash()}")
    print(f"seed:       {seed}  tasks: {n_tasks}")
    print(f"bundles:    {det}  sha256={h1[:16]}")
    print(f"emitted:    {out}/tasks.json, checks.py, manifest.json")
    print()
    by_role: dict[str, int] = {}
    for t in tasks:
        by_role[t["role"]] = by_role.get(t["role"], 0) + 1
    print("roles:", ", ".join(f"{k}={v}" for k, v in sorted(by_role.items())))
    print()
    for t in tasks:
        print(f"  [{t['id']}] {t['archetype']:<22} {t['role']:<5} {t['goal_desc'](t['ctx'])}")
    return 0


def _stripped(tasks: list[dict]) -> list[dict]:
    from benchbrew.spec import canonical_tasks
    return canonical_tasks(tasks)


if __name__ == "__main__":
    raise SystemExit(main())
