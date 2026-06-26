"""Temporal-difference learning for the Blokus state evaluator.

This is the learning core that replaces (optionally; regression remains the
default fallback) the fixed-ply linear-regression refit. Instead of regressing
isolated snapshots onto ``final_score``, it learns a linear value model
``V(s) = w·f(s) + b`` from *trajectories* using TD(0):

    target = reward_t + γ · V(s_{t+1})          (non-terminal)
    target = terminal_value                      (terminal)
    error  = clip(target − V(s_t))
    w     += α · (error · f(s_t)) − α · l2 · w
    b     += α · error

Weights are learned **per phase** (early / mid / late) independently, over the
rich ``rich_blokus_v1`` feature space. Because the live agent's
:class:`BlokusStateEvaluator` only consumes the eight Layer-6 features (the rich
features are far too slow for per-rollout evaluation), the learned weights are
*projected* onto those eight names and rescaled exactly like the regression path
(``WEIGHT_SCALE``) to produce an agent-compatible ``state_eval_phase_weights``.
The full rich weight vectors are also persisted for transparency / future use.

CLI::

    python -m training.td_learning \
        --input data/td_trajectories.csv \
        --output training/state/td_evaluator_weights.json
"""

from __future__ import annotations

import argparse
import json
import random as _random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from mcts.state_evaluator import (
    DEFAULT_WEIGHTS,
    FEATURE_NAMES as SE_FEATURE_NAMES,
    PHASE_EARLY_THRESHOLD,
    PHASE_LATE_THRESHOLD,
)
from training import REPO_ROOT
from training.rich_features import FEATURE_SET_VERSION, RICH_FEATURE_NAMES
from training import trajectory_store

DEFAULT_OUTPUT = REPO_ROOT / "training" / "state" / "td_evaluator_weights.json"
WEIGHT_SCALE = 0.30  # matches scripts.champion_loop.WEIGHT_SCALE for agent weights

PHASES = ("early", "mid", "late")

# Rank → normalised value (configurable via TDConfig.rank_value_map).
DEFAULT_RANK_VALUE_MAP: Dict[int, float] = {1: 1.0, 2: 0.5, 3: -0.25, 4: -1.0}

# Final-score normalisation centre/spread (configurable via TDConfig).
#
# These default to values calibrated from the observed terminal-score distribution
# in ``data/td_trajectories.csv`` rather than the original hardcoded ``(40, 20)``.
# The old centre of 40 sat far below the real mean final score (~82, median 83),
# so ``tanh((score-40)/20)`` saturated: ~75% of terminal rows mapped to |v|>0.9
# and the score component of the terminal value collapsed to ≈+1, carrying almost
# no signal. Centring on the empirical mean with the empirical spread (~19) keeps
# the score component informative across the rank-1..rank-4 range. See
# ``tasks/TODO.md`` ("Calibrate label normalisation") and ``docs/TD_AUDIT.md`` §3.
DEFAULT_SCORE_CENTER: float = 82.0
DEFAULT_SCORE_SPREAD: float = 19.0


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class TDConfig:
    """Hyper-parameters for one TD training run."""

    gamma: float = 0.98
    alpha: float = 0.01
    epochs: int = 10
    l2: float = 0.001
    clip_td_error: Tuple[float, float] = (-2.0, 2.0)
    min_rows_per_phase: int = 200
    blend_rank_weight: float = 0.50
    blend_score_weight: float = 0.30
    blend_margin_weight: float = 0.20
    rank_value_map: Dict[int, float] = field(default_factory=lambda: dict(DEFAULT_RANK_VALUE_MAP))
    score_center: float = DEFAULT_SCORE_CENTER
    score_spread: float = DEFAULT_SCORE_SPREAD
    seed: int = 12345

    def normalized_blend(self) -> Tuple[float, float, float]:
        total = self.blend_rank_weight + self.blend_score_weight + self.blend_margin_weight
        if total <= 0:
            return (0.5, 0.3, 0.2)
        return (
            self.blend_rank_weight / total,
            self.blend_score_weight / total,
            self.blend_margin_weight / total,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gamma": self.gamma,
            "alpha": self.alpha,
            "epochs": self.epochs,
            "l2": self.l2,
            "clip_td_error": list(self.clip_td_error),
            "min_rows_per_phase": self.min_rows_per_phase,
            "blend_rank_weight": self.blend_rank_weight,
            "blend_score_weight": self.blend_score_weight,
            "blend_margin_weight": self.blend_margin_weight,
            "rank_value_map": {str(k): v for k, v in self.rank_value_map.items()},
            "score_center": self.score_center,
            "score_spread": self.score_spread,
            "seed": self.seed,
        }


