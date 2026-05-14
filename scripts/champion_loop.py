#!/usr/bin/env python
"""Champion Self-Improvement Loop.

Runs repeated arena generations where the champion competes against a
randomized pool of challengers (previous champion checkpoints, heuristic/
random baselines, and MCTS variants with different hyper-parameters).

After each generation:
  - TrueSkill ratings are updated for all agents and persisted across runs
  - Snapshot data (including se_ state-evaluator features) is accumulated
  - Every REFIT_INTERVAL generations the evaluator phase weights are
    re-derived via per-phase linear regression on accumulated snapshots
  - A challenger variant that beats the champion in >60% h2h is promoted
  - A detailed markdown progress report is written

Goal: Drive the champion's TrueSkill conservative estimate (μ - 3σ)
steadily upward until it reliably dominates human-level play.

Usage:
    # run N generations (default: 1 generation, 20 games each)
    python scripts/champion_loop.py [--generations N] [--games-per-gen G]

    # print history without running
    python scripts/champion_loop.py --show

    # force a weight re-fit from accumulated snapshot data
    python scripts/champion_loop.py --refit
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.tournament.trueskill_rating import TrueSkillTracker
from mcts.state_evaluator import DEFAULT_WEIGHTS, FEATURE_NAMES, PHASE_EARLY_THRESHOLD, PHASE_LATE_THRESHOLD

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path("data")
STATE_FILE = DATA_DIR / "champion_state.json"
SNAPSHOT_CSV = DATA_DIR / "champion_snapshots.csv"
PROGRESS_MD = DATA_DIR / "champion_progress.md"
ARENA_RUN_ROOT = "arena_runs/champion_loop"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SE_FEATURE_COLS = [f"se_{f}" for f in FEATURE_NAMES]

# How many generations between evaluator weight re-fits
REFIT_INTERVAL = 3
# Minimum snapshot rows required before attempting re-fit
MIN_ROWS_FOR_REFIT = 200
# Maximum weight magnitude after normalisation
WEIGHT_SCALE = 0.30

# Number of most-recent checkpoints to keep in the active pool
MAX_CHECKPOINTS_IN_POOL = 3

# Champion agent name (stable across all generations for TrueSkill tracking)
CHAMPION_ID = "champion"

# H2H win-rate threshold for promoting a challenger variant to champion
PROMOTION_THRESHOLD = 0.60
# Minimum head-to-head game comparisons required before a promotion can fire
MIN_PROMOTION_GAMES = 6

# TrueSkill μ target representing "reliably beats a human player".
# This is a calibration reference, not a real participant in the tournament.
# Initial estimate: a solid Blokus-experienced human scores ~35 μ when rated
# against agents at the default TrueSkill μ=25 baseline.  Revise as real
# human-vs-agent data accumulates.
HUMAN_BENCHMARK_MU = 35.0

# ---------------------------------------------------------------------------
# Champion starting configuration (Challenge Champion profile as baseline)
# ---------------------------------------------------------------------------

BASE_CHAMPION_PARAMS: Dict[str, Any] = {
    "type": "mcts",
    "thinking_time_ms": 500,
    "params": {
        "deterministic_time_budget": True,
        "iterations_per_ms": 10.0,
        "exploration_constant": 1.414,
        "rollout_policy": "random",
        "rollout_cutoff_depth": 5,
        "minimax_backup_alpha": 0.25,
        "rave_enabled": True,
        "rave_k": 1000,
        "progressive_widening_enabled": True,
        "pw_c": 2.0,
        "pw_alpha": 0.5,
        "adaptive_rollout_depth_enabled": True,
        "adaptive_rollout_depth_base": 5,
        "adaptive_rollout_depth_avg_bf": 80.0,
        "state_eval_phase_weights": None,
    },
}

# ---------------------------------------------------------------------------
# Challenger pool: MCTS variants that test different hypotheses
# ---------------------------------------------------------------------------

MCTS_VARIANTS: List[Dict[str, Any]] = [
    {"id": "mcts_high_c",          "params_override": {"exploration_constant": 2.5}},
    {"id": "mcts_low_c",           "params_override": {"exploration_constant": 0.7}},
    {"id": "mcts_heuristic_roll",  "params_override": {"rollout_policy": "heuristic"}},
    {"id": "mcts_deep_cutoff",     "params_override": {"rollout_cutoff_depth": 15,
                                                         "adaptive_rollout_depth_enabled": False}},
    {"id": "mcts_no_cutoff",       "params_override": {"rollout_cutoff_depth": None,
                                                         "adaptive_rollout_depth_enabled": False}},
    {"id": "mcts_high_rave",       "params_override": {"rave_k": 5000}},
    {"id": "mcts_no_rave",         "params_override": {"rave_enabled": False}},
    {"id": "mcts_minimax",         "params_override": {"minimax_backup_alpha": 0.5}},
    {"id": "mcts_loss_avoid",      "params_override": {"loss_avoidance_enabled": True,
                                                         "loss_avoidance_threshold": -30.0}},
    {"id": "mcts_sufficiency",     "params_override": {"sufficiency_threshold_enabled": True}},
    {"id": "mcts_opp_model",       "params_override": {"opponent_modeling_enabled": True,
                                                         "alliance_detection_enabled": True}},
    {"id": "mcts_fast_iters",      "params_override": {"thinking_time_ms": 250}},
    {"id": "mcts_slow_iters",      "params_override": {"thinking_time_ms": 1000}},
]


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def _default_state() -> Dict[str, Any]:
    return {
        "generation": 0,
        "champion_params": copy.deepcopy(BASE_CHAMPION_PARAMS),
        "trueskill_ratings": {},
        "checkpoints": [],   # {"generation": N, "id": str, "mu": float, "params": dict}
        "history": [],       # per-generation records
        "total_snapshot_rows": 0,
        "last_refit_generation": -1,
        "promotions": [],    # log of champion promotions
    }


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        with STATE_FILE.open() as f:
            state = json.load(f)
        # Back-compat: add promotions key if missing
        state.setdefault("promotions", [])
        return state
    return _default_state()


def save_state(state: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# TrueSkill helpers
# ---------------------------------------------------------------------------

def build_tracker(state: Dict[str, Any]) -> TrueSkillTracker:
    tracker = TrueSkillTracker()
    for agent_id, rating in state.get("trueskill_ratings", {}).items():
        tracker._ratings[agent_id] = tracker._model.rating(
            mu=float(rating["mu"]),
            sigma=float(rating["sigma"]),
        )
        tracker._games_played[agent_id] = int(rating.get("games_played", 0))
    return tracker


def persist_tracker(tracker: TrueSkillTracker, state: Dict[str, Any]) -> None:
    state["trueskill_ratings"] = {}
    for agent_id in tracker.agent_ids:
        r = tracker.get_rating(agent_id)
        state["trueskill_ratings"][agent_id] = r


# ---------------------------------------------------------------------------
# Agent config builders
# ---------------------------------------------------------------------------

def _build_champion_agent_config(params: Dict[str, Any]) -> Dict[str, Any]:
    """Produce an arena-runner agent dict for the champion."""
    cfg = copy.deepcopy(params)
    cfg["name"] = CHAMPION_ID
    return cfg


def _build_checkpoint_agent_config(checkpoint: Dict[str, Any]) -> Dict[str, Any]:
    cfg = copy.deepcopy(checkpoint["params"])
    cfg["name"] = checkpoint["id"]
    return cfg


def _build_variant_agent_config(
    base_params: Dict[str, Any], variant: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge base champion params with a variant's override, return agent config."""
    cfg = copy.deepcopy(base_params)
    override = variant.get("params_override", {})
    # Handle thinking_time_ms override at top level
    if "thinking_time_ms" in override:
        cfg["thinking_time_ms"] = override.pop("thinking_time_ms")
    cfg["params"].update(override)
    cfg["name"] = variant["id"]
    return cfg


