"""Self-play data generation: grow the snapshot corpus the trainers fit on.

    python -m mcts_lab.self_play --games 24

Plays champion-vs-challenger arenas with per-ply board snapshots enabled and
accumulates the rows into ``data/champion_snapshots.csv`` — the corpus that
``mcts_lab.train`` (regression refit) consumes. TD trajectories are generated
separately by ``python -m training.td_selfplay`` when needed.
"""

from __future__ import annotations

import argparse
import random
import sys

from mcts_lab._common import load_state


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=12, help="games per generation arena (default 12)")
    ap.add_argument("--generations", type=int, default=1, help="how many arenas to run (default 1)")
    ap.add_argument("--seed", type=int, default=None, help="base RNG seed (default: random)")
    ap.add_argument("--thinking-ms", type=int, default=None,
                    help="override MCTS thinking budget (smaller = faster, noisier data)")
    ap.add_argument("--collect-policy-games", type=int, default=0,
                    help="also collect this many games of MCTS visit-count policy targets "
                         "into data/policy_targets.csv (feeds the 'policy' approach)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    from training import TrainingPaths, selfplay_core as sc
    from training import state_store
    from scripts.champion_loop import build_tracker

    paths = TrainingPaths.default()
    paths.ensure_dirs()
    state = load_state(paths)
    base_seed = args.seed if args.seed is not None else random.randrange(1, 2**31)
    rng = random.Random(base_seed)
    tracker = build_tracker(state)

    total_rows = 0
    for g in range(args.generations):
        gen = int(state.get("generation", 0))
        result = sc.run_generation(
            state, paths, generation=gen, games_per_arena=args.games,
            seed=base_seed + g, rng=rng, tracker=tracker,
            thinking_time_ms=args.thinking_ms, verbose=args.verbose,
        )
        total_rows = result.snapshot_rows
        print(f"generation arena {g + 1}/{args.generations}: {result.games_run} games, "
              f"corpus now {result.snapshot_rows} rows, "
              f"challengers={result.challengers} ({result.elapsed_s:.0f}s)")

    state_store.save_latest(paths, state)
    print(f"\nsnapshot corpus: {total_rows} rows (data/champion_snapshots.csv)")

    if args.collect_policy_games > 0:
        import copy
        from training.policy_selfplay import collect_policy_targets

        champ = copy.deepcopy(state["champion_params"])
        champ["name"] = "champion"
        champ2 = copy.deepcopy(champ)
        champ2["name"] = "champion2"
        roster = [champ, {"name": "heuristic", "type": "heuristic"},
                  champ2, {"name": "random", "type": "random"}]
        if args.thinking_ms is not None:
            for a in roster:
                if a.get("type", "mcts") == "mcts":
                    a["thinking_time_ms"] = int(args.thinking_ms)
        rows = collect_policy_targets(
            roster, run_id=f"selfplay_{base_seed}", num_games=args.collect_policy_games,
            seed=base_seed, verbose=args.verbose,
        )
        print(f"policy targets: +{rows} rows (data/policy_targets.csv)")
        print("next: python -m training.policy_learning")

    print("next: python -m mcts_lab.train")
    return 0


if __name__ == "__main__":
    sys.exit(main())
