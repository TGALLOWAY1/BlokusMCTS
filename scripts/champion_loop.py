#!/usr/bin/env python
"""Champion Self-Improvement Loop.

Runs repeated arena generations where the champion competes against a
randomized pool of challengers (previous champion checkpoints, heuristic/
random baselines, and MCTS variants at three difficulty tiers).

After each generation:
  - TrueSkill ratings are updated for all agents and persisted across runs
  - Snapshot data (including se_ state-evaluator features) is accumulated
  - Every REFIT_INTERVAL generations the evaluator phase weights are
    re-derived via per-phase linear regression on accumulated snapshots
  - The champion is promoted when a challenger earns a higher conservative
    TrueSkill estimate with sufficient game evidence
  - A detailed markdown progress report is written, including the champion's
    gap relative to the heuristic "human-proxy" baseline

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
CALIBRATED_WEIGHTS_FILE = DATA_DIR / "layer6_calibrated_weights.json"
ARENA_RUN_ROOT = "arena_runs/champion_loop"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SE_FEATURE_COLS = [f"se_{f}" for f in FEATURE_NAMES]

REFIT_INTERVAL = 3          # generations between evaluator weight re-fits
MIN_ROWS_FOR_REFIT = 200    # minimum snapshot rows before attempting re-fit
WEIGHT_SCALE = 0.30         # maximum weight magnitude after normalisation

MAX_CHECKPOINTS_IN_POOL = 3

CHAMPION_ID = "champion"
HUMAN_PROXY_ID = "heuristic"  # heuristic agent tracked as the "human-level proxy"

# Conservative-rating gap (champion - heuristic) needed to declare the
# champion "reliably better than human-proxy" for milestone reporting.
HUMAN_PROXY_TARGET_GAP = 5.0

# How many games a pool agent must have before it can displace the champion.
MIN_GAMES_FOR_PROMOTION = 20


# ---------------------------------------------------------------------------
# Load calibrated phase weights
# ---------------------------------------------------------------------------

def _load_calibrated_phase_weights() -> Optional[Dict[str, Any]]:
    """Return phase_weights from data/layer6_calibrated_weights.json, or None."""
    if not CALIBRATED_WEIGHTS_FILE.exists():
        return None
    try:
        with CALIBRATED_WEIGHTS_FILE.open() as f:
            data = json.load(f)
        return data.get("phase_weights")
    except (json.JSONDecodeError, KeyError):
        return None


# ---------------------------------------------------------------------------
# Champion starting configuration (loaded with calibrated weights if available)
# ---------------------------------------------------------------------------

def _build_base_champion_params() -> Dict[str, Any]:
    phase_weights = _load_calibrated_phase_weights()
    return {
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
            "state_eval_phase_weights": phase_weights,
        },
    }


# ---------------------------------------------------------------------------
# Tiered challenger pool
#
# TIER_WEAK   — baselines that anchor the lower end of the rating scale
# TIER_MEDIUM — standard MCTS variants (comparable to or slightly below champion)
# TIER_STRONG — full-stack variants that push the champion hard
#
# Each entry has:
#   "id"     : stable agent name (used for TrueSkill continuity)
#   "type"   : "random" | "heuristic" | "mcts"  (default "mcts")
#   "thinking_time_ms" (optional, defaults to champion's time)
#   "params_override"  (optional, merged over champion base params)
# ---------------------------------------------------------------------------

TIER_WEAK: List[Dict[str, Any]] = [
    {"id": "pool_random",      "type": "random"},
    {"id": "pool_mcts_50ms",   "type": "mcts",
     "thinking_time_ms": 50,
     "params_override": {"progressive_widening_enabled": False,
                         "rave_enabled": False,
                         "adaptive_rollout_depth_enabled": False}},
    {"id": "pool_mcts_100ms",  "type": "mcts",
     "thinking_time_ms": 100,
     "params_override": {"progressive_widening_enabled": False,
                         "rave_enabled": False,
                         "adaptive_rollout_depth_enabled": False}},
    {"id": "mcts_no_rave",     "params_override": {"rave_enabled": False}},
]

TIER_MEDIUM: List[Dict[str, Any]] = [
    {"id": "mcts_high_c",         "params_override": {"exploration_constant": 2.5}},
    {"id": "mcts_low_c",          "params_override": {"exploration_constant": 0.7}},
    {"id": "mcts_heuristic_roll", "params_override": {"rollout_policy": "heuristic"}},
    {"id": "mcts_deep_cutoff",    "params_override": {"rollout_cutoff_depth": 15,
                                                       "adaptive_rollout_depth_enabled": False}},
    {"id": "mcts_no_cutoff",      "params_override": {"rollout_cutoff_depth": None,
                                                       "adaptive_rollout_depth_enabled": False}},
    {"id": "mcts_high_rave",      "params_override": {"rave_k": 5000}},
    {"id": "pool_rave_k500",      "params_override": {"rave_k": 500}},
    {"id": "mcts_minimax",        "params_override": {"minimax_backup_alpha": 0.5}},
    {"id": "pool_heuristic_roll", "params_override": {"rollout_policy": "heuristic"}},
    {"id": "pool_full_rollout",   "params_override": {"rollout_cutoff_depth": None,
                                                       "adaptive_rollout_depth_enabled": False}},
    {"id": "pool_prog_widening",  "params_override": {"progressive_widening_enabled": True,
                                                       "pw_c": 2.0, "pw_alpha": 0.5}},
    {"id": "pool_nst",            "params_override": {"nst_enabled": True, "nst_weight": 0.5}},
]

TIER_STRONG: List[Dict[str, Any]] = [
    {"id": "mcts_loss_avoid",     "params_override": {"loss_avoidance_enabled": True,
                                                       "loss_avoidance_threshold": -30.0}},
    {"id": "mcts_sufficiency",    "params_override": {"sufficiency_threshold_enabled": True}},
    {"id": "mcts_opp_model",      "params_override": {"opponent_modeling_enabled": True,
                                                       "alliance_detection_enabled": True}},
    {"id": "mcts_slow_iters",     "thinking_time_ms": 1000, "params_override": {}},
    {"id": "pool_deploy_hard",    "thinking_time_ms": 900,
     "params_override": {"sufficiency_threshold_enabled": True,
                          "loss_avoidance_enabled": True,
                          "loss_avoidance_threshold": -50.0}},
    {"id": "pool_l9_full",        "params_override": {
        "adaptive_exploration_enabled": True,
        "adaptive_exploration_base": 1.414,
        "adaptive_exploration_avg_bf": 80.0,
        "adaptive_rollout_depth_enabled": True,
        "adaptive_rollout_depth_base": 5,
        "adaptive_rollout_depth_avg_bf": 80.0,
        "sufficiency_threshold_enabled": True,
        "loss_avoidance_enabled": True,
        "loss_avoidance_threshold": -50.0,
    }},
]

ALL_POOL_AGENTS: List[Dict[str, Any]] = TIER_WEAK + TIER_MEDIUM + TIER_STRONG


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def _default_state() -> Dict[str, Any]:
    return {
        "generation": 0,
        "champion_params": _build_base_champion_params(),
        "trueskill_ratings": {},
        "checkpoints": [],   # {"generation": N, "id": str, "mu": float, "params": dict}
        "history": [],       # per-generation records
        "total_snapshot_rows": 0,
        "last_refit_generation": -1,
    }


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        with STATE_FILE.open() as f:
            return json.load(f)
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
    tracker.load_ratings(state.get("trueskill_ratings", {}))
    return tracker


def persist_tracker(tracker: TrueSkillTracker, state: Dict[str, Any]) -> None:
    state["trueskill_ratings"] = tracker.get_ratings()


# ---------------------------------------------------------------------------
# Agent config builders
# ---------------------------------------------------------------------------

def _build_champion_agent_config(params: Dict[str, Any]) -> Dict[str, Any]:
    cfg = copy.deepcopy(params)
    cfg["name"] = CHAMPION_ID
    return cfg


def _build_checkpoint_agent_config(checkpoint: Dict[str, Any]) -> Dict[str, Any]:
    cfg = copy.deepcopy(checkpoint["params"])
    cfg["name"] = checkpoint["id"]
    return cfg


def _build_pool_agent_config(
    pool_entry: Dict[str, Any],
    base_params: Dict[str, Any],
) -> Dict[str, Any]:
    """Build an arena agent config from a pool entry merged over base champion params."""
    agent_type = pool_entry.get("type", "mcts")

    if agent_type != "mcts":
        return {
            "name": pool_entry["id"],
            "type": agent_type,
            "thinking_time_ms": None,
            "params": {},
        }

    cfg = copy.deepcopy(base_params)
    cfg["name"] = pool_entry["id"]

    if "thinking_time_ms" in pool_entry:
        cfg["thinking_time_ms"] = pool_entry["thinking_time_ms"]

    override = pool_entry.get("params_override", {})
    cfg["params"].update(override)
    return cfg


def _build_heuristic_agent_config() -> Dict[str, Any]:
    return {"name": HUMAN_PROXY_ID, "type": "heuristic", "thinking_time_ms": None, "params": {}}


# ---------------------------------------------------------------------------
# Challenger pool selection — tiered: 1 weak, 1 medium/checkpoint, 1 strong
# ---------------------------------------------------------------------------

def select_challengers(
    state: Dict[str, Any],
    base_params: Dict[str, Any],
    rng: random.Random,
) -> List[Dict[str, Any]]:
    """Choose 3 challengers for this generation.

    Slot 0 — always the heuristic "human proxy" (acts as a stable rating anchor)
    Slot 1 — recent checkpoint if available, else a random TIER_WEAK/TIER_MEDIUM agent
    Slot 2 — a random TIER_STRONG variant (pushes the champion at full strength)
    """
    challengers: List[Dict[str, Any]] = []
    used_ids: set = {CHAMPION_ID}

    # Slot 0: heuristic human proxy
    challengers.append(_build_heuristic_agent_config())
    used_ids.add(HUMAN_PROXY_ID)

    # Slot 1: checkpoint (if any) or random weak/medium agent
    checkpoints = state.get("checkpoints", [])
    recent_ckpts = checkpoints[-MAX_CHECKPOINTS_IN_POOL:]
    if recent_ckpts:
        ckpt = rng.choice(recent_ckpts)
        challengers.append(_build_checkpoint_agent_config(ckpt))
        used_ids.add(ckpt["id"])
    else:
        pool = [e for e in (TIER_WEAK + TIER_MEDIUM) if e["id"] not in used_ids]
        if pool:
            entry = rng.choice(pool)
            challengers.append(_build_pool_agent_config(entry, base_params))
            used_ids.add(entry["id"])
        else:
            challengers.append({"name": "pool_random", "type": "random",
                                 "thinking_time_ms": None, "params": {}})

    # Slot 2: strong variant
    pool = [e for e in TIER_STRONG if e["id"] not in used_ids]
    if not pool:
        pool = [e for e in TIER_MEDIUM if e["id"] not in used_ids]
    if pool:
        entry = rng.choice(pool)
        challengers.append(_build_pool_agent_config(entry, base_params))
    else:
        challengers.append({"name": "pool_mcts_100ms", "type": "mcts",
                             "thinking_time_ms": 100, "params": {}})

    return challengers


# ---------------------------------------------------------------------------
# Auto-promotion: promote a pool agent if it beats the champion
# ---------------------------------------------------------------------------

def check_and_promote(
    tracker: TrueSkillTracker,
    state: Dict[str, Any],
    challengers: List[Dict[str, Any]],
) -> Optional[str]:
    """Promote a challenger if it beats the champion. Returns promoted agent ID or None."""
    champ_rating = tracker.get_rating(CHAMPION_ID)
    champ_cons = champ_rating["conservative"]

    best_id: Optional[str] = None
    best_cons = champ_cons

    for cfg in challengers:
        name = cfg.get("name", "")
        if name in (CHAMPION_ID, HUMAN_PROXY_ID):
            continue
        r = tracker.get_rating(name)
        if r["games_played"] < MIN_GAMES_FOR_PROMOTION:
            continue
        if r["conservative"] > best_cons:
            best_cons = r["conservative"]
            best_id = name

    if best_id is None:
        return None

    print(f"\n[champion_loop] *** PROMOTION *** {best_id} → champion")
    print(f"  {best_id}: cons={best_cons:.2f}  champion: cons={champ_cons:.2f}")

    promoted_cfg: Optional[Dict[str, Any]] = None
    for cfg in challengers:
        if cfg.get("name") == best_id:
            promoted_cfg = copy.deepcopy(cfg)
            break

    if promoted_cfg is None:
        return None

    promoted_cfg["name"] = CHAMPION_ID
    state["champion_params"] = promoted_cfg

    promoted_rating = tracker.get_rating(best_id)
    tracker.load_ratings({"champion": promoted_rating})

    return best_id


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
    """Overwrite data/layer6_calibrated_weights.json with new weights."""
    payload = {
        "single_weights": refit["single_weights"],
        "phase_weights": refit["phase_weights"],
        "default_weights": dict(DEFAULT_WEIGHTS),
    }
    with CALIBRATED_WEIGHTS_FILE.open("w") as f:
        json.dump(payload, f, indent=2)
    print(f"[champion_loop] Saved calibrated weights → {CALIBRATED_WEIGHTS_FILE}")


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
    tracker.load_ratings({ckpt_id: rating})
    print(f"[champion_loop] Checkpoint saved: {ckpt_id} (μ={rating['mu']:.2f})")


# ---------------------------------------------------------------------------
# Progress reporting
# ---------------------------------------------------------------------------

def _human_proxy_gap(tracker: TrueSkillTracker) -> Optional[float]:
    """Conservative rating of champion minus conservative rating of human proxy."""
    all_agents = tracker.agent_ids
    if HUMAN_PROXY_ID not in all_agents or CHAMPION_ID not in all_agents:
        return None
    champ = tracker.get_rating(CHAMPION_ID)
    proxy = tracker.get_rating(HUMAN_PROXY_ID)
    return champ["conservative"] - proxy["conservative"]


def print_leaderboard(tracker: TrueSkillTracker) -> None:
    board = tracker.get_leaderboard()
    print(f"\n{'─'*70}")
    print(f"  {'#':>2}  {'Agent':<32}  {'μ':>6}  {'σ':>5}  {'μ-3σ':>7}  {'Games':>5}")
    print(f"{'─'*70}")
    for entry in board:
        if entry["agent_id"] == CHAMPION_ID:
            marker = " ★"
        elif entry["agent_id"] == HUMAN_PROXY_ID:
            marker = " H"
        else:
            marker = "  "
        print(
            f"  {entry['rank']:>2}  {entry['agent_id']:<32}  "
            f"{entry['mu']:>6.2f}  {entry['sigma']:>5.2f}  "
            f"{entry['conservative']:>7.2f}  {entry['games_played']:>5}{marker}"
        )
    print(f"{'─'*70}")
    gap = _human_proxy_gap(tracker)
    if gap is not None:
        status = "GOAL MET ✓" if gap >= HUMAN_PROXY_TARGET_GAP else f"need +{HUMAN_PROXY_TARGET_GAP - gap:.1f} more"
        print(f"  Champion vs human proxy gap: {gap:+.2f}  ({status})")
    print(f"{'─'*70}")


def write_progress_markdown(state: Dict[str, Any], tracker: TrueSkillTracker) -> None:
    lines: List[str] = []
    lines.append("# Champion Self-Improvement Progress\n")
    lines.append(f"_Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n")
    lines.append(f"\n**Generation:** {state['generation']}  ")
    lines.append(f"**Snapshot rows accumulated:** {state.get('total_snapshot_rows', 0)}  ")
    lines.append(f"**Last weight re-fit:** generation {state.get('last_refit_generation', 'never')}\n")

    gap = _human_proxy_gap(tracker)
    if gap is not None:
        goal_status = "✅ GOAL MET" if gap >= HUMAN_PROXY_TARGET_GAP else f"⏳ gap = {gap:+.2f} (need ≥ {HUMAN_PROXY_TARGET_GAP})"
        lines.append(f"\n**Human-proxy gap (champion − heuristic μ-3σ):** {goal_status}\n")

    lines.append("\n## TrueSkill Leaderboard\n")
    lines.append("| Rank | Agent | μ | σ | μ-3σ | Games | Note |\n")
    lines.append("|------|-------|---|---|------|-------|------|\n")
    for entry in tracker.get_leaderboard():
        if entry["agent_id"] == CHAMPION_ID:
            note = "★ champion"
        elif entry["agent_id"] == HUMAN_PROXY_ID:
            note = "H human proxy"
        elif entry["agent_id"].startswith("ckpt_"):
            note = "checkpoint"
        else:
            note = ""
        lines.append(
            f"| {entry['rank']} | {entry['agent_id']} | "
            f"{entry['mu']:.2f} | {entry['sigma']:.2f} | "
            f"{entry['conservative']:.2f} | {entry['games_played']} | {note} |\n"
        )

    history = state.get("history", [])
    if history:
        lines.append("\n## Champion TrueSkill Trend\n")
        lines.append("| Gen | μ | σ | μ-3σ | WR% | AvgScore | Proxy Gap | Promoted | Refitted |\n")
        lines.append("|-----|---|---|------|-----|----------|-----------|----------|----------|\n")
        for rec in history:
            gap_str = f"{rec.get('human_proxy_gap', float('nan')):+.2f}" if rec.get("human_proxy_gap") is not None else "—"
            promoted_str = rec.get("promoted_from") or ""
            lines.append(
                f"| {rec['generation']} "
                f"| {rec['champion_mu']:.2f} "
                f"| {rec['champion_sigma']:.2f} "
                f"| {rec['champion_conservative']:.2f} "
                f"| {rec.get('champion_win_rate', 0)*100:.1f}% "
                f"| {rec.get('champion_avg_score', 0):.1f} "
                f"| {gap_str} "
                f"| {promoted_str} "
                f"| {'Yes' if rec.get('evaluator_refitted') else 'No'} |\n"
            )

    lines.append("\n## Current Champion Parameters\n")
    lines.append("```json\n")
    lines.append(json.dumps(state["champion_params"].get("params", {}), indent=2))
    lines.append("\n```\n")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_MD.write_text("".join(lines), encoding="utf-8")


def show_progress(state: Dict[str, Any]) -> None:
    print(f"\n{'='*70}")
    print(f"  Champion Self-Improvement Progress — Generation {state['generation']}")
    print(f"{'='*70}")
    if not state.get("history"):
        print("  No generations run yet.")
        return

    tracker = build_tracker(state)
    print_leaderboard(tracker)

    history = state.get("history", [])
    print(f"\n  Trend (last {min(5, len(history))} generations):")
    for rec in history[-5:]:
        refitted = " [REFITTED]" if rec.get("evaluator_refitted") else ""
        promoted = f" [PROMOTED from {rec['promoted_from']}]" if rec.get("promoted_from") else ""
        gap_str = f"  proxy_gap={rec['human_proxy_gap']:+.2f}" if rec.get("human_proxy_gap") is not None else ""
        print(
            f"    Gen {rec['generation']:>3}: μ={rec['champion_mu']:.2f}  "
            f"σ={rec['champion_sigma']:.2f}  "
            f"μ-3σ={rec['champion_conservative']:.2f}  "
            f"WR={rec.get('champion_win_rate', 0)*100:.1f}%{gap_str}{refitted}{promoted}"
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

        # Check for promotion
        promoted_from = check_and_promote(tracker, state, challengers)

        # Record generation history
        champion_rating = tracker.get_rating(CHAMPION_ID)
        proxy_gap = _human_proxy_gap(tracker)
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
            "human_proxy_gap": proxy_gap,
            "promoted_from": promoted_from,
            "evaluator_refitted": refit_result is not None,
            "refit_r2_global": refit_result["r2_global"] if refit_result else None,
            "total_snapshot_rows": total_rows,
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
        if proxy_gap is not None:
            goal = " ✓ GOAL MET" if proxy_gap >= HUMAN_PROXY_TARGET_GAP else ""
            print(f"  Human-proxy gap: {proxy_gap:+.2f}{goal}")
        print_leaderboard(tracker)

        if refit_result:
            print(
                f"  Evaluator re-fitted: global R²={refit_result['r2_global']:.4f}, "
                f"{refit_result['rows_used']} rows"
            )
        if promoted_from:
            print(f"  Champion promoted (displaced {promoted_from})")

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
