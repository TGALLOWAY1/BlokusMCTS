#!/usr/bin/env python3
"""Champion League — Persistent self-improvement loop for the MCTS champion.

Each round the current champion plays against a freshly-sampled pool of 3
opponents drawn from a randomised parameter space.  Game data is captured via
the arena's built-in snapshot collection and fed into an evaluator calibration
pipeline.  The champion's TrueSkill rating persists across all rounds so that
improvement is visible over many sessions.

Loop (one round):
  1. Load current champion from data/champion_registry.json
  2. Sample 3 randomised opponents (varied strategies + time budgets)
  3. Run arena tournament with snapshots enabled (champion + pool = 4 agents)
  4. Update champion's persistent TrueSkill from per-game scores (games.jsonl)
  5. Merge new snapshot rows into data/champion_league_snapshots.parquet
  6. When accumulated rows exceed threshold: re-calibrate state_eval_phase_weights
     via per-phase linear regression and promote champion to a new version
  7. Write detailed log entry to data/champion_league_log.json

Usage
-----
    # Single round, 40 games
    python scripts/champion_league.py

    # Five rounds, 20 games each, display after each round
    python scripts/champion_league.py --rounds 5 --num-games 20

    # Show history only (no new run)
    python scripts/champion_league.py --show

    # Raise the calibration threshold (more data before re-fitting)
    python scripts/champion_league.py --calibrate-every 4000

    # Dry-run: skip auto-promotion after calibration
    python scripts/champion_league.py --no-promote

Persistent state files
-----------------------
    data/champion_trueskill.json         — champion TrueSkill across sessions
    data/champion_league_log.json        — detailed per-round history
    data/champion_league_snapshots.parquet — cumulative ML dataset
    data/tmp_champion_league_arena.json  — ephemeral arena config (overwritten)
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
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.tournament.trueskill_rating import TrueSkillTracker

# ── Paths ─────────────────────────────────────────────────────────────────────

REGISTRY_PATH = Path("data/champion_registry.json")
TRUESKILL_PATH = Path("data/champion_trueskill.json")
LOG_PATH = Path("data/champion_league_log.json")
SNAPSHOTS_PARQUET = Path("data/champion_league_snapshots.parquet")
TEMP_CONFIG = Path("data/tmp_champion_league_arena.json")
CALIBRATED_WEIGHTS_PATH = Path("data/layer6_calibrated_weights.json")

# ── League constants ──────────────────────────────────────────────────────────

CHAMPION_NAME = "champion"
CHAMPION_TIME_MS = 200          # thinking budget for champion (Layer 9 standard)
CHAMPION_ITERS_PER_MS = 0.5    # → 100 iterations at 200 ms
HUMAN_TARGET_MU = 35.0          # TrueSkill µ considered "beats a human"

DEFAULT_NUM_GAMES = 40
DEFAULT_CALIBRATION_THRESHOLD = 2000   # snapshot rows before re-calibrating
DEFAULT_ROUNDS = 1

# ── Opponent pool parameter space ─────────────────────────────────────────────

_TIMES_MS = [50, 100, 150, 200]
_EXPLORATIONS = [0.7, 1.0, 1.414, 2.0]
_ROLLOUTS = ["random", "heuristic"]
_RAVE_K = [500, 1000, 2000]
_CUTOFFS: List[Optional[int]] = [None, 3, 5, 10]
_MINIMAX_ALPHAS = [0.0, 0.1, 0.25]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Opponent sampling
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _mcts_variant(rng: random.Random, slot: int) -> Dict[str, Any]:
    """Build one randomised MCTS opponent from the parameter space."""
    time_ms = int(rng.choice(_TIMES_MS))
    rave = bool(rng.choice([True, False]))
    cutoff = rng.choice(_CUTOFFS)
    pw = bool(rng.choice([True, False]))

    params: Dict[str, Any] = {
        "deterministic_time_budget": True,
        "iterations_per_ms": 0.5,
        "exploration_constant": float(rng.choice(_EXPLORATIONS)),
        "rollout_policy": rng.choice(_ROLLOUTS),
        "rave_enabled": rave,
        "minimax_backup_alpha": float(rng.choice(_MINIMAX_ALPHAS)),
    }
    if rave:
        params["rave_k"] = int(rng.choice(_RAVE_K))
    if cutoff is not None:
        params["rollout_cutoff_depth"] = int(cutoff)
    if pw:
        params["progressive_widening_enabled"] = True
        params["pw_c"] = 2.0
        params["pw_alpha"] = 0.5

    return {
        "name": f"opp_{slot}_mcts_{time_ms}ms",
        "type": "mcts",
        "thinking_time_ms": time_ms,
        "params": params,
    }


def sample_opponents(rng: random.Random, n: int = 3) -> List[Dict[str, Any]]:
    """Sample n diverse opponents — at most one non-MCTS baseline."""
    pool: List[Dict[str, Any]] = []

    if rng.choices([True, False], weights=[35, 65], k=1)[0]:
        bt = rng.choice(["random", "heuristic"])
        pool.append({"name": f"opp_0_{bt[:4]}", "type": bt, "params": {}})

    slot = len(pool)
    while len(pool) < n:
        pool.append(_mcts_variant(rng, slot))
        slot += 1

    rng.shuffle(pool)
    return pool


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Registry helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _load_registry() -> Dict[str, Any]:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Champion registry not found: {REGISTRY_PATH}")
    with REGISTRY_PATH.open() as fh:
        return json.load(fh)


def _save_registry(reg: Dict[str, Any]) -> None:
    with REGISTRY_PATH.open("w") as fh:
        json.dump(reg, fh, indent=2)


def _champion_params(reg: Dict[str, Any]) -> Dict[str, Any]:
    return dict(reg["versions"][reg["current_version"]]["params"])


def _champion_agent_config(reg: Dict[str, Any]) -> Dict[str, Any]:
    params = _champion_params(reg)
    params.setdefault("deterministic_time_budget", True)
    params.setdefault("iterations_per_ms", CHAMPION_ITERS_PER_MS)
    return {
        "name": CHAMPION_NAME,
        "type": "mcts",
        "thinking_time_ms": CHAMPION_TIME_MS,
        "params": params,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Persistent TrueSkill
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _load_ts_state() -> Dict[str, Any]:
    if TRUESKILL_PATH.exists():
        with TRUESKILL_PATH.open() as fh:
            return json.load(fh)
    return {
        "ratings": {},
        "history": [],
        "total_games": 0,
        "last_calibration_rows": 0,
    }


def _save_ts_state(state: Dict[str, Any]) -> None:
    TRUESKILL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRUESKILL_PATH.open("w") as fh:
        json.dump(state, fh, indent=2)


def _seeded_tracker(state: Dict[str, Any]) -> TrueSkillTracker:
    """Build TrueSkillTracker pre-seeded with champion's prior rating."""
    tracker = TrueSkillTracker()
    prior = state.get("ratings", {})
    if prior:
        tracker.load_ratings(prior)
    return tracker