# ---------------------------------------------------------------------------
# Outcome labels / terminal value
# ---------------------------------------------------------------------------


def normalized_rank_value(rank: int, rank_map: Optional[Dict[int, float]] = None) -> float:
    rank_map = rank_map or DEFAULT_RANK_VALUE_MAP
    return float(rank_map.get(int(rank), -1.0))


def normalized_final_score(
    score: float,
    center: float = DEFAULT_SCORE_CENTER,
    spread: float = DEFAULT_SCORE_SPREAD,
) -> float:
    """Map a raw final score (~0..89 squares) onto [-1, 1].

    ``center``/``spread`` default to the empirically calibrated values (see
    :data:`DEFAULT_SCORE_CENTER`). Pass the original ``(40, 20)`` to reproduce the
    pre-calibration behaviour.
    """
    spread = spread if spread > 1e-6 else 1.0
    return float(np.tanh((float(score) - float(center)) / float(spread)))


def normalized_score_margin(margin_to_next: float) -> float:
    """Signed closeness to the adjacent better player (or lead if winning)."""
    return float(np.tanh(float(margin_to_next) / 20.0))


def terminal_value(row: Dict[str, Any], config: TDConfig) -> float:
    """Blended terminal value in roughly [-1, 1] from a trajectory row's labels."""
    w_rank, w_score, w_margin = config.normalized_blend()
    rv = normalized_rank_value(int(row.get("final_rank", 4)), config.rank_value_map)
    sv = normalized_final_score(
        float(row.get("final_score", 0)), config.score_center, config.score_spread
    )
    mv = normalized_score_margin(float(row.get("score_margin_to_next", 0.0)))
    return float(w_rank * rv + w_score * sv + w_margin * mv)


# ---------------------------------------------------------------------------
# Linear value model
# ---------------------------------------------------------------------------


@dataclass
class PhaseModel:
    """Per-phase linear value model over the rich feature space."""

    weights: np.ndarray  # shape (n_features,)
    bias: float = 0.0

    def value(self, x: np.ndarray) -> float:
        return float(np.dot(self.weights, x) + self.bias)


def _initial_weights() -> np.ndarray:
    """Initialise rich weights: SE-feature slots seeded from DEFAULT_WEIGHTS, rest 0.

    This gives projection-to-agent a sane prior even for under-trained phases and
    speeds convergence on the eight features the agent ultimately consumes.
    """
    w = np.zeros(len(RICH_FEATURE_NAMES), dtype=float)
    index = {name: i for i, name in enumerate(RICH_FEATURE_NAMES)}
    for name, val in DEFAULT_WEIGHTS.items():
        if name in index:
            w[index[name]] = float(val)
    return w


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


@dataclass
class TDResult:
    phase_models: Dict[str, PhaseModel]
    trained_phases: Dict[str, bool]
    rows_by_phase: Dict[str, int]
    td_loss: float
    td_loss_by_phase: Dict[str, float]
    mean_abs_td_error: float
    source_rows: int
    # Layer-4 diagnostics (defaults keep older callers / tests working).
    target_variance: float = 0.0
    prediction_variance: float = 0.0
    target_variance_by_phase: Dict[str, float] = field(default_factory=dict)
    prediction_variance_by_phase: Dict[str, float] = field(default_factory=dict)
    feature_variance: Dict[str, float] = field(default_factory=dict)

    def diagnostics(self) -> Dict[str, Any]:
        """Compact training-metrics bundle for the learning-diagnostics store."""
        return {
            "td_loss": self.td_loss,
            "td_loss_by_phase": dict(self.td_loss_by_phase),
            "mean_abs_td_error": self.mean_abs_td_error,
            "rows_by_phase": dict(self.rows_by_phase),
            "target_variance": self.target_variance,
            "prediction_variance": self.prediction_variance,
            "target_variance_by_phase": dict(self.target_variance_by_phase),
            "prediction_variance_by_phase": dict(self.prediction_variance_by_phase),
        }


