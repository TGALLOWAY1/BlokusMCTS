"""Gated champion replacement: screen, confirm, then promote a candidate.

    python -m mcts_lab.promote --candidate training/artifacts/candidates/<artifact>.json
    python -m mcts_lab.promote --candidate <artifact>.json --dry-run

Two-stage promotion against the fixed benchmark pool (heuristic, random, and
two fixed MCTS anchors), always with the current champion in every game:

1. **Screen** — a cheap evaluation (default 20+ games over 2 seeds). The
   candidate must beat the champion head-to-head, show positive Elo and
   TrueSkill deltas, and rank #1 against the pool (conservative 6-gate).
2. **Confirm** — the screen winner is re-evaluated over a larger sample
   (default 60+ games) and must clear the same gate again at the higher game
   floor. A lucky short run can never promote on its own.

On success the champion registry (``training/state/champion.json``) is updated
atomically: the old champion is checkpointed (immutable, becomes a future
benchmark opponent), the lineage is appended, and history/ratings are recorded.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from mcts_lab._common import load_state, parse_seeds

DEFAULT_SEEDS = "20260620,20260621"


def _load_candidate(path: str):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg = data.get("agent_config", data)
    if not isinstance(cfg, dict) or not cfg.get("type"):
        raise SystemExit(f"{path}: no usable agent_config")
    name = data.get("name") or cfg.get("name") or "candidate"
    approach = data.get("approach", "manual")
    metrics = data.get("metrics", {}) or {}
    return name, approach, cfg, metrics


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", required=True, help="candidate artifact or agent-config JSON")
    ap.add_argument("--games", type=int, default=5,
                    help="screen games per arena per seed (2 arenas x seeds x games; default 5 -> 20 total)")
    ap.add_argument("--confirm-games", type=int, default=60,
                    help="total games for the confirmation stage (default 60)")
    ap.add_argument("--seeds", default=DEFAULT_SEEDS)
    ap.add_argument("--thinking-ms", type=int, default=None,
                    help="uniform thinking budget for all MCTS agents during evaluation")
    ap.add_argument("--budget-minutes", type=float, default=120.0, help="wall-clock cap")
    ap.add_argument("--dry-run", action="store_true", help="evaluate + report, never persist")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    from training import TrainingPaths, state_store, ratings_db
    from training.evaluation.benchmark_pool import build_benchmark_pool
    from training.evaluation.head_to_head import (
        confirm_winner, evaluate_candidate_vs_pool,
    )
    from training.evaluation.promotion_gate import GateThresholds, evaluate_gate
    from training.nightly_run import (
        _ensure_cold_start, _promote_winner, _seed_elo_tracker, _seed_trueskill_tracker,
    )
    from scripts.champion_loop import CHAMPION_ID, persist_tracker

    name, approach, cfg, metrics = _load_candidate(args.candidate)
    seeds = parse_seeds(args.seeds)
    paths = TrainingPaths.default()
    paths.ensure_dirs()
    state = load_state(paths)
    champion = state_store.load_champion(paths)
    _ensure_cold_start(state, champion)

    pool = build_benchmark_pool(state, seeds=seeds)
    deadline = time.monotonic() + args.budget_minutes * 60.0

    # --- Stage 1: screen -----------------------------------------------------
    print(f"screen: {name} ({approach}) vs champion + pool "
          f"[{args.games} games/arena x {len(seeds)} seeds]")
    ce, games, _dirs = evaluate_candidate_vs_pool(
        state, name, approach, cfg, pool, paths,
        games_per_arena=args.games, seeds=seeds, thinking_time_ms=args.thinking_ms,
        deadline=deadline, verbose=args.verbose,
    )
    gate = evaluate_gate(ce, GateThresholds())
    _print_eval("screen", ce, gate)
    if not gate.passed:
        print("\nHOLD — candidate did not clear the screen gate.")
        return 1

    # --- Stage 2: confirmation ----------------------------------------------
    print(f"\nconfirm: re-evaluating over >= {args.confirm_games} games")
    conf_eval, conf_games, _cd = confirm_winner(
        state, name, approach, cfg, pool, paths,
        seeds=seeds, thinking_time_ms=args.thinking_ms,
        target_total_games=args.confirm_games, deadline=deadline, verbose=args.verbose,
    )
    conf_gate = evaluate_gate(conf_eval, GateThresholds(min_total_games=args.confirm_games))
    _print_eval("confirm", conf_eval, conf_gate)
    if not conf_gate.passed:
        print("\nHOLD — screen result did not hold up over the confirmation sample.")
        return 1

    if args.dry_run:
        print("\nDRY RUN — gate PASSED but nothing was persisted.")
        return 0

    # --- Persist -------------------------------------------------------------
    conn = ratings_db.connect(paths.ratings_db)
    latest_db = ratings_db.latest_ratings(conn)
    elo = _seed_elo_tracker(latest_db)
    tracker = _seed_trueskill_tracker(state, latest_db)
    for g in games + conf_games:
        scores = g.get("agent_scores", {})
        if scores:
            elo.update_game(scores)
            tracker.update_game(scores)

    state["generation"] = int(state.get("generation", 0)) + 1
    promoted = _promote_winner(
        state, champion, conf_eval, cfg, metrics, conf_gate.reason, paths,
        tracker=tracker, elo=elo, promote_registry=False,
    )
    state_store.append_jsonl(paths.history_jsonl, {
        "schema_version": state_store.HISTORY_SCHEMA_VERSION,
        "kind": state_store.HISTORY_KIND_APPROACH,
        "generation": int(state["generation"]),
        "run_id": f"cli_promote_{name}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "games": len(games) + len(conf_games),
        "approaches": [approach],
        "candidates_created": [name],
        "winner": name,
        "promoted": bool(promoted),
        "champion_elo": float(elo.get_rating(CHAMPION_ID)),
        "champion_mu": tracker.get_rating(CHAMPION_ID)["mu"],
        "champion_sigma": tracker.get_rating(CHAMPION_ID)["sigma"],
        "champion_conservative": tracker.get_rating(CHAMPION_ID)["conservative"],
    })
    persist_tracker(tracker, state)
    state_store.save_latest(paths, state)
    conn.close()

    print(f"\nPROMOTED {name} -> champion {champion['version']} "
          f"(training/state/champion.json updated; previous champion checkpointed)")
    return 0


def _print_eval(stage, ce, gate) -> None:
    vs = ce.vs_champion
    print(f"  [{stage}] games={ce.games} seeds={ce.n_seeds} "
          f"win%={ce.win_rate * 100:.1f} CI=[{ce.win_rate_ci[0]:.2f},{ce.win_rate_ci[1]:.2f}] "
          f"vs champion {vs.get('candidate_wins')}-{vs.get('champion_wins')} "
          f"dElo={ce.elo_delta_vs_champion:+.1f} "
          f"dMu={(ce.trueskill_mu_delta_vs_champion if ce.trueskill_mu_delta_vs_champion is not None else float('nan')):+.2f}")
    print(f"  [{stage}] {gate.reason}")


if __name__ == "__main__":
    sys.exit(main())
