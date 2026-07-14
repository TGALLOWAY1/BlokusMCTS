"""Evaluator-track v1: train candidate value models and run the D-015 gates.

Trains per-player state-value models (predict normalized standard final score
from the 45 current-state `f_*` rich features) on the manifested
`data/value_dataset_v1` corpus with a GAME-level held-out split, compares a
linear baseline against non-linear models (gate 1), and runs the root
Q-spread probe (gate 2) by plugging the best model into the MCTS rich-leaf
slot (duck-typed `evaluate(board, player)` — the agent multiplies by its
x100 reward scale).

Gate references: docs/agent-strength-rebuild/DECISIONS.md D-015.

    python -m training.experiments.value_model \
        --dataset data/value_dataset_v1 --out training/artifacts/value_models/v1
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

TARGET_SCALE = 100.0  # model predicts final_score / TARGET_SCALE


# ---------------------------------------------------------------------------
# Training + gate 1 (held-out skill, game-level split)
# ---------------------------------------------------------------------------

def load_dataset(dataset_dir: Path):
    df = pd.read_csv(dataset_dir / "trajectories.csv")
    feature_cols = [c for c in df.columns if c.startswith("f_")]
    manifest = json.loads((dataset_dir / "manifest.json").read_text())
    return df, feature_cols, manifest


def game_split(df: pd.DataFrame, test_frac: float, seed: int):
    games = sorted(df["game_id"].unique())
    rng = random.Random(seed)
    rng.shuffle(games)
    n_test = max(1, int(round(len(games) * test_frac)))
    test_games = set(games[:n_test])
    return df[~df["game_id"].isin(test_games)], df[df["game_id"].isin(test_games)]


def pairwise_rank_accuracy(df: pd.DataFrame, preds: np.ndarray) -> float:
    """Fraction of within-decision player pairs ordered consistently with the
    true final scores — the discrimination measure that matters for search."""
    work = df[["game_id", "ply", "final_score"]].copy()
    work["pred"] = preds
    correct = total = 0
    for (_, _), group in work.groupby(["game_id", "ply"]):
        rows = group.to_records()
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                if a.final_score == b.final_score:
                    continue
                total += 1
                if (a.pred - b.pred) * (a.final_score - b.final_score) > 0:
                    correct += 1
    return correct / total if total else float("nan")


def build_models(seed: int) -> Dict[str, object]:
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return {
        "ridge_baseline": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "hist_gb": HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.06, max_depth=None,
            min_samples_leaf=40, l2_regularization=0.1, random_state=seed,
        ),
        "mlp": make_pipeline(
            StandardScaler(),
            MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=400,
                         early_stopping=True, random_state=seed),
        ),
    }


def train_and_evaluate(df, feature_cols, args):
    from sklearn.metrics import mean_absolute_error, r2_score

    train_df, test_df = game_split(df, args.test_frac, args.split_seed)
    x_train = train_df[feature_cols].to_numpy(dtype=float)
    y_train = (train_df["final_score"] / TARGET_SCALE).to_numpy(dtype=float)
    x_test = test_df[feature_cols].to_numpy(dtype=float)
    y_test = (test_df["final_score"] / TARGET_SCALE).to_numpy(dtype=float)

    results = {}
    fitted = {}
    for name, model in build_models(args.split_seed).items():
        model.fit(x_train, y_train)
        preds = model.predict(x_test)
        results[name] = {
            "held_out_r2": float(r2_score(y_test, preds)),
            "held_out_mae_points": float(
                mean_absolute_error(y_test, preds) * TARGET_SCALE
            ),
            "pairwise_rank_accuracy": float(
                pairwise_rank_accuracy(test_df, preds)
            ),
        }
        fitted[name] = model
        print(f"{name:<16} R2={results[name]['held_out_r2']:.3f}  "
              f"MAE={results[name]['held_out_mae_points']:.2f} pts  "
              f"pairwise_rank_acc={results[name]['pairwise_rank_accuracy']:.3f}")

    return results, fitted, {
        "train_games": int(train_df["game_id"].nunique()),
        "test_games": int(test_df["game_id"].nunique()),
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
    }


# ---------------------------------------------------------------------------
# Gate 2: root Q-spread probe with the model as the leaf evaluator
# ---------------------------------------------------------------------------

def q_spread_probe(model, feature_names, seeds=(20260620,), plies=(8, 24)) -> Dict:
    from engine.board import Board
    from engine.move_generator import get_shared_generator
    from mcts.mcts_agent import MCTSAgent
    from mcts_lab.node_stats import run_search_with_root, tree_statistics
    from training.experiments.search_scaling import MINIMAL_SEARCH_PARAMS, PW_PARAMS

    gen = get_shared_generator()

    def board_at(n_plies, seed):
        rng = random.Random(seed)
        b = Board()
        n = 0
        while n < n_plies:
            p = b.current_player
            ms = gen.get_legal_moves(b, p)
            if not ms:
                b._update_current_player()
                continue
            m = rng.choice(ms)
            b.place_piece(m.get_positions(gen.piece_orientations_cache[m.piece_id]),
                          p, m.piece_id)
            n += 1
        return b

    params = {k: v for k, v in {**MINIMAL_SEARCH_PARAMS, **PW_PARAMS}.items()
              if k not in ("deterministic_time_budget",)}
    probe = {}
    for seed in seeds:
        for n_plies in plies:
            board = board_at(n_plies, seed)
            bf = len(gen.get_legal_moves(board, board.current_player))
            agent = MCTSAgent(iterations=500, seed=7, **params)
            from mcts.value_model_evaluator import ValueModelLeafEvaluator

            agent.rich_leaf_eval_enabled = True
            agent.rich_leaf_evaluator = ValueModelLeafEvaluator.from_fitted(
                model, feature_names
            )
            root = run_search_with_root(agent, board, board.current_player)
            _, depth_hist = tree_statistics(root)
            qs = sorted((c.total_reward / c.visits for c in root.children if c.visits),
                        reverse=True)
            best = max(root.children, key=lambda c: c.visits)
            probe[f"seed{seed}_ply{n_plies}"] = {
                "branching_factor": bf,
                "expanded_children": len(root.children),
                "max_depth": int(max(depth_hist)),
                "best_child_visit_share": round(best.visits / root.visits, 3),
                "q_top3": [round(q, 2) for q in qs[:3]],
                "q_spread": round(qs[0] - qs[-1], 2),
            }
            print(f"probe seed{seed} ply{n_plies} bf={bf}: "
                  f"children={len(root.children)} depth={max(depth_hist)} "
                  f"best_share={best.visits/root.visits:.0%} "
                  f"Q_top3={[round(q,2) for q in qs[:3]]} "
                  f"Q_spread={qs[0]-qs[-1]:.2f}")
    return probe


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m training.experiments.value_model", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dataset", default="data/value_dataset_v1")
    parser.add_argument("--out", default="training/artifacts/value_models/v1")
    parser.add_argument("--test-frac", type=float, default=0.2)
    parser.add_argument("--split-seed", type=int, default=20260713)
    parser.add_argument("--skip-probe", action="store_true")
    parser.add_argument("--save-model", default=None,
                        help="save this model's artifact instead of the best "
                             "non-linear one (e.g. ridge_baseline)")
    args = parser.parse_args(argv)

    dataset_dir = Path(args.dataset)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df, feature_cols, manifest = load_dataset(dataset_dir)
    feature_names = [c[len("f_"):] for c in feature_cols]
    print(f"dataset: {len(df)} rows, {df['game_id'].nunique()} games, "
          f"{len(feature_cols)} features\n")

    results, fitted, split_info = train_and_evaluate(df, feature_cols, args)

    # Gate 1: best non-linear model must beat the linear baseline on held-out
    # skill AND pairwise discrimination.
    baseline = results["ridge_baseline"]
    non_linear = {k: v for k, v in results.items() if k != "ridge_baseline"}
    if args.save_model:
        best_name = args.save_model
        if best_name not in fitted:
            raise SystemExit(f"--save-model must be one of {sorted(fitted)}")
    else:
        best_name = max(non_linear,
                        key=lambda k: non_linear[k]["pairwise_rank_accuracy"])
    best = results[best_name]
    gate1 = (best["held_out_r2"] > baseline["held_out_r2"]
             and best["pairwise_rank_accuracy"] > baseline["pairwise_rank_accuracy"])
    print(f"\nGate 1 (beat linear baseline): {'PASS' if gate1 else 'FAIL'} "
          f"(best={best_name})")

    probe = None
    if not args.skip_probe:
        print("\nGate 2 probe (root Q-spread with model as leaf evaluator, "
              "PW, 500 iterations; Layer-6 reference flatness ~1.3):")
        probe = q_spread_probe(fitted[best_name], feature_names)

    artifact = {
        "model_name": best_name,
        "model": fitted[best_name],
        "feature_names": feature_names,
        "target": f"final_score / {TARGET_SCALE} (standard scoring)",
        "dataset": str(dataset_dir),
        "dataset_manifest": manifest,
        "split": split_info,
        "metrics": results,
    }
    artifact_path = out_dir / f"value_v1_{best_name}.joblib"
    joblib.dump(artifact, artifact_path)

    report = {
        "experiment": "value_model_v1",
        "dataset": str(dataset_dir),
        "split": split_info,
        "metrics": results,
        "gate1_beat_linear_baseline": bool(gate1),
        "best_model": best_name,
        "q_spread_probe": probe,
        "artifact": str(artifact_path),
    }
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nartifact -> {artifact_path}\nreport -> {out_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