def _build_baseline_agent_config(agent_type: str) -> Dict[str, Any]:
    return {"name": agent_type, "type": agent_type, "thinking_time_ms": None, "params": {}}


# ---------------------------------------------------------------------------
# Challenger pool selection
# ---------------------------------------------------------------------------

def select_challengers(
    state: Dict[str, Any],
    base_params: Dict[str, Any],
    rng: random.Random,
) -> List[Dict[str, Any]]:
    """Choose 3 challengers for this generation.

    Strategy:
      - Slot 0: always heuristic (strong baseline)
      - Slot 1: random checkpoint if available, else random agent as simpler baseline
      - Slot 2: random MCTS variant (different from slot 1 if possible)
    """
    challengers: List[Dict[str, Any]] = []

    # Slot 0: heuristic baseline
    challengers.append(_build_baseline_agent_config("heuristic"))

    # Gather recent checkpoints
    checkpoints = state.get("checkpoints", [])
    recent_ckpts = checkpoints[-MAX_CHECKPOINTS_IN_POOL:]

    # Slot 1: checkpoint (if any) or random agent as the simpler baseline
    if recent_ckpts:
        ckpt = rng.choice(recent_ckpts)
        challengers.append(_build_checkpoint_agent_config(ckpt))
    else:
        challengers.append(_build_baseline_agent_config("random"))

    # Slot 2: MCTS variant (sample one not already in challengers)
    used_ids = {c["name"] for c in challengers}
    available_variants = [v for v in MCTS_VARIANTS if v["id"] not in used_ids]
    if available_variants:
        variant = rng.choice(available_variants)
        challengers.append(_build_variant_agent_config(base_params, variant))
    else:
        challengers.append(_build_baseline_agent_config("random"))

    return challengers


