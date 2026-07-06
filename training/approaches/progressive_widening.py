"""Progressive-widening approach — a genuinely-different search candidate.

Motivation
----------
The plateau diagnosis found the nightly roster had collapsed onto the champion:
``baseline`` reproduced it byte-for-byte and ``policy`` self-distilled back into the
fixed heuristic, so the only "candidate" with real degrees of freedom (evaluator
re-fit) kept regressing. To move Elo the loop needs candidates that explore *new
search behaviour*, not copies of the incumbent.

Progressive widening is a strong fit for Blokus specifically: the opening branching
factor is enormous (hundreds of legal placements), so plain UCT spreads a fixed
simulation budget thinly across many shallow children. PW instead caps a node's child
count at ``pw_c · N^pw_alpha`` and — with heuristic move ordering already on — expands
the best-ranked moves first, concentrating the budget on the moves that matter and
searching them more deeply. It is exactly the kind of high-branching-factor lever the
audit flagged (``AUDIT_REPORT.md`` §6.4) and, per the repo rules, its pre-maxⁿ-fix
verdict is invalid and must be **re-measured** — which making it a gated candidate does.

Always created (no learned data required). The evaluation gate / SPRT screen decides
whether it actually beats the champion.
"""

from __future__ import annotations

from typing import Any, Dict

from training.approaches.base import Approach, ApproachContext, Candidate
from training.approaches.baseline_mcts import strong_baseline_params

NAME = "progressive_widening"

# Widening schedule. At N visits a node exposes up to ``pw_c · N^pw_alpha`` children:
# with ~250 sims/move that is ~2·√250 ≈ 31 children at the root, a large cut from the
# hundreds of legal opening moves, so the budget deepens the best-ordered lines.
PW_C = 2.0
PW_ALPHA = 0.5


class ProgressiveWideningApproach:
    name = NAME

    def generate(self, ctx: ApproachContext) -> Candidate:
        champ = ctx.champion_params()
        if not champ:
            return Candidate(
                name=self.name, approach="progressive_widening", created=False,
                reason="progressive_widening: no champion_params in state (cold start incomplete)",
            )
        cfg = strong_baseline_params(champ)  # corrected strong search as the base
        cfg.setdefault("params", {})
        params: Dict[str, Any] = cfg["params"]
        params["progressive_widening_enabled"] = True
        params["pw_c"] = PW_C
        params["pw_alpha"] = PW_ALPHA
        cfg["name"] = self.name
        return Candidate(
            name=self.name,
            approach="progressive_widening",
            created=True,
            reason=(
                f"progressive_widening: focus search on top moves via PW "
                f"(pw_c={PW_C}, pw_alpha={PW_ALPHA}) on the corrected strong maxⁿ search "
                f"— re-measuring the layer post-maxⁿ-fix"
            ),
            agent_config=cfg,
            metrics={
                "progressive_widening_enabled": True,
                "pw_c": PW_C,
                "pw_alpha": PW_ALPHA,
                "learning_method": None,
            },
        )


def make() -> Approach:
    return ProgressiveWideningApproach()
