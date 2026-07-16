"""Phase 6, gates 1-2 (EXP-010): teacher-distilled move-level candidate scorer.

Trains listwise log-linear softmax scorers (the mcts/move_policy.py structure,
generalized to N features + per-piece bias) by distilling TEACHER root visit
distributions from the validated teacher-record datasets, and evaluates
move-ordering quality on held-out teacher decisions against the fixed
4-feature heuristic and the legacy policy artifact.

Feature sets (D-017):
  mf4    — the four MOVE_FEATURE_NAMES (order-stable prefix)
  mf_v2  — mf4 + six move-varying extensions (MOVE_FEATURES_V2_EXTENSIONS)

Gate order (master plan Phase 6): tiny-data overfit sanity first, then the
held-out bars pre-registered in EXPERIMENT_LOG.md EXP-010. This module is
experiment-only: production wiring (a versioned move_policy_v2) happens in a
separate change only if the bars clear.

    python -m training.experiments.move_scorer --split-seed 20260716
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from engine.board import Board, Player
from engine.move_generator import Move, get_shared_generator
from mcts.move_heuristic import (
    MOVE_FEATURE_NAMES,
    _get_piece_positions,
    compute_move_features,
)
from mcts.move_policy import DEFAULT_FEATURE_WEIGHTS
from training.experiments.teacher_selfplay import iter_dataset_records

MOVE_FEATURES_V2_EXTENSIONS = (
    "own_frontier_consumed",   # my corner-anchor cells this move occupies
    "opp_frontier_occupied",   # opponents' corner-anchor cells this move occupies
    "opp_contact",             # orthogonal adjacency to opponent cells (walling)
    "own_diag_links",          # diagonal links to my own pieces beyond the required 1
    "phase_x_size",            # game-phase x piece-size interaction
    "edge_fraction",           # fraction of cells on the outer border
)
MOVE_FEATURES_V2 = tuple(MOVE_FEATURE_NAMES) + MOVE_FEATURES_V2_EXTENSIONS

FEATURE_SETS: Dict[str, Tuple[str, ...]] = {
    "mf4": tuple(MOVE_FEATURE_NAMES),
    "mf_v2": MOVE_FEATURES_V2,
}


def compute_move_features_v2(board: Board, player: Player, move: Move,
                             generator) -> np.ndarray:
    """mf4 features followed by the six D-017 move-varying extensions."""
    base = compute_move_features(board, player, move, generator)
    positions = _get_piece_positions(move, generator)
    cells = {(p.row, p.col) for p in positions}
    size = board.SIZE

    own_frontier = board.player_frontiers[player]
    own_frontier_consumed = sum(1 for c in cells if c in own_frontier)
    opp_frontier_occupied = 0
    for opp in Player:
        if opp is player:
            continue
        frontier = board.player_frontiers[opp]
        opp_frontier_occupied += sum(1 for c in cells if c in frontier)

    opp_contact = 0
    own_diag = 0
    for r, c in cells:
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < size and 0 <= nc < size:
                v = board.grid[nr, nc]
                if v != 0 and v != player.value:
                    opp_contact += 1
        for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < size and 0 <= nc < size and (nr, nc) not in cells:
                if board.grid[nr, nc] == player.value:
                    own_diag += 1

    phase = min(board.move_count / 60.0, 1.0)
    edge_cells = sum(1 for r, c in cells
                     if r == 0 or c == 0 or r == size - 1 or c == size - 1)

    ext = (
        min(own_frontier_consumed / 4.0, 1.0),
        min(opp_frontier_occupied / 4.0, 1.0),
        min(opp_contact / 8.0, 1.0),
        min(max(own_diag - 1, 0) / 4.0, 1.0),
        phase * base[0],
        edge_cells / len(cells),
    )
    return np.array(tuple(base) + ext, dtype=float)


# ---------------------------------------------------------------------------
# Decision extraction
# ---------------------------------------------------------------------------


@dataclass
class Decision:
    """One teacher decision: candidate features, piece ids, visit target."""

    game_id: str
    features: np.ndarray   # (n_children, n_feat) for mf_v2; mf4 = prefix cols
    piece_ids: np.ndarray  # (n_children,)
    target: np.ndarray     # (n_children,) normalized visit distribution


def extract_decisions(dataset_dir: Path) -> List[Decision]:
    generator = get_shared_generator()
    out: List[Decision] = []
    for _, record in iter_dataset_records(dataset_dir):
        search = record["search"]
        if len(search) < 2:
            continue
        board = Board.from_dict(record["state"])
        player = Player(record["player_id"])
        feats = np.stack([
            compute_move_features_v2(board, player,
                                     Move.from_dict(entry["action"]), generator)
            for entry in search
        ])
        out.append(Decision(
            game_id=record["game_id"],
            features=feats,
            piece_ids=np.array([entry["action"]["piece_id"] for entry in search],
                               dtype=int),
            target=np.asarray(record["policy_target"], dtype=float),
        ))
    return out


# ---------------------------------------------------------------------------
# Listwise trainer (move_policy.train_move_policy generalized to N features)
# ---------------------------------------------------------------------------


@dataclass
class ListwiseModel:
    feature_names: Tuple[str, ...]
    weights: np.ndarray
    piece_bias: Dict[int, float]

    def logits(self, features: np.ndarray, piece_ids: np.ndarray) -> np.ndarray:
        bias = np.array([self.piece_bias.get(int(p), 0.0) for p in piece_ids])
        return features[:, :len(self.weights)] @ self.weights + bias


def train_listwise(decisions: Sequence[Decision], n_feat: int,
                   feature_names: Tuple[str, ...],
                   epochs: int = 60, lr: float = 0.20, l2: float = 1e-4,
                   ) -> ListwiseModel:
    piece_ids = tuple(range(1, 22))
    piece_index = {p: i for i, p in enumerate(piece_ids)}
    w = np.zeros(n_feat, dtype=float)
    w[:len(DEFAULT_FEATURE_WEIGHTS)] = DEFAULT_FEATURE_WEIGHTS
    b = np.zeros(len(piece_ids), dtype=float)

    for _ in range(epochs):
        gw = np.zeros_like(w)
        gb = np.zeros_like(b)
        for d in decisions:
            feats = d.features[:, :n_feat]
            bias = np.array([b[piece_index[int(p)]] for p in d.piece_ids])
            z = feats @ w + bias
            z -= z.max()
            q = np.exp(z)
            q /= q.sum()
            dz = q - d.target
            gw += feats.T @ dz
            for j, p in enumerate(d.piece_ids):
                gb[piece_index[int(p)]] += dz[j]
        n = max(len(decisions), 1)
        w -= lr * (gw / n + l2 * w)
        b -= lr * (gb / n + l2 * b)

    bias_map = {int(piece_ids[i]): float(b[i])
                for i in range(len(piece_ids)) if abs(b[i]) > 1e-9}
    return ListwiseModel(feature_names=feature_names, weights=w,
                         piece_bias=bias_map)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_ordering(name: str, decisions: Sequence[Decision],
                      logit_fn) -> Dict[str, float]:
    """Top-1 agreement with the visit argmax + within-decision pairwise accuracy."""
    top1 = 0
    pair_correct = 0
    pair_total = 0
    for d in decisions:
        z = logit_fn(d)
        if int(np.argmax(z)) == int(np.argmax(d.target)):
            top1 += 1
        n = len(z)
        for i in range(n):
            for j in range(i + 1, n):
                if d.target[i] == d.target[j]:
                    continue
                pair_total += 1
                if (z[i] - z[j]) * (d.target[i] - d.target[j]) > 0:
                    pair_correct += 1
    n_dec = max(len(decisions), 1)
    out = {
        "top1": top1 / n_dec,
        "top1_se": math.sqrt(max(top1 / n_dec * (1 - top1 / n_dec), 1e-12) / n_dec),
        "pairwise": pair_correct / max(pair_total, 1),
        "n_decisions": len(decisions),
        "n_pairs": pair_total,
    }
    print(f"{name:<28} top1={out['top1']:.3f}±{out['top1_se']:.3f}  "
          f"pairwise={out['pairwise']:.3f}  (n={out['n_decisions']})")
    return out


def legacy_policy_logit_fn(artifact_path: Path):
    artifact = json.loads(artifact_path.read_text())
    policy = artifact["policy"]
    w = np.asarray(policy["feature_weights"], dtype=float)
    bias = {int(k): float(v) for k, v in (policy.get("piece_bias") or {}).items()}

    def fn(d: Decision) -> np.ndarray:
        bias_vec = np.array([bias.get(int(p), 0.0) for p in d.piece_ids])
        return d.features[:, :len(w)] @ w + bias_vec
    return fn


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m training.experiments.move_scorer", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--teacher", default="data/teacher_dataset_v1")
    parser.add_argument("--bulk", default="data/value_dataset_v2")
    parser.add_argument("--legacy-policy", default="training/state/policy_weights.json")
    parser.add_argument("--out", default="training/artifacts/move_scorer/v1")
    parser.add_argument("--test-frac", type=float, default=0.25)
    parser.add_argument("--split-seed", type=int, default=20260716)
    parser.add_argument("--overfit-n", type=int, default=200)
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("extracting decisions...", flush=True)
    teacher = extract_decisions(Path(args.teacher))
    bulk = extract_decisions(Path(args.bulk))
    print(f"teacher: {len(teacher)} decisions; bulk: {len(bulk)} decisions")

    def split(decisions: List[Decision]) -> Tuple[List[Decision], List[Decision]]:
        games = sorted({d.game_id for d in decisions})
        rng = random.Random(args.split_seed)
        rng.shuffle(games)
        n_test = max(2, int(round(len(games) * args.test_frac)))
        test_games = set(games[:n_test])
        return ([d for d in decisions if d.game_id not in test_games],
                [d for d in decisions if d.game_id in test_games])

    teacher_train, teacher_test = split(teacher)
    bulk_train, bulk_test = split(bulk)
    train = teacher_train + bulk_train
    print(f"train: {len(train)} decisions; held-out teacher: {len(teacher_test)}; "
          f"held-out bulk: {len(bulk_test)}\n")

    # Gate 1 — tiny-data overfit sanity: optimization must clearly beat the
    # fixed heuristic ON the decisions it trained on.
    tiny = train[:args.overfit_n]
    n_v2 = len(MOVE_FEATURES_V2)
    tiny_model = train_listwise(tiny, n_v2, MOVE_FEATURES_V2)
    print(f"gate 1 (overfit sanity, n={len(tiny)}):")
    heuristic_fn = lambda d: d.features[:, :4] @ np.asarray(DEFAULT_FEATURE_WEIGHTS)
    g1_base = evaluate_ordering("  fixed_heuristic(train)", tiny, heuristic_fn)
    g1_model = evaluate_ordering("  mf_v2_tiny(train)", tiny,
                                 lambda d: tiny_model.logits(d.features, d.piece_ids))
    gate1 = g1_model["top1"] > g1_base["top1"] + 0.05
    print(f"gate 1: {'PASS' if gate1 else 'FAIL'}\n")

    # Gate 2 — held-out generalization (primary: held-out TEACHER decisions).
    models = {
        name: train_listwise(train, len(cols), cols)
        for name, cols in FEATURE_SETS.items()
    }
    results: Dict[str, Dict] = {}
    for eval_name, eval_set in (("teacher_heldout", teacher_test),
                                ("bulk_heldout", bulk_test)):
        print(f"held-out evaluation ({eval_name}):")
        block: Dict[str, Dict] = {}
        block["fixed_heuristic"] = evaluate_ordering(
            "  fixed_heuristic", eval_set, heuristic_fn)
        legacy_path = Path(args.legacy_policy)
        if legacy_path.exists():
            block["legacy_policy"] = evaluate_ordering(
                "  legacy_policy", eval_set, legacy_policy_logit_fn(legacy_path))
        for name, model in models.items():
            block[name] = evaluate_ordering(
                f"  {name}_trained", eval_set,
                lambda d, m=model: m.logits(d.features, d.piece_ids))
        results[eval_name] = block
        print()

    primary = results["teacher_heldout"]
    baselines = [primary["fixed_heuristic"]] + (
        [primary["legacy_policy"]] if "legacy_policy" in primary else [])
    v2 = primary["mf_v2"]
    beats_baselines = all(
        v2["top1"] > b["top1"] + 2 * (v2["top1_se"] + b["top1_se"]) / 2
        and v2["pairwise"] > b["pairwise"]
        for b in baselines)
    beats_mf4 = (v2["top1"] > primary["mf4"]["top1"]
                 and v2["pairwise"] > primary["mf4"]["pairwise"])
    print(f"gate 2 (pre-registered bars, held-out teacher): "
          f"beats_baselines={beats_baselines} beats_mf4={beats_mf4}")

    report = {
        "experiment": "EXP-010",
        "feature_sets": {k: list(v) for k, v in FEATURE_SETS.items()},
        "split": {"seed": args.split_seed, "test_frac": args.test_frac},
        "gate1_overfit_sanity": {"pass": bool(gate1),
                                 "baseline": g1_base, "model": g1_model},
        "gate2": {"beats_baselines": bool(beats_baselines),
                  "beats_mf4": bool(beats_mf4)},
        "results": results,
        "models": {
            name: {"feature_names": list(m.feature_names),
                   "weights": [float(x) for x in m.weights],
                   "piece_bias": m.piece_bias}
            for name, m in models.items()
        },
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    print(f"report -> {out_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
