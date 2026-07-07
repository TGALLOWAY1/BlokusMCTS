"""Rich-leaf approach — deploy the full 45-feature TD value model at MCTS leaves.

The ``td`` approach projects the TD-learned rich weights down to the 8 features
the rollout-cutoff evaluator understands, discarding the 37 rich features —
including the most predictive ones (score margin, rank). This approach closes
that bottleneck: it trains the TD model **masked to the "score" leaf subset**
(so training sees exactly the feature view served at leaves), writes a
dedicated artifact, and proposes a champion clone that evaluates leaves with
the full rich model (``rich_leaf_eval_enabled``) instead of running rollouts.
Leaf evaluation costs ~1 ms vs ~10 ms per greedy-sample rollout, so at the
same iteration budget the candidate is also much faster.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path

from training.approaches.base import Approach, ApproachContext, Candidate

NAME = "rich_leaf"

# Dedicated artifact so this approach never fights the `td` approach over
# training/state/td_evaluator_weights.json (trained unmasked, for projection).
DEFAULT_ARTIFACT = "training/state/rich_leaf_weights.json"
FEATURE_SUBSET = "score"


class RichLeafApproach:
    name = NAME

    def __init__(self, min_rows_per_phase: int = 200) -> None:
        self.min_rows_per_phase = min_rows_per_phase

    def generate(self, ctx: ApproachContext) -> Candidate:
        from training import td_learning as td
        from training import trajectory_store

        out_path = ctx.repo_root / DEFAULT_ARTIFACT
        traj_path = Path(trajectory_store.DEFAULT_TRAJECTORY_CSV)

        trained_ok, reason, metrics = self._train(td, traj_path, out_path)
        if not trained_ok and not out_path.exists():
            return Candidate(name=self.name, approach="rich_leaf", created=False,
                             reason=reason, metrics=metrics)

        champ = ctx.champion_params()
        if not champ:
            return Candidate(name=self.name, approach="rich_leaf", created=False,
                             reason="rich_leaf: no champion_params in state")
        cfg = copy.deepcopy(champ)
        cfg.setdefault("params", {})
        cfg["params"]["rich_leaf_eval_enabled"] = True
        cfg["params"]["rich_leaf_weights_path"] = str(out_path)
        cfg["params"]["rich_leaf_feature_subset"] = FEATURE_SUBSET
        cfg["name"] = self.name
        return Candidate(
            name=self.name,
            approach="rich_leaf",
            created=True,
            reason=(
                f"rich_leaf: 45-feature TD leaf value (subset '{FEATURE_SUBSET}') "
                f"replacing rollouts; trained on {metrics.get('source_rows', '?')} rows"
                if trained_ok else
                f"rich_leaf: reusing existing artifact at {out_path}"
            ),
            agent_config=cfg,
            metrics={**metrics, "learning_method": "temporal_difference",
                     "feature_subset": FEATURE_SUBSET},
        )

    def _train(self, td, traj_path: Path, out_path: Path):
        if not traj_path.exists():
            return (False,
                    f"rich_leaf: no trajectory CSV at {traj_path}; run "
                    "`python -m training.td_selfplay` first",
                    {})
        config = td.TDConfig(min_rows_per_phase=self.min_rows_per_phase,
                             feature_subset=FEATURE_SUBSET)
        try:
            result, _rows = td.train_from_file(traj_path, config)
        except Exception as exc:  # noqa: BLE001 — surface the real failure
            return (False, f"rich_leaf: training raised {type(exc).__name__}: {exc}", {})

        metrics = {
            "source_rows": result.source_rows,
            "rows_by_phase": dict(result.rows_by_phase),
            "trained_phases": dict(result.trained_phases),
            "td_loss": round(float(result.td_loss), 6),
            "mean_abs_td_error": round(float(result.mean_abs_td_error), 6),
        }
        if not any(result.trained_phases.values()):
            return (False,
                    "rich_leaf: no phase reached min_rows_per_phase="
                    f"{self.min_rows_per_phase} (rows_by_phase={dict(result.rows_by_phase)})",
                    metrics)
        if not math.isfinite(result.td_loss):
            return (False, f"rich_leaf: non-finite training loss ({result.td_loss})", metrics)

        artifact = td.build_artifact(result, config)
        td.write_artifact(artifact, out_path)
        return (True, "rich_leaf: trained", metrics)


def make(min_rows_per_phase: int = 200) -> Approach:
    return RichLeafApproach(min_rows_per_phase=min_rows_per_phase)
