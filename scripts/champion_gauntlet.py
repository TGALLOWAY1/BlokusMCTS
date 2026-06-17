#!/usr/bin/env python
"""Champion Gauntlet — one-command, multi-seed evaluation of champion candidates.

Resolves the repo's central contradiction (a registry champion with null
metrics vs. a docs page that says there is no validated champion) by running a
single, reproducible, multi-seed tournament between the champion candidates and
producing real, ranked metrics.

It is intentionally conservative about promotion: it will only write a new
champion into ``data/champion_registry.json`` when (a) ``--promote`` is passed
*and* (b) the top candidate clears every promotion gate. Otherwise it prints
"No validated champion promoted." and leaves the registry untouched.

Candidates (4, exactly one game's worth of seats):
    champion_v1        config/champion_arena_params.json
    champion_minimal   config/champion_minimal_params.json
    pool_peer_500ms    config/pool_peer_500ms_params.json
    key_findings_best  config/key_findings_best_params.json

Usage:
    # Evaluate only (writes summaries, never touches the registry):
    python scripts/champion_gauntlet.py

    # Full decisive run, 3 seeds x 60 games, promote if gates pass:
    python scripts/champion_gauntlet.py --seeds 20260617 20260618 20260619 \
        --num-games 60 --promote

    # Fast smoke test (cheap, proves the pipeline end-to-end):
    python scripts/champion_gauntlet.py --num-games 2 \
        --seeds 1 2 --thinking-time-ms 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.tournament.arena_runner import RunConfig, run_experiment
from analytics.tournament.gauntlet import (
    DEFAULT_CANDIDATES,
    PromotionThresholds,
    aggregate_summary,
    build_leaderboard,
    build_registry_entry,
    evaluate_promotion,
    load_candidate_config,
    pairwise_record,
    rank_candidates,
    render_gauntlet_markdown,
    update_registry,
)

DEFAULT_SEEDS = [20260617, 20260618, 20260619]
DEFAULT_NUM_GAMES = 30
DEFAULT_OUTPUT_ROOT = "arena_runs/gauntlets"
DEFAULT_REGISTRY = "data/champion_registry.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a multi-seed champion gauntlet and (optionally) promote a winner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--candidates",
        nargs="+",
        default=None,
        metavar="NAME=PATH",
        help=(
            "Candidate specs as NAME=path/to/config.json. Defaults to the four "
            "standard candidates. Must total exactly 4 (one game's seats)."
        ),
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=DEFAULT_SEEDS,
        help=f"Deterministic run seeds, one arena run per seed (default: {DEFAULT_SEEDS}).",
    )
    parser.add_argument(
        "--num-games",
        type=int,
        default=DEFAULT_NUM_GAMES,
        help=f"Games per seed (default: {DEFAULT_NUM_GAMES}).",
    )
    parser.add_argument(
        "--seat-policy",
        choices=["randomized", "round_robin"],
        default="round_robin",
        help="Seat assignment policy (default: round_robin, controls seat bias).",
    )
    parser.add_argument(
        "--thinking-time-ms",
        type=int,
        default=None,
        help="Override every candidate's thinking_time_ms (use small values for smoke tests).",
    )
    parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Root directory for gauntlet run dirs (default: {DEFAULT_OUTPUT_ROOT}).",
    )
    parser.add_argument(
        "--snapshots",
        action="store_true",
        help="Enable ply snapshots (slower; produces se_ dataset rows).",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Update data/champion_registry.json IF the top candidate passes all gates.",
    )
    parser.add_argument(
        "--registry",
        default=DEFAULT_REGISTRY,
        help=f"Path to the champion registry (default: {DEFAULT_REGISTRY}).",
    )
    parser.add_argument(
        "--min-seeds",
        type=int,
        default=2,
        help="Promotion gate: minimum number of seeds (default: 2).",
    )
    parser.add_argument(
        "--min-total-games",
        type=int,
        default=40,
        help="Promotion gate: minimum total games across seeds (default: 40).",
    )
    parser.add_argument(
        "--min-mu-margin",
        type=float,
        default=0.5,
        help="Promotion gate: minimum TrueSkill Delta-mu over runner-up (default: 0.5).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-game progress from each arena run.",
    )
    return parser.parse_args()


def resolve_candidates(specs: List[str] | None) -> List[Dict[str, Any]]:
    """Resolve --candidates specs (or defaults) into loaded agent dicts."""
    if specs:
        pairs: Dict[str, str] = {}
        for spec in specs:
            if "=" not in spec:
                raise SystemExit(
                    f"Invalid --candidates entry '{spec}'. Expected NAME=path/to/config.json."
                )
            name, path = spec.split("=", 1)
            pairs[name.strip()] = path.strip()
    else:
        pairs = dict(DEFAULT_CANDIDATES)

    candidates = [load_candidate_config(name, path) for name, path in pairs.items()]
    if len(candidates) != 4:
        raise SystemExit(
            f"The arena requires exactly 4 agents; got {len(candidates)} candidate(s). "
            "Pass exactly four NAME=PATH specs."
        )
    return candidates


def run_one_seed(
    *,
    candidates: List[Dict[str, Any]],
    seed: int,
    num_games: int,
    seat_policy: str,
    output_root: str,
    snapshots: bool,
    thinking_time_ms: int | None,
    verbose: bool,
) -> Dict[str, Any]:
    """Run a single arena tournament for one seed and return its result dict."""
    agents = []
    for cand in candidates:
        tt = thinking_time_ms if thinking_time_ms is not None else cand["thinking_time_ms"]
        agents.append(
            {
                "name": cand["name"],
                "type": cand["type"],
                "thinking_time_ms": tt,
                "params": cand["params"],
            }
        )
    config = {
        "agents": agents,
        "num_games": num_games,
        "seed": seed,
        "seat_policy": seat_policy,
        "output_root": output_root,
        "max_turns": 2500,
        "notes": f"Champion gauntlet seed={seed}",
        "snapshots": {
            "enabled": snapshots,
            "strategy": "fixed_ply",
            "checkpoints": [8, 16, 24, 32, 40, 48, 56, 64] if snapshots else [],
        },
    }
    run_config = RunConfig.from_dict(config)
    print(f"[gauntlet] Seed {seed}: running {num_games} games ...", flush=True)
    result = run_experiment(run_config, verbose=verbose)
    return result


def load_games_from_run(run_dir: str) -> List[Dict[str, Any]]:
    games: List[Dict[str, Any]] = []
    path = Path(run_dir) / "games.jsonl"
    if not path.exists():
        return games
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                games.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return games


def main() -> None:
    args = parse_args()
    candidates = resolve_candidates(args.candidates)
    candidate_names = [c["name"] for c in candidates]
    thinking_by_agent = {
        c["name"]: (args.thinking_time_ms if args.thinking_time_ms is not None else c["thinking_time_ms"])
        for c in candidates
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    gauntlet_id = f"gauntlet_{ts}"
    gauntlet_dir = Path(args.output_root) / gauntlet_id
    gauntlet_dir.mkdir(parents=True, exist_ok=True)

    print(f"[gauntlet] {gauntlet_id}")
    print(f"[gauntlet] Candidates: {candidate_names}")
    print(f"[gauntlet] Seeds: {args.seeds}  Games/seed: {args.num_games}")
    print(f"[gauntlet] Output: {gauntlet_dir}")

    # Run one arena per seed, pooling all games.
    all_games: List[Dict[str, Any]] = []
    seed_runs: List[Dict[str, Any]] = []
    for seed in args.seeds:
        result = run_one_seed(
            candidates=candidates,
            seed=seed,
            num_games=args.num_games,
            seat_policy=args.seat_policy,
            output_root=str(gauntlet_dir / f"seed_{seed}"),
            snapshots=args.snapshots,
            thinking_time_ms=args.thinking_time_ms,
            verbose=args.verbose,
        )
        run_dir = result["run_dir"]
        games = load_games_from_run(run_dir)
        all_games.extend(games)
        seed_runs.append(
            {
                "seed": seed,
                "run_id": result["run_id"],
                "run_dir": run_dir,
                "completed_games": result["summary"].get("completed_games"),
            }
        )

    # Aggregate across seeds and rank.
    pooled = aggregate_summary(
        all_games,
        agent_names=candidate_names,
        thinking_time_ms_by_agent=thinking_by_agent,
        seeds=args.seeds,
        seat_policy=args.seat_policy,
        run_config={"gauntlet_id": gauntlet_id, "candidates": candidate_names},
    )
    leaderboard = build_leaderboard(pooled)
    ranked = rank_candidates(leaderboard)
    total_games = pooled.get("completed_games", len(all_games))

    # Pairwise display lines.
    pairwise_lines: List[str] = []
    for i in range(len(candidate_names)):
        for j in range(i + 1, len(candidate_names)):
            a, b = candidate_names[i], candidate_names[j]
            rec = pairwise_record(pooled, a, b)
            pairwise_lines.append(
                f"`{a}` vs `{b}`: {rec['a_wins']}-{rec['b_wins']} "
                f"(ties {rec['tie']}, n={rec['total']})"
            )

    thresholds = PromotionThresholds(
        min_seeds=args.min_seeds,
        min_total_games=args.min_total_games,
        min_mu_margin=args.min_mu_margin,
        num_agents=len(candidate_names),
    )
    decision = evaluate_promotion(
        ranked,
        pooled,
        n_seeds=len(args.seeds),
        total_games=total_games,
        thresholds=thresholds,
    )

    # Assemble the report.
    report: Dict[str, Any] = {
        "gauntlet_id": gauntlet_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seeds": list(args.seeds),
        "num_games_per_seed": args.num_games,
        "total_games": total_games,
        "seat_policy": args.seat_policy,
        "candidates": [
            {
                "name": c["name"],
                "config_path": c.get("config_path"),
                "config_hash": c.get("config_hash"),
                "thinking_time_ms": thinking_by_agent[c["name"]],
                "type": c["type"],
            }
            for c in candidates
        ],
        "seed_runs": seed_runs,
        "ranked": ranked,
        "pairwise_lines": pairwise_lines,
        "pooled_summary": pooled,
        "promotion": decision.to_dict(),
        "thresholds": {
            "min_seeds": thresholds.min_seeds,
            "min_total_games": thresholds.min_total_games,
            "min_mu_margin": thresholds.min_mu_margin,
            "num_agents": thresholds.num_agents,
            "random_baseline_win_rate": 1.0 / thresholds.num_agents,
        },
        "registry_updated": False,
        "registry_path": args.registry,
        "registry_version": None,
    }

    # Registry update only on validated promotion AND --promote.
    if decision.promote and args.promote:
        champ_row = next(r for r in ranked if r["name"] == decision.champion)
        champ_cand = next(c for c in candidates if c["name"] == decision.champion)
        runner_up = ranked[1]["name"]
        entry = build_registry_entry(
            champion_row=champ_row,
            config_path=champ_cand.get("config_path"),
            params=champ_cand["params"],
            seeds=args.seeds,
            total_games=total_games,
            gauntlet_run_path=str(gauntlet_dir),
            comparison_opponents=[n for n in candidate_names if n != decision.champion],
            promoted_from=_current_registry_version(args.registry),
            promotion_reason=(
                f"Validated by champion gauntlet {gauntlet_id}: ranked #1 by TrueSkill "
                f"conservative, beat runner-up {runner_up} head-to-head, and cleared all "
                f"promotion gates across {len(args.seeds)} seeds / {total_games} games."
            ),
            notes=decision.summary_line,
        )
        version = update_registry(args.registry, entry)
        report["registry_updated"] = True
        report["registry_version"] = version
        print(f"[gauntlet] Registry promoted: {decision.champion} → {version}")
    elif decision.promote and not args.promote:
        print(
            "[gauntlet] Top candidate PASSES the gates, but --promote was not set; "
            "registry left untouched."
        )

    # Persist artifacts.
    (gauntlet_dir / "gauntlet_summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (gauntlet_dir / "gauntlet_summary.md").write_text(
        render_gauntlet_markdown(report), encoding="utf-8"
    )

    # Console summary.
    print("\n" + "=" * 72)
    print(f" Champion Gauntlet Results — {gauntlet_id}")
    print("=" * 72)
    print(f" Total games: {total_games}  Seeds: {args.seeds}")
    print(f" {'Rank':<5}{'Candidate':<20}{'Win%':>7}{'Wilson95':>18}{'Cons':>8}")
    for row in ranked:
        ci = f"[{row['win_rate_ci_lower']*100:.0f},{row['win_rate_ci_upper']*100:.0f}]"
        cons = row.get("trueskill_conservative")
        cons_s = f"{cons:.2f}" if cons is not None else "n/a"
        print(
            f" {row['rank']:<5}{row['name']:<20}{row['win_rate']*100:>6.1f}%"
            f"{ci:>18}{cons_s:>8}"
        )
    print("-" * 72)
    print(f" {decision.summary_line}")
    print("=" * 72)
    print(f"\n[gauntlet] Wrote: {gauntlet_dir}/gauntlet_summary.md")
    print(f"[gauntlet] Wrote: {gauntlet_dir}/gauntlet_summary.json")


def _current_registry_version(registry_path: str) -> str | None:
    path = Path(registry_path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text()).get("current_version")
    except (json.JSONDecodeError, OSError):
        return None


if __name__ == "__main__":
    main()
