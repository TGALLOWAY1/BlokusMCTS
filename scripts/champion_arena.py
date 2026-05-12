#!/usr/bin/env python
"""Champion Arena — continuous self-improvement loop for the best MCTS agent.

Runs the current champion against a randomized pool of strategy checkpoints.
Every game captures board-state snapshots for evaluator retraining.
TrueSkill ratings persist across runs; the champion is promoted automatically
when a challenger's conservative rating surpasses it with enough evidence.
Every REFIT_INTERVAL runs, per-phase linear regression re-derives the
state-evaluator weights from accumulated snapshot data and applies them to
the champion's configuration.

Detailed per-run reports land in data/champion_reports/. A cumulative history
and TrueSkill leaderboard are persisted in data/champion_arena_state.json.

Usage:
    python scripts/champion_arena.py                     # 40 games, auto pool
    python scripts/champion_arena.py --num-games 20
    python scripts/champion_arena.py --generations 5     # 5 back-to-back runs
    python scripts/champion_arena.py --pool random heuristic pool_deploy_hard
    python scripts/champion_arena.py --show              # print history, no run
    python scripts/champion_arena.py --no-promote        # skip auto-promotion
    python scripts/champion_arena.py --refit             # force weight re-fit
    python scripts/champion_arena.py --seed 12345        # reproducible run
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
CHAMPION_STATE_PATH = "data/champion_arena_state.json"
REPORTS_DIR = "data/champion_reports"
TEMP_CONFIG_PATH = "data/_champion_arena_tmp.json"
SNAPSHOT_CSV = Path("data/champion_arena_snapshots.csv")

DEFAULT_NUM_GAMES = 40
DEFAULT_POOL_SIZE = 3          # agents alongside champion per game (total = 4)
MIN_GAMES_FOR_PROMOTION = 20   # challenger needs this many games before promotion check
REFIT_INTERVAL = 3             # runs between evaluator weight re-fits
MIN_ROWS_FOR_REFIT = 200       # minimum snapshot rows before attempting re-fit
WEIGHT_SCALE = 0.30            # max weight magnitude after normalisation

# Human-proxy win-rate target (champion must beat pool_heuristic at this rate to
# be considered "human-competitive"; the heuristic agent models a strong rule-following
# human who always plays the highest-scoring legal move).
HUMAN_PROXY_NAME = "pool_heuristic"
HUMAN_COMPETITIVE_WINRATE = 0.55   # 55 %+ against the heuristic proxy


# ---------------------------------------------------------------------------
# Best champion configuration — full Layer 1-9 stack with calibrated weights
# ---------------------------------------------------------------------------
_SINGLE_WEIGHTS: Dict[str, float] = {
    "squares_placed": 0.0295,
    "remaining_piece_area": -0.0295,
    "accessible_corners": 0.243,
    "reachable_empty_squares": 0.081,
    "largest_remaining_piece_size": -0.231,
    "opponent_avg_mobility": -0.3,
    "center_proximity": 0.0,
    "territory_enclosure_area": 0.0,
}

_PHASE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "early": {
        "squares_placed": -0.176,
        "remaining_piece_area": 0.176,
        "accessible_corners": 0.3,
        "reachable_empty_squares": 0.0,
        "largest_remaining_piece_size": 0.0,
        "opponent_avg_mobility": -0.053,
        "center_proximity": 0.0,
        "territory_enclosure_area": 0.0,
    },
    "mid": {
        "squares_placed": -0.004,
        "remaining_piece_area": 0.004,
        "accessible_corners": 0.3,
        "reachable_empty_squares": 0.228,
        "largest_remaining_piece_size": -0.238,
        "opponent_avg_mobility": -0.203,
        "center_proximity": 0.0,
        "territory_enclosure_area": 0.0,
    },
    "late": {
        "squares_placed": 0.3,
        "remaining_piece_area": -0.3,
        "accessible_corners": 0.176,
        "reachable_empty_squares": 0.134,
        "largest_remaining_piece_size": -0.085,
        "opponent_avg_mobility": -0.063,
        "center_proximity": 0.0,
        "territory_enclosure_area": 0.0,
    },
}

CHAMPION_INITIAL_CONFIG: Dict[str, Any] = {
    "name": "champion",
    "type": "mcts",
    "thinking_time_ms": 500,
    "params": {
        "deterministic_time_budget": True,
        "iterations_per_ms": 0.15,   # ~75 iters @ full L9 ~70 iter/s ≈ 1.1 s/move
        "exploration_constant": 1.414,
        "use_transposition_table": True,
        # Layer 3: Progressive Widening
        "progressive_widening_enabled": True,
        "pw_c": 2.0,
        "pw_alpha": 0.5,
        # Layer 4: Simulation strategy
        "rollout_policy": "random",
        "rollout_cutoff_depth": 5,
        "minimax_backup_alpha": 0.25,
        # Layer 5: RAVE
        "rave_enabled": True,
        "rave_k": 1000,
        # Layer 6: Phase-calibrated evaluation
        "state_eval_weights": _SINGLE_WEIGHTS,
        "state_eval_phase_weights": _PHASE_WEIGHTS,
        # Layer 7: Opponent modeling
        "opponent_modeling_enabled": True,
        "alliance_detection_enabled": True,
        "alliance_threshold": 2.0,
        "kingmaker_detection_enabled": True,
        "kingmaker_score_gap": 15,
        # Layer 9: Meta-optimisation
        "adaptive_rollout_depth_enabled": True,
        "adaptive_rollout_depth_base": 5,
        "adaptive_rollout_depth_avg_bf": 80.0,
        "adaptive_exploration_enabled": True,
        "adaptive_exploration_base": 1.414,
        "adaptive_exploration_avg_bf": 80.0,
        "sufficiency_threshold_enabled": True,
        "loss_avoidance_enabled": True,
        "loss_avoidance_threshold": -50.0,
    },
}


# ---------------------------------------------------------------------------
# Pool catalog — named strategy checkpoints. Names are stable across runs so
# TrueSkill ratings accumulate. Add new entries here as new strategies emerge.
# ---------------------------------------------------------------------------
POOL_CATALOG: List[Dict[str, Any]] = [
    # --- Baselines (rating anchors & human proxies) ---
    {"name": "pool_random",    "type": "random",    "thinking_time_ms": None, "params": {}},
    {"name": "pool_heuristic", "type": "heuristic", "thinking_time_ms": None, "params": {}},

    # --- Time-budget sweep (UCB1 + cutoff=5 rollout; calibrated for ~6ms/iter on this hw) ---
    {
        "name": "pool_mcts_50ms",
        "type": "mcts",
        "thinking_time_ms": 500,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.10,   # 50 iters @ ~159 iter/s ≈ 0.31 s/move
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
        },
    },
    {
        "name": "pool_mcts_100ms",
        "type": "mcts",
        "thinking_time_ms": 500,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.20,   # 100 iters @ ~159 iter/s ≈ 0.63 s/move
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
        },
    },

    # --- Deploy difficulty proxies (calibrated feature stack, increasing budget) ---
    {
        "name": "pool_deploy_easy",
        "type": "mcts",
        "thinking_time_ms": 200,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.5,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
        },
    },
    {
        "name": "pool_deploy_medium",
        "type": "mcts",
        "thinking_time_ms": 500,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.20,   # 100 iters @ 159 iter/s ≈ 0.63 s/move
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
            "adaptive_rollout_depth_enabled": True,
            "adaptive_rollout_depth_base": 5,
            "adaptive_rollout_depth_avg_bf": 80.0,
        },
    },
    {
        "name": "pool_deploy_hard",
        "type": "mcts",
        "thinking_time_ms": 500,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.30,   # 150 iters @ 159 iter/s ≈ 0.94 s/move
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
            "adaptive_rollout_depth_enabled": True,
            "adaptive_rollout_depth_base": 5,
            "adaptive_rollout_depth_avg_bf": 80.0,
            "sufficiency_threshold_enabled": True,
            "loss_avoidance_enabled": True,
            "loss_avoidance_threshold": -50.0,
        },
    },

    # --- RAVE k sweep ---
    {
        "name": "pool_rave_k500",
        "type": "mcts",
        "thinking_time_ms": 200,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.5,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 500,
            "state_eval_weights": _SINGLE_WEIGHTS,
        },
    },
    {
        "name": "pool_rave_k5000",
        "type": "mcts",
        "thinking_time_ms": 200,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.5,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 5000,
            "state_eval_weights": _SINGLE_WEIGHTS,
        },
    },

    # --- Phase-calibrated evaluation ---
    {
        "name": "pool_phase_weights",
        "type": "mcts",
        "thinking_time_ms": 200,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.5,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
            "state_eval_phase_weights": _PHASE_WEIGHTS,
        },
    },

    # --- Rollout policy variants ---
    {
        "name": "pool_heuristic_rollout",
        "type": "mcts",
        "thinking_time_ms": 200,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.5,
            "exploration_constant": 1.414,
            "rollout_policy": "heuristic",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
            "state_eval_weights": _SINGLE_WEIGHTS,
        },
    },
    {
        "name": "pool_full_rollout",
        "type": "mcts",
        "thinking_time_ms": 200,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.025,  # 5 iters @ ~5 iter/s (full rollout, no cutoff) ≈ 1 s/move
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
            "state_eval_weights": _SINGLE_WEIGHTS,
        },
    },

    # --- Progressive widening ---
    {
        "name": "pool_progressive_widening",
        "type": "mcts",
        "thinking_time_ms": 200,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.5,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
            "state_eval_weights": _SINGLE_WEIGHTS,
            "progressive_widening_enabled": True,
            "pw_c": 2.0,
            "pw_alpha": 0.5,
        },
    },

    # --- L9 meta-optimisation (no opponent model — tests raw search improvement) ---
    {
        "name": "pool_l9_full",
        "type": "mcts",
        "thinking_time_ms": 200,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.5,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
            "state_eval_weights": _SINGLE_WEIGHTS,
            "adaptive_exploration_enabled": True,
            "adaptive_exploration_base": 1.414,
            "adaptive_exploration_avg_bf": 80.0,
            "adaptive_rollout_depth_enabled": True,
            "adaptive_rollout_depth_base": 5,
            "adaptive_rollout_depth_avg_bf": 80.0,
            "sufficiency_threshold_enabled": True,
            "loss_avoidance_enabled": True,
            "loss_avoidance_threshold": -50.0,
        },
    },

    # --- NST rollout bias ---
    {
        "name": "pool_nst",
        "type": "mcts",
        "thinking_time_ms": 200,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.5,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
            "state_eval_weights": _SINGLE_WEIGHTS,
            "nst_enabled": True,
            "nst_weight": 0.5,
        },
    },

    # --- Opponent modeling variants ---
    {
        "name": "pool_opp_model",
        "type": "mcts",
        "thinking_time_ms": 200,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.5,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
            "state_eval_weights": _SINGLE_WEIGHTS,
            "opponent_modeling_enabled": True,
            "alliance_detection_enabled": True,
        },
    },
]

POOL_BY_NAME: Dict[str, Dict[str, Any]] = {a["name"]: a for a in POOL_CATALOG}

# Names that should never be promoted to champion (weak baselines)
_NON_PROMOTABLE = {"pool_random", "pool_heuristic", "pool_mcts_50ms", "pool_mcts_100ms"}


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def load_state() -> Dict[str, Any]:
    path = Path(CHAMPION_STATE_PATH)
    if path.exists():
        with path.open() as f:
            state = json.load(f)
        # Back-fill new fields for states written by an older version
        state.setdefault("total_snapshot_rows", 0)
        state.setdefault("last_refit_run", -1)
        state.setdefault("generation", 0)
        return state
    return {
        "champion_config": CHAMPION_INITIAL_CONFIG,
        "ratings": {},          # agent_name -> {mu, sigma, games_played, conservative}
        "history": [],          # list of run summaries
        "generation": 0,        # incremented on each promotion
        "total_snapshot_rows": 0,
        "last_refit_run": -1,   # index of history when last refit ran
    }


def save_state(state: Dict[str, Any]) -> None:
    Path(CHAMPION_STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(CHAMPION_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# TrueSkill helpers
# ---------------------------------------------------------------------------

def _build_tracker_with_priors(prior_ratings: Dict[str, Dict[str, float]]) -> Any:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from analytics.tournament.trueskill_rating import TrueSkillTracker
    tracker = TrueSkillTracker()
    tracker.load_ratings(prior_ratings)
    return tracker


def _update_ratings_from_games(
    games: List[Dict[str, Any]],
    prior_ratings: Dict[str, Dict[str, float]],
) -> Dict[str, Dict[str, float]]:
    tracker = _build_tracker_with_priors(prior_ratings)
    for game in games:
        agent_scores = game.get("agent_scores")
        if not agent_scores:
            continue
        tracker.update_game({str(k): int(v) for k, v in agent_scores.items()})
    return {agent_id: tracker.get_rating(agent_id) for agent_id in tracker.agent_ids}


# ---------------------------------------------------------------------------
# Arena helpers
# ---------------------------------------------------------------------------

def _pick_pool_agents(
    exclude_names: Optional[List[str]],
    n: int,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    exclude = set(exclude_names or [])
    candidates = [a for a in POOL_CATALOG if a["name"] not in exclude]
    if len(candidates) < n:
        raise ValueError(
            f"Pool catalog has only {len(candidates)} eligible agents; need {n}."
        )
    return rng.sample(candidates, n)


def _build_arena_config(
    champion_config: Dict[str, Any],
    pool_agents: List[Dict[str, Any]],
    num_games: int,
    seed: int,
) -> Dict[str, Any]:
    agents = [champion_config] + pool_agents
    return {
        "agents": agents,
        "num_games": num_games,
        "seed": seed,
        "seat_policy": "round_robin",
        "output_root": "arena_runs",
        "max_turns": 2500,
        "snapshots": {
            "enabled": True,
            "strategy": "fixed_ply",
            "checkpoints": [8, 16, 24, 32, 40, 48, 56, 64],
        },
        "notes": (
            "Champion arena — champion vs randomized pool. "
            f"Pool: {[a['name'] for a in pool_agents]}."
        ),
    }


def _find_latest_run(output_root: str = "arena_runs") -> Optional[str]:
    root = Path(output_root)
    if not root.exists():
        return None
    runs = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for r in runs:
        if r.is_dir() and (r / "summary.json").exists():
            return str(r)
    return None


def run_arena(config_path: str, num_games: Optional[int] = None) -> str:
    cmd = [sys.executable, "scripts/arena.py", "--config", config_path]
    if num_games is not None:
        cmd += ["--num-games", str(num_games)]
    print(f"[champion_arena] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"[champion_arena] Arena exited with code {result.returncode}")
        sys.exit(1)
    run_dir = _find_latest_run()
    if run_dir is None:
        print("[champion_arena] ERROR: could not find arena output directory.")
        sys.exit(1)
    return run_dir


# ---------------------------------------------------------------------------
# Summary parsing
# ---------------------------------------------------------------------------

def _load_games(run_dir: str) -> List[Dict[str, Any]]:
    games_path = Path(run_dir) / "games.jsonl"
    games = []
    if not games_path.exists():
        return games
    with games_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    games.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return games


def _parse_summary(run_dir: str) -> Dict[str, Any]:
    summary_path = Path(run_dir) / "summary.json"
    with summary_path.open() as f:
        return json.load(f)


def _agent_win_stats(games: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}
    for g in games:
        agent_scores = g.get("agent_scores", {})
        winner_agents = g.get("winner_agents", [])
        is_tie = g.get("is_tie", False)
        for name, score in agent_scores.items():
            if name not in stats:
                stats[name] = {"wins": 0, "ties": 0, "losses": 0, "scores": []}
            stats[name]["scores"].append(score)
            if is_tie:
                stats[name]["ties"] += 1
            elif name in winner_agents:
                stats[name]["wins"] += 1
            else:
                stats[name]["losses"] += 1
    for name, s in stats.items():
        n = len(s["scores"])
        s["games"] = n
        s["avg_score"] = sum(s["scores"]) / n if n else 0.0
        s["win_rate"] = s["wins"] / n if n else 0.0
        del s["scores"]
    return stats


# ---------------------------------------------------------------------------
# Snapshot accumulation
# ---------------------------------------------------------------------------

def accumulate_snapshots(run_dir: str) -> int:
    """Append snapshot rows from this run to the master CSV. Returns total rows."""
    try:
        import pandas as pd
    except ImportError:
        print("[champion_arena] WARNING: pandas not available; skipping snapshot accumulation")
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

    SNAPSHOT_CSV.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(SNAPSHOT_CSV, index=False)
    total = int(len(combined))
    print(f"[champion_arena] Snapshots: {len(new_df)} new rows, {total} total → {SNAPSHOT_CSV}")
    return total


# ---------------------------------------------------------------------------
# Evaluator weight re-fitting
# ---------------------------------------------------------------------------

def _se_feature_names() -> List[str]:
    """Return state-evaluator feature names without importing at module level."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from mcts.state_evaluator import FEATURE_NAMES
    return list(FEATURE_NAMES)


