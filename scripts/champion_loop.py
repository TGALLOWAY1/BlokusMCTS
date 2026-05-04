#!/usr/bin/env python
"""Champion Self-Improvement Loop.

Runs the current champion agent against a randomized pool of challengers,
captures snapshot data for evaluator refinement, and documents TrueSkill
progression toward an agent that reliably beats a human player.

Each iteration:
  1. Loads the current champion config from the persistent registry.
  2. Samples 3 challengers at random from a 5-tier diverse pool (baselines
     through near-peer agents), always including at least 1 strong MCTS.
  3. Runs a 4-player arena experiment with fixed-ply snapshots enabled.
  4. Logs TrueSkill, win rate, and avg score to the registry.
  5. Every --eval-update-interval iterations, runs inline regression on
     accumulated snapshot data and validates new weights in a mini-tournament
     before promoting them — and bumping the champion version.
  6. Writes a detailed Markdown progress report after every iteration.

Usage:
    # Run 10 improvement iterations with 20 games each
    python scripts/champion_loop.py --iterations 10 --games-per-iter 20

    # Alias: --num-games works too
    python scripts/champion_loop.py --iterations 5 --num-games 40

    # Stronger champion (1 second per move)
    python scripts/champion_loop.py --champion-time 1000

    # Re-calibrate evaluator every 5 iterations
    python scripts/champion_loop.py --iterations 20 --eval-update-interval 5

    # Force evaluator update after this run (regardless of interval)
    python scripts/champion_loop.py --retrain

    # Show progress report without running new games
    python scripts/champion_loop.py --show

    # Smoke test
    python scripts/champion_loop.py --iterations 2 --games-per-iter 4
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SCRIPTS_DIR = ROOT / "scripts"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REGISTRY_PATH    = DATA_DIR / "champion_registry.json"
PROGRESS_MD_PATH = DATA_DIR / "champion_progress.md"
CALIBRATED_WEIGHTS_PATH = DATA_DIR / "layer6_calibrated_weights.json"

# ---------------------------------------------------------------------------
# Champion baseline parameters — all beneficial layers enabled
#
# Layer 3:  Progressive widening (c=2.0, α=0.5)
# Layer 4:  Random rollout, cutoff depth=5, minimax backup α=0.25
# Layer 5:  RAVE k=1000
# Layer 6:  Calibrated single weights (phase weights injected at runtime)
# Layer 7:  Opponent modeling — alliance + king-maker detection
# Layer 9:  Adaptive exploration C, adaptive rollout depth, sufficiency
#           threshold, loss avoidance
# ---------------------------------------------------------------------------

_DEFAULT_EVAL_WEIGHTS: Dict[str, float] = {
    "squares_placed":             0.0295,
    "remaining_piece_area":      -0.0295,
    "accessible_corners":         0.243,
    "reachable_empty_squares":    0.081,
    "largest_remaining_piece_size": -0.231,
    "opponent_avg_mobility":     -0.3,
    "center_proximity":           0.0,
    "territory_enclosure_area":   0.0,
}

CHAMPION_BASE_PARAMS: Dict[str, Any] = {
    # Budget (0.5 iter/ms calibrated for rollout_cutoff_depth=5)
    "deterministic_time_budget": True,
    "iterations_per_ms": 0.5,
    # Layer 1/2
    "exploration_constant": 1.414,
    "use_transposition_table": True,
    # Layer 3
    "progressive_widening_enabled": True,
    "pw_c": 2.0,
    "pw_alpha": 0.5,
    # Layer 4
    "rollout_policy": "random",
    "rollout_cutoff_depth": 5,
    "minimax_backup_alpha": 0.25,
    # Layer 5
    "rave_enabled": True,
    "rave_k": 1000,
    # Layer 6 (weights updated by evaluator improvement cycle)
    "state_eval_weights": dict(_DEFAULT_EVAL_WEIGHTS),
    # Layer 7
    "opponent_modeling_enabled": True,
    "alliance_detection_enabled": True,
    "alliance_threshold": 2.0,
    "kingmaker_detection_enabled": True,
    "kingmaker_score_gap": 15,
    # Layer 9
    "adaptive_rollout_depth_enabled": True,
    "adaptive_rollout_depth_base": 5,
    "adaptive_rollout_depth_avg_bf": 80.0,
    "adaptive_exploration_enabled": True,
    "adaptive_exploration_base": 1.414,
    "adaptive_exploration_avg_bf": 80.0,
    "sufficiency_threshold_enabled": True,
    "loss_avoidance_enabled": True,
    "loss_avoidance_threshold": -50.0,
}

CHAMPION_THINKING_TIME_MS = 500

# ---------------------------------------------------------------------------
# Challenger pool — 5 tiers, 14 agents
#
# Tier 1  Baselines       — random, heuristic
# Tier 2  Vanilla MCTS    — plain UCT at 25/50/100/200 ms (fast throughput)
# Tier 3  L4+5 enhanced   — rollout cutoff, minimax, RAVE at 100 ms
# Tier 4  L9 partial      — adaptive meta-opts at 200 ms, no opponent model
# Tier 5  Near-peer       — same budget/layers as champion, no opponent model
# ---------------------------------------------------------------------------

_SHARED_L45 = {
    "deterministic_time_budget": True,
    "iterations_per_ms": 0.5,
    "rollout_policy": "random",
    "rollout_cutoff_depth": 5,
    "minimax_backup_alpha": 0.25,
    "rave_enabled": True,
    "rave_k": 1000,
    "state_eval_weights": dict(_DEFAULT_EVAL_WEIGHTS),
}

CHALLENGER_POOL: List[Dict[str, Any]] = [
    # --- Tier 1: Baselines ---
    {"name": "pool_random",    "type": "random"},
    {"name": "pool_heuristic", "type": "heuristic"},
    # --- Tier 2: Vanilla MCTS (fast, no cutoff) ---
    {"name": "pool_mcts_25ms",  "type": "mcts", "thinking_time_ms": 25,
     "params": {"deterministic_time_budget": True, "iterations_per_ms": 10.0}},
    {"name": "pool_mcts_50ms",  "type": "mcts", "thinking_time_ms": 50,
     "params": {"deterministic_time_budget": True, "iterations_per_ms": 10.0}},
    {"name": "pool_mcts_100ms", "type": "mcts", "thinking_time_ms": 100,
     "params": {"deterministic_time_budget": True, "iterations_per_ms": 10.0}},
    {"name": "pool_mcts_200ms", "type": "mcts", "thinking_time_ms": 200,
     "params": {"deterministic_time_budget": True, "iterations_per_ms": 10.0}},
    # --- Tier 3: L4+5 enhanced ---
    {"name": "pool_rave_100ms",   "type": "mcts", "thinking_time_ms": 100,
     "params": {"deterministic_time_budget": True, "iterations_per_ms": 10.0,
                "rave_enabled": True, "rave_k": 1000}},
    {"name": "pool_l45_100ms",    "type": "mcts", "thinking_time_ms": 100,
     "params": dict(_SHARED_L45)},
    {"name": "pool_explorer_200ms", "type": "mcts", "thinking_time_ms": 200,
     "params": {**_SHARED_L45, "exploration_constant": 2.0}},
    {"name": "pool_full_rollout_200ms", "type": "mcts", "thinking_time_ms": 200,
     "params": {k: v for k, v in _SHARED_L45.items() if k != "rollout_cutoff_depth"}},
    # --- Tier 4: L9 partial (no opponent modeling) ---
    {"name": "pool_l9_partial_200ms", "type": "mcts", "thinking_time_ms": 200,
     "params": {**_SHARED_L45,
                "adaptive_exploration_enabled": True,
                "adaptive_exploration_base": 1.414,
                "adaptive_exploration_avg_bf": 80.0,
                "adaptive_rollout_depth_enabled": True,
                "adaptive_rollout_depth_base": 5,
                "sufficiency_threshold_enabled": True,
                "loss_avoidance_enabled": True}},
    # --- Tier 5: Near-peer (same layers, same budget, no opponent modeling) ---
    {"name": "pool_peer_500ms", "type": "mcts", "thinking_time_ms": 500,
     "params": {**_SHARED_L45,
                "exploration_constant": 1.414,
                "use_transposition_table": True,
                "progressive_widening_enabled": True, "pw_c": 2.0, "pw_alpha": 0.5,
                "adaptive_exploration_enabled": True,
                "adaptive_exploration_base": 1.414,
                "adaptive_exploration_avg_bf": 80.0,
                "adaptive_rollout_depth_enabled": True,
                "adaptive_rollout_depth_base": 5,
                "adaptive_rollout_depth_avg_bf": 80.0,
                "sufficiency_threshold_enabled": True,
                "loss_avoidance_enabled": True}},
    # Champion clone at half budget (tests compute efficiency)
    {"name": "pool_champion_clone_250ms", "type": "mcts", "thinking_time_ms": 250,
     "params": dict(CHAMPION_BASE_PARAMS)},
]

_STRONG_POOL = [c["name"] for c in CHALLENGER_POOL if c.get("type") == "mcts"]
_WEAK_POOL   = [c["name"] for c in CHALLENGER_POOL if c.get("type") != "mcts"]
_POOL_BY_NAME = {c["name"]: c for c in CHALLENGER_POOL}

# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------


def _load_registry() -> Dict[str, Any]:
    if REGISTRY_PATH.exists():
        with REGISTRY_PATH.open() as f:
            return json.load(f)
    return {
        "current_version": "v1",
        "versions": {},
        "iterations": [],
        "snapshot_csv_paths": [],
        "total_games_played": 0,
    }


def _save_registry(registry: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with REGISTRY_PATH.open("w") as f:
        json.dump(registry, f, indent=2)


def _get_champion_params(registry: Dict[str, Any]) -> Dict[str, Any]:
    """Return current champion MCTS params, injecting calibrated phase weights."""
    version = registry.get("current_version", "v1")
    versions = registry.get("versions", {})
    base = versions[version].get("params", CHAMPION_BASE_PARAMS) if version in versions else CHAMPION_BASE_PARAMS

    # Always layer in the latest calibrated phase weights if available
    if CALIBRATED_WEIGHTS_PATH.exists():
        with CALIBRATED_WEIGHTS_PATH.open() as f:
            cal = json.load(f)
        if cal.get("phase_weights"):
            base = dict(base)
            base["state_eval_phase_weights"] = cal["phase_weights"]
            base["state_eval_weights"] = cal.get("single_weights", base.get("state_eval_weights"))
    return base


# ---------------------------------------------------------------------------
# Challenger sampling
# ---------------------------------------------------------------------------


def _sample_challengers(rng: random.Random) -> List[str]:
    """Sample 3 challengers ensuring at least 1 strong MCTS competitor."""
    strong = rng.choice(_STRONG_POOL)
    rest = [n for n in (_STRONG_POOL + _WEAK_POOL) if n != strong]
    others = rng.sample(rest, k=min(2, len(rest)))
    return [strong] + others


# ---------------------------------------------------------------------------
# Arena config / execution
# ---------------------------------------------------------------------------


def _build_arena_config(
    champion_params: Dict[str, Any],
    challenger_names: List[str],
    games: int,
    seed: int,
    iteration: int,
    thinking_time_ms: int = CHAMPION_THINKING_TIME_MS,
) -> Dict[str, Any]:
    agents: List[Dict[str, Any]] = [
        {
            "name": "champion",
            "type": "mcts",
            "thinking_time_ms": thinking_time_ms,
            "params": champion_params,
        }
    ]
    for name in challenger_names:
        cfg = _POOL_BY_NAME[name]
        agents.append({
            "name": cfg["name"],
            "type": cfg["type"],
            "thinking_time_ms": cfg.get("thinking_time_ms"),
            "params": dict(cfg.get("params", {})),
        })
    return {
        "agents": agents,
        "num_games": games,
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
            f"Champion loop iteration {iteration} — "
            f"champion v{iteration} vs {', '.join(challenger_names)}"
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


def _run_arena(config: Dict[str, Any]) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="champion_iter_",
        dir=str(SCRIPTS_DIR), delete=False,
    ) as tmp:
        json.dump(config, tmp, indent=2)
        tmp_path = tmp.name
    try:
        cmd = [sys.executable, str(SCRIPTS_DIR / "arena.py"), "--config", tmp_path]
        print(f"  [arena] {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=False, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"arena.py exited with code {result.returncode}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    run_dir = _find_latest_run()
    if run_dir is None:
        raise RuntimeError("Could not locate arena output directory after run.")
    return run_dir


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------


def _parse_summary(run_dir: str) -> Dict[str, Any]:
    with open(Path(run_dir) / "summary.json") as f:
        data = json.load(f)

    agents_out: Dict[str, Any] = {}
    for name, ad in data.get("agents", {}).items():
        mu    = ad.get("trueskill_mu")
        sigma = ad.get("trueskill_sigma")
        agents_out[name] = {
            "wins":                  ad.get("wins", 0),
            "win_rate":              ad.get("win_rate", 0.0),
            "avg_score":             ad.get("avg_score", 0.0),
            "trueskill_mu":          mu,
            "trueskill_sigma":       sigma,
            "trueskill_conservative": (mu - 3.0 * sigma) if (mu and sigma) else None,
        }

    snapshot_csv: Optional[str] = None
    sm = data.get("snapshots", {})
    if isinstance(sm, dict) and sm.get("path_csv"):
        snapshot_csv = sm["path_csv"]

    return {
        "num_games":       data.get("num_games", 0),
        "completed_games": data.get("completed_games", data.get("num_games", 0)),
        "agents":          agents_out,
        "snapshot_csv":    snapshot_csv,
    }


# ---------------------------------------------------------------------------
# Evaluator weight improvement
# ---------------------------------------------------------------------------


def _try_improve_evaluator(snapshot_csv_paths: List[str]) -> Optional[Dict[str, float]]:
    """Concatenate snapshots, run linear regression, return new weight dict or None."""
    try:
        import pandas as pd
        from sklearn.linear_model import LinearRegression
    except ImportError:
        print("  [eval] pandas/sklearn not available — skipping evaluator update.")
        return None

    valid = [p for p in snapshot_csv_paths if p and Path(p).exists()]
    if not valid:
        print("  [eval] No valid snapshot CSVs — skipping.")
        return None

    dfs = []
    for p in valid:
        try:
            dfs.append(pd.read_csv(p))
        except Exception as exc:
            print(f"  [eval] Warning: could not read {p}: {exc}")
    if not dfs:
        return None

    df = pd.concat(dfs, ignore_index=True)
    print(f"  [eval] Loaded {len(df)} snapshot rows from {len(dfs)} file(s).")

    feature_names = list(_DEFAULT_EVAL_WEIGHTS)
    se_cols = [f"se_{f}" for f in feature_names]
    available = [c for c in se_cols if c in df.columns]

    if len(available) < 4:
        print(f"  [eval] Only {len(available)} SE feature columns present — skipping.")
        return None

    label_col = "label_is_winner"
    if label_col not in df.columns:
        # Fall back to final_score if available
        if "final_score" in df.columns:
            label_col = "final_score"
        else:
            print("  [eval] No usable label column — skipping.")
            return None

    X = df[available].fillna(0.0).values.astype(float)
    y = df[label_col].fillna(0.0).values.astype(float)

    if len(X) < 100:
        print(f"  [eval] Only {len(X)} rows — not enough data ({len(X)} < 100).")
        return None

    from sklearn.linear_model import LinearRegression
    lr = LinearRegression().fit(X, y)
    raw = dict(zip(available, lr.coef_))
    coefs = {f: raw.get(f"se_{f}", 0.0) for f in feature_names}
    max_abs = max(abs(v) for v in coefs.values()) or 1.0
    scale = 0.3 / max_abs
    new_weights = {f: round(v * scale, 6) for f, v in coefs.items()}

    print("  [eval] Derived new evaluator weights:")
    for f, w in new_weights.items():
        old = _DEFAULT_EVAL_WEIGHTS.get(f, 0.0)
        print(f"    {f:>35s}:  {w:+.4f}  (was {old:+.4f})")
    return new_weights


def _validate_new_weights(
    old_params: Dict[str, Any],
    new_weights: Dict[str, float],
    games: int,
    seed: int,
    thinking_time_ms: int,
) -> bool:
    """Mini-tournament: champion_new vs champion_old. Return True if new wins more."""
    new_params = {**old_params, "state_eval_weights": new_weights}
    config = {
        "agents": [
            {"name": "champion_new", "type": "mcts",
             "thinking_time_ms": thinking_time_ms, "params": new_params},
            {"name": "champion_old", "type": "mcts",
             "thinking_time_ms": thinking_time_ms, "params": old_params},
            {"name": "random_a", "type": "random"},
            {"name": "random_b", "type": "random"},
        ],
        "num_games": games,
        "seed": seed,
        "seat_policy": "round_robin",
        "output_root": "arena_runs",
        "max_turns": 2500,
        "snapshots": {"enabled": False, "checkpoints": []},
        "notes": "Champion evaluator weight validation",
    }
    print("  [eval] Running weight validation arena …")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="weight_val_",
        dir=str(SCRIPTS_DIR), delete=False,
    ) as tmp:
        json.dump(config, tmp, indent=2)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "arena.py"), "--config", tmp_path],
            capture_output=False, text=True,
        )
        if result.returncode != 0:
            print("  [eval] Validation arena failed.")
            return False
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    run_dir = _find_latest_run()
    if not run_dir:
        return False
    parsed = _parse_summary(run_dir)
    new_wr = parsed["agents"].get("champion_new", {}).get("win_rate", 0.0)
    old_wr = parsed["agents"].get("champion_old", {}).get("win_rate", 0.0)
    print(f"  [eval] Validation: new_WR={new_wr:.1%}  old_WR={old_wr:.1%}")
    return new_wr > old_wr


# ---------------------------------------------------------------------------
# Per-version running stats
# ---------------------------------------------------------------------------


def _update_version_stats(
    registry: Dict[str, Any],
    version: str,
    entry: Dict[str, Any],
    champion_params: Dict[str, Any],
) -> None:
    versions = registry.setdefault("versions", {})
    if version not in versions:
        versions[version] = {
            "promoted_at": entry["timestamp"],
            "params": champion_params,
            "_wr_acc": 0.0, "_mu_acc": 0.0, "_sc_acc": 0.0, "_count": 0,
        }
    v = versions[version]
    cs = entry.get("champion_stats", {})
    v["_count"] += 1
    n = v["_count"]
    v["_wr_acc"]  += cs.get("win_rate", 0.0)
    v["_mu_acc"]  += cs.get("trueskill_mu", 0.0) or 0.0
    v["_sc_acc"]  += cs.get("avg_score", 0.0)
    v["avg_win_rate"]      = v["_wr_acc"] / n
    v["avg_trueskill_mu"]  = v["_mu_acc"] / n
    v["avg_score"]         = v["_sc_acc"] / n


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def _render_markdown(registry: Dict[str, Any]) -> str:
    iters     = registry.get("iterations", [])
    total     = registry.get("total_games_played", 0)
    version   = registry.get("current_version", "v1")
    versions  = registry.get("versions", {})
    now       = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: List[str] = [
        "# Champion Self-Improvement Progress",
        "",
        f"_Last updated: {now}_",
        "",
        f"**Goal:** Build an MCTS agent that reliably beats a human Blokus player.",
        f"**Champion version:** {version}  |  "
        f"**Iterations:** {len(iters)}  |  **Total games:** {total}",
        "",
    ]

    # -- Champion version history --
    if versions:
        lines += ["## Champion Versions", "", "| Version | Promoted | Avg WR% | Avg μ | Avg Score |",
                  "|---------|----------|---------|-------|-----------|"]
        for ver, vd in versions.items():
            promo = vd.get("promoted_at", "?")[:10]
            awr   = vd.get("avg_win_rate", 0) * 100
            amu   = vd.get("avg_trueskill_mu", 0)
            asc   = vd.get("avg_score", 0)
            tag   = " ← current" if ver == version else ""
            lines.append(f"| {ver}{tag} | {promo} | {awr:.1f} | {amu:.1f} | {asc:.1f} |")
        lines.append("")

    # -- TrueSkill progression --
    if iters:
        lines += [
            "## TrueSkill Progression",
            "",
            "| # | Date | Ver | Games | Challengers | WR% | Avg Score | μ | σ | Conservative |",
            "|---|------|-----|-------|-------------|-----|-----------|---|---|--------------|",
        ]
        for i, e in enumerate(iters, 1):
            ts    = e.get("timestamp", "?")[:10]
            ver   = e.get("champion_version", "?")
            ng    = e.get("num_games", "?")
            chs   = [n.replace("pool_", "") for n in e.get("challengers", [])]
            chs_s = ", ".join(chs) if chs else "—"
            cs    = e.get("champion_stats", {})
            wr    = cs.get("win_rate", 0.0) * 100
            avg   = cs.get("avg_score", 0.0)
            mu    = cs.get("trueskill_mu")
            sig   = cs.get("trueskill_sigma")
            cons  = cs.get("trueskill_conservative")
            mu_s    = f"{mu:.1f}"   if mu   is not None else "—"
            sig_s   = f"{sig:.2f}"  if sig  is not None else "—"
            cons_s  = f"{cons:.1f}" if cons is not None else "—"
            ev_tag  = " ✓" if e.get("eval_updated") else ""
            lines.append(
                f"| {i} | {ts} | {ver}{ev_tag} | {ng} | {chs_s} "
                f"| {wr:.1f} | {avg:.1f} | {mu_s} | {sig_s} | {cons_s} |"
            )
        lines.append("")

        # Trend
        if len(iters) >= 2:
            first_c = iters[0].get("champion_stats", {})
            last_c  = iters[-1].get("champion_stats", {})
            dwr  = (last_c.get("win_rate", 0) - first_c.get("win_rate", 0)) * 100
            dsc  = last_c.get("avg_score", 0) - first_c.get("avg_score", 0)
            lwr  = last_c.get("win_rate", 0) * 100
            if lwr >= 55.0:
                status = f"Champion wins {lwr:.0f}% vs mixed pool — **likely competitive with human players.**"
            elif lwr >= 35.0:
                status = f"Champion WR={lwr:.0f}% vs mixed pool — developing."
            else:
                status = f"Champion WR={lwr:.0f}% — early stage, continue iterating."
            lines += [
                "## Trend",
                "",
                f"- Win-rate shift (first → latest): **{'+' if dwr >= 0 else ''}{dwr:.1f} pp**",
                f"- Avg-score shift: **{'+' if dsc >= 0 else ''}{dsc:.1f}**",
                f"- {status}",
                "",
            ]

    # -- Challenger breakdown --
    opp_records: Dict[str, List[float]] = {}
    for e in iters:
        for name, s in e.get("challenger_stats", {}).items():
            opp_records.setdefault(name, []).append(s.get("win_rate", 0.0))
    if opp_records:
        lines += [
            "## Challenger Win Rates (lower = champion dominates)",
            "",
            "| Challenger | Apps | Avg WR% | Trend |",
            "|------------|------|---------|-------|",
        ]
        for name in sorted(opp_records):
            wrs    = opp_records[name]
            avg_wr = sum(wrs) / len(wrs) * 100
            if len(wrs) >= 3:
                trend = ("▲ champion improving" if wrs[-1] < wrs[0] - 0.02
                         else "▼ opponent catching up" if wrs[-1] > wrs[0] + 0.02
                         else "→ stable")
            else:
                trend = "—"
            lines.append(f"| {name} | {len(wrs)} | {avg_wr:.1f} | {trend} |")
        lines.append("")

    # -- Evaluator promotion events --
    promo_events = [e for e in iters if e.get("eval_updated")]
    if promo_events:
        lines += [
            "## Evaluator Promotion Events",
            "",
            "| # | Date | Iteration | New version |",
            "|---|------|-----------|-------------|",
        ]
        for idx, e in enumerate(promo_events, 1):
            ts  = e.get("timestamp", "?")[:10]
            it  = e.get("iteration", "?")
            ver = e.get("champion_version", "?")
            lines.append(f"| {idx} | {ts} | {it} | {ver} |")
        lines.append("")

    # -- Challenger pool reference --
    lines += [
        "## Challenger Pool",
        "",
        "| Agent | Type | Budget | Tier |",
        "|-------|------|--------|------|",
    ]
    tier_labels = {
        "pool_random": "1 — Baseline",
        "pool_heuristic": "1 — Baseline",
        "pool_mcts_25ms": "2 — Vanilla MCTS",
        "pool_mcts_50ms": "2 — Vanilla MCTS",
        "pool_mcts_100ms": "2 — Vanilla MCTS",
        "pool_mcts_200ms": "2 — Vanilla MCTS",
        "pool_rave_100ms": "3 — L4+5 Enhanced",
        "pool_l45_100ms": "3 — L4+5 Enhanced",
        "pool_explorer_200ms": "3 — L4+5 Enhanced",
        "pool_full_rollout_200ms": "3 — L4+5 Enhanced",
        "pool_l9_partial_200ms": "4 — L9 Partial",
        "pool_peer_500ms": "5 — Near-Peer",
        "pool_champion_clone_250ms": "5 — Near-Peer",
    }
    for c in CHALLENGER_POOL:
        tms    = c.get("thinking_time_ms")
        budget = f"{tms} ms" if tms else "—"
        tier   = tier_labels.get(c["name"], "?")
        lines.append(f"| {c['name']} | {c['type']} | {budget} | {tier} |")
    lines.append("")

    return "\n".join(lines)


def _write_report(registry: Dict[str, Any]) -> None:
    md = _render_markdown(registry)
    PROGRESS_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_MD_PATH.write_text(md)
    print(f"  [report] Written → {PROGRESS_MD_PATH}")


# ---------------------------------------------------------------------------
# Console history display
# ---------------------------------------------------------------------------


def _show_history(registry: Dict[str, Any]) -> None:
    iters   = registry.get("iterations", [])
    total   = registry.get("total_games_played", 0)
    version = registry.get("current_version", "v1")

    print(f"\n{'=' * 72}")
    print(f"  Champion Progress — {len(iters)} iteration(s), {total} total games")
    print(f"  Current version: {version}")
    print(f"{'=' * 72}")

    for e in iters:
        ts   = e.get("timestamp", "?")[:19].replace("T", " ")
        it   = e.get("iteration", "?")
        ng   = e.get("num_games", "?")
        chs  = ", ".join(e.get("challengers", []))
        cs   = e.get("champion_stats", {})
        wr   = cs.get("win_rate", 0) * 100
        mu   = cs.get("trueskill_mu")
        mu_s = f"  μ={mu:.1f}" if mu is not None else ""
        ev   = "  [eval updated ✓]" if e.get("eval_updated") else ""
        print(f"\n--- Iteration {it}  ({ts}, {ng} games) ---")
        print(f"  Challengers: {chs}")
        print(f"  Champion WR={wr:.1f}%  AvgScore={cs.get('avg_score', 0):.1f}{mu_s}{ev}")

    if len(iters) >= 2:
        first = iters[0].get("champion_stats", {})
        last  = iters[-1].get("champion_stats", {})
        dwr   = (last.get("win_rate", 0) - first.get("win_rate", 0)) * 100
        print(f"\n  Trend: WR {'+' if dwr >= 0 else ''}{dwr:.1f} pp  "
              f"({first.get('win_rate', 0)*100:.1f}% → {last.get('win_rate', 0)*100:.1f}%)")
    print()


# ---------------------------------------------------------------------------
# Single iteration
# ---------------------------------------------------------------------------


def _run_iteration(
    iteration: int,
    registry: Dict[str, Any],
    games: int,
    base_seed: int,
    rng: random.Random,
    thinking_time_ms: int,
) -> Dict[str, Any]:
    version         = registry.get("current_version", "v1")
    champion_params = _get_champion_params(registry)
    challengers     = _sample_challengers(rng)
    seed            = base_seed + iteration

    print(f"\n{'=' * 70}")
    print(f"  Iteration {iteration}  |  Champion: {version}  |  Pool: {', '.join(challengers)}")
    print(f"{'=' * 70}")

    config  = _build_arena_config(champion_params, challengers, games, seed, iteration, thinking_time_ms)
    run_dir = _run_arena(config)
    parsed  = _parse_summary(run_dir)

    cs = parsed["agents"].get("champion", {})
    print(
        f"  Champion WR={cs.get('win_rate', 0):.1%}  "
        f"μ={cs.get('trueskill_mu', 0):.1f}  "
        f"σ={cs.get('trueskill_sigma', 0):.2f}  "
        f"avg_score={cs.get('avg_score', 0):.1f}"
    )
    for name in challengers:
        s = parsed["agents"].get(name, {})
        print(f"  {name:38s}  WR={s.get('win_rate', 0):.1%}  μ={s.get('trueskill_mu', 0):.1f}")

    return {
        "iteration":        iteration,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "champion_version": version,
        "challengers":      challengers,
        "run_dir":          run_dir,
        "num_games":        parsed["num_games"],
        "completed_games":  parsed["completed_games"],
        "champion_stats":   cs,
        "challenger_stats": {n: parsed["agents"].get(n, {}) for n in challengers},
        "snapshot_csv":     parsed.get("snapshot_csv"),
        "eval_updated":     False,
        "new_eval_weights": None,
    }


def _update_version_stats_wrapper(
    registry: Dict[str, Any],
    version: str,
    entry: Dict[str, Any],
    champion_params: Dict[str, Any],
) -> None:
    versions = registry.setdefault("versions", {})
    if version not in versions:
        versions[version] = {
            "promoted_at": entry["timestamp"],
            "params": champion_params,
            "_wr_acc": 0.0, "_mu_acc": 0.0, "_sc_acc": 0.0, "_count": 0,
        }
    v = versions[version]
    cs = entry.get("champion_stats", {})
    v["_count"] += 1
    n = v["_count"]
    v["_wr_acc"] += cs.get("win_rate", 0.0)
    v["_mu_acc"] += cs.get("trueskill_mu", 0.0) or 0.0
    v["_sc_acc"] += cs.get("avg_score", 0.0)
    v["avg_win_rate"]     = v["_wr_acc"] / n
    v["avg_trueskill_mu"] = v["_mu_acc"] / n
    v["avg_score"]        = v["_sc_acc"] / n


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Champion Self-Improvement Loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--iterations",  type=int, default=10,
                        help="Number of arena iterations to run.")
    parser.add_argument("--games-per-iter", "--num-games", type=int, default=20,
                        dest="games_per_iter", help="Arena games per iteration.")
    parser.add_argument("--champion-time", type=int, default=CHAMPION_THINKING_TIME_MS,
                        help=f"Champion thinking time in ms (default: {CHAMPION_THINKING_TIME_MS}).")
    parser.add_argument("--seed", type=int, default=20260429,
                        help="Base RNG seed for the loop.")
    parser.add_argument("--eval-update-interval", type=int, default=5,
                        help="Re-calibrate evaluator weights every N iterations (0 = never).")
    parser.add_argument("--eval-validation-games", type=int, default=16,
                        help="Games used to validate new evaluator weights before adopting.")
    parser.add_argument("--retrain", action="store_true",
                        help="Force evaluator update after the final iteration.")
    parser.add_argument("--show", action="store_true",
                        help="Print progress report and exit without running.")
    args = parser.parse_args()

    registry = _load_registry()

    if args.show:
        _show_history(registry)
        print(_render_markdown(registry))
        return

    rng = random.Random(args.seed)
    completed_so_far = len(registry.get("iterations", []))

    for i in range(1, args.iterations + 1):
        global_iter     = completed_so_far + i
        champion_params = _get_champion_params(registry)

        entry = _run_iteration(
            iteration=global_iter,
            registry=registry,
            games=args.games_per_iter,
            base_seed=args.seed,
            rng=rng,
            thinking_time_ms=args.champion_time,
        )

        if entry.get("snapshot_csv"):
            registry.setdefault("snapshot_csv_paths", []).append(entry["snapshot_csv"])

        registry["total_games_played"] = (
            registry.get("total_games_played", 0) + entry["completed_games"]
        )

        version = registry.get("current_version", "v1")
        _update_version_stats_wrapper(registry, version, entry, champion_params)

        # --- Evaluator improvement ---
        force = args.retrain and (i == args.iterations)
        on_interval = (
            args.eval_update_interval > 0
            and global_iter % args.eval_update_interval == 0
        )
        if force or on_interval:
            print(f"\n  [eval] Attempting evaluator calibration (iteration {global_iter}) …")
            snapshot_paths = registry.get("snapshot_csv_paths", [])
            new_weights = _try_improve_evaluator(snapshot_paths)
            if new_weights is not None:
                old_params = _get_champion_params(registry)
                accepted = _validate_new_weights(
                    old_params, new_weights,
                    games=args.eval_validation_games,
                    seed=args.seed + global_iter * 1000,
                    thinking_time_ms=args.champion_time,
                )
                if accepted:
                    old_ver  = registry.get("current_version", "v1")
                    ver_num  = int(old_ver.lstrip("v") or "1") + 1
                    new_ver  = f"v{ver_num}"
                    new_par  = {**old_params, "state_eval_weights": new_weights}
                    registry["current_version"] = new_ver
                    registry.setdefault("versions", {})[new_ver] = {
                        "promoted_at":     datetime.now(timezone.utc).isoformat(),
                        "params":          new_par,
                        "promoted_from":   old_ver,
                        "promotion_reason": f"Evaluator recalibration at iteration {global_iter}",
                        "_wr_acc": 0.0, "_mu_acc": 0.0, "_sc_acc": 0.0, "_count": 0,
                    }
                    # Write updated weights to calibrated file
                    cal: Dict[str, Any] = {}
                    if CALIBRATED_WEIGHTS_PATH.exists():
                        with CALIBRATED_WEIGHTS_PATH.open() as f:
                            cal = json.load(f)
                    cal["single_weights"] = new_weights
                    with CALIBRATED_WEIGHTS_PATH.open("w") as f:
                        json.dump(cal, f, indent=2)
                    print(f"  [eval] Accepted → champion promoted to {new_ver}!")
                    entry["eval_updated"]     = True
                    entry["new_eval_weights"] = new_weights
                    entry["champion_version"] = new_ver
                else:
                    print("  [eval] New weights did not improve — keeping current.")
            else:
                print("  [eval] Calibration skipped (insufficient data).")

        registry.setdefault("iterations", []).append(entry)
        _save_registry(registry)
        _write_report(registry)

        print(f"\n  Iteration {global_iter} complete. "
              f"Champion WR this run: {entry['champion_stats'].get('win_rate', 0):.1%}")

    print(f"\n{'=' * 70}")
    print(f"  Champion loop complete — {args.iterations} iteration(s) run.")
    print(f"  Current champion: {registry.get('current_version', '?')}")
    print(f"  Total games played: {registry.get('total_games_played', 0)}")
    print(f"  Progress report: {PROGRESS_MD_PATH}")
    print(f"  Registry: {REGISTRY_PATH}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
