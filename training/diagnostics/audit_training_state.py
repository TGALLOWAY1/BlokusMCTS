"""Quick audit of durable MCTS training state.

Run with:
    python -m training.diagnostics.audit_training_state
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List

from analytics.tournament.elo import EloTracker
from analytics.tournament.trueskill_rating import TrueSkillTracker
from training import TrainingPaths, ratings_db
from training.evaluation.benchmark_pool import build_benchmark_pool
from training.evaluation.head_to_head import EVAL_MIN_SEEDS, EVAL_MIN_TOTAL_GAMES
from training.evaluation.rating_analysis import trend_per_step


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _history(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"_malformed": line[:120]})
    return rows


def _latest_comparison(state: Dict[str, Any]) -> Dict[str, Any]:
    comp = state.get("last_approach_comparison") or {}
    return comp if isinstance(comp, dict) else {}


def promotion_gate_satisfiability(comp: Dict[str, Any]) -> Dict[str, Any]:
    rows = comp.get("candidates") or comp.get("rows") or []
    counts = {r.get("name") or r.get("approach"): int(r.get("games") or 0) for r in rows}
    max_games = max(counts.values(), default=0)
    seeds = comp.get("seeds") or []
    created = [r for r in rows if r.get("created", True)]
    under_min = {
        r.get("name") or r.get("approach"): int(r.get("games") or 0)
        for r in created
        if int(r.get("games") or 0) < EVAL_MIN_TOTAL_GAMES
    }
    return {
        "min_total_games": EVAL_MIN_TOTAL_GAMES,
        "min_seeds": EVAL_MIN_SEEDS,
        "max_candidate_games": max_games,
        "seeds": len(seeds),
        "any_candidate_satisfiable_by_latest_counts": max_games >= EVAL_MIN_TOTAL_GAMES and len(seeds) >= EVAL_MIN_SEEDS,
        "all_created_candidates_satisfy_game_floor": not under_min and len(seeds) >= EVAL_MIN_SEEDS,
        "under_min_total_games": under_min,
        "candidate_games": counts,
    }


def benchmark_pool_health(state: Dict[str, Any], seeds: List[int]) -> Dict[str, Any]:
    pool = build_benchmark_pool(state, seeds=seeds or None)
    names = pool.opponent_names()
    mcts = [n for n in names if "mcts" in n or n == "best_historical"]
    return {
        "version": pool.version,
        "opponents": names,
        "seeds": pool.seeds,
        "has_random": "random" in names,
        "has_heuristic": "heuristic" in names,
        "mcts_anchor_count": len(mcts),
        "has_stable_mcts_anchor": bool(mcts),
    }


def validate_history(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    missing_result = 0
    malformed = 0
    duplicates = 0
    seen = set()
    by_candidate: Counter[str] = Counter()
    for i, r in enumerate(rows):
        if r.get("_malformed"):
            malformed += 1
            continue
        key = (r.get("run_id"), r.get("generation"), r.get("timestamp"))
        if key in seen:
            duplicates += 1
        seen.add(key)
        if "winner" not in r and "promoted" not in r and "champion_elo" not in r:
            missing_result += 1
        for c in r.get("candidates_created") or []:
            by_candidate[str(c)] += 1
    return {"rows": len(list(rows)) if not isinstance(rows, list) else len(rows),
            "malformed_rows": malformed, "duplicate_keys": duplicates,
            "missing_result_like_fields": missing_result,
            "created_counts": dict(by_candidate)}


def replay_rating_direction(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Replay a small sample and flag games where the top scorer loses rating."""
    elo = EloTracker()
    ts = TrueSkillTracker()
    suspicious = 0
    checked = 0
    for g in games:
        scores = g.get("agent_scores") or {}
        if len(scores) < 2:
            continue
        winner = max(scores, key=scores.get)
        before_e = elo.get_rating(winner)
        before_mu = ts.get_rating(winner)["mu"]
        elo.update_game(scores)
        ts.update_game(scores)
        after_e = elo.get_rating(winner)
        after_mu = ts.get_rating(winner)["mu"]
        checked += 1
        if after_e < before_e or after_mu < before_mu:
            suspicious += 1
    return {"checked_games": checked, "top_scorer_rating_drops": suspicious}


