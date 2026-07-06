"""Baseline-MCTS approach — a *stronger search seed* the champion can be replaced by.

The audited champion is a near-crippled MCTS (``rollout_policy="random"``,
``rollout_cutoff_depth=5``, ~250 iterations/move) that loses to the plain heuristic
agent. This approach proposes the same agent with corrected, well-understood search
settings — heuristic rollouts, no shallow cutoff, more iterations — so the base agent
can clear the sub-heuristic floor if it wins the gate. It needs no learned data, so it
is always created.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

from training.approaches.base import Approach, ApproachContext, Candidate

NAME = "baseline"

# Corrected, conventional strong-MCTS search settings (override the weak champion).
# "greedy_sample" scores a K-move random sample with the fast move heuristic each
# rollout step: near-heuristic move quality at ~1/8th the cost of full-heuristic
# rollouts (which score every legal move every step and starve the eval budget).
STRONG_SEARCH_OVERRIDES: Dict[str, Any] = {
    "rollout_policy": "greedy_sample",  # was "random"
    "rollout_cutoff_depth": 12,         # was 5 (too shallow to see tactics)
    "adaptive_rollout_depth_enabled": False,  # was True with base=5 (shallow)
    "iterations_per_ms": 0.5,           # unchanged budget: strength from search quality
    "rave_enabled": False,              # RAVE stats were corrupted pre-maxⁿ fix; retest later
    "minimax_backup_alpha": 0.0,        # plain UCT averaging on the fixed maxⁿ backups
    "heuristic_move_ordering": True,    # expand strong moves first
    "num_workers": 1,                   # single-process: deterministic, no fork overhead
}


def strong_baseline_params(champion_params: Dict[str, Any]) -> Dict[str, Any]:
    """Return champion params with the strong-search overrides applied."""
    cfg = copy.deepcopy(champion_params)
    cfg.setdefault("params", {})
    for k, v in STRONG_SEARCH_OVERRIDES.items():
        cfg["params"][k] = v
    return cfg


class BaselineMctsApproach:
    name = NAME

    def generate(self, ctx: ApproachContext) -> Candidate:
        champ = ctx.champion_params()
        if not champ:
            return Candidate(
                name=self.name, approach="baseline_mcts", created=False,
                reason="baseline: no champion_params in state (cold start incomplete)",
            )
        cfg = strong_baseline_params(champ)
        cfg["name"] = self.name
        # Self-retire when this is a no-op. Once a strong-baseline agent has been
        # promoted (as gen140 was), applying the SAME overrides reproduces the champion
        # byte-for-byte, so the "candidate" is the champion playing itself: it can never
        # strictly beat the champion and only burns evaluation budget. Skip with a
        # specific reason. If a future champion ever drifts away from these settings,
        # this approach automatically becomes a genuine control again.
        if (champ.get("params") or {}) == (cfg.get("params") or {}):
            return Candidate(
                name=self.name, approach="baseline_mcts", created=False,
                reason=("baseline: identical to the current champion (strong-search "
                        "settings already promoted) — nothing to test, skipping"),
                metrics={"identical_to_champion": True},
            )
        changed = {k: v for k, v in STRONG_SEARCH_OVERRIDES.items()
                   if (champ.get("params") or {}).get(k) != v}
        return Candidate(
            name=self.name,
            approach="baseline_mcts",
            created=True,
            reason=(
                "baseline: corrected weak-champion search settings "
                "(greedy-sample rollouts, cutoff 12, RAVE/minimax off, move ordering on)"
            ),
            agent_config=cfg,
            metrics={"overrides": changed},
        )


def make() -> Approach:
    return BaselineMctsApproach()
