"""Simulator: tool dispatch + policy enforcement.

Every write tool call passes through every rule first; a violation raises
PolicyError and the call never executes. This is where the spec's policy
becomes the oracle: valid outcomes are exactly those reachable without a
policy violation, and the verifier checks the resulting state.
"""
from __future__ import annotations

from .spec import DomainSpec, PolicyError, World


class Simulator:
    def __init__(self, spec: DomainSpec):
        self.spec = spec

    def execute(self, world: World, tool: str, args: dict, ctx: dict | None = None) -> dict:
        ctx = ctx or {}
        if tool not in self.spec.tool_impls:
            raise ValueError(f"unknown tool: {tool}")
        ts = self.spec.tools[tool]
        missing = [
            p for p in ts.params
            if p not in args and not _optional(ts.params[p])
        ]
        if missing:
            raise ValueError(f"{tool}: missing params {sorted(missing)}")
        unknown = [k for k in args if k not in ts.params]
        if unknown:
            # actor binding: reject undeclared args (e.g. spoofed user ids)
            raise ValueError(f"{tool}: unknown params {sorted(unknown)}")
        # policy first
        for rule in self.spec.rules.values():
            rule(world, tool, args, ctx)
        return self.spec.tool_impls[tool](world, args, ctx)


def _optional(t: type) -> bool:
    """True when the declared type admits None (None-able params are optional)."""
    if t is type(None):
        return True
    args = getattr(t, "__args__", None)
    return bool(args) and type(None) in args
