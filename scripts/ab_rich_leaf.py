"""Direct A/B: baseline MCTS vs MCTS + rich leaf evaluator.

Plays full 4-player Blokus games with two baseline agents and two rich-leaf
agents per game, rotating seat assignment to cancel seat bias. Reports win rate,
mean score, per-leaf evaluation cost, and iterations/move at a **fixed iteration
budget** so the strength delta is isolated from the per-leaf time cost (which is
reported separately so the time-budget tradeoff can be reasoned about).

Usage:
    python -m scripts.ab_rich_leaf --games 16 --iterations 250 --subset score
"""

from __future__ import annotations

import argparse
import time
from typing import Dict

import numpy as np

from engine.board import Player
from engine.game import BlokusGame
from mcts.mcts_agent import MCTSAgent


def _make_agent(rich: bool, iterations: int, subset: str, seed: int) -> MCTSAgent:
    return MCTSAgent(
        iterations=iterations,
        seed=seed,
        use_transposition_table=True,
        rich_leaf_eval_enabled=rich,
        rich_leaf_feature_subset=subset,
    )


def run_ab(games: int, iterations: int, subset: str, base_seed: int) -> Dict:
    players = list(Player)
    # Seat rotation: 'A' = baseline, 'B' = rich. Two of each per game; rotate.
    rotations = [
        ["A", "B", "A", "B"],
        ["B", "A", "B", "A"],
        ["A", "B", "B", "A"],
        ["B", "A", "A", "B"],
    ]

    wins = {"baseline": 0, "rich": 0}
    ties = 0
    scores = {"baseline": [], "rich": []}
    iter_per_move = {"baseline": [], "rich": []}
    time_per_iter_ms = {"baseline": [], "rich": []}
    leaf_calls_total = 0

    for g in range(games):
        layout = rotations[g % len(rotations)]
        seed = base_seed + g
        game = BlokusGame()
        # Build one agent per seat.
        agents: Dict[Player, MCTSAgent] = {}
        role: Dict[Player, str] = {}
        for i, seat in enumerate(players):
            is_rich = layout[i] == "B"
            agents[seat] = _make_agent(is_rich, iterations, subset, seed * 17 + i)
            role[seat] = "rich" if is_rich else "baseline"

        turns = 0
        max_turns = 400
        while not game.is_game_over() and turns < max_turns:
            p = game.get_current_player()
            moves = game.get_legal_moves(p)
            if not moves:
                game.board._update_current_player()
                game._check_game_over()
                turns += 1
                continue
            agent = agents[p]
            mv = agent.select_action(game.board, p, moves)
            if mv is None:
                game.board._update_current_player()
                game._check_game_over()
                turns += 1
                continue
            # Telemetry.
            iters = agent.stats.get("iterations_run", 0)
            elapsed = agent.stats.get("time_elapsed", 0.0)
            if iters > 0:
                iter_per_move[role[p]].append(iters)
                time_per_iter_ms[role[p]].append(elapsed / iters * 1000.0)
            if role[p] == "rich":
                leaf_calls_total += agent.stats.get("rich_leaf_eval_calls", 0)
            game.make_move(mv, p)
            turns += 1

        # Tally result.
        final_scores = {seat: game.get_score(seat) for seat in players}
        for seat in players:
            scores[role[seat]].append(final_scores[seat])
        winner = game.get_winner()
        if winner is None:
            ties += 1
        else:
            wins[role[winner]] += 1
        print(
            f"[game {g+1}/{games}] layout={''.join(layout)} "
            f"winner={'tie' if winner is None else role[winner]} "
            f"scores={{base:{np.mean([final_scores[s] for s in players if role[s]=='baseline']):.0f}, "
            f"rich:{np.mean([final_scores[s] for s in players if role[s]=='rich']):.0f}}}",
            flush=True,
        )

    decisive = wins["baseline"] + wins["rich"]
    summary = {
        "games": games,
        "iterations": iterations,
        "subset": subset,
        "wins": wins,
        "ties": ties,
        "rich_win_rate_overall": wins["rich"] / games if games else 0.0,
        "rich_win_rate_decisive": wins["rich"] / decisive if decisive else 0.0,
        "mean_score_baseline": float(np.mean(scores["baseline"])) if scores["baseline"] else 0.0,
        "mean_score_rich": float(np.mean(scores["rich"])) if scores["rich"] else 0.0,
        "mean_iters_per_move_baseline": float(np.mean(iter_per_move["baseline"])) if iter_per_move["baseline"] else 0.0,
        "mean_iters_per_move_rich": float(np.mean(iter_per_move["rich"])) if iter_per_move["rich"] else 0.0,
        "mean_ms_per_iter_baseline": float(np.mean(time_per_iter_ms["baseline"])) if time_per_iter_ms["baseline"] else 0.0,
        "mean_ms_per_iter_rich": float(np.mean(time_per_iter_ms["rich"])) if time_per_iter_ms["rich"] else 0.0,
        "rich_leaf_calls_total": leaf_calls_total,
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=16)
    ap.add_argument("--iterations", type=int, default=250)
    ap.add_argument("--subset", type=str, default="score",
                    choices=["score", "no_opp_mobility", "full"])
    ap.add_argument("--seed", type=int, default=20260626)
    args = ap.parse_args()

    t0 = time.time()
    summary = run_ab(args.games, args.iterations, args.subset, args.seed)
    summary["wall_clock_s"] = round(time.time() - t0, 1)

    print("\n==== A/B SUMMARY (baseline vs rich-leaf, fixed iterations) ====")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    base_ms = summary["mean_ms_per_iter_baseline"]
    rich_ms = summary["mean_ms_per_iter_rich"]
    if base_ms > 0:
        print(f"\n  per-iteration cost ratio rich/baseline: {rich_ms / base_ms:.2f}x")
        print(f"  implied per-leaf overhead: {rich_ms - base_ms:+.3f} ms/iter")


if __name__ == "__main__":
    main()
