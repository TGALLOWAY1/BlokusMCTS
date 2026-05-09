#!/usr/bin/env python
"""Champion Self-Improvement Loop.

Runs repeated arena generations where the champion competes against a
randomized pool of challengers drawn from a tiered catalog:
  Tier 0 — baselines (heuristic, random) — rating anchors, always eligible
  Tier 1 — weak MCTS (50 / 100 ms) — calibration anchors
  Tier 2 — standalone strong MCTS — realistic challengers that CAN be promoted
  Tier 3 — champion-based variants (param overrides) — hypothesis testing

After each generation:
  - TrueSkill ratings are updated for all agents and persisted across runs
  - Snapshot data (including se_ state-evaluator features) is accumulated
  - If a Tier 0-2 challenger beats the champion by PROMOTION_MARGIN with
    enough game evidence, its config is adopted as the new champion
  - Every REFIT_INTERVAL generations the evaluator phase weights are
    re-derived via per-phase linear regression on accumulated snapshots
  - A detailed markdown progress report is written, including progress
    toward the human-proxy goal

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

REFIT_INTERVAL = 3
MIN_ROWS_FOR_REFIT = 200
WEIGHT_SCALE = 0.30

MAX_CHECKPOINTS_IN_POOL = 3

CHAMPION_ID = "champion"

# Human proxy: the heuristic agent approximates a typical human Blokus player.
# Goal: champion's conservative TrueSkill (μ-3σ) exceeds the proxy's μ.
HUMAN_PROXY_ID = "pool_heuristic"

# Auto-promotion: challenger must beat champion conservative TS by this margin
# with MIN_GAMES_FOR_PROMOTION evidence before being adopted.
PROMOTION_MARGIN = 0.5
MIN_GAMES_FOR_PROMOTION = 20

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
# Challenger catalog — tiered pool of agents.
#
# Entries with "params_override" are champion-based variants (Tier 3).
# All other entries carry their own complete config and may be promoted.
# ---------------------------------------------------------------------------

CHALLENGER_CATALOG: List[Dict[str, Any]] = [
    # ── Tier 0: Baselines (rating anchors, human proxy) ───────────────────
    {
        "id": "pool_random", "tier": 0,
        "type": "random", "thinking_time_ms": None, "params": {},
    },
    {
        "id": "pool_heuristic", "tier": 0,
        "type": "heuristic", "thinking_time_ms": None, "params": {},
    },

    # ── Tier 1: Weak MCTS (calibration) ──────────────────────────────────
    {
        "id": "pool_mcts_50ms", "tier": 1, "type": "mcts",
        "thinking_time_ms": 50,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
            "exploration_constant": 1.414,
        },
    },
    {
        "id": "pool_mcts_100ms", "tier": 1, "type": "mcts",
        "thinking_time_ms": 100,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
            "exploration_constant": 1.414,
        },
    },
    {
        "id": "pool_mcts_200ms", "tier": 1, "type": "mcts",
        "thinking_time_ms": 200,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 10.0,
            "exploration_constant": 1.414,
        },
    },

    # ── Tier 2: Standalone MCTS (realistic challengers, promotable) ───────
    {
        "id": "pool_deploy_easy", "tier": 2, "type": "mcts",
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
        "id": "pool_deploy_medium", "tier": 2, "type": "mcts",
        "thinking_time_ms": 450,
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
        "id": "pool_deploy_hard", "tier": 2, "type": "mcts",
        "thinking_time_ms": 900,
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
    {
        "id": "pool_rave_k500", "tier": 2, "type": "mcts",
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
        },
    },
    {
        "id": "pool_rave_k5000", "tier": 2, "type": "mcts",
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
        },
    },
    {
        "id": "pool_heuristic_rollout", "tier": 2, "type": "mcts",
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
        },
    },
    {
        "id": "pool_full_rollout", "tier": 2, "type": "mcts",
        "thinking_time_ms": 200,
        "params": {
            "deterministic_time_budget": True,
            "iterations_per_ms": 0.5,
            "exploration_constant": 1.414,
            "rollout_policy": "random",
            "minimax_backup_alpha": 0.25,
            "rave_enabled": True,
            "rave_k": 1000,
        },
    },
    {
        "id": "pool_progressive_widening", "tier": 2, "type": "mcts",
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
            "progressive_widening_enabled": True,
            "pw_c": 2.0,
            "pw_alpha": 0.5,
        },
    },
    {
        "id": "pool_l9_full", "tier": 2, "type": "mcts",
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
        "id": "pool_nst", "tier": 2, "type": "mcts",
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
            "nst_enabled": True,
            "nst_weight": 0.5,
        },
    },

    # ── Tier 3: Champion-based variants (hypothesis testing, not promoted) ─
    # These override specific params of the current champion config.
    {"id": "mcts_high_c",         "tier": 3, "params_override": {"exploration_constant": 2.5}},
    {"id": "mcts_low_c",          "tier": 3, "params_override": {"exploration_constant": 0.7}},
    {"id": "mcts_heuristic_roll", "tier": 3, "params_override": {"rollout_policy": "heuristic"}},
    {"id": "mcts_deep_cutoff",    "tier": 3, "params_override": {
        "rollout_cutoff_depth": 15, "adaptive_rollout_depth_enabled": False}},
    {"id": "mcts_no_cutoff",      "tier": 3, "params_override": {
        "rollout_cutoff_depth": None, "adaptive_rollout_depth_enabled": False}},
    {"id": "mcts_high_rave",      "tier": 3, "params_override": {"rave_k": 5000}},
    {"id": "mcts_no_rave",        "tier": 3, "params_override": {"rave_enabled": False}},
    {"id": "mcts_minimax",        "tier": 3, "params_override": {"minimax_backup_alpha": 0.5}},
    {"id": "mcts_loss_avoid",     "tier": 3, "params_override": {
        "loss_avoidance_enabled": True, "loss_avoidance_threshold": -30.0}},
    {"id": "mcts_sufficiency",    "tier": 3, "params_override": {"sufficiency_threshold_enabled": True}},
    {"id": "mcts_opp_model",      "tier": 3, "params_override": {
        "opponent_modeling_enabled": True, "alliance_detection_enabled": True}},
    {"id": "mcts_fast_iters",     "tier": 3, "params_override": {"thinking_time_ms": 250}},
    {"id": "mcts_slow_iters",     "tier": 3, "params_override": {"thinking_time_ms": 1000}},
    {"id": "mcts_nst_variant",    "tier": 3, "params_override": {"nst_enabled": True, "nst_weight": 0.5}},
    {"id": "mcts_adaptive_all",   "tier": 3, "params_override": {
        "adaptive_exploration_enabled": True,
        "adaptive_rollout_depth_enabled": True,
        "sufficiency_threshold_enabled": True,
        "loss_avoidance_enabled": True,
    }},
]

# Fast lookup by ID
CATALOG_BY_ID: Dict[str, Dict[str, Any]] = {e["id"]: e for e in CHALLENGER_CATALOG}

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
        "promotions": [],    # {"generation", "from_id", "reason"}
        "total_snapshot_rows": 0,
        "last_refit_generation": -1,
    }


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        with STATE_FILE.open() as f:
            s = json.load(f)
        # backfill fields added in newer versions
        s.setdefault("promotions", [])
        return s
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
    cfg = copy.deepcopy(params)
    cfg["name"] = CHAMPION_ID
    return cfg


def _build_challenger_config(
    entry: Dict[str, Any],
    base_champion_params: Dict[str, Any],
) -> Dict[str, Any]:
    """Build an arena agent config from a catalog entry.

    Tier 0-2 entries carry their own complete config.
    Tier 3 entries use params_override merged onto the champion config.
    """
    if "params_override" in entry:
        # Tier 3: merge overrides into current champion config
        cfg = copy.deepcopy(base_champion_params)
        override = dict(entry["params_override"])
        if "thinking_time_ms" in override:
            cfg["thinking_time_ms"] = override.pop("thinking_time_ms")
        cfg["params"].update(override)
        cfg["name"] = entry["id"]
        return cfg
    else:
        # Tier 0-2: standalone config
        return {
            "name": entry["id"],
            "type": entry.get("type", "mcts"),
            "thinking_time_ms": entry.get("thinking_time_ms"),
            "params": copy.deepcopy(entry.get("params", {})),
        }


def _build_checkpoint_agent_config(checkpoint: Dict[str, Any]) -> Dict[str, Any]:
    cfg = copy.deepcopy(checkpoint["params"])
    cfg["name"] = checkpoint["id"]
    return cfg


# ---------------------------------------------------------------------------
# Challenger pool selection
# ---------------------------------------------------------------------------

def select_challengers(
    state: Dict[str, Any],
    base_params: Dict[str, Any],
    rng: random.Random,
) -> List[Dict[str, Any]]:
    """Choose 3 challengers for this generation.

    Selection strategy (3 slots for a 4-player game):
      Slot 0 — pool_heuristic (always; human-proxy baseline)
      Slot 1 — recent champion checkpoint if available, else random Tier 0-2
      Slot 2 — random entry from full catalog (Tier 2-3 weighted)

    This ensures every generation tests the human proxy, benchmarks against
    the champion's own history, and explores the parameter/strategy space.
    """
    challengers: List[Dict[str, Any]] = []
    used_ids: set = set()

    # ── Slot 0: heuristic (human proxy / rating anchor) ────────────────────
    heuristic_entry = CATALOG_BY_ID["pool_heuristic"]
    challengers.append(_build_challenger_config(heuristic_entry, base_params))
    used_ids.add("pool_heuristic")

    # ── Slot 1: recent checkpoint (regression test) or Tier 0-2 standalone ─
    checkpoints = state.get("checkpoints", [])
    recent_ckpts = [c for c in checkpoints[-MAX_CHECKPOINTS_IN_POOL:]]
    if recent_ckpts:
        ckpt = rng.choice(recent_ckpts)
        challengers.append(_build_checkpoint_agent_config(ckpt))
        used_ids.add(ckpt["id"])
    else:
        # No checkpoints yet — use a Tier 1 calibration anchor
        tier1 = [e for e in CHALLENGER_CATALOG if e["tier"] == 1 and e["id"] not in used_ids]
        if tier1:
            entry = rng.choice(tier1)
            challengers.append(_build_challenger_config(entry, base_params))
            used_ids.add(entry["id"])
        else:
            random_entry = CATALOG_BY_ID["pool_random"]
            challengers.append(_build_challenger_config(random_entry, base_params))
            used_ids.add("pool_random")

    # ── Slot 2: random from Tier 2-3 (favor unexplored / strong opponents) ─
    # Weight Tier 2 (standalone) twice as heavily as Tier 3 (variants) so
    # we regularly face promotable challengers.
    tier2 = [e for e in CHALLENGER_CATALOG if e["tier"] == 2 and e["id"] not in used_ids]
    tier3 = [e for e in CHALLENGER_CATALOG if e["tier"] == 3 and e["id"] not in used_ids]
    pool = tier2 * 2 + tier3
    if pool:
        entry = rng.choice(pool)
        challengers.append(_build_challenger_config(entry, base_params))
    else:
        # Fallback: any unused catalog entry
        remaining = [e for e in CHALLENGER_CATALOG if e["id"] not in used_ids]
        if remaining:
            challengers.append(_build_challenger_config(rng.choice(remaining), base_params))

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

    cmd = [sys.executable, "scripts/arena.py", "--config", str(config_path)]
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Arena exited with code {result.returncode}")

    run_dir = _find_latest_run(ARENA_RUN_ROOT)
    if run_dir is None:
        raise RuntimeError("Could not locate arena output directory")
    print(f"[champion_loop] Run saved to: {run_dir}")
    return run_dir


# ---------------------------------------------------------------------------
# Results parsing
# ---------------------------------------------------------------------------

def parse_summary(run_dir: str) -> Dict[str, Any]:
    path = Path(run_dir) / "summary.json"
    with path.open() as f:
        return json.load(f)


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
        w, r2 = _fit_phase(df)
        phase_weights = {"early": w, "mid": w, "late": w}
        r2_by_phase = {"early": r2, "mid": r2, "late": r2}
        print(f"  Global fit: R²={r2:.4f}")

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
    tracker._ratings[ckpt_id] = tracker._model.rating(
        mu=rating["mu"], sigma=rating["sigma"]
    )
    tracker._games_played[ckpt_id] = rating["games_played"]
    print(f"[champion_loop] Checkpoint saved: {ckpt_id} (μ={rating['mu']:.2f})")


# ---------------------------------------------------------------------------
# Auto-promotion
# ---------------------------------------------------------------------------

def _check_promotion(
    tracker: TrueSkillTracker,
    state: Dict[str, Any],
) -> Optional[str]:
    """Return the ID of a challenger that should replace the champion, or None.

    Only Tier 0-2 standalone catalog entries (and their checkpoints) are
    eligible for promotion. Tier 3 variants test hypotheses but are never
    directly adopted — their winning params inform the next refit instead.
    """
    if CHAMPION_ID not in tracker.agent_ids:
        return None
    champ_cons = tracker.get_rating(CHAMPION_ID)["conservative"]
    threshold = champ_cons + PROMOTION_MARGIN

    best_id: Optional[str] = None
    best_cons = threshold  # must exceed threshold to win

    for entry in CHALLENGER_CATALOG:
        if entry["tier"] >= 3:
            continue  # variants are not promotable
        eid = entry["id"]
        if eid not in tracker.agent_ids:
            continue
        r = tracker.get_rating(eid)
        if r["games_played"] < MIN_GAMES_FOR_PROMOTION:
            continue
        if r["conservative"] > best_cons:
            best_cons = r["conservative"]
            best_id = eid

    return best_id


def _apply_promotion(
    winner_id: str,
    state: Dict[str, Any],
    tracker: TrueSkillTracker,
    generation: int,
) -> None:
    """Adopt the winning challenger's config as the new champion."""
    entry = CATALOG_BY_ID.get(winner_id)
    if entry is None:
        print(f"[champion_loop] Promotion skipped: {winner_id} not in catalog")
        return

    # Build new champion params from the winner's standalone config
    prev_phase_weights = state["champion_params"]["params"].get("state_eval_phase_weights")
    new_params: Dict[str, Any] = {
        "type": entry.get("type", "mcts"),
        "thinking_time_ms": entry.get("thinking_time_ms", BASE_CHAMPION_PARAMS["thinking_time_ms"]),
        "params": copy.deepcopy(entry.get("params", {})),
    }
    # Preserve the most recent calibrated phase weights across promotions
    if prev_phase_weights is not None and "state_eval_phase_weights" not in new_params["params"]:
        new_params["params"]["state_eval_phase_weights"] = prev_phase_weights

    state["champion_params"] = new_params

    winner_rating = tracker.get_rating(winner_id)
    print(
        f"\n[champion_loop] ★ CHAMPION PROMOTED ★  {winner_id} → champion  "
        f"(μ={winner_rating['mu']:.2f}, cons={winner_rating['conservative']:.2f})"
    )

    # Transfer the winner's TrueSkill to the champion slot
    tracker._ratings[CHAMPION_ID] = tracker._model.rating(
        mu=winner_rating["mu"], sigma=winner_rating["sigma"]
    )
    tracker._games_played[CHAMPION_ID] = winner_rating["games_played"]

    state["promotions"].append({
        "generation": generation,
        "from_id": winner_id,
        "winner_mu": winner_rating["mu"],
        "winner_conservative": winner_rating["conservative"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# Human-proxy goal tracking
# ---------------------------------------------------------------------------

def _compute_goal_progress(tracker: TrueSkillTracker) -> Dict[str, Any]:
    """Estimate progress toward reliably beating the human-proxy agent.

    The proxy is pool_heuristic.  Goal achieved when:
        champion μ-3σ  ≥  proxy μ

    Progress is expressed as a [0, 150] percentage: how far champion's
    conservative estimate has travelled from the random-baseline floor
    toward (and past) the proxy's mean.
    """
    if CHAMPION_ID not in tracker.agent_ids:
        return {"progress_pct": 0.0, "status": "no champion data"}

    champ = tracker.get_rating(CHAMPION_ID)
    champ_cons = champ["conservative"]
    champ_mu = champ["mu"]

    proxy_mu = 25.0  # TrueSkill default until we have data
    if HUMAN_PROXY_ID in tracker.agent_ids:
        proxy_mu = tracker.get_rating(HUMAN_PROXY_ID)["mu"]

    baseline_cons = 0.0
    if "pool_random" in tracker.agent_ids:
        baseline_cons = tracker.get_rating("pool_random")["conservative"]

    target_gap = proxy_mu - baseline_cons
    achieved = champ_cons - baseline_cons
    progress = (achieved / max(target_gap, 1.0)) * 100.0 if target_gap > 0 else 0.0
    progress = max(0.0, min(progress, 150.0))

    if champ_cons >= proxy_mu:
        status = "GOAL ACHIEVED — conservative TS above human proxy"
    elif champ_mu >= proxy_mu:
        status = "LIKELY — μ above proxy, need more evidence (lower σ)"
    elif champ_cons >= proxy_mu - 1.0:
        status = "CLOSE — within 1 TrueSkill point of goal"
    else:
        status = "IN PROGRESS"

    return {
        "progress_pct": progress,
        "champion_conservative": champ_cons,
        "champion_mu": champ_mu,
        "human_proxy_mu": proxy_mu,
        "baseline_conservative": baseline_cons,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Progress reporting
# ---------------------------------------------------------------------------

def _bar(value: float, width: int = 20) -> str:
    filled = int(round(min(max(value, 0.0), 1.0) * width))
    return "█" * filled + "░" * (width - filled)


def print_leaderboard(tracker: TrueSkillTracker) -> None:
    board = tracker.get_leaderboard()
    goal = _compute_goal_progress(tracker)
    proxy_mu = goal.get("human_proxy_mu", 25.0)
    print(f"\n{'─'*72}")
    print(f"  {'#':>2}  {'Agent':<30}  {'μ':>6}  {'σ':>5}  {'μ-3σ':>7}  {'Games':>5}  {'Notes'}")
    print(f"{'─'*72}")
    for entry in board:
        notes = ""
        if entry["agent_id"] == CHAMPION_ID:
            notes = "★ champion"
        elif entry["agent_id"] == HUMAN_PROXY_ID:
            notes = "≈ human proxy"
        print(
            f"  {entry['rank']:>2}  {entry['agent_id']:<30}  "
            f"{entry['mu']:>6.2f}  {entry['sigma']:>5.2f}  "
            f"{entry['conservative']:>7.2f}  {entry['games_played']:>5}  {notes}"
        )
    print(f"{'─'*72}")
    pct = goal["progress_pct"]
    bar = _bar(pct / 100.0)
    print(f"  Human-proxy goal: {bar} {pct:.1f}%  [{goal['status']}]")
    print(f"  (target: champion μ-3σ={goal['champion_conservative']:.2f}"
          f" ≥ proxy μ={proxy_mu:.2f})\n")


def write_progress_markdown(state: Dict[str, Any], tracker: TrueSkillTracker) -> None:
    goal = _compute_goal_progress(tracker)
    lines: List[str] = []
    lines.append("# Champion Self-Improvement Progress\n")
    lines.append(f"_Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n")
    lines.append(f"\n**Generation:** {state['generation']}  ")
    lines.append(f"**Snapshot rows accumulated:** {state.get('total_snapshot_rows', 0)}  ")
    lines.append(f"**Last weight re-fit:** generation {state.get('last_refit_generation', 'never')}  ")
    lines.append(f"**Promotions:** {len(state.get('promotions', []))}\n")

    # Goal progress
    pct = goal["progress_pct"]
    bar = _bar(pct / 100.0, width=30)
    lines.append(f"\n## Goal: Beat Human-Level Play\n")
    lines.append(f"**Human proxy:** `{HUMAN_PROXY_ID}` (heuristic agent ≈ average Blokus player)  \n")
    lines.append(f"**Target:** champion μ−3σ ≥ proxy μ  \n")
    lines.append(f"**Progress:** `{bar}` **{pct:.1f}%**  \n")
    lines.append(f"**Status:** {goal['status']}  \n")
    lines.append(
        f"_(champion cons={goal['champion_conservative']:.2f}, "
        f"proxy μ={goal['human_proxy_mu']:.2f}, "
        f"baseline cons={goal['baseline_conservative']:.2f})_\n"
    )

    # Leaderboard
    lines.append("\n## TrueSkill Leaderboard\n")
    lines.append("| Rank | Agent | μ | σ | μ−3σ | Games | Notes |\n")
    lines.append("|------|-------|---|---|------|-------|-------|\n")
    for entry in tracker.get_leaderboard():
        notes = ""
        if entry["agent_id"] == CHAMPION_ID:
            notes = "★ champion"
        elif entry["agent_id"] == HUMAN_PROXY_ID:
            notes = "≈ human proxy"
        lines.append(
            f"| {entry['rank']} | `{entry['agent_id']}`{'' if not notes else ' **'+notes+'**'} | "
            f"{entry['mu']:.2f} | {entry['sigma']:.2f} | "
            f"{entry['conservative']:.2f} | {entry['games_played']} | {notes} |\n"
        )

    # Champion trend
    history = state.get("history", [])
    if history:
        lines.append("\n## Champion TrueSkill Trend\n")
        lines.append("| Gen | μ | σ | μ−3σ | WR% | AvgScore | Goal% | Challengers | Events |\n")
        lines.append("|-----|---|---|------|-----|----------|-------|-------------|--------|\n")
        promotions_by_gen = {p["generation"]: p["from_id"] for p in state.get("promotions", [])}
        for rec in history:
            g = rec["generation"]
            events = []
            if rec.get("evaluator_refitted"):
                events.append("refit")
            if g in promotions_by_gen:
                events.append(f"promoted←{promotions_by_gen[g]}")
            lines.append(
                f"| {g} "
                f"| {rec['champion_mu']:.2f} "
                f"| {rec['champion_sigma']:.2f} "
                f"| {rec['champion_conservative']:.2f} "
                f"| {rec.get('champion_win_rate', 0)*100:.1f}% "
                f"| {rec.get('champion_avg_score', 0):.1f} "
                f"| {rec.get('goal_progress_pct', 0):.1f}% "
                f"| {', '.join(rec.get('challengers', []))} "
                f"| {', '.join(events) if events else '—'} |\n"
            )

    # Promotion history
    promotions = state.get("promotions", [])
    if promotions:
        lines.append("\n## Promotion Events\n")
        lines.append("| Gen | New Champion | μ | μ−3σ | Timestamp |\n")
        lines.append("|-----|-------------|---|------|----------|\n")
        for p in promotions:
            lines.append(
                f"| {p['generation']} | `{p['from_id']}` "
                f"| {p['winner_mu']:.2f} | {p['winner_conservative']:.2f} "
                f"| {p['timestamp'][:19]} |\n"
            )

    # Current champion params
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
    print(f"  Trend (last {min(5, len(history))} generations):")
    for rec in history[-5:]:
        events = []
        if rec.get("evaluator_refitted"):
            events.append("REFITTED")
        if rec.get("promoted_from"):
            events.append(f"PROMOTED←{rec['promoted_from']}")
        event_str = f"  [{', '.join(events)}]" if events else ""
        print(
            f"    Gen {rec['generation']:>3}: μ={rec['champion_mu']:.2f}  "
            f"σ={rec['champion_sigma']:.2f}  "
            f"μ-3σ={rec['champion_conservative']:.2f}  "
            f"WR={rec.get('champion_win_rate', 0)*100:.1f}%  "
            f"Goal={rec.get('goal_progress_pct', 0):.1f}%{event_str}"
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

        # Update TrueSkill
        update_trueskill_from_run(tracker, run_dir)

        # Check for promotion (before refit — use current eval weights)
        promoted_from: Optional[str] = None
        if not args.no_promote:
            winner_id = _check_promotion(tracker, state)
            if winner_id is not None:
                _apply_promotion(winner_id, state, tracker, generation)
                promoted_from = winner_id

        # Accumulate snapshots
        total_rows = accumulate_snapshots(run_dir)
        state["total_snapshot_rows"] = total_rows

        # Parse summary for win-rate / avg-score reporting
        summary = parse_summary(run_dir)
        champ_summary = summary.get("agents", {}).get(CHAMPION_ID, {})

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
                tracker.reset_agent(CHAMPION_ID, increase_sigma=True)
                print("[champion_loop] Applied new evaluator weights to champion, reset σ")

        # Compute goal progress
        goal = _compute_goal_progress(tracker)

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
            "champion_win_rate": champ_summary.get("win_rate", 0.0),
            "champion_avg_score": champ_summary.get("avg_score", 0.0),
            "evaluator_refitted": refit_result is not None,
            "refit_r2_global": refit_result["r2_global"] if refit_result else None,
            "total_snapshot_rows": total_rows,
            "goal_progress_pct": goal["progress_pct"],
            "goal_status": goal["status"],
            "promoted_from": promoted_from,
        }
        state["history"].append(gen_record)
        state["generation"] = generation

        persist_tracker(tracker, state)
        save_state(state)
        write_progress_markdown(state, tracker)

        # Console summary
        print(f"\n[champion_loop] Generation {generation} complete")
        print(
            f"  Champion: μ={champion_rating['mu']:.2f}  "
            f"σ={champion_rating['sigma']:.2f}  "
            f"μ-3σ={champion_rating['conservative']:.2f}  "
            f"WR={champ_summary.get('win_rate', 0)*100:.1f}%  "
            f"AvgScore={champ_summary.get('avg_score', 0):.1f}"
        )
        if promoted_from:
            print(f"  ★ CHAMPION PROMOTED from {promoted_from}")
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
    parser.add_argument(
        "--no-promote", action="store_true",
        help="Disable automatic champion promotion (useful for pure eval-refit runs)"
    )
    parser.add_argument(
        "--promotion-margin", type=float, default=PROMOTION_MARGIN,
        help=f"Conservative TrueSkill margin a challenger must beat champion by "
             f"to trigger promotion (default: {PROMOTION_MARGIN})"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    # Allow CLI to override module-level constant
    global PROMOTION_MARGIN
    PROMOTION_MARGIN = args.promotion_margin

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