def _row_phase(row: Dict[str, Any]) -> str:
    occ = float(row.get("board_occupancy", 0.0))
    if occ < PHASE_EARLY_THRESHOLD:
        return "early"
    if occ < PHASE_LATE_THRESHOLD:
        return "mid"
    return "late"


def _row_next_phase(row: Dict[str, Any], cur_phase: str) -> str:
    """Phase of the bootstrap target s_{t+1}.

    Prefers the explicit ``next_phase`` column (written by the collector / filled
    in by :func:`training.trajectory_store.annotate_next_phase`). Falls back to the
    current phase when absent — reproducing the pre-fix single-phase behaviour for
    legacy rows that were never annotated.
    """
    nxt = str(row.get("next_phase") or "").strip()
    return nxt if nxt in PHASES else cur_phase


@dataclass
class _Sample:
    """One pre-extracted TD transition ready for the update loop."""

    cur_phase: str
    next_phase: str
    s: np.ndarray
    s_next: np.ndarray
    terminal: bool
    tv: float


def train_td(rows: List[Dict[str, Any]], config: TDConfig) -> TDResult:
    """Run TD(0) training over loaded trajectory rows. Pure (no I/O).

    **Phase-correct bootstrapping.** Each transition's TD target is
    ``γ · V(s_{t+1})`` evaluated with the *next* state's phase model, which may
    differ from the current state's phase model when the transition crosses a
    phase boundary. All three phase models are therefore held simultaneously and
    updated in an interleaved loop (a phase with insufficient rows keeps its prior
    weights but can still serve as a bootstrap target for its neighbours).
    """
    rng = _random.Random(config.seed)
    lo, hi = config.clip_td_error

    # Pre-extract every transition, tagged with current + next phase.
    samples_by_phase: Dict[str, List[_Sample]] = {p: [] for p in PHASES}
    for row in rows:
        cur_phase = _row_phase(row)
        nxt_phase = _row_next_phase(row, cur_phase)
        s = np.asarray(trajectory_store.state_vector(row), dtype=float)
        s_next = np.asarray(trajectory_store.next_state_vector(row), dtype=float)
        terminal = bool(int(row.get("terminal", 0)))
        tv = terminal_value(row, config) if terminal else 0.0
        samples_by_phase[cur_phase].append(
            _Sample(cur_phase, nxt_phase, s, s_next, terminal, tv)
        )

    rows_by_phase = {p: len(samples_by_phase[p]) for p in PHASES}
    trained = {p: rows_by_phase[p] >= config.min_rows_per_phase for p in PHASES}

    # Initialise ALL phase models up front so cross-phase bootstrap targets always
    # have a model to query (prior weights for under-trained phases).
    phase_models: Dict[str, PhaseModel] = {
        p: PhaseModel(weights=_initial_weights(), bias=0.0) for p in PHASES
    }

    # Global training pool: only transitions whose *current* phase is trainable get
    # their model updated; their bootstrap may still read an under-trained model.
    train_pool: List[_Sample] = [
        smp for p in PHASES if trained[p] for smp in samples_by_phase[p]
    ]

    def _target(smp: _Sample) -> float:
        if smp.terminal:
            return smp.tv
        return config.gamma * phase_models[smp.next_phase].value(smp.s_next)

    for _epoch in range(config.epochs):
        order = list(range(len(train_pool)))
        rng.shuffle(order)
        for idx in order:
            smp = train_pool[idx]
            model = phase_models[smp.cur_phase]
            v_s = model.value(smp.s)
            error = _target(smp) - v_s
            if error < lo:
                error = lo
            elif error > hi:
                error = hi
            # Semi-gradient TD update with L2 on weights only.
            model.weights += config.alpha * (error * smp.s) - config.alpha * config.l2 * model.weights
            model.bias += config.alpha * error

    # Per-phase final-pass metrics (using the phase-correct bootstrap).
    loss_by_phase: Dict[str, float] = {}
    all_abs_errors: List[float] = []
    all_sq_errors: List[float] = []
    all_targets: List[float] = []
    all_preds: List[float] = []
    target_var_by_phase: Dict[str, float] = {}
    pred_var_by_phase: Dict[str, float] = {}
    for phase in PHASES:
        samples = samples_by_phase[phase]
        if not trained[phase] or not samples:
            loss_by_phase[phase] = 0.0
            target_var_by_phase[phase] = 0.0
            pred_var_by_phase[phase] = 0.0
            continue
        sq = 0.0
        targets: List[float] = []
        preds: List[float] = []
        for smp in samples:
            pred = phase_models[phase].value(smp.s)
            tgt = _target(smp)
            err = tgt - pred
            sq += err * err
            all_sq_errors.append(err * err)
            all_abs_errors.append(abs(err))
            targets.append(tgt)
            preds.append(pred)
        loss_by_phase[phase] = sq / max(len(samples), 1)
        target_var_by_phase[phase] = float(np.var(targets))
        pred_var_by_phase[phase] = float(np.var(preds))
        all_targets.extend(targets)
        all_preds.extend(preds)

    td_loss = float(np.mean(all_sq_errors)) if all_sq_errors else 0.0
    mean_abs = float(np.mean(all_abs_errors)) if all_abs_errors else 0.0

    # Per-feature variance over the *current-state* vectors of all training rows —
    # near-zero variance means a feature carries no learnable signal in this corpus.
    feature_variance: Dict[str, float] = {}
    if train_pool:
        mat = np.vstack([smp.s for smp in train_pool])
        var = np.var(mat, axis=0)
        feature_variance = {name: float(var[i]) for i, name in enumerate(RICH_FEATURE_NAMES)}

    return TDResult(
        phase_models=phase_models,
        trained_phases=trained,
        rows_by_phase=rows_by_phase,
        td_loss=td_loss,
        td_loss_by_phase=loss_by_phase,
        mean_abs_td_error=mean_abs,
        source_rows=len(rows),
        target_variance=float(np.var(all_targets)) if all_targets else 0.0,
        prediction_variance=float(np.var(all_preds)) if all_preds else 0.0,
        target_variance_by_phase=target_var_by_phase,
        prediction_variance_by_phase=pred_var_by_phase,
        feature_variance=feature_variance,
    )