def summarize(paths: TrainingPaths) -> Dict[str, Any]:
    state = _load_json(paths.latest_json)
    champion = _load_json(paths.champion_json)
    conn = ratings_db.connect(paths.ratings_db)
    series = ratings_db.champion_elo_series(conn, since_run_id=ratings_db.MULTI_AGENT_EPOCH_RUN_ID)
    latest = ratings_db.last_run_summary(conn) or {}
    conn.close()

    elos = [float(r["elo"]) for r in series]
    comp = _latest_comparison(state)
    candidates = comp.get("candidates") or comp.get("rows") or []
    recent_decisions = [{
        "approach": c.get("approach"), "name": c.get("name"), "games": c.get("games"),
        "win_rate_vs_champ": c.get("win_rate_vs_champion"), "elo_delta": c.get("elo_delta_vs_champion", c.get("elo_delta")),
        "promoted": c.get("promoted"), "reason": c.get("gate_reason") or c.get("reason"),
    } for c in candidates]

    hrows = _history(paths.history_jsonl)
    return {
        "champion": {
            "state_name": (state.get("champion") or {}).get("name"),
            "state_version": (state.get("champion") or {}).get("version"),
            "champion_json_version": champion.get("version"),
            "params_consistent": bool(state.get("champion_params") == champion.get("params")),
            "last_promoted_generation": state.get("last_promoted_generation"),
        },
        "latest_generation": state.get("generation"),
        "latest_run": {"run_id": latest.get("run_id"), "games_today": latest.get("games_today"),
                       "champion_elo": latest.get("champion_elo")},
        "recent_elo_trend_per_game": (trend_per_step(elos[-10:]) if len(elos) >= 2 else 0.0),
        "recent_promotion_decisions": recent_decisions,
        "gate_satisfiability": promotion_gate_satisfiability(comp),
        "benchmark_pool": benchmark_pool_health(state, comp.get("seeds") or []),
        "history_validation": validate_history(hrows),
        "suspicious_rating_movements": replay_rating_direction([]),
    }


def format_markdown(summary: Dict[str, Any]) -> str:
    lines = ["# Training State Audit", ""]
    lines += ["## Champion", f"- Identity: `{summary['champion']['state_name']}` {summary['champion']['state_version']}",
              f"- Champion params consistent with champion.json: {summary['champion']['params_consistent']}",
              f"- Last promoted generation: {summary['champion']['last_promoted_generation']}", ""]
    latest = summary["latest_run"]
    lines += ["## Latest generation", f"- Generation: {summary['latest_generation']}",
              f"- Run: {latest.get('run_id')} ({latest.get('games_today')} games, Elo {latest.get('champion_elo')})",
              f"- Recent Elo trend per recorded game/run point: {summary['recent_elo_trend_per_game']:.3f}", ""]
    lines += ["## Promotion decisions"]
    for d in summary["recent_promotion_decisions"]:
        lines.append(f"- {d.get('approach')} / {d.get('name')}: games={d.get('games')} promoted={d.get('promoted')} reason={d.get('reason')}")
    sat = summary["gate_satisfiability"]
    lines += ["", "## Gate satisfiability", f"- Required: {sat['min_total_games']} games over {sat['min_seeds']} seeds",
              f"- Latest max candidate games: {sat['max_candidate_games']} over {sat['seeds']} seeds",
              f"- Any candidate satisfiable under latest counts: {sat['any_candidate_satisfiable_by_latest_counts']}",
              f"- All created candidates satisfy game floor: {sat['all_created_candidates_satisfy_game_floor']}",
              f"- Under game floor: {sat['under_min_total_games']}",
              f"- Candidate game counts: {sat['candidate_games']}", ""]
    pool = summary["benchmark_pool"]
    lines += ["## Benchmark pool", f"- Version: {pool['version']}",
              f"- Opponents: {', '.join(pool['opponents'])}",
              f"- Stable MCTS anchors: {pool['mcts_anchor_count']}", ""]
    hv = summary["history_validation"]
    lines += ["## State/history validation", f"- History rows: {hv['rows']}",
              f"- Malformed rows: {hv['malformed_rows']}", f"- Duplicate keys: {hv['duplicate_keys']}",
              f"- Missing result-like fields: {hv['missing_result_like_fields']}"]
    return "\n".join(lines) + "\n"


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(TrainingPaths.default().root))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    paths = TrainingPaths.under(Path(args.root))
    s = summarize(paths)
    print(json.dumps(s, indent=2, sort_keys=True) if args.json else format_markdown(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