# ---------------------------------------------------------------------------
# Arena execution
# ---------------------------------------------------------------------------

def _find_run_dir_created_after(output_root: str, after_time: float) -> Optional[str]:
    """Find the most recently created run dir whose mtime is >= after_time."""
    root = Path(output_root)
    if not root.exists():
        return None
    candidates = []
    for p in root.iterdir():
        if p.is_dir() and (p / "summary.json").exists():
            mtime = p.stat().st_mtime
            if mtime >= after_time:
                candidates.append((mtime, str(p)))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def run_generation_arena(
    generation: int,
    champion_cfg: Dict[str, Any],
    challengers: List[Dict[str, Any]],
    num_games: int,
    seed: int,
) -> str:
    """Write a temp arena config and run it. Returns the run directory path."""
    agents = [champion_cfg] + challengers
    arena_config = {
        "agents": agents,
        "num_games": num_games,
        "seed": seed,
        "seat_policy": "randomized",
        "output_root": ARENA_RUN_ROOT,
        "max_turns": 2500,
        "notes": f"champion_loop gen={generation}",
        "snapshots": {
            "enabled": True,
            "strategy": "fixed_ply",
            "checkpoints": [8, 16, 24, 32, 40, 48, 56, 64],
        },
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    config_path = DATA_DIR / f"champion_loop_arena_gen{generation:04d}.json"
    with config_path.open("w") as f:
        json.dump(arena_config, f, indent=2)

    print(f"\n[champion_loop] Generation {generation}: running {num_games} games")
    print(f"  Champion vs: {[c['name'] for c in challengers]}")

    start_time = time.time() - 1.0  # 1-second grace window for clock skew
    cmd = [sys.executable, "scripts/arena.py", "--config", str(config_path)]
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Arena exited with code {result.returncode}")

    run_dir = _find_run_dir_created_after(ARENA_RUN_ROOT, start_time)
    if run_dir is None:
        raise RuntimeError("Could not locate arena output directory created by this run")
    print(f"[champion_loop] Run saved to: {run_dir}")
    return run_dir


# ---------------------------------------------------------------------------
# Results parsing
# ---------------------------------------------------------------------------

def parse_summary(run_dir: str) -> Dict[str, Any]:
    path = Path(run_dir) / "summary.json"
    with path.open() as f:
        return json.load(f)


def _extract_champion_stats(summary: Dict[str, Any]) -> Tuple[float, float]:
    """Return (win_rate, avg_score) for the champion from a summary dict."""
    win_rate = summary.get("win_stats", {}).get(CHAMPION_ID, {}).get("win_rate", 0.0)
    avg_score = summary.get("score_stats", {}).get(CHAMPION_ID, {}).get("mean", 0.0) or 0.0
    return float(win_rate), float(avg_score)


def _extract_pairwise_h2h(
    summary: Dict[str, Any], challengers: List[Dict[str, Any]]
) -> Dict[str, float]:
    """Return champion win-rate vs each challenger from pairwise matchups.

    Win rate here = fraction of head-to-head score comparisons the champion
    won (i.e. champion score > challenger score in games where both played).
    Returns an empty dict if pairwise data is missing.
    """
    pairwise = summary.get("pairwise_matchups", {})
    result: Dict[str, float] = {}
    for cfg in challengers:
        opp = cfg["name"]
        # Keys are sorted alphabetically: champion < most other names
        key_ab = f"{CHAMPION_ID}__vs__{opp}"
        key_ba = f"{opp}__vs__{CHAMPION_ID}"
        if key_ab in pairwise:
            entry = pairwise[key_ab]
            total = entry.get("total", 0)
            if total >= 1:
                result[opp] = float(entry.get("a_beats_b", 0)) / total
        elif key_ba in pairwise:
            entry = pairwise[key_ba]
            total = entry.get("total", 0)
            if total >= 1:
                result[opp] = float(entry.get("b_beats_a", 0)) / total
    return result


def update_trueskill_from_run(tracker: TrueSkillTracker, run_dir: str) -> None:
    """Replay every game in games.jsonl through the TrueSkill tracker."""
    games_path = Path(run_dir) / "games.jsonl"
    if not games_path.exists():
        return
    with games_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            agent_scores = record.get("agent_scores", {})
            if agent_scores:
                tracker.update_game(agent_scores)


# ---------------------------------------------------------------------------
# Champion promotion
# ---------------------------------------------------------------------------

def _find_promotion_candidate(
    h2h_rates: Dict[str, float],
    challengers: List[Dict[str, Any]],
    summary: Dict[str, Any],
    num_games: int,
) -> Optional[Dict[str, Any]]:
    """Return the challenger config to promote, or None.

    A variant is eligible when:
      - Its pairwise win rate vs champion exceeds PROMOTION_THRESHOLD
      - At least MIN_PROMOTION_GAMES head-to-head comparisons were made
      - It is an MCTS type (not heuristic/random — those can't be promoted)
    """
    # Build a lookup from challenger name to config
    cfg_by_name: Dict[str, Dict[str, Any]] = {c["name"]: c for c in challengers}

    best_candidate: Optional[Dict[str, Any]] = None
    best_rate = PROMOTION_THRESHOLD

    for opp, rate in h2h_rates.items():
        cfg = cfg_by_name.get(opp)
        if cfg is None or cfg.get("type") not in (None, "mcts"):
            continue
        # Count how many h2h comparisons there were
        key_ab = f"{CHAMPION_ID}__vs__{opp}"
        key_ba = f"{opp}__vs__{CHAMPION_ID}"
        pairwise = summary.get("pairwise_matchups", {})
        entry = pairwise.get(key_ab) or pairwise.get(key_ba) or {}
        comparisons = entry.get("total", 0)
        if comparisons < MIN_PROMOTION_GAMES:
            continue
        if rate > best_rate:
            best_rate = rate
            best_candidate = cfg

    return best_candidate


def promote_challenger(
    state: Dict[str, Any],
    tracker: TrueSkillTracker,
    candidate: Dict[str, Any],
    h2h_rate: float,
    generation: int,
) -> None:
    """Merge the candidate's params into the champion and log the event."""
    old_params = copy.deepcopy(state["champion_params"])
    new_params = copy.deepcopy(candidate)
    # Preserve champion-specific keys that the variant may not have
    new_params.setdefault("type", "mcts")
    new_params.setdefault("thinking_time_ms", old_params.get("thinking_time_ms", 500))
    new_params.setdefault("params", {})
    # Start from the old champion params and overlay the candidate's params
    merged = copy.deepcopy(old_params)
    for k, v in new_params.get("params", {}).items():
        merged["params"][k] = v
    # Don't carry over the challenger's name as the champion's type config
    merged.pop("name", None)

    state["champion_params"] = merged

    # Increase sigma so TrueSkill can re-converge after the change
    tracker.reset_agent(CHAMPION_ID, increase_sigma=True)

    promotion_record = {
        "generation": generation,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "promoted_from": candidate["name"],
        "h2h_win_rate": h2h_rate,
        "new_params": dict(merged.get("params", {})),
    }
    state["promotions"].append(promotion_record)

    print(
        f"\n[champion_loop] *** PROMOTION *** Gen {generation}: "
        f"'{candidate['name']}' h2h={h2h_rate:.1%} → new champion params merged. "
        f"Champion σ reset for re-convergence."
    )


# ---------------------------------------------------------------------------
# Snapshot accumulation
# ---------------------------------------------------------------------------

def accumulate_snapshots(run_dir: str) -> int:
    """Append snapshot rows from this run to the master CSV. Returns total rows."""
    try:
        import pandas as pd
    except ImportError:
        print("[champion_loop] WARNING: pandas not available; skipping snapshot accumulation")
        return 0

    src = Path(run_dir) / "snapshots.csv"
    if not src.exists():
        return 0

    new_df = pd.read_csv(src)
    new_df = new_df.dropna(subset=["final_score"])

    if SNAPSHOT_CSV.exists():
        existing = pd.read_csv(SNAPSHOT_CSV)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(SNAPSHOT_CSV, index=False)
    return int(len(combined))


# ---------------------------------------------------------------------------
# Evaluator weight re-fitting
# ---------------------------------------------------------------------------

def refit_evaluator_weights() -> Optional[Dict[str, Any]]:
    """Run per-phase linear regression on accumulated snapshots.

    Returns a dict with keys 'phase_weights', 'single_weights', 'r2_by_phase',
    or None if there is insufficient data or sklearn is unavailable.
    """
    try:
        import pandas as pd
        from sklearn.linear_model import LinearRegression
    except ImportError:
        print("[champion_loop] sklearn not available; skipping weight re-fit")
        return None

    if not SNAPSHOT_CSV.exists():
        print("[champion_loop] No snapshot CSV yet; skipping weight re-fit")
        return None

    df = pd.read_csv(SNAPSHOT_CSV)
    df = df.dropna(subset=["final_score"])

    missing = [c for c in SE_FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"[champion_loop] Missing se_ columns {missing}; skipping weight re-fit")
        return None

    if len(df) < MIN_ROWS_FOR_REFIT:
        print(f"[champion_loop] Only {len(df)} snapshot rows (need {MIN_ROWS_FOR_REFIT}); skipping re-fit")
        return None

    print(f"\n[champion_loop] Refitting evaluator weights from {len(df)} snapshot rows ...")

    def _fit_phase(phase_df: Any) -> Tuple[Dict[str, float], float]:
        if len(phase_df) < 50:
            return dict(DEFAULT_WEIGHTS), 0.0
        X = phase_df[SE_FEATURE_COLS].values.astype(float)
        y = phase_df["final_score"].values.astype(float)
        lr = LinearRegression().fit(X, y)
        coefs = lr.coef_
        max_abs = float(np.max(np.abs(coefs))) if np.max(np.abs(coefs)) > 0 else 1.0
        scale = WEIGHT_SCALE / max_abs
        weights = {FEATURE_NAMES[i]: float(coefs[i] * scale) for i in range(len(FEATURE_NAMES))}
        return weights, float(lr.score(X, y))

    occ = df["phase_board_occupancy"] if "phase_board_occupancy" in df.columns else None

    phase_weights: Dict[str, Dict[str, float]] = {}
    r2_by_phase: Dict[str, float] = {}

    if occ is not None:
        phase_masks = {
            "early": occ < PHASE_EARLY_THRESHOLD,
            "mid": (occ >= PHASE_EARLY_THRESHOLD) & (occ < PHASE_LATE_THRESHOLD),
            "late": occ >= PHASE_LATE_THRESHOLD,
        }
        for phase_name, mask in phase_masks.items():
            w, r2 = _fit_phase(df[mask])
            phase_weights[phase_name] = w
            r2_by_phase[phase_name] = r2
            print(f"  Phase '{phase_name}': R²={r2:.4f}, n={int(mask.sum())}")
            for fname, wval in sorted(w.items(), key=lambda x: abs(x[1]), reverse=True):
                if abs(wval) > 0.01:
                    print(f"    {fname:>35s}: {wval:+.4f}")
    else:
        # No occupancy data: fit single global weights and use for all phases
        w, r2 = _fit_phase(df)
        phase_weights = {"early": w, "mid": w, "late": w}
        r2_by_phase = {"early": r2, "mid": r2, "late": r2}
        print(f"  Global fit: R²={r2:.4f}")

    # Single global weights
    X_all = df[SE_FEATURE_COLS].values.astype(float)
    y_all = df["final_score"].values.astype(float)
    lr_all = LinearRegression().fit(X_all, y_all)
    coefs_all = lr_all.coef_
    max_abs_all = float(np.max(np.abs(coefs_all))) if np.max(np.abs(coefs_all)) > 0 else 1.0
    single_weights = {
        FEATURE_NAMES[i]: float(coefs_all[i] * WEIGHT_SCALE / max_abs_all)
        for i in range(len(FEATURE_NAMES))
    }
    r2_global = float(lr_all.score(X_all, y_all))
    print(f"  Global R²={r2_global:.4f}")

    return {
        "phase_weights": phase_weights,
        "single_weights": single_weights,
        "r2_by_phase": r2_by_phase,
        "r2_global": r2_global,
        "rows_used": int(len(df)),
    }


def _save_calibrated_weights(refit: Dict[str, Any]) -> None:
    """Overwrite data/layer6_calibrated_weights.json with new weights."""
    payload = {
        "single_weights": refit["single_weights"],
        "phase_weights": refit["phase_weights"],
        "default_weights": dict(DEFAULT_WEIGHTS),
    }
    weights_path = DATA_DIR / "layer6_calibrated_weights.json"
    with weights_path.open("w") as f:
        json.dump(payload, f, indent=2)
    print(f"[champion_loop] Saved calibrated weights → {weights_path}")


# ---------------------------------------------------------------------------
# Checkpoint management
# ---------------------------------------------------------------------------

def save_champion_checkpoint(state: Dict[str, Any], tracker: TrueSkillTracker) -> None:
    generation = state["generation"]
    ckpt_id = f"ckpt_v{generation}"
    rating = tracker.get_rating(CHAMPION_ID)
    checkpoint = {
        "generation": generation,
        "id": ckpt_id,
        "mu": rating["mu"],
        "sigma": rating["sigma"],
        "params": copy.deepcopy(state["champion_params"]),
    }
    state["checkpoints"].append(checkpoint)
    # Register this checkpoint in TrueSkill with the champion's current rating
    tracker._ratings[ckpt_id] = tracker._model.rating(
        mu=rating["mu"], sigma=rating["sigma"]
    )
    tracker._games_played[ckpt_id] = rating["games_played"]
    print(f"[champion_loop] Checkpoint saved: {ckpt_id} (μ={rating['mu']:.2f})")


# ---------------------------------------------------------------------------
# Progress reporting
# ---------------------------------------------------------------------------

def _champion_rank(tracker: TrueSkillTracker) -> int:
    for entry in tracker.get_leaderboard():
        if entry["agent_id"] == CHAMPION_ID:
            return entry["rank"]
    return -1


def print_leaderboard(tracker: TrueSkillTracker) -> None:
    board = tracker.get_leaderboard()
    print(f"\n{'─'*72}")
    print(f"  {'#':>2}  {'Agent':<32}  {'μ':>6}  {'σ':>5}  {'μ-3σ':>7}  {'Games':>5}")
    print(f"{'─'*72}")
    for entry in board:
        marker = " ★" if entry["agent_id"] == CHAMPION_ID else "  "
        print(
            f"  {entry['rank']:>2}  {entry['agent_id']:<32}  "
            f"{entry['mu']:>6.2f}  {entry['sigma']:>5.2f}  "
            f"{entry['conservative']:>7.2f}  {entry['games_played']:>5}{marker}"
        )
    # Show human benchmark target
    champ_rating = tracker.get_rating(CHAMPION_ID)
    gap = HUMAN_BENCHMARK_MU - champ_rating["mu"]
    gap_str = f"{gap:+.2f}" if gap > 0 else "REACHED ✓"
    print(f"{'─'*72}")
    print(f"  ·· Human benchmark target: μ={HUMAN_BENCHMARK_MU:.1f}  (champion gap: {gap_str})")
    print(f"{'─'*72}")


def write_progress_markdown(
    state: Dict[str, Any],
    tracker: TrueSkillTracker,
    last_h2h: Optional[Dict[str, float]] = None,
    last_challengers: Optional[List[str]] = None,
) -> None:
    lines: List[str] = []
    lines.append("# Champion Self-Improvement Progress\n")
    lines.append(f"_Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n")
    lines.append(f"\n**Generation:** {state['generation']}  ")
    lines.append(f"**Snapshot rows accumulated:** {state.get('total_snapshot_rows', 0)}  ")
    lines.append(f"**Last weight re-fit:** generation {state.get('last_refit_generation', 'never')}\n")

    # Human benchmark progress
    champ_rating = tracker.get_rating(CHAMPION_ID)
    gap = HUMAN_BENCHMARK_MU - champ_rating["mu"]
    lines.append(f"\n### Human Benchmark Target\n")
    lines.append(f"Target μ = {HUMAN_BENCHMARK_MU:.1f} | Champion μ = {champ_rating['mu']:.2f} | ")
    if gap <= 0:
        lines.append("**TARGET REACHED** 🎯\n")
    else:
        lines.append(f"Gap = {gap:.2f} μ points remaining\n")

    # Current leaderboard
    lines.append("\n## TrueSkill Leaderboard\n")
    lines.append("| Rank | Agent | μ | σ | μ-3σ | Games |\n")
    lines.append("|------|-------|---|---|------|-------|\n")
    for entry in tracker.get_leaderboard():
        marker = " ★" if entry["agent_id"] == CHAMPION_ID else ""
        lines.append(
            f"| {entry['rank']} | {entry['agent_id']}{marker} | "
            f"{entry['mu']:.2f} | {entry['sigma']:.2f} | "
            f"{entry['conservative']:.2f} | {entry['games_played']} |\n"
        )
    lines.append(f"| — | _Human benchmark target_ | {HUMAN_BENCHMARK_MU:.1f} | — | — | — |\n")

    # Last generation H2H breakdown
    if last_h2h and last_challengers:
        lines.append("\n## Last Generation Head-to-Head\n")
        lines.append("| Challenger | Champion win % |\n")
        lines.append("|------------|----------------|\n")
        for opp in last_challengers:
            wr = last_h2h.get(opp)
            wr_str = f"{wr:.1%}" if wr is not None else "N/A"
            lines.append(f"| {opp} | {wr_str} |\n")

    # Champion trend
    history = state.get("history", [])
    if history:
        lines.append("\n## Champion TrueSkill Trend\n")
        lines.append("| Gen | μ | σ | μ-3σ | WR% | AvgScore | Challengers | Promoted | Refitted |\n")
        lines.append("|-----|---|---|------|-----|----------|-------------|----------|----------|\n")
        for rec in history:
            lines.append(
                f"| {rec['generation']} "
                f"| {rec['champion_mu']:.2f} "
                f"| {rec['champion_sigma']:.2f} "
                f"| {rec['champion_conservative']:.2f} "
                f"| {rec.get('champion_win_rate', 0)*100:.1f}% "
                f"| {rec.get('champion_avg_score', 0):.1f} "
                f"| {', '.join(rec.get('challengers', []))} "
                f"| {'Yes' if rec.get('challenger_promoted') else 'No'} "
                f"| {'Yes' if rec.get('evaluator_refitted') else 'No'} |\n"
            )

    # Promotion history
    promotions = state.get("promotions", [])
    if promotions:
        lines.append("\n## Champion Promotion History\n")
        lines.append("| Gen | Promoted From | H2H Win Rate | Timestamp |\n")
        lines.append("|-----|--------------|-------------|----------|\n")
        for promo in promotions:
            lines.append(
                f"| {promo['generation']} "
                f"| {promo['promoted_from']} "
                f"| {promo['h2h_win_rate']:.1%} "
                f"| {promo['timestamp'][:19]} |\n"
            )

    # Current champion params summary
    lines.append("\n## Current Champion Parameters\n")
    lines.append("```json\n")
    lines.append(json.dumps(state["champion_params"]["params"], indent=2))
    lines.append("\n```\n")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_MD.write_text("".join(lines), encoding="utf-8")


def show_progress(state: Dict[str, Any]) -> None:
    print(f"\n{'='*72}")
    print(f"  Champion Self-Improvement Progress — Generation {state['generation']}")
    print(f"{'='*72}")
    if not state.get("history"):
        print("  No generations run yet.")
        return

    tracker = build_tracker(state)
    print_leaderboard(tracker)

    history = state.get("history", [])
    print(f"\n  Trend (last {min(5, len(history))} generations):")
    for rec in history[-5:]:
        parts = []
        if rec.get("challenger_promoted"):
            parts.append("[PROMOTED]")
        if rec.get("evaluator_refitted"):
            parts.append("[REFITTED]")
        suffix = " " + " ".join(parts) if parts else ""
        print(
            f"    Gen {rec['generation']:>3}: μ={rec['champion_mu']:.2f}  "
            f"σ={rec['champion_sigma']:.2f}  "
            f"μ-3σ={rec['champion_conservative']:.2f}  "
            f"WR={rec.get('champion_win_rate', 0)*100:.1f}%  "
            f"AvgScore={rec.get('champion_avg_score', 0):.1f}{suffix}"
        )

    promotions = state.get("promotions", [])
    if promotions:
        print(f"\n  Promotions: {len(promotions)}")
        for promo in promotions[-3:]:
            print(
                f"    Gen {promo['generation']}: '{promo['promoted_from']}' "
                f"h2h={promo['h2h_win_rate']:.1%}"
            )
    print()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_loop(args: argparse.Namespace) -> None:
    state = load_state()

    for gen_offset in range(args.generations):
        generation = state["generation"] + gen_offset + 1
        rng = random.Random(generation * 997 + 42)
        seed = generation * 7919

        champion_cfg = _build_champion_agent_config(state["champion_params"])
        challengers = select_challengers(state, state["champion_params"], rng)

        # Save checkpoint of current champion before this generation
        tracker = build_tracker(state)
        if generation > 1 or state.get("checkpoints"):
            save_champion_checkpoint(state, tracker)

        # Run arena
        run_dir = run_generation_arena(
            generation, champion_cfg, challengers, args.games_per_gen, seed
        )

        # Update TrueSkill from individual game records
        update_trueskill_from_run(tracker, run_dir)

        # Accumulate snapshots for evaluator retraining
        total_rows = accumulate_snapshots(run_dir)
        state["total_snapshot_rows"] = total_rows

        # Parse summary for win-rate, score, and pairwise data
        summary = parse_summary(run_dir)
        champ_win_rate, champ_avg_score = _extract_champion_stats(summary)
        h2h_rates = _extract_pairwise_h2h(summary, challengers)

        # Check for champion promotion
        promotion_candidate = _find_promotion_candidate(
            h2h_rates, challengers, summary, args.games_per_gen
        )
        challenger_promoted = False
        if promotion_candidate is not None:
            opp_name = promotion_candidate["name"]
            h2h_rate = h2h_rates.get(opp_name, 0.0)
            promote_challenger(state, tracker, promotion_candidate, h2h_rate, generation)
            challenger_promoted = True

        # Maybe refit evaluator weights
        refit_result = None
        gens_since_refit = generation - state.get("last_refit_generation", -999)
        if (
            total_rows >= MIN_ROWS_FOR_REFIT
            and gens_since_refit >= REFIT_INTERVAL
        ):
            refit_result = refit_evaluator_weights()
            if refit_result:
                state["champion_params"]["params"]["state_eval_phase_weights"] = (
                    refit_result["phase_weights"]
                )
                _save_calibrated_weights(refit_result)
                state["last_refit_generation"] = generation
                # Increase sigma to signal the champion has changed
                tracker.reset_agent(CHAMPION_ID, increase_sigma=True)
                print("[champion_loop] Applied new evaluator weights to champion, reset σ")

        # Record generation history
        champion_rating = tracker.get_rating(CHAMPION_ID)
        gen_record: Dict[str, Any] = {
            "generation": generation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_dir": run_dir,
            "games": args.games_per_gen,
            "challengers": [c["name"] for c in challengers],
            "champion_mu": champion_rating["mu"],
            "champion_sigma": champion_rating["sigma"],
            "champion_conservative": champion_rating["conservative"],
            "champion_games_played": champion_rating["games_played"],
            "champion_win_rate": champ_win_rate,
            "champion_avg_score": champ_avg_score,
            "champion_rank": _champion_rank(tracker),
            "h2h_win_rates": h2h_rates,
            "challenger_promoted": challenger_promoted,
            "evaluator_refitted": refit_result is not None,
            "refit_r2_global": refit_result["r2_global"] if refit_result else None,
            "total_snapshot_rows": total_rows,
        }
        state["history"].append(gen_record)
        state["generation"] = generation

        persist_tracker(tracker, state)
        save_state(state)
        write_progress_markdown(
            state, tracker,
            last_h2h=h2h_rates,
            last_challengers=[c["name"] for c in challengers],
        )

        # Console summary
        print(f"\n[champion_loop] Generation {generation} complete")
        print(
            f"  Champion: μ={champion_rating['mu']:.2f}  "
            f"σ={champion_rating['sigma']:.2f}  "
            f"μ-3σ={champion_rating['conservative']:.2f}  "
            f"WR={champ_win_rate*100:.1f}%  "
            f"AvgScore={champ_avg_score:.1f}  "
            f"Rank=#{_champion_rank(tracker)}"
        )
        if h2h_rates:
            h2h_str = "  H2H: " + "  ".join(
                f"{opp}={wr:.0%}" for opp, wr in sorted(h2h_rates.items())
            )
            print(h2h_str)
        print_leaderboard(tracker)

        if refit_result:
            print(
                f"  Evaluator re-fitted: global R²={refit_result['r2_global']:.4f}, "
                f"{refit_result['rows_used']} rows"
            )

    print(f"\n[champion_loop] All {args.generations} generation(s) complete.")
    print(f"  Progress report: {PROGRESS_MD}")
    print(f"  State: {STATE_FILE}")


def force_refit(state: Dict[str, Any]) -> None:
    tracker = build_tracker(state)
    refit_result = refit_evaluator_weights()
    if refit_result:
        state["champion_params"]["params"]["state_eval_phase_weights"] = (
            refit_result["phase_weights"]
        )
        _save_calibrated_weights(refit_result)
        state["last_refit_generation"] = state["generation"]
        tracker.reset_agent(CHAMPION_ID, increase_sigma=True)
        persist_tracker(tracker, state)
        save_state(state)
        write_progress_markdown(state, tracker)
        print("[champion_loop] Force re-fit complete.")
    else:
        print("[champion_loop] Re-fit skipped (insufficient data or missing libraries).")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Champion Self-Improvement Loop — drive MCTS to beat human players"
    )
    parser.add_argument(
        "--generations", type=int, default=1,
        help="Number of generations to run (default: 1)"
    )
    parser.add_argument(
        "--games-per-gen", type=int, default=20,
        help="Arena games per generation (default: 20)"
    )
    parser.add_argument(
        "--show", action="store_true",
        help="Print progress without running any games"
    )
    parser.add_argument(
        "--refit", action="store_true",
        help="Force evaluator weight re-fit from accumulated snapshots and exit"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = load_state()

    if args.show:
        show_progress(state)
        return

    if args.refit:
        force_refit(state)
        return

    run_loop(args)


if __name__ == "__main__":
    main()