def _default_weights() -> Dict[str, float]:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from mcts.state_evaluator import DEFAULT_WEIGHTS
    return dict(DEFAULT_WEIGHTS)


def refit_evaluator_weights() -> Optional[Dict[str, Any]]:
    """Run per-phase linear regression on accumulated snapshots.

    Returns a dict with keys 'phase_weights', 'single_weights', 'r2_by_phase',
    'r2_global', 'rows_used', or None if insufficient data or missing libraries.
    """
    try:
        import pandas as pd
        from sklearn.linear_model import LinearRegression
    except ImportError:
        print("[champion_arena] sklearn not available; skipping weight re-fit")
        return None

    if not SNAPSHOT_CSV.exists():
        print("[champion_arena] No snapshot data yet; skipping weight re-fit")
        return None

    df = pd.read_csv(SNAPSHOT_CSV)
    df = df.dropna(subset=["final_score"])

    feature_names = _se_feature_names()
    se_cols = [f"se_{f}" for f in feature_names]
    missing = [c for c in se_cols if c not in df.columns]
    if missing:
        print(f"[champion_arena] Missing se_ columns {missing}; skipping re-fit")
        return None

    if len(df) < MIN_ROWS_FOR_REFIT:
        print(f"[champion_arena] Only {len(df)} snapshot rows (need {MIN_ROWS_FOR_REFIT}); skipping re-fit")
        return None

    print(f"\n[champion_arena] Refitting evaluator weights from {len(df)} snapshot rows ...")

    def _fit_phase(phase_df: Any) -> Tuple[Dict[str, float], float]:
        if len(phase_df) < 50:
            return _default_weights(), 0.0
        X = phase_df[se_cols].values.astype(float)
        y = phase_df["final_score"].values.astype(float)
        lr = LinearRegression().fit(X, y)
        coefs = lr.coef_
        max_abs = float(np.max(np.abs(coefs))) if np.max(np.abs(coefs)) > 0 else 1.0
        scale = WEIGHT_SCALE / max_abs
        weights = {feature_names[i]: float(coefs[i] * scale) for i in range(len(feature_names))}
        return weights, float(lr.score(X, y))

    phase_weights: Dict[str, Dict[str, float]] = {}
    r2_by_phase: Dict[str, float] = {}

    if "phase_board_occupancy" in df.columns:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from mcts.state_evaluator import PHASE_EARLY_THRESHOLD, PHASE_LATE_THRESHOLD
        occ = df["phase_board_occupancy"]
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
    else:
        w, r2 = _fit_phase(df)
        phase_weights = {"early": w, "mid": w, "late": w}
        r2_by_phase = {"early": r2, "mid": r2, "late": r2}
        print(f"  Global fit (no occupancy): R²={r2:.4f}")

    X_all = df[se_cols].values.astype(float)
    y_all = df["final_score"].values.astype(float)
    lr_all = LinearRegression().fit(X_all, y_all)
    coefs_all = lr_all.coef_
    max_abs_all = float(np.max(np.abs(coefs_all))) if np.max(np.abs(coefs_all)) > 0 else 1.0
    single_weights = {
        feature_names[i]: float(coefs_all[i] * WEIGHT_SCALE / max_abs_all)
        for i in range(len(feature_names))
    }
    r2_global = float(lr_all.score(X_all, y_all))
    print(f"  Global R²={r2_global:.4f}")

    for fname, wval in sorted(single_weights.items(), key=lambda x: abs(x[1]), reverse=True):
        if abs(wval) > 0.005:
            print(f"    {fname:>35s}: {wval:+.4f}")

    return {
        "phase_weights": phase_weights,
        "single_weights": single_weights,
        "r2_by_phase": r2_by_phase,
        "r2_global": r2_global,
        "rows_used": int(len(df)),
    }


