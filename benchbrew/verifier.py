"""Verifier: valid-outcome-set predicates.

Zero-LLM by construction (the audit): a task passes iff its DB-state
predicates hold on the final world. No judge, no natural-language assertions.
"""
from __future__ import annotations

from typing import Callable

from .spec import World


def check(task: dict, world: World) -> tuple[bool, list[str]]:
    goal: Callable[[World, dict], tuple[bool, list[str]]] = task["goal"]
    return goal(world, task["ctx"])
