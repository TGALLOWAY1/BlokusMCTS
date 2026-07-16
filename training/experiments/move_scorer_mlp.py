"""Phase 6, step 2 (EXP-011): shape-aware MLP move scorer.

EXP-010 attributed the linear scorer's failure to CAPACITY (0.165 tie-aware
top-1 on its own training data). This module tests the remediation: a small
numpy MLP over a shape-aware move encoding (move_encoding_v1) —

  * 9x9 board patch centered on the placement centroid, 6 channels:
    own occupied / opponent occupied / off-board / new-piece cells /
    own frontier / opponent frontier                       (486 inputs)
  * piece one-hot (21)
  * the 10 move_features_v2 scalars + game phase           (11)

scored by a 518->64(tanh)->1 network shared across candidates, trained with
the same listwise softmax cross-entropy over each decision's children
(teacher visit distillation), Adam, fixed seed. Inference is plain numpy
(Pyodide-safe per D-006/D-017).

Gate order (pre-registered in EXPERIMENT_LOG.md EXP-011): strict overfit gate
(tie-aware top-1 >= 0.80 on 200 training decisions) BEFORE the held-out bars
(identical sets and baselines as EXP-010). Experiment-only: production wiring
is a separate change gated on the bars.

    python -m training.experiments.move_scorer_mlp --split-seed 20260716
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.board import Board, Player
from engine.move_generator import Move, get_shared_generator
from mcts.move_heuristic import _get_piece_positions
from mcts.move_policy import DEFAULT_FEATURE_WEIGHTS
from training.experiments.move_scorer import (
    MOVE_FEATURES_V2,
    compute_move_features_v2,
    evaluate_ordering,
    legacy_policy_logit_fn,
)
from training.experiments.teacher_selfplay import iter_dataset_records

MOVE_ENCODING_VERSION = "move_encoding_v1"
PATCH = 9  # odd; centered on the placement centroid
N_CHANNELS = 6
N_PIECES = 21
N_SCALARS = len(MOVE_FEATURES_V2) + 1  # + phase
INPUT_DIM = N_CHANNELS * PATCH * PATCH + N_PIECES + N_SCALARS


@dataclass
class EncodedDecision:
    """One teacher decision with per-candidate encoded inputs."""

    game_id: str
    inputs: np.ndarray     # (n_children, INPUT_DIM) float32
    target: np.ndarray     # (n_children,) visit distribution
    mf4: np.ndarray        # (n_children, 4) for the heuristic baseline
    features_v2: np.ndarray  # (n_children, 10) for the legacy-policy baseline
    piece_ids: np.ndarray  # (n_children,)

    # Baseline evaluate_ordering expects `.features` (mf prefix layout).
    @property
    def features(self) -> np.ndarray:
        return self.features_v2


def encode_move(board: Board, player: Player, move: Move, generator,
                grid_own: np.ndarray, grid_opp: np.ndarray,
                own_frontier: np.ndarray, opp_frontier: np.ndarray,
                ) -> np.ndarray:
    """move_encoding_v1 input vector for one candidate move."""
    positions = _get_piece_positions(move, generator)
    size = board.SIZE
    rows = [p.row for p in positions]
    cols = [p.col for p in positions]
    cr = int(round(sum(rows) / len(rows)))
    cc = int(round(sum(cols) / len(cols)))
    half = PATCH // 2

    patch = np.zeros((N_CHANNELS, PATCH, PATCH), dtype=np.float32)
    r0, c0 = cr - half, cc - half
    for pr in range(PATCH):
        br = r0 + pr
        if br < 0 or br >= size:
            patch[2, pr, :] = 1.0  # off-board row
            continue
        for pc in range(PATCH):
            bc = c0 + pc
            if bc < 0 or bc >= size:
                patch[2, pr, pc] = 1.0
                continue
            patch[0, pr, pc] = grid_own[br, bc]
            patch[1, pr, pc] = grid_opp[br, bc]
            patch[4, pr, pc] = own_frontier[br, bc]
            patch[5, pr, pc] = opp_frontier[br, bc]
    for p in positions:
        pr, pc = p.row - r0, p.col - c0
        if 0 <= pr < PATCH and 0 <= pc < PATCH:
            patch[3, pr, pc] = 1.0

    piece_onehot = np.zeros(N_PIECES, dtype=np.float32)
    if 1 <= move.piece_id <= N_PIECES:
        piece_onehot[move.piece_id - 1] = 1.0

    scalars = compute_move_features_v2(board, player, move, generator)
    phase = min(board.move_count / 60.0, 1.0)
    return np.concatenate([
        patch.ravel(), piece_onehot,
        np.asarray(list(scalars) + [phase], dtype=np.float32),
    ]).astype(np.float32)


def extract_encoded(dataset_dir: Path) -> List[EncodedDecision]:
    generator = get_shared_generator()
    out: List[EncodedDecision] = []
    for _, record in iter_dataset_records(dataset_dir):
        search = record["search"]
        if len(search) < 2:
            continue
        board = Board.from_dict(record["state"])
        player = Player(record["player_id"])
        size = board.SIZE
        grid_own = (board.grid == player.value).astype(np.float32)
        grid_opp = ((board.grid != 0) & (board.grid != player.value)).astype(np.float32)
        own_frontier = np.zeros((size, size), dtype=np.float32)
        for r, c in board.player_frontiers[player]:
            own_frontier[r, c] = 1.0
        opp_frontier = np.zeros((size, size), dtype=np.float32)
        for opp in Player:
            if opp is player:
                continue
            for r, c in board.player_frontiers[opp]:
                opp_frontier[r, c] = 1.0

        moves = [Move.from_dict(e["action"]) for e in search]
        inputs = np.stack([
            encode_move(board, player, m, generator, grid_own, grid_opp,
                        own_frontier, opp_frontier)
            for m in moves
        ])
        feats_v2 = inputs[:, -N_SCALARS:-1]  # the move_features_v2 scalar block
        out.append(EncodedDecision(
            game_id=record["game_id"],
            inputs=inputs,
            target=np.asarray(record["policy_target"], dtype=float),
            mf4=feats_v2[:, :4].astype(float),
            features_v2=feats_v2.astype(float),
            piece_ids=np.array([m.piece_id for m in moves], dtype=int),
        ))
    return out


# ---------------------------------------------------------------------------
# Numpy MLP with listwise softmax CE (Adam)
# ---------------------------------------------------------------------------


class MLPScorer:
    """518 -> hidden (tanh) -> 1 logit per candidate; listwise softmax CE."""

    def __init__(self, input_dim: int, hidden: int, seed: int) -> None:
        rng = np.random.default_rng(seed)
        self.W1 = rng.normal(0.0, np.sqrt(2.0 / input_dim),
                             (input_dim, hidden)).astype(np.float64)
        self.b1 = np.zeros(hidden)
        self.W2 = rng.normal(0.0, np.sqrt(2.0 / hidden), (hidden, 1)).astype(np.float64)
        self.b2 = np.zeros(1)
        self._adam = {k: [np.zeros_like(v), np.zeros_like(v)]
                      for k, v in self.params().items()}
        self._t = 0

    def params(self) -> Dict[str, np.ndarray]:
        return {"W1": self.W1, "b1": self.b1, "W2": self.W2, "b2": self.b2}

    def logits(self, x: np.ndarray) -> np.ndarray:
        h = np.tanh(x @ self.W1 + self.b1)
        return (h @ self.W2 + self.b2).ravel()

    def train(self, decisions: List[EncodedDecision], epochs: int, lr: float,
              l2: float, batch: int, seed: int, verbose: bool = False) -> None:
        order_rng = random.Random(seed)
        idx = list(range(len(decisions)))
        beta1, beta2, eps = 0.9, 0.999, 1e-8
        for epoch in range(epochs):
            order_rng.shuffle(idx)
            total_loss = 0.0
            for start in range(0, len(idx), batch):
                grads = {k: np.zeros_like(v) for k, v in self.params().items()}
                n_in_batch = 0
                for di in idx[start:start + batch]:
                    d = decisions[di]
                    x = d.inputs.astype(np.float64)
                    h = np.tanh(x @ self.W1 + self.b1)
                    z = (h @ self.W2 + self.b2).ravel()
                    z -= z.max()
                    q = np.exp(z)
                    q /= q.sum()
                    total_loss += float(-(d.target * np.log(np.clip(q, 1e-12, 1.0))).sum())
                    dz = (q - d.target)[:, None]          # (n,1)
                    grads["W2"] += h.T @ dz
                    grads["b2"] += dz.sum(axis=0)
                    dh = (dz @ self.W2.T) * (1.0 - h * h)  # (n,hidden)
                    grads["W1"] += x.T @ dh
                    grads["b1"] += dh.sum(axis=0)
                    n_in_batch += 1
                if not n_in_batch:
                    continue
                self._t += 1
                for k, v in self.params().items():
                    g = grads[k] / n_in_batch + l2 * v
                    m, s = self._adam[k]
                    m[:] = beta1 * m + (1 - beta1) * g
                    s[:] = beta2 * s + (1 - beta2) * g * g
                    mh = m / (1 - beta1 ** self._t)
                    sh = s / (1 - beta2 ** self._t)
                    v -= lr * mh / (np.sqrt(sh) + eps)
            if verbose and (epoch + 1) % 10 == 0:
                print(f"  epoch {epoch + 1}/{epochs} loss={total_loss / len(idx):.4f}",
                      flush=True)

    def export(self) -> Dict:
        return {
            "encoding_version": MOVE_ENCODING_VERSION,
            "input_dim": self.W1.shape[0],
            "hidden": self.W1.shape[1],
            "W1": self.W1.tolist(), "b1": self.b1.tolist(),
            "W2": self.W2.ravel().tolist(), "b2": float(self.b2[0]),
        }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m training.experiments.move_scorer_mlp", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--teacher", default="data/teacher_dataset_v1")
    parser.add_argument("--bulk", default="data/value_dataset_v2")
    parser.add_argument("--legacy-policy", default="training/state/policy_weights.json")
    parser.add_argument("--out", default="training/artifacts/move_scorer/v2_mlp")
    parser.add_argument("--test-frac", type=float, default=0.25)
    parser.add_argument("--split-seed", type=int, default=20260716)
    parser.add_argument("--hidden", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--overfit-epochs", type=int, default=300)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--l2", type=float, default=1e-5)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--overfit-n", type=int, default=200)
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("encoding decisions...", flush=True)
    teacher = extract_encoded(Path(args.teacher))
    bulk = extract_encoded(Path(args.bulk))
    print(f"teacher: {len(teacher)} decisions; bulk: {len(bulk)} decisions; "
          f"input_dim={INPUT_DIM}")

    def split(decisions: List[EncodedDecision]):
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
    print(f"train: {len(train)}; held-out teacher: {len(teacher_test)}; "
          f"held-out bulk: {len(bulk_test)}\n")

    # Gate 1 — STRICT overfit: must nearly memorize 200 training decisions
    # (pre-registered bar: tie-aware top-1 >= 0.80; linear scorer: 0.165).
    tiny = train[:args.overfit_n]
    print(f"gate 1 (strict overfit, n={len(tiny)}, "
          f"{args.overfit_epochs} epochs):", flush=True)
    tiny_model = MLPScorer(INPUT_DIM, args.hidden, args.seed)
    tiny_model.train(tiny, epochs=args.overfit_epochs, lr=args.lr, l2=0.0,
                     batch=args.batch, seed=args.seed, verbose=True)
    g1 = evaluate_ordering("  mlp_tiny(train)", tiny,
                           lambda d: tiny_model.logits(d.inputs.astype(np.float64)))
    gate1 = g1["top1"] >= 0.80
    print(f"gate 1: {'PASS' if gate1 else 'FAIL'} (bar: top1 >= 0.80)\n")

    # Gate 2 — held-out generalization (same sets/baselines as EXP-010).
    print(f"training full model ({len(train)} decisions, {args.epochs} epochs)...",
          flush=True)
    model = MLPScorer(INPUT_DIM, args.hidden, args.seed)
    model.train(train, epochs=args.epochs, lr=args.lr, l2=args.l2,
                batch=args.batch, seed=args.seed, verbose=True)

    heuristic_fn = lambda d: d.mf4 @ np.asarray(DEFAULT_FEATURE_WEIGHTS)
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
        block["mlp"] = evaluate_ordering(
            "  mlp_trained", eval_set,
            lambda d: model.logits(d.inputs.astype(np.float64)))
        results[eval_name] = block
        print()

    primary = results["teacher_heldout"]
    baselines = [primary["fixed_heuristic"]] + (
        [primary["legacy_policy"]] if "legacy_policy" in primary else [])
    mlp = primary["mlp"]
    beats_baselines = all(
        mlp["top1"] > b["top1"] + (mlp["top1_se"] + b["top1_se"])
        and mlp["pairwise"] > b["pairwise"]
        for b in baselines)
    print(f"gate 2 (pre-registered bars, held-out teacher): "
          f"beats_baselines={beats_baselines}")

    report = {
        "experiment": "EXP-011",
        "encoding_version": MOVE_ENCODING_VERSION,
        "input_dim": INPUT_DIM,
        "hidden": args.hidden,
        "hyperparams": {"epochs": args.epochs, "overfit_epochs": args.overfit_epochs,
                        "lr": args.lr, "l2": args.l2, "batch": args.batch,
                        "seed": args.seed},
        "split": {"seed": args.split_seed, "test_frac": args.test_frac},
        "gate1_strict_overfit": {"pass": bool(gate1), "bar": 0.80, "result": g1},
        "gate2": {"beats_baselines": bool(beats_baselines)},
        "results": results,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    (out_dir / "mlp_weights.json").write_text(json.dumps(model.export()))
    print(f"report -> {out_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
