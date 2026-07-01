"""Benchmark arena: evaluate agents against each other over fixed seeds.

    python -m mcts_lab.eval --agents champion,baseline --games 10 --seeds 20260620,20260621

Runs seeded 4-agent arenas (missing seats are filled with the fixed heuristic /
random anchors), pools every game, and prints a leaderboard with win rate,
95% Wilson confidence interval, average rank, TrueSkill and Elo. Writes the
pooled summary JSON next to the per-run outputs under
``training/state/selfplay_runs/``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from mcts_lab._common import load_state, parse_seeds, resolve_agent

DEFAULT_SEEDS = "20260620,20260621"
ANCHOR_FILL = ("heuristic", "random")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--agents", required=True,
                    help="2-4 comma-separated agent specs: champion|baseline|heuristic|random|<config.json>")
    ap.add_argument("--games", type=int, default=10, help="games per seed (default 10)")
    ap.add_argument("--seeds", default=DEFAULT_SEEDS, help=f"comma-separated seeds (default {DEFAULT_SEEDS})")
    ap.add_argument("--thinking-ms", type=int, default=None,
                    help="override thinking budget for all MCTS agents (keeps quick evals quick)")
    ap.add_argument("--out", default=None, help="write pooled summary JSON here")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    from analytics.tournament import gauntlet
    from training import TrainingPaths, selfplay_core as sc

    state = load_state()
    specs = [s for s in args.agents.split(",") if s.strip()]
    if not 2 <= len(specs) <= 4:
        ap.error("--agents needs 2-4 entries")
    agents = [resolve_agent(s, state) for s in specs]
    # Fill remaining seats with anchor agents (unique names required by the arena).
    filler_idx = 0
    while len(agents) < 4:
        base = ANCHOR_FILL[filler_idx % len(ANCHOR_FILL)]
        suffix = filler_idx // len(ANCHOR_FILL)
        name = base if suffix == 0 else f"{base}_{suffix + 1}"
        filler_idx += 1
        if name in {a["name"] for a in agents}:
            continue
        agents.append(resolve_agent(base, state, name=name))

    seeds = parse_seeds(args.seeds)
    paths = TrainingPaths.default()
    paths.ensure_dirs()
    sc._apply_thinking_override(agents, args.thinking_ms)

    all_games = []
    t0 = time.monotonic()
    for seed in seeds:
        result = sc.run_arena_inproc(
            agents, paths=paths, run_label=f"cli_eval_s{seed}",
            num_games=args.games, seed=seed, enable_snapshots=False, verbose=args.verbose,
        )
        all_games.extend(sc._load_games(result["run_dir"]))
        print(f"seed {seed}: {args.games} games -> {result['run_dir']}")

    names = sorted({a["name"] for a in agents})
    pooled = gauntlet.aggregate_summary(
        all_games, agent_names=names,
        thinking_time_ms_by_agent={a["name"]: a.get("thinking_time_ms") for a in agents},
        seeds=seeds, seat_policy="randomized",
        run_config={"phase": "cli_eval"},
    )
    leaderboard = gauntlet.build_leaderboard(pooled)

    print(f"\n{len(all_games)} games over {len(seeds)} seed(s) in {time.monotonic() - t0:.0f}s\n")
    print(f"{'agent':<22} {'win%':>6} {'95% CI':>15} {'avg rank':>9} {'TS mu':>7} {'sigma':>6}")
    for row in leaderboard:
        ci = f"[{row.get('win_rate_ci_lower', 0):.2f},{row.get('win_rate_ci_upper', 0):.2f}]"
        mu = row.get("trueskill_mu")
        sigma = row.get("trueskill_sigma")
        print(f"{row['name']:<22} {row.get('win_rate', 0) * 100:>5.1f}% {ci:>15} "
              f"{row.get('avg_rank', 0):>9.2f} "
              f"{(mu if mu is not None else float('nan')):>7.2f} "
              f"{(sigma if sigma is not None else float('nan')):>6.2f}")

    if args.out:
        Path(args.out).write_text(json.dumps(pooled, indent=2, default=str), encoding="utf-8")
        print(f"\npooled summary -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
