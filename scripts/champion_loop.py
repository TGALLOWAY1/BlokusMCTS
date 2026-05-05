#!/usr/bin/env python
"""Champion Self-Improvement Loop (unified).

Runs repeated arena generations where the champion competes against a
stratified randomized pool:

  Tier 0 — Baselines (random, heuristic): rating anchors, never promoted
  Tier 1 — Time-budget sweep (plain UCT): strength calibration
  Tier 2 — Feature-variant MCTS: hypothesis tests, promotable to champion
  Tier 3 — Deploy difficulty proxies: game-product difficulty levels

Pool selection per generation (3 challengers):
  Slot 0: always 1 Tier-0 baseline (alternating random / heuristic)
  Slot 1: 1 from Tier 1 or 3 (calibration or deploy-level)
  Slot 2: 1 from Tier 2 (hypothesis variant) or a recent champion checkpoint

After each generation:
  - TrueSkill ratings updated for all agents and persisted
  - Snapshot rows (se_ features + final_score) accumulated for evaluator refit
  - Every REFIT_INTERVAL gens: per-phase linear regression refits champion weights
  - If a Tier-2 promotable agent's conservative TrueSkill (μ-3σ) surpasses the
    champion's (with ≥ MIN_GAMES_FOR_PROMOTION evidence): champion is promoted
  - Per-generation report written to data/champion_reports/
  - Cumulative progress written to data/champion_progress.md

Human-target reference:
  An intermediate-level human Blokus player is estimated to have TrueSkill
  μ-3σ ≈ 10-15.  The loop tracks the gap between the champion's conservative
  estimate and HUMAN_TARGET_CONSERVATIVE (default 10.0) as its primary KPI.

Usage:
    python scripts/champion_loop.py                     # 1 generation, 20 games
    python scripts/champion_loop.py --generations 5 --games-per-gen 40
    python scripts/champion_loop.py --show              # print history, no run
    python scripts/champion_loop.py --refit             # force weight re-fit
    python scripts/champion_loop.py --no-promote        # disable auto-promotion
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import subprocess
import sys
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
REPORTS_DIR = DATA_DIR / "champion_reports"
ARENA_RUN_ROOT = "arena_runs/champion_loop"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SE_FEATURE_COLS = [f"se_{f}" for f in FEATURE_NAMES]

REFIT_INTERVAL = 3           # Generations between evaluator weight refits
MIN_ROWS_FOR_REFIT = 200     # Minimum snapshot rows before attempting refit
WEIGHT_SCALE = 0.30          # Maximum weight magnitude after normalization
MAX_CHECKPOINTS_IN_POOL = 3  # Most-recent champion checkpoints kept in pool
MIN_GAMES_FOR_PROMOTION = 30 # Challenger needs this many games before promotion check

CHAMPION_ID = "champion"

# Human-level TrueSkill reference (calibrated against human-play observations).
# An intermediate Blokus player against strong MCTS has conservative ≈ 10-15.
# The champion targets HUMAN_TARGET_CONSERVATIVE or above.
HUMAN_TARGET_CONSERVATIVE = 10.0

# ---------------------------------------------------------------------------
# Champion starting configuration (full Layer-9 stack, calibrated weights)
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

# Layer-6 calibrated weights embedded here so pool agents can reference them
# without reading the json file on every import.
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

# ---------------------------------------------------------------------------
# Pool catalog — 4 tiers of challenger agents
#
# Fields:
#   tier       — 0=baseline, 1=time-budget, 2=feature-variant, 3=deploy-proxy
#   promotable — If True this agent can replace the champion when it wins
# ---------------------------------------------------------------------------
POOL_CATALOG: List[Dict[str, Any]] = [
    # ── Tier 0: Baselines (rating anchors) ───────────────────────────────────
    {"name": "pool_random",    "type": "random",    "tier": 0, "promotable": False},
    {"name": "pool_heuristic", "type": "heuristic", "tier": 0, "promotable": False},

    # ── Tier 1: Time-budget sweep (plain UCT, no extra features) ─────────────
    {
        "name": "pool_mcts_100ms", "type": "mcts", "thinking_time_ms": 100,
        "tier": 1, "promotable": False,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
            "exploration_constant": 1.414,
        },
    },
    {
        "name": "pool_mcts_500ms", "type": "mcts", "thinking_time_ms": 500,
        "tier": 1, "promotable": False,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
            "exploration_constant": 1.414,
        },
    },

    # ── Tier 2: Feature variants (hypothesis tests, promotable) ──────────────
    {
        "name": "pool_rave_k500", "type": "mcts", "thinking_time_ms": 500,
        "tier": 2, "promotable": True,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
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
        "name": "pool_rave_k5000", "type": "mcts", "thinking_time_ms": 500,
        "tier": 2, "promotable": True,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 5000,
            "state_eval_weights": _SINGLE_WEIGHTS,
        },
    },
    {
        "name": "pool_phase_weights", "type": "mcts", "thinking_time_ms": 500,
        "tier": 2, "promotable": True,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
            "state_eval_phase_weights": _PHASE_WEIGHTS,
        },
    },
    {
        "name": "pool_heuristic_rollout", "type": "mcts", "thinking_time_ms": 500,
        "tier": 2, "promotable": True,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
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
        "name": "pool_full_rollout", "type": "mcts", "thinking_time_ms": 500,
        "tier": 2, "promotable": True,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
            "state_eval_weights": _SINGLE_WEIGHTS,
        },
    },
    {
        "name": "pool_progressive_widening", "type": "mcts", "thinking_time_ms": 500,
        "tier": 2, "promotable": True,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
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
    {
        "name": "pool_l9_full", "type": "mcts", "thinking_time_ms": 500,
        "tier": 2, "promotable": True,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
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
    {
        "name": "pool_nst", "type": "mcts", "thinking_time_ms": 500,
        "tier": 2, "promotable": True,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
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
    {
        "name": "pool_minimax_heavy", "type": "mcts", "thinking_time_ms": 500,
        "tier": 2, "promotable": True,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "rollout_cutoff_depth": 5,
            "minimax_backup_alpha": 0.5,
            "rave_enabled": True,
            "rave_k": 1000,
            "state_eval_weights": _SINGLE_WEIGHTS,
        },
    },

    # ── Tier 3: Deploy difficulty proxies ─────────────────────────────────────
    {
        "name": "pool_deploy_easy", "type": "mcts", "thinking_time_ms": 200,
        "tier": 3, "promotable": False,
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
        "name": "pool_deploy_medium", "type": "mcts", "thinking_time_ms": 450,
        "tier": 3, "promotable": False,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.5,
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
        "name": "pool_deploy_hard", "type": "mcts", "thinking_time_ms": 900,
        "tier": 3, "promotable": False,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.5,
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
]

POOL_BY_NAME: Dict[str, Dict[str, Any]] = {a["name"]: a for a in POOL_CATALOG}


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def _default_state() -> Dict[str, Any]:
    return {
        "generation": 0,
        "champion_params": copy.deepcopy(BASE_CHAMPION_PARAMS),
        "trueskill_ratings": {},
        "checkpoints": [],      # {"id", "generation", "mu", "sigma", "params"}
        "history": [],          # per-generation records
        "total_snapshot_rows": 0,
        "last_refit_generation": -1,
    }


def _migrate_state(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Handle state written by older versions of this script or champion_arena.py."""
    # champion_arena.py used "champion_config" key
    if "champion_config" in raw and "champion_params" not in raw:
        raw["champion_params"] = raw.pop("champion_config")
    # champion_arena.py used "ratings" key
    if "ratings" in raw and "trueskill_ratings" not in raw:
        raw["trueskill_ratings"] = raw.pop("ratings")
    # Fill defaults for keys added in later versions
    for key, default in _default_state().items():
        raw.setdefault(key, default)
    return raw


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        with STATE_FILE.open() as f:
            return _migrate_state(json.load(f))
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
        state["trueskill_ratings"][agent_id] = tracker.get_rating(agent_id)


