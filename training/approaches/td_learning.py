"""TD-learning approach — temporal-difference re-fit of the state evaluator.

A first-class, *always-explained* candidate pathway. It (re)trains the TD(0) value
model from the collected trajectory corpus, writes the weights artifact, and builds a
champion clone with the TD-learned ``state_eval_phase_weights``. Every failure mode
returns a specific reason instead of silently skipping:

* no trajectory CSV (collector never ran),
* too few rows in every phase (``rows_by_phase`` < ``min_rows_per_phase``),
* non-finite training loss,
* a malformed artifact that fails candidate validation.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from training.approaches.base import Approach, ApproachContext, Candidate

NAME = "td"


class TdLearningApproach:
    name = NAME

    def __init__(self, min_rows_per_phase: int = 200) -> None:
        self.min_rows_per_phase = min_rows_per_phase

    def generate(self, ctx: ApproachContext) -> Candidate:
        from training import selfplay_core as sc
        from training import td_learning as td
        from training import trajectory_store

        out_path = Path(ctx.td_weights_path) if ctx.td_weights_path else td.DEFAULT_OUTPUT
        traj_path = Path(trajectory_store.DEFAULT_TRAJECTORY_CSV)

        # 1. Train fresh if we have a trajectory corpus; else reuse an existing artifact.
        trained_ok, train_reason, metrics = self._train(td, traj_path, out_path)
        if not trained_ok and not out_path.exists():
            return Candidate(name=self.name, approach="td_learning", created=False,
                             reason=train_reason)

        # 2. Build the candidate from the artifact (reuses the vetted loader).
        state = {"champion_params": ctx.champion_params()}
        cand_cfg, refit = sc.build_td_candidate(state, str(out_path))
        if cand_cfg is None:
            return Candidate(
                name=self.name, approach="td_learning", created=False,
                reason=(train_reason if not trained_ok
                        else f"td: artifact at {out_path} has no usable phase_weights"),
                metrics=metrics,
            )
        cfg = sc.strip_candidate_meta(cand_cfg)
        cfg["name"] = self.name
        return Candidate(
            name=self.name,
            approach="td_learning",
            created=True,
            reason=(
                f"td: trained on {metrics.get('source_rows', '?')} trajectory rows "
                f"(td_loss={metrics.get('td_loss')})"
                if trained_ok else f"td: reused existing artifact at {out_path}"
            ),
            agent_config=cfg,
            metrics={**metrics, "learning_method": "temporal_difference"},
        )

    def _train(self, td, traj_path: Path, out_path: Path):
        """Train TD model -> (ok, reason, metrics). Writes the artifact on success."""
        if not traj_path.exists():
            return (False,
                    f"td: no trajectory CSV at {traj_path}; run "
                    "`python -m training.td_selfplay` to collect trajectories first",
                    {})
        config = td.TDConfig(min_rows_per_phase=self.min_rows_per_phase)
        try:
            result, _rows = td.train_from_file(traj_path, config)
        except Exception as exc:  # noqa: BLE001 — surface the real failure
            return (False, f"td: training raised {type(exc).__name__}: {exc}", {})

        metrics = {
            "source_rows": result.source_rows,
            "rows_by_phase": dict(result.rows_by_phase),
            "trained_phases": dict(result.trained_phases),
            "td_loss": round(float(result.td_loss), 6),
            "td_loss_by_phase": {k: round(float(v), 6) for k, v in result.td_loss_by_phase.items()},
            "mean_abs_td_error": round(float(result.mean_abs_td_error), 6),
        }
        if not any(result.trained_phases.values()):
            return (False,
                    "td: no phase reached min_rows_per_phase="
                    f"{self.min_rows_per_phase} (rows_by_phase={dict(result.rows_by_phase)})",
                    metrics)
        if not math.isfinite(result.td_loss):
            return (False, f"td: non-finite training loss ({result.td_loss})", metrics)

        artifact = td.build_artifact(result, config)
        td.write_artifact(artifact, out_path)
        return (True, "td: trained", metrics)


def make(min_rows_per_phase: int = 200) -> Approach:
    return TdLearningApproach(min_rows_per_phase=min_rows_per_phase)
