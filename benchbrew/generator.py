"""Generator: (spec, seed) -> baseline world + N task instances.

Deterministic by construction: every random choice flows from a single
`random.Random(seed)`. Same seed -> identical world, identical tasks,
identical bundle hash. Public seed = anyone regenerates (the trust model).
"""
from __future__ import annotations

import random

from .spec import DomainSpec, World


class Generator:
    def __init__(self, spec: DomainSpec):
        self.spec = spec

    def generate(self, seed: int, n_tasks: int = 10) -> tuple[World, list[dict]]:
        rng = random.Random(seed)
        baseline = World()
        if self.spec.seed_world:
            self.spec.seed_world(baseline, rng)

        tasks: list[dict] = []
        archetype_names = sorted(self.spec.archetypes)
        for i in range(n_tasks):
            a_name = archetype_names[i % len(archetype_names)]
            arch = self.spec.archetypes[a_name]
            # per-task world: baseline clone, then the archetype pre-seeds its
            # entities (listings, offers, messages) into THIS task's world only
            world = baseline.clone()
            ctx = arch["sample"](rng, world, i)
            task = {
                "id": str(i),
                "archetype": a_name,
                "role": arch["role"],
                "ctx": ctx,
                "prompt": arch["prompt"](ctx),
                "inbox": arch["inbox"](rng, ctx, world),
                "initial_world": world,
                # goal is a function reference; serialized form emitted separately
                "goal": arch["goal"],
                "goal_desc": arch.get("goal_desc", lambda ctx: "complete the task"),
            }
            tasks.append(task)
        return baseline, tasks
