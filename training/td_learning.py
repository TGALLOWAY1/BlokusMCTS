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
            "seed": self.seed,
        }


# ---------------------------------------------------------------------------
# Outcome labels / terminal value
# ---------------------------------------------------------------------------


def normalized_rank_value(rank: int, rank_map: Optional[Dict[int, float]] = None) -> float:
    rank_map = rank_map or DEFAULT_RANK_VALUE_MAP
    return float(rank_map.get(int(rank), -1.0))


def normalized_final_score(score: float) -> float:
    """Map a raw final score (~0..89 squares) onto [-1, 1]."""
    return float(np.tanh((float(score) - 40.0) / 20.0))


def normalized_score_margin(margin_to_next: float) -> float:
    """Signed closeness to the adjacent better player (or lead if winning)."""
    return float(np.tanh(float(margin_to_next) / 20.0))


def terminal_value(row: Dict[str, Any], config: TDConfig) -> float:
    """Blended terminal value in roughly [-1, 1] from a trajectory row's labels."""
    w_rank, w_score, w_margin = config.normalized_blend()
    rv = normalized_rank_value(int(row.get("final_rank", 4)), config.rank_value_map)
    sv = normalized_final_score(float(row.get("final_score", 0)))
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


def _row_phase(row: Dict[str, Any]) -> str:
    occ = float(row.get("board_occupancy", 0.0))
    if occ < PHASE_EARLY_THRESHOLD:
        return "early"
    if occ < PHASE_LATE_THRESHOLD:
        return "mid"
    return "late"


def train_td(rows: List[Dict[str, Any]], config: TDConfig) -> TDResult:
    """Run TD(0) training over loaded trajectory rows. Pure (no I/O)."""
    rng = _random.Random(config.seed)
    lo, hi = config.clip_td_error

    # Bucket rows by phase, pre-extracting vectors and targets.
    by_phase: Dict[str, List[Tuple[np.ndarray, np.ndarray, bool, float]]] = {
        p: [] for p in PHASES
    }
    for row in rows:
        phase = _row_phase(row)
        s = np.asarray(trajectory_store.state_vector(row), dtype=float)
        s_next = np.asarray(trajectory_store.next_state_vector(row), dtype=float)
        terminal = bool(int(row.get("terminal", 0)))
        tv = terminal_value(row, config) if terminal else 0.0
        by_phase[phase].append((s, s_next, terminal, tv))

    phase_models: Dict[str, PhaseModel] = {}
    trained: Dict[str, bool] = {}
    rows_by_phase: Dict[str, int] = {}
    loss_by_phase: Dict[str, float] = {}

    all_abs_errors: List[float] = []
    all_sq_errors: List[float] = []

    for phase in PHASES:
        samples = by_phase[phase]
        rows_by_phase[phase] = len(samples)
        model = PhaseModel(weights=_initial_weights(), bias=0.0)

        if len(samples) < config.min_rows_per_phase:
            # Insufficient data: keep the prior (initialised) weights, mark untrained.
            phase_models[phase] = model
            trained[phase] = False
            loss_by_phase[phase] = 0.0
            continue

        for _epoch in range(config.epochs):
            order = list(range(len(samples)))
            rng.shuffle(order)
            for idx in order:
                s, s_next, terminal, tv = samples[idx]
                v_s = model.value(s)
                if terminal:
                    target = tv
                else:
                    target = config.gamma * model.value(s_next)
                error = target - v_s
                if error < lo:
                    error = lo
                elif error > hi:
                    error = hi
                # Semi-gradient TD update with L2 on weights only.
                model.weights += config.alpha * (error * s) - config.alpha * config.l2 * model.weights
                model.bias += config.alpha * error

        # Final-pass metrics on this phase.
        sq = 0.0
        ab = 0.0
        for s, s_next, terminal, tv in samples:
            v_s = model.value(s)
            target = tv if terminal else config.gamma * model.value(s_next)
            err = target - v_s
            sq += err * err
            ab += abs(err)
            all_sq_errors.append(err * err)
            all_abs_errors.append(abs(err))
        n = max(len(samples), 1)
        loss_by_phase[phase] = sq / n
        phase_models[phase] = model
        trained[phase] = True

    td_loss = float(np.mean(all_sq_errors)) if all_sq_errors else 0.0
    mean_abs = float(np.mean(all_abs_errors)) if all_abs_errors else 0.0

    return TDResult(
        phase_models=phase_models,
        trained_phases=trained,
        rows_by_phase=rows_by_phase,
        td_loss=td_loss,
        td_loss_by_phase=loss_by_phase,
        mean_abs_td_error=mean_abs,
        source_rows=len(rows),
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