def _save_calibrated_weights(refit: Dict[str, Any]) -> None:
    payload = {
        "single_weights": refit["single_weights"],
        "phase_weights": refit["phase_weights"],
        "default_weights": _default_weights(),
    }
    weights_path = Path("data/layer6_calibrated_weights.json")
    with weights_path.open("w") as f:
        json.dump(payload, f, indent=2)
    print(f"[champion_arena] Saved calibrated weights → {weights_path}")


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _bar(value: float, width: int = 20) -> str:
    filled = int(round(value * width))
    return "█" * filled + "░" * (width - filled)


def _write_report(
    run_dir: str,
    pool_names: List[str],
    win_stats: Dict[str, Dict[str, Any]],
    ratings_before: Dict[str, Dict[str, float]],
    ratings_after: Dict[str, Dict[str, float]],
    promoted: Optional[str],
    generation: int,
    total_snapshot_rows: int,
    refit_result: Optional[Dict[str, Any]],
    report_path: Path,
) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Determine human-proxy performance
    heuristic_stats = win_stats.get(HUMAN_PROXY_NAME, {})
    champ_stats = win_stats.get("champion", {})
    human_competitive = (
        champ_stats.get("win_rate", 0.0) >= HUMAN_COMPETITIVE_WINRATE
        if heuristic_stats else None
    )

    lines = [
        f"# Champion Arena Run Report",
        f"",
        f"**Date:** {ts}  ",
        f"**Run dir:** `{run_dir}`  ",
        f"**Champion generation:** {generation}  ",
        f"**Pool:** {', '.join(pool_names)}",
        f"**Accumulated snapshots:** {total_snapshot_rows:,} rows",
        f"",
        f"---",
        f"",
        f"## Win/Loss Summary",
        f"",
        f"| Agent | Games | Wins | Win% | Avg Score |",
        f"|-------|-------|------|------|-----------|",
    ]
    for name in sorted(win_stats, key=lambda n: -win_stats[n]["win_rate"]):
        s = win_stats[name]
        bar = _bar(s["win_rate"])
        marker = " 👑" if name == "champion" else ""
        lines.append(
            f"| {name}{marker} | {s['games']} | {s['wins']} "
            f"| {s['win_rate']*100:.1f}% {bar} | {s['avg_score']:.1f} |"
        )

    # Human-proxy callout
    if HUMAN_PROXY_NAME in win_stats and "champion" in win_stats:
        hstat = win_stats[HUMAN_PROXY_NAME]
        cstat = win_stats["champion"]
        target = HUMAN_COMPETITIVE_WINRATE * 100
        actual = cstat.get("win_rate", 0.0) * 100
        status = "✅ **HUMAN-COMPETITIVE**" if human_competitive else f"⏳ targeting ≥{target:.0f}%"
        lines += [
            f"",
            f"### Human-Competitiveness",
            f"Champion win rate vs `{HUMAN_PROXY_NAME}` (human proxy): "
            f"**{actual:.1f}%** (target ≥{target:.0f}%)  ",
            f"Status: {status}",
        ]

    lines += [
        f"",
        f"---",
        f"",
        f"## TrueSkill Ratings",
        f"",
        f"Conservative estimate = μ − 3σ. Δμ and Δcons show change from prior.",
        f"",
        f"| Rank | Agent | μ | σ | Conservative | Δμ | Δcons | Games |",
        f"|------|-------|---|---|-------------|----|----|-------|",
    ]

    leaderboard = sorted(
        ratings_after.items(),
        key=lambda x: x[1]["conservative"],
        reverse=True,
    )
    for rank, (name, r) in enumerate(leaderboard, 1):
        prev = ratings_before.get(name, {})
        prev_mu = prev.get("mu", 25.0)
        prev_cons = prev.get("conservative", prev_mu - 3 * prev.get("sigma", 8.333))
        delta_mu = r["mu"] - prev_mu
        delta_cons = r["conservative"] - prev_cons
        sign_mu = "+" if delta_mu >= 0 else ""
        sign_cons = "+" if delta_cons >= 0 else ""
        marker = " 👑" if name == "champion" else ""
        lines.append(
            f"| {rank} | {name}{marker} | {r['mu']:.2f} | {r['sigma']:.2f} "
            f"| {r['conservative']:.2f} | {sign_mu}{delta_mu:.2f} "
            f"| {sign_cons}{delta_cons:.2f} | {r['games_played']} |"
        )

    # Evaluator re-fit section
    if refit_result:
        lines += [
            f"",
            f"---",
            f"",
            f"## Evaluator Weight Re-fit",
            f"",
            f"Re-fit from **{refit_result['rows_used']:,}** snapshot rows.  ",
            f"Global R² = **{refit_result['r2_global']:.4f}**",
            f"",
            f"| Phase | R² |",
            f"|-------|----|",
        ]
        for phase, r2 in refit_result.get("r2_by_phase", {}).items():
            lines.append(f"| {phase} | {r2:.4f} |")
        lines += [
            f"",
            f"Refitted weights applied to champion's `state_eval_phase_weights`.",
        ]

    # Promotion / status
    if promoted:
        lines += [
            f"",
            f"---",
            f"",
            f"## ⬆️ Champion Promotion",
            f"",
            f"**New champion:** `{promoted}`  ",
            f"The challenger's conservative TrueSkill surpassed the previous champion "
            f"with ≥{MIN_GAMES_FOR_PROMOTION} games of evidence.",
        ]
    else:
        lines += [
            f"",
            f"---",
            f"",
            f"## Champion Status",
            f"",
            f"Champion held. No challenger exceeded the champion's conservative TrueSkill "
            f"with sufficient evidence.",
        ]

    lines += [
        f"",
        f"---",
        f"",
        f"## Snapshot Data",
        f"",
        f"Board-state snapshots accumulated in `{SNAPSHOT_CSV}` "
        f"({total_snapshot_rows:,} rows total).  ",
        f"Run `scripts/analyze_layer6_features.py` for full SHAP + residual analysis.",
    ]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines))
    print(f"[champion_arena] Report written: {report_path}")


