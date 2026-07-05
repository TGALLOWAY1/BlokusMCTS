"""Policy-prior approach — learn a move policy and search with it (PUCT).

Distils the MCTS visit-count corpus collected by :mod:`training.policy_selfplay`
into a compact move policy (:mod:`training.policy_learning`) and builds a champion
clone that searches with that policy as its PUCT prior and rollout/ordering policy
(``policy_prior_enabled=True`` + ``policy_weights``). This is the first candidate
pathway that changes *how the search itself is guided by learned knowledge* rather
than only re-fitting the leaf evaluator — the expert-iteration lever from
``AUDIT_REPORT.md`` §6.4.

Like the TD approach, every failure mode returns a specific reason (no corpus, too
few decisions, non-finite loss) instead of silently skipping.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Optional

from training.approaches.base import Approach, ApproachContext, Candidate

NAME = "policy"


class PolicyPriorApproach:
    name = NAME

    def __init__(self, min_samples: int = 200) -> None:
        self.min_samples = min_samples

    def generate(self, ctx: ApproachContext) -> Candidate:
        from training import policy_learning as pl
        from training.approaches.baseline_mcts import strong_baseline_params
        from training.policy_selfplay import DEFAULT_POLICY_CSV

        champ = ctx.champion_params()
        if not champ:
            return Candidate(
                name=self.name, approach="policy_prior", created=False,
                reason="policy: no champion_params in state (cold start incomplete)",
            )

        out_path = pl.DEFAULT_OUTPUT
        traj_path = Path(DEFAULT_POLICY_CSV)

        # Train fresh if we have a corpus; else reuse an existing artifact.
        trained_ok, reason, policy_dict, metrics = self._train(pl, traj_path, out_path)
        if not trained_ok and policy_dict is None:
            return Candidate(name=self.name, approach="policy_prior", created=False,
                             reason=reason, metrics=metrics)

        # Build on the corrected strong-search base, then enable the learned prior.
        cfg = strong_baseline_params(champ)
        cfg.setdefault("params", {})
        cfg["params"]["policy_prior_enabled"] = True
        cfg["params"]["policy_weights"] = policy_dict
        cfg["name"] = self.name
        return Candidate(
            name=self.name,
            approach="policy_prior",
            created=True,
            reason=(
                f"policy: distilled {metrics.get('n_samples', '?')} decisions "
                f"(loss={metrics.get('loss')}, top1={metrics.get('top1_agreement')})"
                if trained_ok else f"policy: reused existing artifact at {out_path}"
            ),
            agent_config=cfg,
            metrics={**metrics, "learning_method": "visit_count_distillation"},
        )

    def _train(self, pl, traj_path: Path, out_path: Path):
        """Train the policy -> (ok, reason, policy_dict_or_None, metrics)."""
        import json

        if not traj_path.exists():
            # No corpus: try to reuse a previously written artifact.
            if out_path.exists():
                try:
                    art = json.loads(out_path.read_text(encoding="utf-8"))
                    return False, "policy: reused artifact", art.get("policy"), {}
                except (json.JSONDecodeError, OSError):
                    pass
            return (False,
                    f"policy: no target CSV at {traj_path}; run "
                    "`python -m training.policy_selfplay` to collect visit targets first",
                    None, {})

        from mcts.move_policy import PolicyTrainConfig

        config = PolicyTrainConfig()
        result, reason, _samples = pl.train_from_file(
            traj_path, config, min_samples=self.min_samples
        )
        if result is None:
            # Fall back to an existing artifact if training could not proceed.
            if out_path.exists():
                try:
                    art = json.loads(out_path.read_text(encoding="utf-8"))
                    return False, reason, art.get("policy"), {}
                except (json.JSONDecodeError, OSError):
                    pass
            return False, reason, None, {}

        artifact = pl.build_artifact(result, config)
        pl.write_artifact(artifact, out_path)
        metrics = {
            "n_samples": result.n_samples,
            "loss": round(float(result.loss), 6),
            "top1_agreement": round(float(result.top1_agreement), 4),
        }
        return True, reason, artifact["policy"], metrics


def make(min_samples: int = 200) -> Approach:
    return PolicyPriorApproach(min_samples=min_samples)
