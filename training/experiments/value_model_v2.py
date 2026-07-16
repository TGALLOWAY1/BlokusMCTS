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

Volume mode (Phase 6 path 1, EXP-009): pass --bulk with additional
teacher-record-format dirs (state-carrying, so the CURRENT feature set is
extractable) to train at volume. Adds feature-set-controlled conditions —
volume_full (all features) vs volume_45 (rich_blokus_v1 columns) on the same
rows isolates the v2 feature block's contribution at equal data. Held-out
evaluation stays on the SAME held-out teacher games (same split seed) so
results are comparable across runs.

    python -m training.experiments.value_model_v2 \
        --bulk data/value_dataset_v2 --out training/artifacts/value_models/v4
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


def extract_teacher_frame(dataset_dir: Path,
                          cache_dir: Optional[Path] = None) -> pd.DataFrame:
    """One row per (recorded state, player perspective) with rich features.

    Extraction is deterministic given the dataset and feature-set version, so
    an optional cache_dir stores the frame as CSV keyed on dataset name +
    FEATURE_SET_VERSION (bulk dirs take minutes to extract).
    """
    from training.rich_features import (
        FEATURE_SET_VERSION, RICH_FEATURE_NAMES, FeatureCache, extract_rich_features)

    cache_path = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{dataset_dir.name}.{FEATURE_SET_VERSION}.features.csv"
        if cache_path.exists():
            return pd.read_csv(cache_path)

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
    frame = pd.DataFrame(rows)
    if cache_path is not None:
        frame.to_csv(cache_path, index=False)
    return frame


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
    parser.add_argument("--bulk", nargs="*", default=[],
                        help="additional teacher-record-format dirs used as TRAINING "
                             "data only (volume conditions); evaluation stays on the "
                             "held-out --teacher games")
    parser.add_argument("--frame-cache", default=None,
                        help="dir for cached extracted feature frames (CSV, keyed on "
                             "dataset name + feature-set version)")
    parser.add_argument("--out", default="training/artifacts/value_models/v2")
    parser.add_argument("--test-frac", type=float, default=0.25)
    parser.add_argument("--split-seed", type=int, default=20260716)
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(args.frame_cache) if args.frame_cache else None

    print("extracting teacher features...", flush=True)
    teacher_df = extract_teacher_frame(Path(args.teacher), cache_dir=cache_dir)
    bulk_frames = []
    for bulk_dir in args.bulk:
        print(f"extracting bulk features: {bulk_dir} ...", flush=True)
        bulk_frames.append(extract_teacher_frame(Path(bulk_dir), cache_dir=cache_dir))
    bulk_df = (pd.concat(bulk_frames, ignore_index=True)
               if bulk_frames else pd.DataFrame(columns=teacher_df.columns))
    v1_df = load_v1_frame(Path(args.v1))
    feature_cols = [c for c in teacher_df.columns if c.startswith("f_")]
    # v1 CSV rows may predate feature-set extensions; mixed conditions use the
    # column intersection (v1_cols below), teacher-only conditions the full set.
    print(f"teacher rows: {len(teacher_df)} ({teacher_df['game_id'].nunique()} games); "
          f"bulk rows: {len(bulk_df)} ({bulk_df['game_id'].nunique() if len(bulk_df) else 0} games); "
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

    # Feature-set control: v1 CSV rows only carry the 45 rich_blokus_v1
    # columns (no states to re-extract from), so mixed conditions train on
    # the 45-column intersection; teacher-only conditions can use the full
    # current feature set (51 under rich_blokus_v2).
    v1_cols = [c for c in feature_cols if c in v1_df.columns]

    def fit_ridge_cols(frame: pd.DataFrame, cols: List[str]):
        model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        model.fit(frame[cols].to_numpy(dtype=float),
                  (frame["final_score"] / TARGET_SCALE).to_numpy(dtype=float))
        return model

    # Each condition: (training frame from the TRAIN teacher split, columns).
    # The final artifact retrains the winning condition with the full teacher
    # frame substituted for the train split (see frame_for below).
    meta_cols = ["game_id", "ply", "final_score"]

    def frame_for(name: str, teacher_part: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        if name == "teacher_only_full":
            return teacher_part, feature_cols
        if name == "teacher_only_45":
            return teacher_part, v1_cols
        if name == "mixed_45":
            return (pd.concat([teacher_part[v1_cols + meta_cols], v1_df],
                              ignore_index=True), v1_cols)
        if name == "volume_full":
            return (pd.concat([teacher_part, bulk_df], ignore_index=True),
                    feature_cols)
        if name == "volume_45":
            return (pd.concat([teacher_part, bulk_df], ignore_index=True), v1_cols)
        if name == "volume_plus_v1_45":
            return (pd.concat([teacher_part[v1_cols + meta_cols],
                               bulk_df[v1_cols + meta_cols], v1_df],
                              ignore_index=True), v1_cols)
        raise ValueError(name)

    condition_names = ["teacher_only_full", "teacher_only_45", "mixed_45"]
    if len(bulk_df):
        # volume_full vs volume_45 on identical rows isolates the current
        # feature block's contribution at equal (state-carrying) data volume.
        condition_names += ["volume_full", "volume_45", "volume_plus_v1_45"]

    conditions: Dict[str, Tuple[object, List[str]]] = {}
    for name in condition_names:
        frame, cols = frame_for(name, teacher_train)
        conditions[name] = (fit_ridge_cols(frame, cols), cols)
    v1_artifact = joblib.load(args.v1_artifact)
    v1_feat_cols = [f"f_{n}" for n in v1_artifact["feature_names"]]
    conditions["v1_ridge_baseline"] = (v1_artifact["model"], v1_feat_cols)

    print("held-out evaluation (held-out TEACHER games):")
    results = {}
    for name, (model, cols) in conditions.items():
        results[name] = evaluate(name, model, teacher_test, cols)

    baseline = results["v1_ridge_baseline"]
    candidates = {k: v for k, v in results.items() if k != "v1_ridge_baseline"}
    best_name = max(candidates, key=lambda k: candidates[k]["pairwise_rank_accuracy"])
    best = results[best_name]
    pre_check = (best["pairwise_rank_accuracy"] > baseline["pairwise_rank_accuracy"]
                 and best["held_out_r2"] > baseline["held_out_r2"])
    print(f"\nGate-C pre-check (beat v1 ridge on held-out teacher games): "
          f"{'PASS' if pre_check else 'FAIL'} (best={best_name})")

    # Save the best condition retrained on ALL its training data (held-out
    # numbers above are the honest generalization estimate).
    final_frame, best_cols = frame_for(best_name, teacher_df)
    final_model = fit_ridge_cols(final_frame, best_cols)
    uses_v1 = best_name in ("mixed_45", "volume_plus_v1_45")
    artifact = {
        "model_name": f"{best_name}_ridge",
        "model": final_model,
        "feature_names": [c[len("f_"):] for c in best_cols],
        "target": f"final_score / {TARGET_SCALE} (standard scoring)",
        "datasets": {"teacher": str(args.teacher),
                     "bulk": list(args.bulk) if best_name.startswith("volume") else None,
                     "v1": str(args.v1) if uses_v1 else None},
        "split": {"held_out_teacher_games": sorted(test_games),
                  "split_seed": args.split_seed},
        "metrics": results,
        "gate_c_precheck": bool(pre_check),
    }
    artifact_path = out_dir / f"value_{best_name}.joblib"
    joblib.dump(artifact, artifact_path)
    (out_dir / "report.json").write_text(
        json.dumps({k: v for k, v in artifact.items() if k != "model"},
                   indent=2, default=str), encoding="utf-8")
    print(f"artifact -> {artifact_path}\nreport -> {out_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