def snapshot_ratings(tracker: TrueSkillTracker) -> Dict[str, Dict[str, float]]:
    return {aid: dict(tracker.get_rating(aid)) for aid in tracker.agent_ids}


# ---------------------------------------------------------------------------
# Agent config builders
# ---------------------------------------------------------------------------

def _strip_metadata(pool_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Remove tier/promotable metadata; ensure params/thinking_time_ms present."""
    cfg = {k: v for k, v in pool_entry.items() if k not in ("tier", "promotable")}
    cfg.setdefault("params", {})
    cfg.setdefault("thinking_time_ms", None)
    return cfg


def _build_champion_agent_config(params: Dict[str, Any]) -> Dict[str, Any]:
    cfg = copy.deepcopy(params)
    cfg["name"] = CHAMPION_ID
    return cfg


def _build_checkpoint_agent_config(checkpoint: Dict[str, Any]) -> Dict[str, Any]:
    cfg = copy.deepcopy(checkpoint["params"])
    cfg["name"] = checkpoint["id"]
    return cfg


# ---------------------------------------------------------------------------
# Stratified challenger pool selection
# ---------------------------------------------------------------------------

def select_challengers(
    state: Dict[str, Any],
    rng: random.Random,
) -> List[Dict[str, Any]]:
    """Select 3 challengers using a stratified sampling strategy.

    Slot 0: 1 Tier-0 baseline (weak rating anchor)
    Slot 1: 1 Tier-1 or Tier-3 agent (compute calibration or deploy proxy)
    Slot 2: 1 Tier-2 hypothesis variant, OR a recent checkpoint (30% chance)
    """
    challengers: List[Dict[str, Any]] = []

    # Slot 0 — Tier-0 baseline
    tier0 = [p for p in POOL_CATALOG if p["tier"] == 0]
    challengers.append(_strip_metadata(rng.choice(tier0)))

    # Slot 1 — Tier-1 or Tier-3
    tier1_3 = [p for p in POOL_CATALOG if p["tier"] in (1, 3)]
    challengers.append(_strip_metadata(rng.choice(tier1_3)))

    # Slot 2 — Tier-2 variant (70%) or recent champion checkpoint (30%)
    checkpoints = state.get("checkpoints", [])[-MAX_CHECKPOINTS_IN_POOL:]
    used_names = {c["name"] for c in challengers}

    if checkpoints and rng.random() < 0.30:
        challengers.append(_build_checkpoint_agent_config(rng.choice(checkpoints)))
    else:
        tier2 = [p for p in POOL_CATALOG if p["tier"] == 2 and p["name"] not in used_names]
        if tier2:
            challengers.append(_strip_metadata(rng.choice(tier2)))
        elif checkpoints:
            challengers.append(_build_checkpoint_agent_config(rng.choice(checkpoints)))
        else:
            challengers.append({"name": "pool_random", "type": "random", "thinking_time_ms": None, "params": {}})

    return challengers


# ---------------------------------------------------------------------------
# Arena execution
# ---------------------------------------------------------------------------

def _find_latest_run(output_root: str) -> Optional[str]:
    root = Path(output_root)
    if not root.exists():
        return None
    runs = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for r in runs:
        if r.is_dir() and (r / "summary.json").exists():
            return str(r)
    return None


def run_generation_arena(
    generation: int,
    champion_cfg: Dict[str, Any],
    challengers: List[Dict[str, Any]],
    num_games: int,
    seed: int,
) -> str:
    """Write a temp arena config and execute it. Returns the run directory path."""
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

    print(f"\n[champion_loop] Generation {generation}: {num_games} games")
    print(f"  Champion vs: {[c['name'] for c in challengers]}")

    cmd = [sys.executable, "scripts/arena.py", "--config", str(config_path)]
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Arena exited with code {result.returncode}")

    run_dir = _find_latest_run(ARENA_RUN_ROOT)
    if run_dir is None:
        raise RuntimeError("Could not locate arena output directory")
    print(f"[champion_loop] Run saved: {run_dir}")
    return run_dir


# ---------------------------------------------------------------------------
# Results parsing
# ---------------------------------------------------------------------------

def load_games(run_dir: str) -> List[Dict[str, Any]]:
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


def agent_win_stats(games: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Compute wins/ties/losses/avg_score per agent from games.jsonl records."""
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


def update_trueskill_from_games(tracker: TrueSkillTracker, games: List[Dict[str, Any]]) -> None:
    for game in games:
        agent_scores = game.get("agent_scores", {})
        if agent_scores:
            tracker.update_game(agent_scores)


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
# Evaluator weight refitting
# ---------------------------------------------------------------------------

def refit_evaluator_weights() -> Optional[Dict[str, Any]]:
    """Per-phase linear regression on accumulated snapshot rows.

    Returns dict with 'phase_weights', 'single_weights', 'r2_by_phase',
    'r2_global', 'rows_used', or None when data / libraries are unavailable.
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

    occ = df.get("phase_board_occupancy") if "phase_board_occupancy" in df.columns else None

    phase_weights: Dict[str, Dict[str, float]] = {}
    r2_by_phase: Dict[str, float] = {}

    if occ is not None:
        masks = {
            "early": occ < PHASE_EARLY_THRESHOLD,
            "mid": (occ >= PHASE_EARLY_THRESHOLD) & (occ < PHASE_LATE_THRESHOLD),
            "late": occ >= PHASE_LATE_THRESHOLD,
        }
        for phase_name, mask in masks.items():
            w, r2 = _fit_phase(df[mask])
            phase_weights[phase_name] = w
            r2_by_phase[phase_name] = r2
            print(f"  Phase '{phase_name}': R²={r2:.4f}, n={int(mask.sum())}")
            for fname, wval in sorted(w.items(), key=lambda x: abs(x[1]), reverse=True):
                if abs(wval) > 0.01:
                    print(f"    {fname:>35s}: {wval:+.4f}")
    else:
        w, r2 = _fit_phase(df)
        phase_weights = {"early": w, "mid": w, "late": w}
        r2_by_phase = {"early": r2, "mid": r2, "late": r2}
        print(f"  Global fit (no phase_board_occupancy col): R²={r2:.4f}")

    # Global single-weight regression
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


def apply_refit_to_champion(refit: Dict[str, Any], state: Dict[str, Any]) -> None:
    """Update champion params and persist calibrated weights file."""
    state["champion_params"]["params"]["state_eval_phase_weights"] = refit["phase_weights"]

    weights_path = DATA_DIR / "layer6_calibrated_weights.json"
    payload = {
        "single_weights": refit["single_weights"],
        "phase_weights": refit["phase_weights"],
        "default_weights": dict(DEFAULT_WEIGHTS),
    }
    with weights_path.open("w") as f:
        json.dump(payload, f, indent=2)
    print(f"[champion_loop] Calibrated weights saved → {weights_path}")


# ---------------------------------------------------------------------------
# Auto-promotion
# ---------------------------------------------------------------------------

def check_and_apply_promotion(
    tracker: TrueSkillTracker,
    state: Dict[str, Any],
    auto_promote: bool,
) -> Optional[str]:
    """Promote the best Tier-2 promotable agent to champion if it beats champion.

    Returns the promoted agent name, or None if no promotion occurred.
    """
    if not auto_promote:
        return None

    champ_rating = tracker.get_rating(CHAMPION_ID)
    champ_cons = champ_rating["conservative"]

    best_name: Optional[str] = None
    best_cons = champ_cons  # challenger must strictly exceed this

    for entry in POOL_CATALOG:
        if not entry["promotable"]:
            continue
        name = entry["name"]
        rating = tracker.get_rating(name)
        if rating["games_played"] < MIN_GAMES_FOR_PROMOTION:
            continue
        if rating["conservative"] > best_cons:
            best_cons = rating["conservative"]
            best_name = name

    if best_name is None:
        return None

    challenger = POOL_BY_NAME[best_name]
    challenger_rating = tracker.get_rating(best_name)

    print(
        f"\n[champion_loop] PROMOTION: {best_name} → champion  "
        f"(challenger μ-3σ={best_cons:.2f} > champion μ-3σ={champ_cons:.2f})"
    )

    # Build new champion params from challenger config
    new_params = copy.deepcopy(BASE_CHAMPION_PARAMS)
    new_params["params"].update(challenger.get("params", {}))
    if "thinking_time_ms" in challenger and challenger["thinking_time_ms"] is not None:
        new_params["thinking_time_ms"] = challenger["thinking_time_ms"]
    state["champion_params"] = new_params

    # Transfer challenger's rating to champion slot, reset sigma to signal change
    tracker._ratings[CHAMPION_ID] = tracker._model.rating(
        mu=challenger_rating["mu"],
        sigma=tracker._sigma,  # reset uncertainty after promotion
    )

    return best_name


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
    # Register checkpoint in TrueSkill with the champion's current rating
    tracker._ratings[ckpt_id] = tracker._model.rating(
        mu=rating["mu"], sigma=rating["sigma"]
    )
    tracker._games_played[ckpt_id] = rating["games_played"]
    print(f"[champion_loop] Checkpoint saved: {ckpt_id} (μ={rating['mu']:.2f})")


# ---------------------------------------------------------------------------
# Progress display
# ---------------------------------------------------------------------------

def _human_progress_bar(conservative: float, width: int = 30) -> str:
    """ASCII progress bar from baseline (0) toward human target."""
    baseline = -25.0  # typical random-agent conservative estimate
    target = HUMAN_TARGET_CONSERVATIVE
    span = target - baseline
    frac = max(0.0, min(1.0, (conservative - baseline) / span))
    filled = int(round(frac * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {frac*100:.1f}%"


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
    print(f"{'─'*72}")

    champ_rating = tracker.get_rating(CHAMPION_ID)
    cons = champ_rating["conservative"]
    gap = HUMAN_TARGET_CONSERVATIVE - cons
    bar = _human_progress_bar(cons)
    print(f"\n  Human target (μ-3σ ≥ {HUMAN_TARGET_CONSERVATIVE:.0f})  {bar}")
    if gap <= 0:
        print(f"  ✅ Champion exceeds human target! (μ-3σ = {cons:.2f})")
    else:
        print(f"  Gap to human target: {gap:.2f} points  (champion μ-3σ = {cons:.2f})")
    print()


def show_progress(state: Dict[str, Any]) -> None:
    print(f"\n{'='*72}")
    print(f"  Champion Self-Improvement — Generation {state['generation']}")
    print(f"{'='*72}")
    if not state.get("history"):
        print("  No generations run yet.")
        return

    tracker = build_tracker(state)
    print_leaderboard(tracker)

    history = state.get("history", [])
    print(f"  Trend (last {min(5, len(history))} generations):")
    for rec in history[-5:]:
        tags = []
        if rec.get("evaluator_refitted"):
            tags.append("REFITTED")
        if rec.get("promoted"):
            tags.append(f"PROMOTED:{rec['promoted']}")
        tag_str = f"  [{', '.join(tags)}]" if tags else ""
        print(
            f"    Gen {rec['generation']:>3}: μ={rec['champion_mu']:.2f}  "
            f"σ={rec['champion_sigma']:.2f}  "
            f"μ-3σ={rec['champion_conservative']:.2f}  "
            f"WR={rec.get('champion_win_rate', 0)*100:.1f}%{tag_str}"
        )
    print()


# ---------------------------------------------------------------------------
# Per-generation markdown report
# ---------------------------------------------------------------------------

def write_run_report(
    generation: int,
    run_dir: str,
    challengers: List[Dict[str, Any]],
    win_stats: Dict[str, Dict[str, Any]],
    tracker: TrueSkillTracker,
    ratings_before: Dict[str, Dict[str, float]],
    promoted: Optional[str],
    refit_result: Optional[Dict[str, Any]],
    total_snapshot_rows: int,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    report_path = REPORTS_DIR / f"gen{generation:04d}_{ts.strftime('%Y%m%d_%H%M%S')}.md"

    lines: List[str] = []
    lines.append(f"# Champion Self-Improvement — Generation {generation}\n\n")
    lines.append(f"**Date:** {ts.strftime('%Y-%m-%d %H:%M UTC')}  \n")
    lines.append(f"**Run dir:** `{run_dir}`  \n")
    pool_names = [c["name"] for c in challengers]
    lines.append(f"**Pool:** {', '.join(pool_names)}\n\n")

    # Win / loss table
    lines.append("## Win / Loss Summary\n\n")
    lines.append("| Agent | Games | Wins | Ties | Win% | Avg Score |\n")
    lines.append("|-------|-------|------|------|------|-----------|  \n")
    for name in sorted(win_stats, key=lambda n: -win_stats[n].get("win_rate", 0)):
        s = win_stats[name]
        wr = s.get("win_rate", 0)
        bar = "█" * int(round(wr * 20)) + "░" * (20 - int(round(wr * 20)))
        marker = " 👑" if name == CHAMPION_ID else ""
        lines.append(
            f"| {name}{marker} | {s.get('games', 0)} | {s.get('wins', 0)} "
            f"| {s.get('ties', 0)} | {wr*100:.1f}% {bar} | {s.get('avg_score', 0):.1f} |\n"
        )

    # TrueSkill leaderboard
    lines.append("\n## TrueSkill Leaderboard\n\n")
    lines.append("Conservative estimate = μ − 3σ (primary ranking metric).  \n")
    lines.append("Δμ shows change from before this generation.\n\n")
    lines.append("| Rank | Agent | μ | σ | μ-3σ | Δμ | Games |\n")
    lines.append("|------|-------|---|---|------|----|-------|\n")
    for entry in tracker.get_leaderboard():
        prev = ratings_before.get(entry["agent_id"], {})
        delta_mu = entry["mu"] - prev.get("mu", 25.0)
        marker = " 👑" if entry["agent_id"] == CHAMPION_ID else ""
        sign = "+" if delta_mu >= 0 else ""
        lines.append(
            f"| {entry['rank']} | {entry['agent_id']}{marker} | "
            f"{entry['mu']:.2f} | {entry['sigma']:.2f} | "
            f"{entry['conservative']:.2f} | {sign}{delta_mu:.2f} | "
            f"{entry['games_played']} |\n"
        )

    # Human-target progress
    champ_rating = tracker.get_rating(CHAMPION_ID)
    cons = champ_rating["conservative"]
    gap = HUMAN_TARGET_CONSERVATIVE - cons
    bar = _human_progress_bar(cons)
    lines.append(f"\n**Human target (μ-3σ ≥ {HUMAN_TARGET_CONSERVATIVE:.0f}):**  \n")
    lines.append(f"{bar}  \n")
    if gap <= 0:
        lines.append(f"✅ Champion exceeds human target! (μ-3σ = {cons:.2f})\n")
    else:
        lines.append(f"Gap: **{gap:.2f}** points remaining (champion μ-3σ = {cons:.2f})\n")

    # Promotion notice
    if promoted:
        lines.append(f"\n## ⬆️ Champion Promoted\n\n")
        lines.append(f"**{promoted}** surpassed the champion's conservative TrueSkill ")
        lines.append(f"(μ-3σ) with ≥ {MIN_GAMES_FOR_PROMOTION} game evidence.  \n")
        lines.append(f"Champion parameters updated to {promoted}'s configuration.\n")

    # Evaluator refit summary
    if refit_result:
        lines.append(f"\n## Evaluator Weight Refit\n\n")
        lines.append(f"Refitted on **{refit_result['rows_used']}** snapshot rows.  \n")
        lines.append(f"Global R² = **{refit_result['r2_global']:.4f}**  \n\n")
        lines.append("| Phase | R² | n |\n|-------|-----|---|\n")
        for phase, r2 in refit_result.get("r2_by_phase", {}).items():
            lines.append(f"| {phase} | {r2:.4f} | — |\n")
        lines.append("\nNew weights applied to champion and saved to `data/layer6_calibrated_weights.json`.\n")

    # Data collection status
    lines.append(f"\n## Data Collection\n\n")
    lines.append(f"**Snapshot rows accumulated:** {total_snapshot_rows}  \n")
    lines.append(f"**Next refit at:** ≥ {MIN_ROWS_FOR_REFIT} rows (currently {total_snapshot_rows})  \n")
    lines.append(f"Run `python scripts/analyze_layer6_features.py` for full SHAP analysis.\n")

    report_path.write_text("".join(lines), encoding="utf-8")
    print(f"[champion_loop] Report: {report_path}")
    return report_path


# ---------------------------------------------------------------------------
# Cumulative progress markdown
# ---------------------------------------------------------------------------

def write_progress_markdown(state: Dict[str, Any], tracker: TrueSkillTracker) -> None:
    lines: List[str] = []
    lines.append("# Champion Self-Improvement Progress\n\n")
    lines.append(f"_Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n\n")
    lines.append(f"**Generation:** {state['generation']}  \n")
    lines.append(f"**Snapshot rows accumulated:** {state.get('total_snapshot_rows', 0)}  \n")
    last_refit = state.get("last_refit_generation", "never")
    lines.append(f"**Last weight re-fit:** generation {last_refit}  \n")

    champ_rating = tracker.get_rating(CHAMPION_ID)
    cons = champ_rating["conservative"]
    bar = _human_progress_bar(cons)
    gap = HUMAN_TARGET_CONSERVATIVE - cons
    lines.append(f"**Human-target progress:** {bar}  \n")
    if gap <= 0:
        lines.append(f"**Status:** ✅ Champion exceeds human target (μ-3σ = {cons:.2f})\n\n")
    else:
        lines.append(f"**Status:** Gap = {gap:.2f} points (champion μ-3σ = {cons:.2f})\n\n")

    # Leaderboard
    lines.append("## TrueSkill Leaderboard\n\n")
    lines.append("| Rank | Agent | μ | σ | μ-3σ | Games |\n")
    lines.append("|------|-------|---|---|------|-------|\n")
    for entry in tracker.get_leaderboard():
        marker = " 👑" if entry["agent_id"] == CHAMPION_ID else ""
        lines.append(
            f"| {entry['rank']} | {entry['agent_id']}{marker} | "
            f"{entry['mu']:.2f} | {entry['sigma']:.2f} | "
            f"{entry['conservative']:.2f} | {entry['games_played']} |\n"
        )

    # Generation trend
    history = state.get("history", [])
    if history:
        lines.append("\n## Champion TrueSkill Trend\n\n")
        lines.append("| Gen | μ | σ | μ-3σ | WR% | AvgScore | Pool | Notes |\n")
        lines.append("|-----|---|---|------|-----|----------|------|-------|\n")
        for rec in history:
            notes = []
            if rec.get("evaluator_refitted"):
                notes.append(f"R²={rec.get('refit_r2_global', 0):.3f}")
            if rec.get("promoted"):
                notes.append(f"promoted:{rec['promoted']}")
            pool_str = ", ".join(rec.get("challengers", []))
            lines.append(
                f"| {rec['generation']} "
                f"| {rec['champion_mu']:.2f} "
                f"| {rec['champion_sigma']:.2f} "
                f"| {rec['champion_conservative']:.2f} "
                f"| {rec.get('champion_win_rate', 0)*100:.1f}% "
                f"| {rec.get('champion_avg_score', 0):.1f} "
                f"| {pool_str} "
                f"| {'; '.join(notes) if notes else '—'} |\n"
            )

    # Current champion params
    lines.append("\n## Current Champion Parameters\n\n")
    lines.append("```json\n")
    lines.append(json.dumps(state["champion_params"]["params"], indent=2))
    lines.append("\n```\n")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_MD.write_text("".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_loop(args: argparse.Namespace) -> None:
    state = load_state()
    auto_promote = not args.no_promote

    for gen_offset in range(args.generations):
        generation = state["generation"] + gen_offset + 1
        rng = random.Random(generation * 997 + 42)
        seed = generation * 7919

        tracker = build_tracker(state)

        # Save checkpoint of current champion at start of this generation
        save_champion_checkpoint(state, tracker)

        # Build this generation's lineup
        champion_cfg = _build_champion_agent_config(state["champion_params"])
        challengers = select_challengers(state, rng)

        # Capture ratings before this run for delta reporting
        ratings_before = snapshot_ratings(tracker)

        # Run arena
        run_dir = run_generation_arena(generation, champion_cfg, challengers, args.games_per_gen, seed)

        # Load game records
        games = load_games(run_dir)
        win_stats = agent_win_stats(games)

        # Update TrueSkill
        update_trueskill_from_games(tracker, games)

        # Accumulate snapshot rows
        total_rows = accumulate_snapshots(run_dir)
        state["total_snapshot_rows"] = total_rows

        # Champion summary stats from game records
        champ_ws = win_stats.get(CHAMPION_ID, {})

        # Maybe refit evaluator weights
        refit_result: Optional[Dict[str, Any]] = None
        gens_since_refit = generation - state.get("last_refit_generation", -999)
        if total_rows >= MIN_ROWS_FOR_REFIT and gens_since_refit >= REFIT_INTERVAL:
            refit_result = refit_evaluator_weights()
            if refit_result:
                apply_refit_to_champion(refit_result, state)
                state["last_refit_generation"] = generation
                tracker.reset_agent(CHAMPION_ID, increase_sigma=True)
                print("[champion_loop] New evaluator weights applied; champion σ reset")

        # Check for promotion
        promoted = check_and_apply_promotion(tracker, state, auto_promote)

        # Record generation
        champ_rating = tracker.get_rating(CHAMPION_ID)
        gen_record: Dict[str, Any] = {
            "generation": generation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_dir": run_dir,
            "games": args.games_per_gen,
            "challengers": [c["name"] for c in challengers],
            "champion_mu": champ_rating["mu"],
            "champion_sigma": champ_rating["sigma"],
            "champion_conservative": champ_rating["conservative"],
            "champion_games_played": champ_rating["games_played"],
            "champion_win_rate": champ_ws.get("win_rate", 0.0),
            "champion_avg_score": champ_ws.get("avg_score", 0.0),
            "evaluator_refitted": refit_result is not None,
            "refit_r2_global": refit_result["r2_global"] if refit_result else None,
            "promoted": promoted,
            "total_snapshot_rows": total_rows,
        }
        state["history"].append(gen_record)
        state["generation"] = generation

        persist_tracker(tracker, state)
        save_state(state)
        write_progress_markdown(state, tracker)

        # Per-run report
        write_run_report(
            generation=generation,
            run_dir=run_dir,
            challengers=challengers,
            win_stats=win_stats,
            tracker=tracker,
            ratings_before=ratings_before,
            promoted=promoted,
            refit_result=refit_result,
            total_snapshot_rows=total_rows,
        )

        # Console summary
        print(f"\n[champion_loop] Generation {generation} complete")
        print(
            f"  Champion: μ={champ_rating['mu']:.2f}  "
            f"σ={champ_rating['sigma']:.2f}  "
            f"μ-3σ={champ_rating['conservative']:.2f}  "
            f"WR={champ_ws.get('win_rate', 0)*100:.1f}%  "
            f"AvgScore={champ_ws.get('avg_score', 0):.1f}"
        )
        if promoted:
            print(f"  *** PROMOTED: {promoted} → champion ***")
        if refit_result:
            print(
                f"  Evaluator refitted: global R²={refit_result['r2_global']:.4f}, "
                f"{refit_result['rows_used']} rows"
            )
        print_leaderboard(tracker)

    print(f"\n[champion_loop] All {args.generations} generation(s) complete.")
    print(f"  Progress report : {PROGRESS_MD}")
    print(f"  Per-gen reports : {REPORTS_DIR}/")
    print(f"  State           : {STATE_FILE}")


# ---------------------------------------------------------------------------
# Force refit (standalone)
# ---------------------------------------------------------------------------

def force_refit(state: Dict[str, Any]) -> None:
    tracker = build_tracker(state)
    refit_result = refit_evaluator_weights()
    if refit_result:
        apply_refit_to_champion(refit_result, state)
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
        help="Number of generations to run (default: 1)",
    )
    parser.add_argument(
        "--games-per-gen", type=int, default=20,
        help="Arena games per generation (default: 20)",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="Print current progress without running any games",
    )
    parser.add_argument(
        "--refit", action="store_true",
        help="Force evaluator weight re-fit from accumulated snapshots and exit",
    )
    parser.add_argument(
        "--no-promote", action="store_true",
        help="Disable automatic champion promotion when a challenger wins",
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