# ---------------------------------------------------------------------------
# History display
# ---------------------------------------------------------------------------

def show_history(state: Dict[str, Any]) -> None:
    history = state.get("history", [])
    ratings = state.get("ratings", {})
    generation = state.get("generation", 0)
    total_rows = state.get("total_snapshot_rows", 0)

    print(f"\n{'='*72}")
    print(f" Champion Arena — generation {generation}, {len(history)} run(s), {total_rows:,} snapshot rows")
    print(f"{'='*72}")

    if not history:
        print(" No runs yet.")
        return

    for i, entry in enumerate(history):
        ts = entry.get("timestamp", "?")
        games = entry.get("num_games", "?")
        pool = ", ".join(entry.get("pool", []))
        promoted = entry.get("promoted_to")
        refitted = " [REFITTED]" if entry.get("evaluator_refitted") else ""
        print(f"\n Run {i+1}  {ts}  ({games} games)  pool=[{pool}]{refitted}")
        if promoted:
            print(f"   *** Promoted champion → {promoted} ***")
        for name, s in sorted(
            entry.get("win_stats", {}).items(),
            key=lambda x: -x[1].get("win_rate", 0),
        ):
            wr = s.get("win_rate", 0) * 100
            avg = s.get("avg_score", 0)
            mu = entry.get("ratings_after", {}).get(name, {}).get("mu")
            cons = entry.get("ratings_after", {}).get(name, {}).get("conservative")
            mu_str = f"  μ={mu:.1f}" if mu is not None else ""
            cons_str = f"  μ-3σ={cons:.1f}" if cons is not None else ""
            marker = " 👑" if name == "champion" else ""
            print(f"   {name+marker:38s} WR={wr:5.1f}%  AvgScore={avg:5.1f}{mu_str}{cons_str}")

    print(f"\n{'='*72}")
    print(" Current TrueSkill Leaderboard")
    print(f"{'='*72}")
    print(f"  {'#':>2}  {'Agent':<38}  {'μ':>6}  {'σ':>5}  {'μ-3σ':>7}  {'Games':>5}")
    print(f"  {'─'*70}")
    leaderboard = sorted(ratings.items(), key=lambda x: x[1].get("conservative", 0), reverse=True)
    for rank, (name, r) in enumerate(leaderboard, 1):
        marker = " 👑" if name == "champion" else ""
        print(
            f"  {rank:>2}. {name+marker:<38}  "
            f"{r['mu']:>6.2f}  {r['sigma']:>5.2f}  "
            f"{r['conservative']:>7.2f}  {r['games_played']:>5}"
        )

    # Champion vs human proxy
    champ_r = ratings.get("champion")
    heur_r = ratings.get(HUMAN_PROXY_NAME)
    if champ_r and heur_r:
        gap = champ_r["conservative"] - heur_r["conservative"]
        sign = "+" if gap >= 0 else ""
        status = "✅ HUMAN-COMPETITIVE" if gap > 0 else "⏳ below human proxy"
        print(f"\n  Human-proxy gap (champion μ-3σ vs {HUMAN_PROXY_NAME} μ-3σ): {sign}{gap:.2f}  [{status}]")
    print()


