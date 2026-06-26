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
STRONG_SEARCH_OVERRIDES: Dict[str, Any] = {
    "rollout_policy": "heuristic",      # was "random"
    "rollout_cutoff_depth": None,       # was 5 (shallow) -> full heuristic rollout
    "adaptive_rollout_depth_enabled": False,  # was True with base=5 (shallow)
    "iterations_per_ms": 1.0,           # was 0.5 (~250 iters) -> ~500 iters/move
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
        changed = {k: v for k, v in STRONG_SEARCH_OVERRIDES.items()}
        return Candidate(
            name=self.name,
            approach="baseline_mcts",
            created=True,
            reason=(
                "baseline: corrected weak-champion search settings "
                "(heuristic rollouts, no shallow cutoff, ~2x iterations)"
            ),
            agent_config=cfg,
            metrics={"overrides": changed},
        )


def make() -> Approach:
    return BaselineMctsApproach()
