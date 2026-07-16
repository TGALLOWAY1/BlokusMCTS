"""Phase 8 gate C, training half: value-model v2 from teacher self-play data.

Extracts `rich_blokus_v1` features from every recorded teacher state (all four
player perspectives), trains candidate v2 models against per-player normalized
standard final scores, and evaluates — alongside the frozen v1 ridge artifact —
on HELD-OUT TEACHER GAMES (the distribution that matters for the loop).

Training conditions (controlled data-mixing variable):
  teacher_only   — teacher_dataset_v1 rows only (~5.2k perspective-rows)
  mixed          — teacher rows + value_dataset_v1 rows (~22.6k)

Gate-C pre-check: a v2 condition must beat the v1 ridge baseline on held-out
teacher games (R² / pairwise rank accuracy) to justify the arena half
(direct same-table vm2-500 vs vm1-500 test).

    python -m training.experiments.value_model_v2 \
        --teacher data/teacher_dataset_v1 --v1 data/value_dataset_v1 \
        --out training/artifacts/value_models/v2
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from engine.board import Board, Player

TARGET_SCALE = 100.0


def extract_teacher_frame(dataset_dir: Path) -> pd.DataFrame:
    """One row per (recorded state, player perspective) with rich features."""
    from training.rich_features import RICH_FEATURE_NAMES, FeatureCache, extract_rich_features

    rows: List[Dict] = []
    for shard in sorted(dataset_dir.glob("game_*.jsonl")):
        for line in shard.read_text().splitlines():
            record = json.loads(line)
            board = Board.from_dict(record["state"])
            cache = FeatureCache()
            for p in Player:
                feats = extract_rich_features(board, p, cache=cache)
                row = {f"f_{n}": float(feats.get(n, 0.0)) for n in RICH_FEATURE_NAMES}
                row["game_id"] = record["game_id"]
                row["ply"] = record["decision_index"]
                row["final_score"] = int(record["final_scores"][str(p.value)])
                rows.append(row)
    return pd.DataFrame(rows)


def load_v1_frame(dataset_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(dataset_dir / "trajectories.csv")
    cols = [c for c in df.columns if c.startswith("f_")] + ["game_id", "ply", "final_score"]
    return df[cols].copy()


def pairwise_rank_accuracy(df: pd.DataFrame, preds: np.ndarray) -> float:
    work = df[["game_id", "ply", "final_score"]].copy()
    work["pred"] = preds
    correct = total = 0
    for _, group in work.groupby(["game_id", "ply"]):
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


def evaluate(name: str, model, test_df: pd.DataFrame, feature_cols: List[str]) -> Dict:
    from sklearn.metrics import mean_absolute_error, r2_score

    preds = model.predict(test_df[feature_cols].to_numpy(dtype=float))
    y = (test_df["final_score"] / TARGET_SCALE).to_numpy(dtype=float)
    out = {
        "held_out_r2": float(r2_score(y, preds)),
        "held_out_mae_points": float(mean_absolute_error(y, preds) * TARGET_SCALE),
        "pairwise_rank_accuracy": float(pairwise_rank_accuracy(test_df, preds)),
    }
    print(f"{name:<22} R2={out['held_out_r2']:.3f}  "
          f"MAE={out['held_out_mae_points']:.2f} pts  "
          f"pairwise_rank_acc={out['pairwise_rank_accuracy']:.3f}")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m training.experiments.value_model_v2", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--teacher", default="data/teacher_dataset_v1")
    parser.add_argument("--v1", default="data/value_dataset_v1")
    parser.add_argument("--v1-artifact",
                        default="training/artifacts/value_models/v1/value_v1_ridge_baseline.joblib")
    parser.add_argument("--out", default="training/artifacts/value_models/v2")
    parser.add_argument("--test-frac", type=float, default=0.25)
    parser.add_argument("--split-seed", type=int, default=20260716)
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("extracting teacher features...", flush=True)
    teacher_df = extract_teacher_frame(Path(args.teacher))
    v1_df = load_v1_frame(Path(args.v1))
    feature_cols = [c for c in teacher_df.columns if c.startswith("f_")]
    assert set(feature_cols) <= set(v1_df.columns), "feature schema mismatch"
    print(f"teacher rows: {len(teacher_df)} ({teacher_df['game_id'].nunique()} games); "
          f"v1 rows: {len(v1_df)} ({v1_df['game_id'].nunique()} games)")

    # Held-out split at the TEACHER-game level; the same held-out teacher games
    # are the evaluation set for every condition (and the v1 baseline).
    teacher_games = sorted(teacher_df["game_id"].unique())
    rng = random.Random(args.split_seed)
    rng.shuffle(teacher_games)
    n_test = max(2, int(round(len(teacher_games) * args.test_frac)))
    test_games = set(teacher_games[:n_test])
    teacher_train = teacher_df[~teacher_df["game_id"].isin(test_games)]
    teacher_test = teacher_df[teacher_df["game_id"].isin(test_games)]
    print(f"split: {len(teacher_games) - n_test} train / {n_test} held-out teacher games\n")

    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    def fit_ridge(frame: pd.DataFrame):
        model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        model.fit(frame[feature_cols].to_numpy(dtype=float),
                  (frame["final_score"] / TARGET_SCALE).to_numpy(dtype=float))
        return model

    conditions: Dict[str, object] = {
        "v2_teacher_only": fit_ridge(teacher_train),
        "v2_mixed": fit_ridge(pd.concat([teacher_train, v1_df], ignore_index=True)),
    }
    v1_artifact = joblib.load(args.v1_artifact)
    conditions["v1_ridge_baseline"] = v1_artifact["model"]

    print("held-out evaluation (held-out TEACHER games):")
    results = {name: evaluate(name, model, teacher_test, feature_cols)
               for name, model in conditions.items()}

    baseline = results["v1_ridge_baseline"]
    candidates = {k: v for k, v in results.items() if k.startswith("v2_")}
    best_name = max(candidates, key=lambda k: candidates[k]["pairwise_rank_accuracy"])
    best = results[best_name]
    pre_check = (best["pairwise_rank_accuracy"] > baseline["pairwise_rank_accuracy"]
                 and best["held_out_r2"] > baseline["held_out_r2"])
    print(f"\nGate-C pre-check (beat v1 ridge on held-out teacher games): "
          f"{'PASS' if pre_check else 'FAIL'} (best={best_name})")

    # Save the best v2 (retrained on ALL teacher games [+ v1 for mixed] so the
    # arena artifact uses every available game; the held-out numbers above are
    # the honest generalization estimate).
    final_frame = (pd.concat([teacher_df, v1_df], ignore_index=True)
                   if best_name == "v2_mixed" else teacher_df)
    final_model = fit_ridge(final_frame)
    artifact = {
        "model_name": f"{best_name}_ridge",
        "model": final_model,
        "feature_names": [c[len("f_"):] for c in feature_cols],
        "target": f"final_score / {TARGET_SCALE} (standard scoring)",
        "datasets": {"teacher": str(args.teacher),
                     "v1": str(args.v1) if best_name == "v2_mixed" else None},
        "split": {"held_out_teacher_games": sorted(test_games),
                  "split_seed": args.split_seed},
        "metrics": results,
        "gate_c_precheck": bool(pre_check),
    }
    artifact_path = out_dir / f"value_v2_{best_name}.joblib"
    joblib.dump(artifact, artifact_path)
    (out_dir / "report.json").write_text(
        json.dumps({k: v for k, v in artifact.items() if k != "model"},
                   indent=2, default=str), encoding="utf-8")
    print(f"artifact -> {artifact_path}\nreport -> {out_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