# ---------------------------------------------------------------------------
# Projection onto the agent's 8 evaluator features
# ---------------------------------------------------------------------------


def project_to_agent_weights(
    model: PhaseModel,
    *,
    trained: bool,
    scale: float = WEIGHT_SCALE,
) -> Dict[str, float]:
    """Project a rich PhaseModel onto the eight SE features, rescaled like regression.

    For an untrained phase (insufficient rows) we fall back to ``DEFAULT_WEIGHTS``
    so the agent keeps sane behaviour rather than receiving degenerate weights.
    """
    if not trained:
        return dict(DEFAULT_WEIGHTS)
    index = {name: i for i, name in enumerate(RICH_FEATURE_NAMES)}
    raw = {name: float(model.weights[index[name]]) for name in SE_FEATURE_NAMES}
    max_abs = max((abs(v) for v in raw.values()), default=0.0)
    if max_abs <= 0:
        return dict(DEFAULT_WEIGHTS)
    factor = scale / max_abs
    return {name: float(v * factor) for name, v in raw.items()}


def build_phase_weights(result: TDResult, scale: float = WEIGHT_SCALE) -> Dict[str, Dict[str, float]]:
    """Build the agent-compatible ``state_eval_phase_weights`` dict."""
    return {
        phase: project_to_agent_weights(
            result.phase_models[phase], trained=result.trained_phases[phase], scale=scale
        )
        for phase in PHASES
    }


# ---------------------------------------------------------------------------
# Artifact
# ---------------------------------------------------------------------------


def build_artifact(result: TDResult, config: TDConfig) -> Dict[str, Any]:
    """Assemble the serialisable TD weights artifact."""
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "learning_method": "temporal_difference",
        "feature_set_version": FEATURE_SET_VERSION,
        "source_rows": result.source_rows,
        "feature_names": list(RICH_FEATURE_NAMES),
        "phase_weights": build_phase_weights(result),
        "rich_phase_weights": {
            phase: {
                "weights": {n: float(w) for n, w in zip(RICH_FEATURE_NAMES, result.phase_models[phase].weights)},
                "bias": float(result.phase_models[phase].bias),
                "trained": bool(result.trained_phases[phase]),
            }
            for phase in PHASES
        },
        "training_metrics": {
            "td_loss": result.td_loss,
            "td_loss_by_phase": result.td_loss_by_phase,
            "mean_abs_td_error": result.mean_abs_td_error,
            "rows_by_phase": result.rows_by_phase,
            "target_variance": result.target_variance,
            "prediction_variance": result.prediction_variance,
            "target_variance_by_phase": result.target_variance_by_phase,
            "prediction_variance_by_phase": result.prediction_variance_by_phase,
        },
        "config": config.to_dict(),
    }


