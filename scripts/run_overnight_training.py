#!/usr/bin/env python
"""Overnight training/evaluation orchestrator.

A *thin* wrapper that chains the existing, individually-tested scripts into a
single, reproducible, resumable overnight run. It does NOT reimplement any
training, search, or scoring logic — it only sequences:

    1. scripts/generate_training_data.py   (optional, --generate-data)
    2. scripts/train_eval_model.py          (optional, --train-eval)
    3. scripts/champion_gauntlet.py         (validation; the default stage)

Everything lands in one timestamped run directory with per-stage logs and a
``manifest.json`` so the morning-after review is a single ``cat``.

Safety contract (see docs/03-implementation/TRAINING_AND_OVERNIGHT_RUNS.md):
  * Champion promotion NEVER happens unless ``--promote`` is passed explicitly.
    Without it the gauntlet evaluates and ranks but leaves the registry alone.
  * ``--dry-run`` prints the exact command plan and writes nothing.
  * ``--resume`` skips any stage whose expected output already exists.

Examples
--------
    # See what would run, change nothing:
    python scripts/run_overnight_training.py --dry-run

    # Validation-only overnight gauntlet (no data gen, no promotion):
    python scripts/run_overnight_training.py \
        --seeds 20260617 20260618 20260619 --games-per-seed 60

    # Full pipeline: generate data -> fit evaluator -> gauntlet, still no promote:
    python scripts/run_overnight_training.py --generate-data --train-eval \
        --num-games 400 --agent-type mcts

    # Promote only after a human has read the summary and re-runs with the flag:
    python scripts/run_overnight_training.py --gauntlet --promote
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


# ---------------------------------------------------------------------------
# Pipeline planning (pure, unit-testable)
# ---------------------------------------------------------------------------

def build_pipeline(args: argparse.Namespace, run_dir: Path) -> List[Dict[str, Any]]:
    """Return an ordered list of stage descriptors for the requested run.

    Each stage is a dict with ``name``, ``cmd`` (argv list), ``log`` (path),
    and ``produces`` (an output path used for ``--resume`` skip detection, or
    ``None`` when the stage has no single resumable artifact).

    This function is intentionally side-effect free so it can be unit tested
    and so ``--dry-run`` can render the plan without touching the filesystem.
    """
    py = sys.executable or "python"
    stages: List[Dict[str, Any]] = []

    snapshots = run_dir / "snapshots.parquet"
    eval_model = run_dir / "eval_candidate.pkl"

    if args.generate_data:
        stages.append(
            {
                "name": "generate_data",
                "cmd": [
                    py,
                    str(SCRIPTS / "generate_training_data.py"),
                    "--num-games", str(args.num_games),
                    "--agent-type", args.agent_type,
                    "--thinking-time-ms", str(args.thinking_time_ms),
                    "--checkpoint-interval", str(args.checkpoint_interval),
                    "--workers", str(args.workers),
                    "--seed", str(args.seeds[0]),
                    "--output", str(snapshots),
                ],
                "log": run_dir / "01_generate_data.log",
                "produces": snapshots,
            }
        )

    if args.train_eval:
        stages.append(
            {
                "name": "train_eval",
                "cmd": [
                    py,
                    str(SCRIPTS / "train_eval_model.py"),
                    "--data", str(snapshots),
                    "--model-type", args.model_type,
                    "--output", str(eval_model),
                    "--seed", str(args.seeds[0]),
                ],
                "log": run_dir / "02_train_eval.log",
                "produces": eval_model,
            }
        )

    if args.gauntlet:
        cmd = [
            py,
            str(SCRIPTS / "champion_gauntlet.py"),
            "--seeds", *[str(s) for s in args.seeds],
            "--num-games", str(args.games_per_seed),
            "--seat-policy", args.seat_policy,
            "--output-root", str(run_dir / "gauntlets"),
        ]
        if args.thinking_time_ms_gauntlet is not None:
            cmd += ["--thinking-time-ms", str(args.thinking_time_ms_gauntlet)]
        # Promotion is opt-in ONLY. Default runs never touch the registry.
        if args.promote:
            cmd.append("--promote")
        stages.append(
            {
                "name": "gauntlet",
                "cmd": cmd,
                "log": run_dir / "03_gauntlet.log",
                "produces": None,  # gauntlet always makes a fresh timestamped dir
            }
        )

    return stages


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _should_skip(stage: Dict[str, Any], resume: bool) -> bool:
    produces = stage.get("produces")
    return bool(resume and produces is not None and Path(produces).exists())


def run_stage(stage: Dict[str, Any]) -> int:
    """Run one stage, teeing stdout/stderr to its log file. Returns exit code."""
    log_path: Path = stage["log"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[overnight] === {stage['name']} ===", flush=True)
    print(f"[overnight] cmd: {' '.join(stage['cmd'])}", flush=True)
    print(f"[overnight] log: {log_path}", flush=True)
    t0 = time.time()
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"# {stage['name']} :: {' '.join(stage['cmd'])}\n")
        log.flush()
        proc = subprocess.Popen(
            stage["cmd"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
            log.flush()
        proc.wait()
    elapsed = time.time() - t0
    print(f"[overnight] {stage['name']} exit={proc.returncode} ({elapsed:.1f}s)", flush=True)
    return proc.returncode


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Orchestrate an overnight train/evaluate/gauntlet run.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Stage toggles. Gauntlet (validation) is on by default; data gen + eval fit
    # are opt-in because they are the long, optional pieces of the pipeline.
    p.add_argument("--generate-data", action="store_true", help="Run self-play data generation stage.")
    p.add_argument("--train-eval", action="store_true", help="Fit a learned evaluator from generated data.")
    p.add_argument(
        "--no-gauntlet",
        dest="gauntlet",
        action="store_false",
        help="Skip the champion gauntlet validation stage.",
    )
    p.set_defaults(gauntlet=True)

    # Run identity / IO.
    p.add_argument("--output-dir", default=None, help="Run directory (default: arena_runs/overnight/<ts>).")
    p.add_argument("--dry-run", action="store_true", help="Print the command plan and exit without running.")
    p.add_argument("--resume", action="store_true", help="Skip stages whose output artifact already exists.")

    # Data-gen knobs.
    p.add_argument("--num-games", type=int, default=400, help="Self-play games for data generation.")
    p.add_argument(
        "--agent-type",
        default="mcts",
        choices=["mcts", "heuristic", "random"],
        help="Agent for self-play data (mcts recommended; fast_mcts is archived/invalid).",
    )
    p.add_argument("--thinking-time-ms", type=int, default=100, help="Per-move budget for data generation.")
    p.add_argument("--checkpoint-interval", type=int, default=4, help="Snapshot every N plies during data gen.")
    p.add_argument("--workers", type=int, default=4, help="Parallel workers for data generation.")
    p.add_argument(
        "--model-type",
        default="pairwise_gbt_phase",
        choices=["pairwise_logreg", "pairwise_gbt_phase"],
        help="Evaluator model family for the train stage.",
    )

    # Gauntlet knobs.
    p.add_argument("--seeds", type=int, nargs="+", default=[20260617, 20260618, 20260619], help="Run seeds.")
    p.add_argument("--games-per-seed", type=int, default=60, help="Gauntlet games per seed.")
    p.add_argument("--seat-policy", choices=["randomized", "round_robin"], default="round_robin")
    p.add_argument(
        "--thinking-time-ms-gauntlet",
        type=int,
        default=None,
        help="Override every gauntlet candidate's thinking_time_ms (use small values for smoke tests).",
    )

    # Promotion is guarded: explicit opt-in only.
    p.add_argument(
        "--promote",
        action="store_true",
        help="Allow the gauntlet to promote a champion IF all gates pass. Off by default.",
    )

    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.output_dir) if args.output_dir else (REPO_ROOT / "arena_runs" / "overnight" / ts)

    stages = build_pipeline(args, run_dir)
    if not stages:
        print("[overnight] No stages selected. Nothing to do.", flush=True)
        return 0

    print("=" * 72)
    print(f"[overnight] run_dir: {run_dir}")
    print(f"[overnight] promote: {args.promote}  (registry is left untouched unless True)")
    print(f"[overnight] stages:  {[s['name'] for s in stages]}")
    print("=" * 72)
    for s in stages:
        print(f"  - {s['name']}: {' '.join(s['cmd'])}")

    if args.dry_run:
        print("\n[overnight] --dry-run set: no commands executed, no files written.")
        return 0

    run_dir.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {
        "run_dir": str(run_dir),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "promote_requested": args.promote,
        "args": vars(args),
        "stages": [],
    }

    for stage in stages:
        if _should_skip(stage, args.resume):
            print(f"[overnight] resume: skipping {stage['name']} (output exists: {stage['produces']})", flush=True)
            manifest["stages"].append({"name": stage["name"], "status": "skipped_resume"})
            continue
        code = run_stage(stage)
        manifest["stages"].append(
            {
                "name": stage["name"],
                "status": "ok" if code == 0 else "failed",
                "exit_code": code,
                "cmd": stage["cmd"],
                "log": str(stage["log"]),
            }
        )
        if code != 0:
            manifest["aborted_at"] = stage["name"]
            _write_manifest(run_dir, manifest)
            print(f"[overnight] ABORT: stage '{stage['name']}' failed (exit {code}). "
                  f"Fix and re-run with --resume.", flush=True)
            return code

    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_manifest(run_dir, manifest)
    print(f"\n[overnight] DONE. Manifest: {run_dir / 'manifest.json'}")
    if not args.promote:
        print("[overnight] Reminder: no champion was promoted (run with --promote after "
              "reviewing the gauntlet summary to promote a validated winner).")
    return 0


def _write_manifest(run_dir: Path, manifest: Dict[str, Any]) -> None:
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
