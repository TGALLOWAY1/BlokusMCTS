"""Heuristic-tuning approach — regression re-fit of the Layer-6 state evaluator.

Wraps the existing :func:`training.selfplay_core.build_regression_candidate`
(per-phase linear regression of accumulated self-play snapshots onto ``final_score``)
and turns its terse ``(None, None)`` failure into a specific reason: too few rows,
sklearn missing, or no snapshot CSV.
"""

from __future__ import annotations

from training.approaches.base import Approach, ApproachContext, Candidate

# Distinct from the benchmark opponent named "heuristic" so arena agent names stay
# unique. This approach re-fits the evaluator weights via regression.
NAME = "heuristic_tune"


def _why_no_refit() -> str:
    """Best-effort specific reason the regression re-fit produced nothing."""
    try:
        import pandas as pd  # noqa: F401
        from sklearn.linear_model import LinearRegression  # noqa: F401
    except ImportError:
        return "heuristic: scikit-learn/pandas not installed; cannot re-fit weights"
    from scripts.champion_loop import MIN_ROWS_FOR_REFIT, SE_FEATURE_COLS, SNAPSHOT_CSV
    if not SNAPSHOT_CSV.exists():
        return f"heuristic: no snapshot CSV at {SNAPSHOT_CSV}"
    try:
        import pandas as pd
        df = pd.read_csv(SNAPSHOT_CSV).dropna(subset=["final_score"])
    except Exception as exc:  # noqa: BLE001
        return f"heuristic: could not read snapshot CSV: {exc}"
    missing = [c for c in SE_FEATURE_COLS if c not in df.columns]
    if missing:
        return f"heuristic: snapshot CSV missing feature columns {missing}"
    if len(df) < MIN_ROWS_FOR_REFIT:
        return f"heuristic: only {len(df)} snapshot rows (need {MIN_ROWS_FOR_REFIT})"
    return "heuristic: regression re-fit returned no weights (degenerate fit)"


class HeuristicTuningApproach:
    name = NAME

    def generate(self, ctx: ApproachContext) -> Candidate:
        from training import selfplay_core as sc

        state = {"champion_params": ctx.champion_params()}
        cand_cfg, refit = sc.build_regression_candidate(state)
        if cand_cfg is None:
            return Candidate(
                name=self.name, approach="heuristic_tuning", created=False,
                reason=_why_no_refit(),
            )
        cfg = sc.strip_candidate_meta(cand_cfg)
        cfg["name"] = self.name
        rows = (refit or {}).get("rows_used")
        return Candidate(
            name=self.name,
            approach="heuristic_tuning",
            created=True,
            reason=f"heuristic: re-fit Layer-6 weights from {rows} snapshot rows",
            agent_config=cfg,
            metrics={
                "training_rows": rows,
                "r2_global": (refit or {}).get("r2_global"),
                "r2_by_phase": (refit or {}).get("r2_by_phase"),
                "learning_method": "regression",
            },
        )


def make() -> Approach:
    return HeuristicTuningApproach()