def _update_tracker_from_games(tracker: TrueSkillTracker, run_dir: str) -> int:
    """Feed per-game scores from games.jsonl into tracker. Returns game count."""
    path = Path(run_dir) / "games.jsonl"
    if not path.exists():
        return 0
    count = 0
    with path.open() as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
                scores = rec.get("agent_scores")
                if scores and len(scores) >= 2:
                    tracker.update_game({k: int(v) for k, v in scores.items()})
                    count += 1
            except (json.JSONDecodeError, ValueError):
                continue
    return count


def _commit_ts_state(
    state: Dict[str, Any],
    tracker: TrueSkillTracker,
    games_played: int,
) -> None:
    """Persist champion's updated rating and append a history point."""
    ratings = tracker.get_ratings()
    if CHAMPION_NAME in ratings:
        state["ratings"][CHAMPION_NAME] = ratings[CHAMPION_NAME]
    state["total_games"] = state.get("total_games", 0) + games_played
    champ = ratings.get(CHAMPION_NAME, {})
    state.setdefault("history", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mu": champ.get("mu"),
        "sigma": champ.get("sigma"),
        "games_this_run": games_played,
        "total_games": state["total_games"],
    })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Arena helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _write_arena_config(
    champion: Dict[str, Any],
    opponents: List[Dict[str, Any]],
    num_games: int,
    seed: int,
) -> str:
    cfg = {
        "agents": [champion] + opponents,
        "num_games": num_games,
        "seed": seed,
        "seat_policy": "randomized",
        "output_root": "arena_runs",
        "max_turns": 2500,
        "notes": "Champion League — champion vs randomised pool",
        "snapshots": {
            "enabled": True,
            "strategy": "fixed_ply",
            "checkpoints": [8, 16, 24, 32, 40, 48, 56, 64],
        },
    }
    TEMP_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with TEMP_CONFIG.open("w") as fh:
        json.dump(cfg, fh, indent=2)
    return str(TEMP_CONFIG)


