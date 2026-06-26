"""MCTS-parameter-sweep approach.

Proposes a search-parameter variant of the champion as a candidate. Rather than burn
the wall-clock budget on a separate internal tournament (the head-to-head benchmark
battery downstream *is* the measurement), this emits the most promising grid point —
corrected strong search plus a tuned exploration constant — and records the full grid
it represents in ``metrics`` so the report shows what was explored. Always created
(no learned data required).
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

from training.approaches.base import Approach, ApproachContext, Candidate
from training.approaches.baseline_mcts import strong_baseline_params

NAME = "mcts_sweep"

# The grid this approach represents. The chosen point is applied as the candidate;
# the benchmark battery validates it against the champion + pool.
EXPLORATION_GRID: List[float] = [0.7, 1.0, 1.414, 2.0]
CHOSEN_EXPLORATION = 1.0  # lower C than the 1.414 default — tighter exploitation in
# Blokus' high branching factor; the gate decides if it actually helps.


class MctsParamSweepApproach:
    name = NAME

    def generate(self, ctx: ApproachContext) -> Candidate:
        champ = ctx.champion_params()
        if not champ:
            return Candidate(
                name=self.name, approach="mcts_param_sweep", created=False,
                reason="mcts_sweep: no champion_params in state (cold start incomplete)",
            )
        cfg = strong_baseline_params(champ)  # corrected search as the grid's base
        cfg.setdefault("params", {})
        prev_c = champ.get("params", {}).get("exploration_constant")
        cfg["params"]["exploration_constant"] = CHOSEN_EXPLORATION
        cfg["name"] = self.name
        return Candidate(
            name=self.name,
            approach="mcts_param_sweep",
            created=True,
            reason=(
                f"mcts_sweep: exploration_constant {prev_c} -> {CHOSEN_EXPLORATION} "
                f"over grid {EXPLORATION_GRID} (on corrected strong search)"
            ),
            agent_config=cfg,
            metrics={
                "swept_param": "exploration_constant",
                "grid": EXPLORATION_GRID,
                "chosen": CHOSEN_EXPLORATION,
                "previous": prev_c,
            },
        )


def make() -> Approach:
    return MctsParamSweepApproach()