def write_artifact(artifact: Dict[str, Any], output: Path | str = DEFAULT_OUTPUT) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2)
    return output


def train_from_file(
    input_path: Path | str,
    config: TDConfig,
) -> Tuple[TDResult, List[Dict[str, Any]]]:
    """Load trajectories and train. Returns ``(result, rows)``."""
    rows = trajectory_store.load_trajectories(input_path)
    rows = trajectory_store.sort_trajectories(rows)
    # Fill in next_phase for any rows that predate the column so cross-phase
    # bootstrap targets resolve to the correct phase model.
    rows = trajectory_store.annotate_next_phase(rows)
    result = train_td(rows, config)
    return result, rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train the Blokus state evaluator via TD(0).")
    p.add_argument("--input", default=str(trajectory_store.DEFAULT_TRAJECTORY_CSV),
                   help="Trajectory CSV (data/td_trajectories.csv).")
    p.add_argument("--output", default=str(DEFAULT_OUTPUT),
                   help="Output weights JSON (training/state/td_evaluator_weights.json).")
    p.add_argument("--gamma", type=float, default=0.98)
    p.add_argument("--alpha", type=float, default=0.01)
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--l2", type=float, default=0.001)
    p.add_argument("--clip-td-error", type=float, nargs=2, default=[-2.0, 2.0],
                   metavar=("LOW", "HIGH"))
    p.add_argument("--min-rows-per-phase", type=int, default=200)
    p.add_argument("--blend-rank-weight", type=float, default=0.50)
    p.add_argument("--blend-score-weight", type=float, default=0.30)
    p.add_argument("--blend-margin-weight", type=float, default=0.20)
    p.add_argument("--score-center", type=float, default=DEFAULT_SCORE_CENTER,
                   help="Centre for tanh final-score normalisation (calibrated default).")
    p.add_argument("--score-spread", type=float, default=DEFAULT_SCORE_SPREAD,
                   help="Spread for tanh final-score normalisation (calibrated default).")
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--dry-run", action="store_true",
                   help="Train and print metrics but do not write the output file.")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    config = TDConfig(
        gamma=args.gamma,
        alpha=args.alpha,
        epochs=args.epochs,
        l2=args.l2,
        clip_td_error=(args.clip_td_error[0], args.clip_td_error[1]),
        min_rows_per_phase=args.min_rows_per_phase,
        blend_rank_weight=args.blend_rank_weight,
        blend_score_weight=args.blend_score_weight,
        blend_margin_weight=args.blend_margin_weight,
        score_center=args.score_center,
        score_spread=args.score_spread,
        seed=args.seed,
    )

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[td_learning] Input not found: {input_path}")
        print("[td_learning] Collect trajectories first via training.td_selfplay.")
        return 1

    result, rows = train_from_file(input_path, config)
    if result.source_rows == 0:
        print(f"[td_learning] No usable rows in {input_path}.")
        return 1

    artifact = build_artifact(result, config)

    print(f"[td_learning] rows={result.source_rows} "
          f"td_loss={result.td_loss:.5f} mean_abs_td_error={result.mean_abs_td_error:.5f}")
    for phase in PHASES:
        flag = "trained" if result.trained_phases[phase] else "PRIOR (insufficient rows)"
        print(f"  {phase:>5s}: n={result.rows_by_phase[phase]:>6d} "
              f"loss={result.td_loss_by_phase[phase]:.5f}  [{flag}]")

    if args.dry_run:
        print("[td_learning] --dry-run: not writing output file.")
        print(json.dumps(artifact["phase_weights"], indent=2))
        return 0

    out = write_artifact(artifact, args.output)
    print(f"[td_learning] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
