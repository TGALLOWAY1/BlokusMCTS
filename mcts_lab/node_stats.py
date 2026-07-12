"""Node-statistics inspection CLI for the minimal trusted search
(agent-strength rescue, Phase 3).

Runs a single-tree, single-thread MCTS search on a given position and prints
the root children table (visits, visit share, per-player Q from the acting
player's perspective) plus whole-tree statistics (node count, depth
histogram). Positions come from a Board.to_dict() JSON file (board_state_v1)
or from seeded random self-play plies.

Examples:
    python -m mcts_lab.node_stats --random-plies 16 --board-seed 20260620 \
        --iterations 400 --seed 7
    python -m mcts_lab.node_stats --board-json position.json --iterations 1000
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from typing import Optional, Tuple

from engine.board import Board, Player
from engine.move_generator import LegalMoveGenerator, get_shared_generator
from mcts.mcts_agent import MCTSAgent, MCTSNode


def run_search_with_root(agent: MCTSAgent, board: Board, player: Player) -> MCTSNode:
    """Run the agent's iteration-budget search and RETURN the root node.

    Mirrors the single-tree path of MCTSAgent.select_action (which discards
    the root); used by this CLI and by the Phase 3 search-semantics tests to
    assert node internals. Only valid for the minimal configuration
    (num_workers == 1, iteration budget).
    """
    if agent.num_workers != 1:
        raise ValueError("run_search_with_root requires num_workers == 1")
    if not agent.iterations:
        raise ValueError("run_search_with_root requires an iteration budget")
    agent._search_counter += 1
    agent._root_player = player
    agent._root_score_baseline = {p: board.get_score(p) for p in Player}
    agent._effective_exploration_constant = agent.exploration_constant
    agent._effective_rollout_cutoff_depth = agent.rollout_cutoff_depth
    root = MCTSNode(board, player)
    if agent.heuristic_move_ordering or agent.progressive_widening_enabled or agent._policy_prior_active:
        agent._sort_untried_moves(root)
    agent._run_mcts_with_iterations(root)
    return root


def tree_statistics(root: MCTSNode) -> Tuple[int, Counter]:
    """Walk the tree; return (node_count, depth histogram Counter)."""
    depth_histogram: Counter = Counter()
    stack = [(root, 0)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        depth_histogram[depth] += 1
        for child in node.children:
            stack.append((child, depth + 1))
    return count, depth_histogram


def _load_board(args: argparse.Namespace) -> Board:
    if args.board_json:
        with open(args.board_json, "r", encoding="utf-8") as handle:
            return Board.from_dict(json.load(handle))
    # Seeded random self-play plies through the production move path.
    rng = random.Random(args.board_seed)
    board = Board()
    generator = get_shared_generator()
    plies = 0
    attempts = 0
    while plies < args.random_plies and attempts < args.random_plies * 8:
        attempts += 1
        player = board.current_player
        moves = generator.get_legal_moves(board, player)
        if not moves:
            board._update_current_player()
            continue
        move = rng.choice(moves)
        orientations = generator.piece_orientations_cache[move.piece_id]
        board.place_piece(move.get_positions(orientations), player, move.piece_id)
        plies += 1
    return board


def _resolve_player(board: Board, arg: Optional[str]) -> Player:
    if arg is None:
        return board.current_player
    return Player[arg.upper()]


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m mcts_lab.node_stats", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--board-json", help="Board.to_dict() JSON file (board_state_v1)")
    source.add_argument("--random-plies", type=int, default=16,
                        help="build position by playing N seeded random plies (default 16)")
    parser.add_argument("--board-seed", type=int, default=20260620,
                        help="seed for --random-plies position generation")
    parser.add_argument("--player", choices=[p.name for p in Player],
                        help="player to move (default: board's current player)")
    parser.add_argument("--iterations", type=int, default=400)
    parser.add_argument("--seed", type=int, default=7, help="search seed")
    parser.add_argument("--rollout-policy", default="greedy_sample",
                        choices=["greedy_sample", "random", "heuristic", "two_ply"])
    parser.add_argument("--rollout-cutoff-depth", type=int, default=12)
    parser.add_argument("--top", type=int, default=12, help="root children to print")
    args = parser.parse_args(argv)

    board = _load_board(args)
    player = _resolve_player(board, args.player)
    generator: LegalMoveGenerator = get_shared_generator()
    legal_moves = generator.get_legal_moves(board, player)

    print(f"Position: move_count={board.move_count}, to_move={player.name}, "
          f"legal_moves={len(legal_moves)}")
    print("Scores: " + ", ".join(f"{p.name}={board.get_score(p)}" for p in Player))
    print("Pieces remaining: " + ", ".join(
        f"{p.name}={21 - len(board.player_pieces_used[p])}" for p in Player))
    if not legal_moves:
        print(f"{player.name} has no legal moves (pass).")
        return 0

    agent = MCTSAgent(
        iterations=args.iterations,
        seed=args.seed,
        rollout_policy=args.rollout_policy,
        rollout_cutoff_depth=args.rollout_cutoff_depth,
        use_transposition_table=False,
    )
    root = run_search_with_root(agent, board, player)

    node_count, depth_histogram = tree_statistics(root)
    print(f"\nSearch: iterations={args.iterations}, seed={args.seed}, "
          f"rollout_policy={args.rollout_policy}, C={agent.exploration_constant}")
    print(f"Tree: nodes={node_count}, max_depth={max(depth_histogram)}, "
          f"root_visits={root.visits}, expanded_root_children={len(root.children)}")
    print("Depth histogram: " + ", ".join(
        f"d{d}={depth_histogram[d]}" for d in sorted(depth_histogram)))

    children = sorted(root.children, key=lambda c: -c.visits)
    total_visits = sum(c.visits for c in root.children) or 1
    print(f"\nTop {min(args.top, len(children))} of {len(children)} root children "
          f"(Q is {player.name}'s own mean reward):")
    print(f"{'move':<28}{'visits':>8}{'share':>8}{'Q':>12}")
    for child in children[:args.top]:
        move = child.move
        label = (f"piece {move.piece_id:>2} ori {move.orientation:>2} "
                 f"@({move.anchor_row},{move.anchor_col})") if move else "PASS"
        q = child.total_reward / child.visits if child.visits else float("nan")
        print(f"{label:<28}{child.visits:>8}{child.visits / total_visits:>7.1%}{q:>12.2f}")

    best = root.get_best_move()
    if best is not None:
        print(f"\nBest move: piece {best.piece_id} ori {best.orientation} "
              f"@({best.anchor_row},{best.anchor_col})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
