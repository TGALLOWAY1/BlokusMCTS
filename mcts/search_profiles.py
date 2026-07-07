"""Named search-budget profiles: fast / balanced / strong / teacher.

Budgets in this repo are **iteration-deterministic** (an agent config carries
``deterministic_time_budget: true`` and the arena resolves the budget to a
fixed iteration count, so fixed seeds reproduce identical games). Profiles
express the budget as ``thinking_time_ms × iterations_per_ms`` with
``iterations_per_ms = 1.0``, i.e. **thinking_time_ms is the iteration count**
— the same convention the fixed benchmark anchors already use. The uniform
``--thinking-ms`` evaluation override therefore scales every profiled agent
coherently.

Measured cost (greedy_sample rollouts, cutoff 12, sampled rollout movegen):
roughly 4-10 ms per iteration early game, cheaper later.

* ``fast``     — interactive/smoke budget.
* ``balanced`` — the promoted gen140 champion's budget (250 iterations).
* ``strong``   — a stronger evaluation/play budget.
* ``teacher``  — offline training-data generation. Higher budget plus
  progressive widening: at Blokus' early-game branching factor (200-500) a
  non-widened tree spends its whole budget expanding root children once and
  never reaches depth 2, so visit-count / value targets collected below this
  budget teach almost nothing. Use for ``td_selfplay`` / ``policy_selfplay``,
  never for interactive play.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

SEARCH_PROFILES: Dict[str, Dict[str, Any]] = {
    "fast": {
        "thinking_time_ms": 100,
        "params": {"iterations_per_ms": 1.0, "deterministic_time_budget": True},
    },
    "balanced": {
        "thinking_time_ms": 250,
        "params": {"iterations_per_ms": 1.0, "deterministic_time_budget": True},
    },
    "strong": {
        "thinking_time_ms": 600,
        "params": {"iterations_per_ms": 1.0, "deterministic_time_budget": True},
    },
    "teacher": {
        "thinking_time_ms": 1200,
        "params": {
            "iterations_per_ms": 1.0,
            "deterministic_time_budget": True,
            "progressive_widening_enabled": True,
            "pw_c": 2.0,
            "pw_alpha": 0.5,
        },
    },
}


def apply_search_profile(agent_cfg: Dict[str, Any], profile: str) -> Dict[str, Any]:
    """Return a copy of an arena-style agent config with a budget profile applied.

    Only budget/widening keys are overridden; everything else (rollout policy,
    evaluator weights, exploration constant, ...) is preserved, so a profiled
    champion is still the champion — searched at a different budget.
    """
    spec = SEARCH_PROFILES.get(profile)
    if spec is None:
        raise ValueError(
            f"unknown search profile '{profile}'; expected one of {sorted(SEARCH_PROFILES)}"
        )
    cfg = copy.deepcopy(agent_cfg)
    cfg["thinking_time_ms"] = spec["thinking_time_ms"]
    params = cfg.setdefault("params", {})
    # Champion registry configs historically double-nest params.params.
    if isinstance(params.get("params"), dict):
        params = params["params"]
    params.update(spec["params"])
    return cfg
