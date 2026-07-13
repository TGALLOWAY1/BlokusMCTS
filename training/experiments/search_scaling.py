"""Phase 4 search-scaling gate: does more search compute buy stronger play?

Runs the SAME minimal MCTS configuration (plain UCT + maxⁿ, greedy_sample
rollouts, cutoff 12, heuristic ordering — the gen140 champion search config)
at a ladder of exact iteration budgets in one mixed 4-seat arena, with
round_robin seat rotation and fixed seeds, then reports first-place rates,
average ranks, Wilson CIs, TrueSkill, and paired sign-flip permutation tests
between every agent pair.

Budgets are pinned by passing `iterations` directly with thinking_time_ms
None, so build_agent's deterministic-time path cannot rewrite them and search
is fully seed-reproducible (see analytics/tournament/arena_runner.build_agent).

Examples:
    python -m training.experiments.search_scaling \
        --budgets 50,150,500 --anchor heuristic \
        --games-per-seed 12 --seeds 20260620,20260621 --deadline-minutes 170
    python -m training.experiments.search_scaling \
        --budgets 500,1500 --anchor heuristic,random \
        --games-per-seed 4 --seeds 20260620,20260621 --label probe_hi
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from analytics.tournament import gauntlet
from analytics.tournament.arena_runner import RunConfig, run_experiment
from analytics.tournament.statistics import paired_permutation_test

DEFAULT_OUTPUT_ROOT = Path("training/reports/experiments/search_scaling")

# The minimal trusted search configuration (Phase 3-verified): identical for
# every budget agent; ONLY the iteration budget varies.
MINIMAL_SEARCH_PARAMS: Dict[str, Any] = {
    "deterministic_time_budget": False,   # never rewrite `iterations`
    "rollout_policy": "greedy_sample",
    "greedy_sample_size": 12,
    "rollout_cutoff_depth": 12,
    "heuristic_move_ordering": True,
    "exploration_constant": 1.414,
    "use_transposition_table": True,
    "num_workers": 1,
}


# EXP-002 variant: progressive widening (the existing teacher-profile setting)
# caps expanded children at ceil(pw_c * N^pw_alpha) so visits concentrate on
# top-ordered moves instead of a one-visit-per-child sweep.
PW_PARAMS: Dict[str, Any] = {
    "progressive_widening_enabled": True,
    "pw_c": 2.0,
    "pw_alpha": 0.5,
}


def budget_agent(iterations: int, pw: bool = False,
                 cutoff: Optional[int] = None,
                 value_model: Optional[str] = None) -> Dict[str, Any]:
    params = dict(MINIMAL_SEARCH_PARAMS)
    if pw:
        params.update(PW_PARAMS)
    if cutoff is not None:
        # EXP-003 variant: cutoff 0 = pure static-eval leaves (no rollouts;
        # deterministic, TT-cacheable) — isolates rollout noise from
        # evaluator quality.
        params["rollout_cutoff_depth"] = int(cutoff)
    if value_model:
        # D-015 gate 3: model-artifact leaf evaluator replaces rollouts.
        params["value_model_path"] = str(value_model)
    params["iterations"] = int(iterations)
    return {
        "name": f"mcts_it{iterations}",
        "type": "mcts",
        "thinking_time_ms": None,
        "params": params,
    }


def anchor_agent(kind: str) -> Dict[str, Any]:
    if kind not in ("heuristic", "random"):
        raise ValueError(f"unsupported anchor {kind!r}")
    return {"name": kind, "type": kind, "thinking_time_ms": None, "params": {}}


def _build_agents(args: argparse.Namespace):
    budgets = sorted({int(b) for b in args.budgets.split(",")})
    anchors = [a for a in args.anchor.split(",") if a] if args.anchor else []
    pw = bool(getattr(args, "pw", False))
    cutoff = getattr(args, "cutoff", None)
    value_model = getattr(args, "value_model", None)
    agents = ([budget_agent(b, pw=pw, cutoff=cutoff, value_model=value_model)
               for b in budgets]
              + [anchor_agent(a) for a in anchors])
    if len(agents) != 4:
        raise SystemExit(
            f"Arena needs exactly 4 agents; got {len(agents)} "
            f"({len(budgets)} budgets + {len(anchors)} anchors)."
        )
    seeds = [int(s) for s in args.seeds.split(",")]
    label = args.label or (
        ("pw_" if pw else "")
        + (f"c{cutoff}_" if cutoff is not None else "")
        + ("vm_" if value_model else "")
        + "b" + "_".join(str(b) for b in budgets)
    )
    return agents, seeds, label


def reanalyze(args: argparse.Namespace) -> Dict[str, Any]:
    """Rebuild report.json from an existing label dir's persisted games.

    Use after a deadline-truncated run or a reporting fix — no games replayed.
    """
    agents, seeds, label = _build_agents(args)
    out_dir = Path(args.out_root) / label
    run_dirs = sorted(str(p.parent) for p in out_dir.glob("seed_*/*/games.jsonl"))
    if not run_dirs:
        raise SystemExit(f"No games.jsonl found under {out_dir}/seed_*/")
    all_games: List[Dict[str, Any]] = []
    for run_dir in run_dirs:
        all_games.extend(_load_games(run_dir))
    elapsed = sum(float(g.get("duration_sec") or 0.0) for g in all_games)
    return _analyze(all_games, agents, seeds, label, args, elapsed, run_dirs)


def run(args: argparse.Namespace) -> Dict[str, Any]:
    agents, seeds, label = _build_agents(args)
    out_dir = Path(args.out_root) / label
    out_dir.mkdir(parents=True, exist_ok=True)

    deadline = (
        time.monotonic() + args.deadline_minutes * 60.0
        if args.deadline_minutes else None
    )

    all_games: List[Dict[str, Any]] = []
    run_dirs: List[str] = []
    t0 = time.monotonic()
    for seed in seeds:
        run_cfg = RunConfig.from_dict({
            "agents": agents,
            "num_games": args.games_per_seed,
            "seed": seed,
            "seat_policy": "round_robin",
            "output_root": str(out_dir / f"seed_{seed}"),
            "max_turns": 2500,
            "notes": f"phase4 search-scaling :: {label} :: seed {seed}",
            "scoring_mode": "standard",
            "snapshots": {"enabled": False, "strategy": "fixed_ply", "checkpoints": []},
        })
        result = run_experiment(run_cfg, deadline=deadline)
        run_dirs.append(result["run_dir"])
        games = _load_games(result["run_dir"])
        all_games.extend(games)
        print(f"seed {seed}: {len(games)} games -> {result['run_dir']}", flush=True)

    elapsed = time.monotonic() - t0
    report = _analyze(all_games, agents, seeds, label, args, elapsed, run_dirs)
    return report


def _analyze(all_games, agents, seeds, label, args, elapsed, run_dirs) -> Dict[str, Any]:
    if not all_games:
        raise SystemExit("No completed games to analyze.")
    out_dir = Path(args.out_root) / label
    names = [a["name"] for a in agents]
    pooled = gauntlet.aggregate_summary(
        all_games, agent_names=sorted(names),
        thinking_time_ms_by_agent={a["name"]: a.get("thinking_time_ms") for a in agents},
        seeds=seeds, seat_policy="round_robin",
        run_config={"phase": "phase4_search_scaling", "label": label},
    )
    leaderboard = gauntlet.build_leaderboard(pooled)

    # build_leaderboard does not populate avg_rank; compute it (and the rank
    # distribution) from the per-game records — average finishing rank is a
    # required Phase 4 metric.
    rank_sums: Dict[str, List[int]] = {n: [] for n in names}
    for game in all_games:
        for name, rank in (game.get("agent_ranks") or {}).items():
            if name in rank_sums and rank is not None:
                rank_sums[name].append(int(rank))
    for row in leaderboard:
        ranks = rank_sums.get(row["name"], [])
        row["avg_rank"] = (sum(ranks) / len(ranks)) if ranks else None
        row["rank_distribution"] = {
            r: ranks.count(r) for r in sorted(set(ranks))
        }

    # Paired sign-flip permutation tests on per-game score differences for
    # every agent pair (mixed table => every game is a paired observation).
    pairwise = {}
    for a, b in itertools.combinations(names, 2):
        test = paired_permutation_test(all_games, a, b, seed=args.stat_seed)
        pairwise[f"{a} vs {b}"] = test

    budgets = sorted(int(a["params"]["iterations"]) for a in agents
                     if a["type"] == "mcts")
    anchors = [a["name"] for a in agents if a["type"] != "mcts"]
    report = {
        "experiment": "phase4_search_scaling",
        "label": label,
        "budgets": budgets,
        "anchors": anchors,
        "minimal_search_params": MINIMAL_SEARCH_PARAMS,
        "agent_params": {
            a["name"]: a["params"] for a in agents if a["type"] == "mcts"
        },
        "seeds": seeds,
        "games_per_seed": args.games_per_seed,
        "completed_games": len(all_games),
        "seat_policy": "round_robin",
        "scoring_mode": "standard",
        "elapsed_sec": round(elapsed, 1),
        "run_dirs": run_dirs,
        "leaderboard": leaderboard,
        "pairwise_permutation": pairwise,
        "pooled_summary": pooled,
    }
    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"\n{len(all_games)} games in {elapsed / 60:.1f} min "
          f"({elapsed / max(len(all_games), 1):.0f}s/game)\n")
    print(f"{'agent':<14} {'1st%':>6} {'95% CI':>14} {'avg rank':>9} {'TS mu':>7} {'sigma':>6}")
    def _num(value, default=float("nan")):
        return default if value is None else value

    for row in leaderboard:
        ci = f"[{_num(row.get('win_rate_ci_lower'), 0):.2f},{_num(row.get('win_rate_ci_upper'), 0):.2f}]"
        print(f"{row['name']:<14} {_num(row.get('win_rate'), 0) * 100:>5.1f}% {ci:>14} "
              f"{_num(row.get('avg_rank')):>9.2f} "
              f"{_num(row.get('trueskill_mu')):>7.2f} "
              f"{_num(row.get('trueskill_sigma')):>6.2f}")
    print("\nPaired permutation tests (per-game score diff, sign-flip):")
    for pair, test in pairwise.items():
        print(f"  {pair:<28} diff={test['observed_diff']:>7.2f}  "
              f"p={test['p_value']:.4f}  n={test['n_games']}")
    print(f"\nreport -> {report_path}")
    return report


def _load_games(run_dir: str) -> List[Dict[str, Any]]:
    games = []
    path = Path(run_dir) / "games.jsonl"
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("is_valid_result", True):
                games.append(record)
    return games


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m training.experiments.search_scaling", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--budgets", default="50,150,500",
                        help="comma-separated exact iteration budgets")
    parser.add_argument("--anchor", default="heuristic",
                        help="comma-separated no-search anchors to fill seats "
                             "(heuristic,random); budgets+anchors must equal 4")
    parser.add_argument("--games-per-seed", type=int, default=12)
    parser.add_argument("--seeds", default="20260620,20260621")
    parser.add_argument("--deadline-minutes", type=float, default=None,
                        help="hard wall-clock cutoff (checked between games)")
    parser.add_argument("--label", default=None)
    parser.add_argument("--out-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--pw", action="store_true",
                        help="enable progressive widening on the budget agents "
                             "(pw_c=2.0, pw_alpha=0.5 — EXP-002 variant)")
    parser.add_argument("--cutoff", type=int, default=None,
                        help="override rollout_cutoff_depth on the budget agents "
                             "(0 = pure static-eval leaves — EXP-003 variant)")
    parser.add_argument("--value-model", default=None,
                        help="joblib value-model artifact for the budget agents' "
                             "leaf evaluator (D-015 gate 3)")
    parser.add_argument("--stat-seed", type=int, default=20260712)
    parser.add_argument("--reanalyze", action="store_true",
                        help="rebuild report.json from the label dir's existing "
                             "games (no games played)")
    args = parser.parse_args(argv)
    if args.reanalyze:
        reanalyze(args)
    else:
        run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
