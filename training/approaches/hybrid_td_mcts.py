"""Hybrid approach — corrected strong MCTS search + TD-learned evaluator weights.

Combines the two highest-leverage fixes into one candidate: the strong-search settings
from :mod:`training.approaches.baseline_mcts` (heuristic rollouts, more iterations) and
the TD-learned ``state_eval_phase_weights`` from a TD artifact. Created only when a
usable TD artifact exists (train it first via the ``td`` approach or
``python -m training.td_learning``); otherwise returns a specific reason.
"""

from __future__ import annotations

from pathlib import Path

from training.approaches.base import Approach, ApproachContext, Candidate
from training.approaches.baseline_mcts import strong_baseline_params

NAME = "hybrid"


class HybridTdMctsApproach:
    name = NAME

    def generate(self, ctx: ApproachContext) -> Candidate:
        from training import selfplay_core as sc
        from training import td_learning as td

        champ = ctx.champion_params()
        if not champ:
            return Candidate(
                name=self.name, approach="hybrid_td_mcts", created=False,
                reason="hybrid: no champion_params in state (cold start incomplete)",
            )

        out_path = Path(ctx.td_weights_path) if ctx.td_weights_path else td.DEFAULT_OUTPUT
        if not out_path.exists():
            return Candidate(
                name=self.name, approach="hybrid_td_mcts", created=False,
                reason=(f"hybrid: no TD weights artifact at {out_path}; run the 'td' "
                        "approach or `python -m training.td_learning` first"),
            )

        # Strong search as the base, then graft the TD-learned evaluator weights.
        strong = strong_baseline_params(champ)
        cand_cfg, _refit = sc.build_td_candidate({"champion_params": strong}, str(out_path))
        if cand_cfg is None:
            return Candidate(
                name=self.name, approach="hybrid_td_mcts", created=False,
                reason=f"hybrid: TD artifact at {out_path} has no usable phase_weights",
            )
        cfg = sc.strip_candidate_meta(cand_cfg)
        cfg["name"] = self.name
        return Candidate(
            name=self.name,
            approach="hybrid_td_mcts",
            created=True,
            reason="hybrid: corrected strong search + TD-learned evaluator weights",
            agent_config=cfg,
            metrics={"learning_method": "hybrid_td+strong_search",
                     "td_weights_path": str(out_path)},
        )


def make() -> Approach:
    return HybridTdMctsApproach()