# ---------------------------------------------------------------------------
# Promotion logic
# ---------------------------------------------------------------------------

def _check_promotion(
    ratings_after: Dict[str, Dict[str, float]],
    champion_name: str,
    auto_promote: bool,
) -> Optional[str]:
    if not auto_promote:
        return None
    champ_rating = ratings_after.get(champion_name)
    if champ_rating is None:
        return None
    champ_cons = champ_rating["conservative"]
    best_challenger: Optional[str] = None
    best_cons = champ_cons
    for name, r in ratings_after.items():
        if name == champion_name:
            continue
        if name in _NON_PROMOTABLE:
            continue
        if r["games_played"] < MIN_GAMES_FOR_PROMOTION:
            continue
        if r["conservative"] > best_cons:
            best_cons = r["conservative"]
            best_challenger = name
    return best_challenger


# ---------------------------------------------------------------------------
# Single-run execution
# ---------------------------------------------------------------------------

def _run_one(
    state: Dict[str, Any],
    num_games: int,
    rng_seed: int,
    pool_names_override: Optional[List[str]],
    auto_promote: bool,
    run_index: int,
) -> None:
    """Execute one champion arena run and update state in-place."""
    rng = random.Random(rng_seed)

    if pool_names_override:
        unknown = [n for n in pool_names_override if n not in POOL_BY_NAME]
        if unknown:
            print(f"[champion_arena] Unknown pool agents: {unknown}")
            print(f"  Available: {sorted(POOL_BY_NAME.keys())}")
            sys.exit(1)
        pool_agents = [POOL_BY_NAME[n] for n in pool_names_override]
    else:
        pool_agents = _pick_pool_agents(exclude_names=["champion"], n=DEFAULT_POOL_SIZE, rng=rng)

    pool_names = [a["name"] for a in pool_agents]
    champion_config = state["champion_config"]
    total_runs = len(state["history"])

    print(f"\n[champion_arena] Run #{total_runs + 1}  Champion: {champion_config['name']}")
    print(f"[champion_arena] Pool ({len(pool_agents)}): {pool_names}")
    print(f"[champion_arena] Games: {num_games}  Seed: {rng_seed}")

    arena_seed = rng.randint(10_000_000, 99_999_999)
    arena_config = _build_arena_config(champion_config, pool_agents, num_games, arena_seed)
    Path(TEMP_CONFIG_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(TEMP_CONFIG_PATH, "w") as f:
        json.dump(arena_config, f, indent=2)

    run_dir = run_arena(TEMP_CONFIG_PATH)
    print(f"[champion_arena] Run complete: {run_dir}")

    games = _load_games(run_dir)
    win_stats = _agent_win_stats(games)

    ratings_before = {k: dict(v) for k, v in state["ratings"].items()}
    ratings_after = _update_ratings_from_games(games, ratings_before)

    # Accumulate snapshots
    total_rows = accumulate_snapshots(run_dir)
    state["total_snapshot_rows"] = total_rows

    # Maybe refit evaluator weights
    refit_result = None
    runs_since_refit = total_runs - state.get("last_refit_run", -1)
    if total_rows >= MIN_ROWS_FOR_REFIT and runs_since_refit >= REFIT_INTERVAL:
        refit_result = refit_evaluator_weights()
        if refit_result:
            state["champion_config"]["params"]["state_eval_phase_weights"] = (
                refit_result["phase_weights"]
            )
            state["champion_config"]["params"]["state_eval_weights"] = (
                refit_result["single_weights"]
            )
            _save_calibrated_weights(refit_result)
            state["last_refit_run"] = total_runs
            print("[champion_arena] Applied refitted weights to champion config")

    # Check for promotion
    promoted = _check_promotion(
        ratings_after=ratings_after,
        champion_name=champion_config["name"],
        auto_promote=auto_promote,
    )
    generation = state["generation"]
    if promoted:
        new_champion_config = dict(POOL_BY_NAME[promoted])
        new_champion_config["name"] = "champion"
        # Carry forward any refitted phase weights
        if refit_result:
            new_champion_config.setdefault("params", {})["state_eval_phase_weights"] = (
                refit_result["phase_weights"]
            )
        state["champion_config"] = new_champion_config
        generation += 1
        state["generation"] = generation
        print(f"[champion_arena] *** Champion promoted: {promoted} → generation {generation} ***")

    state["ratings"] = ratings_after

    # Append history entry
    history_entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_dir": run_dir,
        "num_games": len(games),
        "pool": pool_names,
        "arena_seed": arena_seed,
        "win_stats": win_stats,
        "ratings_after": ratings_after,
        "promoted_to": promoted,
        "generation": generation,
        "total_snapshot_rows": total_rows,
        "evaluator_refitted": refit_result is not None,
        "refit_r2_global": refit_result["r2_global"] if refit_result else None,
    }
    state["history"].append(history_entry)
    save_state(state)
    print(f"[champion_arena] State saved → {CHAMPION_STATE_PATH}")

    # Write markdown report
    ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = Path(REPORTS_DIR) / f"run_{ts_str}_gen{generation}.md"
    _write_report(
        run_dir=run_dir,
        pool_names=pool_names,
        win_stats=win_stats,
        ratings_before=ratings_before,
        ratings_after=ratings_after,
        promoted=promoted,
        generation=generation,
        total_snapshot_rows=total_rows,
        refit_result=refit_result,
        report_path=report_path,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Champion Arena — continuous self-improvement loop targeting human-level Blokus play"
    )
    parser.add_argument(
        "--num-games", type=int, default=DEFAULT_NUM_GAMES,
        help=f"Number of games per run (default: {DEFAULT_NUM_GAMES})",
    )
    parser.add_argument(
        "--generations", type=int, default=1,
        help="Number of consecutive runs to execute (default: 1)",
    )
    parser.add_argument(
        "--pool", nargs="+", default=None,
        help="Explicit pool agent names from POOL_CATALOG (default: random sample of 3)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Base random seed (default: derived from current time)",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="Print history and leaderboard without running a new arena session",
    )
    parser.add_argument(
        "--no-promote", action="store_true",
        help="Disable automatic champion promotion",
    )
    parser.add_argument(
        "--refit", action="store_true",
        help="Force evaluator weight re-fit from accumulated snapshots and exit",
    )
    args = parser.parse_args()

    state = load_state()

    if args.show:
        show_history(state)
        return

    if args.refit:
        refit_result = refit_evaluator_weights()
        if refit_result:
            state["champion_config"]["params"]["state_eval_phase_weights"] = (
                refit_result["phase_weights"]
            )
            state["champion_config"]["params"]["state_eval_weights"] = (
                refit_result["single_weights"]
            )
            _save_calibrated_weights(refit_result)
            state["last_refit_run"] = len(state["history"])
            save_state(state)
            print("[champion_arena] Force re-fit complete.")
        else:
            print("[champion_arena] Re-fit skipped (insufficient data or missing libraries).")
        return

    base_seed = args.seed if args.seed is not None else int(datetime.now().timestamp())

    for i in range(args.generations):
        run_seed = base_seed + i * 31337
        _run_one(
            state=state,
            num_games=args.num_games,
            rng_seed=run_seed,
            pool_names_override=args.pool,
            auto_promote=not args.no_promote,
            run_index=i,
        )

    print(f"\n[champion_arena] All {args.generations} run(s) complete.")
    show_history(state)


if __name__ == "__main__":
    main()