def _run_arena(config_path: str) -> str:
    """Invoke the arena subprocess and return the run directory path."""
    cmd = [sys.executable, "scripts/arena.py", "--config", config_path]
    print(f"\n  [arena] {' '.join(cmd)}")
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Arena subprocess exited with code {result.returncode}")
    root = Path("arena_runs")
    for candidate in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if candidate.is_dir() and (candidate / "summary.json").exists():
            return str(candidate)
    raise RuntimeError("Cannot locate arena output directory after run")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Result parsing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _parse_standings(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build a per-agent standings list from summary.json."""
    win_stats = summary.get("win_stats", {})
    score_stats = summary.get("score_stats", {})
    ts_map = {
        e["agent_id"]: e
        for e in summary.get("trueskill_ratings", {}).get("leaderboard", [])
    }
    rows = []
    for agent in win_stats:
        ws = win_stats[agent]
        sc = score_stats.get(agent, {})
        ts = ts_map.get(agent, {})
        rows.append({
            "agent": agent,
            "win_rate": ws.get("win_rate", 0.0),
            "avg_score": sc.get("mean"),
            "ts_mu": ts.get("mu"),
            "ts_sigma": ts.get("sigma"),
            "ts_conservative": ts.get("conservative"),
            "ts_rank": ts.get("rank"),
        })
    rows.sort(key=lambda x: x.get("ts_rank") or 99)
    return rows


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Snapshot accumulation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _accumulate_snapshots(run_dir: str) -> int:
    """Merge new arena snapshots into the cumulative parquet. Returns total rows."""
    try:
        import pandas as pd
    except ImportError:
        return 0

    new_df = None
    for fname in ("snapshots.parquet", "snapshots.csv"):
        src = Path(run_dir) / fname
        if src.exists():
            new_df = (
                pd.read_parquet(str(src))
                if fname.endswith(".parquet")
                else pd.read_csv(str(src))
            )
            break

    if new_df is None or new_df.empty:
        return 0

    if SNAPSHOTS_PARQUET.exists():
        old_df = pd.read_parquet(str(SNAPSHOTS_PARQUET))
        merged = pd.concat([old_df, new_df], ignore_index=True)
    else:
        merged = new_df

    SNAPSHOTS_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(str(SNAPSHOTS_PARQUET), index=False)
    return len(merged)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Evaluator calibration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _calibrate(new_rows: int) -> Optional[Dict[str, Any]]:
    """Re-derive evaluator weights from cumulative snapshot data.

    Runs per-phase linear regression on the 7 state-evaluator features and
    a global regression for the single-weight vector.  Returns a result dict
    or None if preconditions are not met.
    """
    try:
        import numpy as np
        import pandas as pd
        from sklearn.linear_model import LinearRegression
    except ImportError:
        print("  [calibrate] Skipped — pandas or sklearn unavailable")
        return None

    if not SNAPSHOTS_PARQUET.exists():
        return None

    df = pd.read_parquet(str(SNAPSHOTS_PARQUET)).dropna(subset=["final_score"])
    se_cols = sorted(c for c in df.columns if c.startswith("se_"))

    if not se_cols or "phase_board_occupancy" not in df.columns:
        print("  [calibrate] Missing se_ columns or phase_board_occupancy — skipped")
        return None

    n = len(df)
    print(f"  [calibrate] {n:,} total rows | {new_rows:,} new since last calibration")
    if n < 100:
        print("  [calibrate] Need ≥ 100 rows — skipped")
        return None

    feature_names = [c[3:] for c in se_cols]  # strip "se_" prefix
    occ = df["phase_board_occupancy"]
    phase_masks = {
        "early": occ < 0.25,
        "mid": (occ >= 0.25) & (occ < 0.55),
        "late": occ >= 0.55,
    }

    phase_weights: Dict[str, Dict[str, float]] = {}
    phase_r2: Dict[str, float] = {}

    for phase, mask in phase_masks.items():
        pf = df[mask]
        if len(pf) < 50:
            print(f"  [calibrate] Phase '{phase}': {len(pf)} rows — skipped (need ≥ 50)")
            continue
        X = pf[se_cols].values.astype(float)
        y = pf["final_score"].values.astype(float)
        lr = LinearRegression().fit(X, y)
        coefs = lr.coef_
        scale = 0.30 / (float(np.max(np.abs(coefs))) or 1.0)
        phase_weights[phase] = {
            feature_names[i]: float(coefs[i] * scale)
            for i in range(len(feature_names))
        }
        phase_r2[phase] = float(lr.score(X, y))
        top = sorted(phase_weights[phase].items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
        top_str = "  ".join(f"{k}={v:+.3f}" for k, v in top)
        print(f"  [calibrate] Phase '{phase}': R²={phase_r2[phase]:.4f} n={len(pf)} | {top_str}")

    if not phase_weights:
        print("  [calibrate] No phases had enough data — skipped")
        return None

    # Global single-vector regression
    X_all = df[se_cols].values.astype(float)
    y_all = df["final_score"].values.astype(float)
    lr_all = LinearRegression().fit(X_all, y_all)
    coefs_all = lr_all.coef_
    scale_all = 0.30 / (float(np.max(np.abs(coefs_all))) or 1.0)
    single_weights = {
        feature_names[i]: float(coefs_all[i] * scale_all)
        for i in range(len(feature_names))
    }
    global_r2 = float(lr_all.score(X_all, y_all))
    print(f"  [calibrate] Global: R²={global_r2:.4f} n={n}")

    return {
        "phase_weights": phase_weights,
        "single_weights": single_weights,
        "global_r2": global_r2,
        "phase_r2": phase_r2,
        "rows": n,
    }


def _persist_calibrated_weights(cal: Dict[str, Any]) -> None:
    """Write new weights to data/layer6_calibrated_weights.json."""
    payload = {
        "single_weights": cal["single_weights"],
        "phase_weights": cal["phase_weights"],
        "default_weights": cal["single_weights"],
    }
    CALIBRATED_WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CALIBRATED_WEIGHTS_PATH.open("w") as fh:
        json.dump(payload, fh, indent=2)


def _promote_champion(
    reg: Dict[str, Any],
    cal: Dict[str, Any],
    round_num: int,
) -> str:
    """Add a new champion version with calibrated weights. Returns new version."""
    cur = reg["current_version"]
    new_v = f"v{int(cur[1:]) + 1}"
    params = dict(reg["versions"][cur]["params"])
    params["state_eval_phase_weights"] = cal["phase_weights"]
    params["state_eval_weights"] = cal["single_weights"]
    reg["versions"][new_v] = {
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "promoted_from": cur,
        "promotion_reason": (
            f"Champion League round {round_num}: calibrated weights from "
            f"{cal['rows']:,} snapshot rows (global R²={cal['global_r2']:.4f})"
        ),
        "params": params,
        "avg_win_rate": None,
        "avg_trueskill_mu": None,
        "avg_score": None,
        "_wr_acc": 0.0,
        "_mu_acc": 0.0,
        "_sc_acc": 0.0,
        "_count": 0,
    }
    reg["current_version"] = new_v
    return new_v


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Log helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _append_log(entry: Dict[str, Any]) -> int:
    log: List[Dict[str, Any]] = []
    if LOG_PATH.exists():
        with LOG_PATH.open() as fh:
            log = json.load(fh)
    log.append(entry)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("w") as fh:
        json.dump(log, fh, indent=2)
    return len(log)


def _load_log() -> List[Dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    with LOG_PATH.open() as fh:
        return json.load(fh)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Display helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_W = 72


def _f(val: Any, fmt: str, default: str = "?") -> str:
    """Format val or return default if None."""
    return f"{val:{fmt}}" if val is not None else default


def _print_standings(standings: List[Dict[str, Any]]) -> None:
    header = (
        f"  {'Rk':<4} {'Agent':<28} {'WR%':>6} {'AvgScore':>9}"
        f" {'µ(run)':>8} {'σ(run)':>7} {'Consrv':>8}"
    )
    print(f"\n{header}")
    print(f"  {'─' * (_W - 2)}")
    for s in standings:
        rank = str(s.get("ts_rank") or "?")
        agent = (s.get("agent") or "?")[:28]
        wr = (s.get("win_rate") or 0.0) * 100
        avg = s.get("avg_score")
        mu = s.get("ts_mu")
        sigma = s.get("ts_sigma")
        cons = s.get("ts_conservative")
        star = " ★" if s.get("agent") == CHAMPION_NAME else ""
        print(
            f"  {rank:<4} {agent:<28} {wr:5.1f}%"
            f" {_f(avg, '8.1f', '       ?')}"
            f" {_f(mu, '7.1f', '      ?')}"
            f" {_f(sigma, '6.1f', '     ?')}"
            f" {_f(cons, '7.1f', '      ?')}"
            f"{star}"
        )


def _print_trueskill_history(state: Dict[str, Any]) -> None:
    history = state.get("history", [])
    total = state.get("total_games", 0)
    if not history:
        return

    print(f"\n  Champion TrueSkill — persistent across sessions ({total} total games):")
    print(f"  {'#':<5} {'µ':>7} {'σ':>7} {'ΔGames':>8}  Timestamp")
    print(f"  {'─' * 52}")

    shown = history[-14:]
    offset = len(history) - len(shown)
    for i, h in enumerate(shown, offset + 1):
        mu = h.get("mu")
        sigma = h.get("sigma")
        dg = h.get("games_this_run", "?")
        ts = (h.get("timestamp") or "?")[:16]
        at_target = mu is not None and mu >= HUMAN_TARGET_MU
        marker = "  ← TARGET" if at_target else ""
        print(
            f"  {i:<5} {_f(mu, '6.1f', '     ?')} {_f(sigma, '6.1f', '     ?')}"
            f" {str(dg):>8}  {ts}{marker}"
        )

    last_mu = (history[-1] or {}).get("mu")
    if last_mu is not None:
        gap = HUMAN_TARGET_MU - last_mu
        if gap <= 0:
            print(f"\n  Champion has reached the human target (µ={last_mu:.1f} ≥ {HUMAN_TARGET_MU:.0f})!")
        else:
            trend_str = ""
            if len(history) >= 3:
                deltas = [
                    history[j]["mu"] - history[j - 1]["mu"]
                    for j in range(max(1, len(history) - 3), len(history))
                    if history[j].get("mu") and history[j - 1].get("mu")
                ]
                if deltas:
                    avg_d = sum(deltas) / len(deltas)
                    trend_str = f"  avg Δµ/round={avg_d:+.2f}"
            print(
                f"\n  Progress to human target: µ={last_mu:.1f}  "
                f"target={HUMAN_TARGET_MU:.0f}  gap={gap:.1f}{trend_str}"
            )


def show_history() -> None:
    """Print champion league history and TrueSkill progression."""
    log = _load_log()
    ts = _load_ts_state()

    print(f"\n{'═' * _W}")
    print(f"  Champion League History — {len(log)} round(s)")
    print(f"{'═' * _W}")

    if not log:
        print("  No rounds recorded yet.\n")
    else:
        for i, entry in enumerate(log):
            ts_str = (entry.get("timestamp") or "?")[:19]
            ver = entry.get("champion_version", "?")
            ng = entry.get("num_games", "?")
            champ = entry.get("champion_stats", {})
            wr = (champ.get("win_rate") or 0.0) * 100
            mu = entry.get("trueskill", {}).get("mu")
            rank = champ.get("ts_rank")
            promoted = entry.get("promoted_to")
            snap = entry.get("snapshot_rows_total", 0)
            cal_r2 = entry.get("calibration_r2")

            print(f"\n  Round {i + 1:>3} | {ts_str} | {ver}")
            print(f"    Champion: WR={wr:.1f}%  {_f(mu, '.1f', '?')}µ  rank={rank or '?'}/{ng} games")
            if promoted:
                r2_str = f"  R²={cal_r2:.4f}" if cal_r2 is not None else ""
                print(f"    ✦ Promoted → {promoted}{r2_str}  [{snap:,} snapshot rows]")

        # Trend across first/last
        if len(log) >= 2:
            first_mu = (log[0].get("trueskill") or {}).get("mu")
            last_mu = (log[-1].get("trueskill") or {}).get("mu")
            if first_mu is not None and last_mu is not None:
                delta = last_mu - first_mu
                sign = "+" if delta >= 0 else ""
                print(f"\n  Total µ change: {sign}{delta:.2f} over {len(log)} round(s)")

    _print_trueskill_history(ts)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main loop
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Champion League — persistent self-improvement loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/champion_league.py\n"
            "  python scripts/champion_league.py --rounds 5 --num-games 20\n"
            "  python scripts/champion_league.py --show\n"
        ),
    )
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS,
                        help="Number of league rounds to run (default: 1)")
    parser.add_argument("--num-games", type=int, default=DEFAULT_NUM_GAMES,
                        help=f"Games per round (default: {DEFAULT_NUM_GAMES})")
    parser.add_argument("--seed", type=int, default=20260506,
                        help="Base random seed (default: 20260506)")
    parser.add_argument("--calibrate-every", type=int, default=DEFAULT_CALIBRATION_THRESHOLD,
                        help=f"Snapshot rows between calibrations (default: {DEFAULT_CALIBRATION_THRESHOLD})")
    parser.add_argument("--no-promote", action="store_true",
                        help="Disable automatic champion promotion after calibration")
    parser.add_argument("--show", action="store_true",
                        help="Show history and exit (no new run)")
    args = parser.parse_args()

    if args.show:
        show_history()
        return

    for round_num in range(1, args.rounds + 1):
        # ── Load state ─────────────────────────────────────────────────────
        reg = _load_registry()
        version = reg["current_version"]
        ts_state = _load_ts_state()

        print(f"\n{'═' * _W}")
        print(
            f"  Champion League — Round {round_num}/{args.rounds}"
            f"  |  Champion: {version}"
            f"  |  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        print(f"{'═' * _W}")

        # ── Sample opponents ───────────────────────────────────────────────
        round_seed = (args.seed ^ (round_num * 0x5A3C1B9F)) & 0x7FFFFFFF
        rng = random.Random(round_seed)
        opponents = sample_opponents(rng)

        print(f"\n  Opponent pool ({len(opponents)} agents):")
        for opp in opponents:
            time_str = f"  {opp['thinking_time_ms']}ms" if "thinking_time_ms" in opp else ""
            print(f"    • {opp['name']:<30} [{opp['type']}]{time_str}")

        iters = int(CHAMPION_ITERS_PER_MS * CHAMPION_TIME_MS)
        print(f"  Champion: {CHAMPION_NAME} [{version}]  @ {CHAMPION_TIME_MS}ms ({iters} iters)")

        # ── Build and run arena ────────────────────────────────────────────
        champion_cfg = _champion_agent_config(reg)
        config_path = _write_arena_config(
            champion=champion_cfg,
            opponents=opponents,
            num_games=args.num_games,
            seed=round_seed,
        )
        print(f"\n  Running {args.num_games} games …")
        run_dir = _run_arena(config_path)
        print(f"  Run directory: {run_dir}")

        # ── Parse results ──────────────────────────────────────────────────
        with (Path(run_dir) / "summary.json").open() as fh:
            summary = json.load(fh)
        standings = _parse_standings(summary)
        champ_standing = next(
            (s for s in standings if s["agent"] == CHAMPION_NAME), {}
        )

        # ── Update persistent TrueSkill ────────────────────────────────────
        tracker = _seeded_tracker(ts_state)
        games_played = _update_tracker_from_games(tracker, run_dir)
        _commit_ts_state(ts_state, tracker, games_played)
        _save_ts_state(ts_state)

        persistent_mu = ts_state["ratings"].get(CHAMPION_NAME, {}).get("mu")
        persistent_sigma = ts_state["ratings"].get(CHAMPION_NAME, {}).get("sigma")

        # ── Accumulate snapshots ───────────────────────────────────────────
        total_snap_rows = _accumulate_snapshots(run_dir)
        last_cal_rows = ts_state.get("last_calibration_rows", 0)
        new_since_cal = total_snap_rows - last_cal_rows
        print(
            f"\n  Snapshot rows: {total_snap_rows:,} total"
            f"  ({new_since_cal:+,} since last calibration,"
            f"  threshold={args.calibrate_every:,})"
        )

        # ── Maybe calibrate ────────────────────────────────────────────────
        cal_result: Optional[Dict[str, Any]] = None
        promoted_to: Optional[str] = None

        if new_since_cal >= args.calibrate_every:
            print(f"\n  Calibration threshold reached — fitting new weights …")
            cal_result = _calibrate(new_rows=new_since_cal)
            if cal_result:
                _persist_calibrated_weights(cal_result)
                ts_state["last_calibration_rows"] = total_snap_rows
                _save_ts_state(ts_state)

                if not args.no_promote:
                    promoted_to = _promote_champion(reg, cal_result, round_num)
                    _save_registry(reg)
                    print(f"\n  ✦ Champion promoted: {version} → {promoted_to}")
                    print(
                        f"    Calibrated from {cal_result['rows']:,} rows"
                        f"  global R²={cal_result['global_r2']:.4f}"
                    )
                    if cal_result.get("phase_weights"):
                        for ph, pw in cal_result["phase_weights"].items():
                            top = sorted(pw.items(), key=lambda kv: abs(kv[1]), reverse=True)[:2]
                            ts = "  ".join(f"{k}={v:+.3f}" for k, v in top)
                            print(f"    {ph:<6}: {ts}")
                else:
                    print("  [--no-promote] skipping champion version update")
        else:
            remaining = args.calibrate_every - new_since_cal
            print(f"  Next calibration in ≈{remaining:,} more snapshot rows")

        # ── Log entry ──────────────────────────────────────────────────────
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "round": round_num,
            "champion_version": version,
            "num_games": args.num_games,
            "run_dir": run_dir,
            "opponent_pool": [
                {"name": o["name"], "type": o["type"],
                 "thinking_time_ms": o.get("thinking_time_ms")}
                for o in opponents
            ],
            "standings": standings,
            "champion_stats": champ_standing,
            "trueskill": {
                "mu": persistent_mu,
                "sigma": persistent_sigma,
                "total_games": ts_state.get("total_games"),
            },
            "snapshot_rows_total": total_snap_rows,
            "snapshot_rows_new": new_since_cal,
            "calibration_triggered": cal_result is not None,
            "calibration_r2": cal_result.get("global_r2") if cal_result else None,
            "promoted_to": promoted_to,
        }
        entry_num = _append_log(entry)

        # ── Print round summary ────────────────────────────────────────────
        print(f"\n  ── Standings (within-run TrueSkill, {args.num_games} games) ──")
        _print_standings(standings)

        print(f"\n  ── Champion persistent rating ──")
        _print_trueskill_history(ts_state)

        if promoted_to:
            print(f"  New champion version: {promoted_to}")

        print(
            f"\n  Round {round_num} complete | Log entry #{entry_num}"
            f" → {LOG_PATH}"
        )
        print(f"{'═' * _W}\n")

    print(f"Champion League finished ({args.rounds} round(s) completed).")
    print(f"Run  python scripts/champion_league.py --show  to review history.\n")


if __name__ == "__main__":
    main()
