"""
Full-game differential harness: reference engine paths vs optimized engine
paths (agent-strength rescue, Phase 2 task 2).

Reference implementation (per docs/agent-strength-rebuild/MASTER_PLAN.md
Phase 2): naive full-board-scan move generation + grid-based legality.
Optimized implementation: frontier-based move generation + bitboard legality
(the production path).

Seeded full games are driven by the OPTIMIZED path; at every ply the harness
cross-checks the two implementations on legal-move sets and placement
legality. Scale with BLOKUS_DIFF_GAMES (default 3 games ≈ 900+ position
checks; 20 games ≈ 6000+ checks were verified once when this suite landed).
"""

import os
import random

import numpy as np

from engine.board import Board, Player, _PLAYERS
from engine.move_generator import LegalMoveGenerator

NUM_GAMES = int(os.environ.get("BLOKUS_DIFF_GAMES", "3"))
BASE_SEED = 20260620
# Full four-player move-set comparison is naive-generation-heavy; do it on a
# stride so default CI runs stay fast while every ply still checks the mover.
ALL_PLAYER_STRIDE = 10


def _move_positions(generator, move):
    return move.get_positions(generator.piece_orientations_cache[move.piece_id])


def _move_key(generator, move):
    """Coordinate-canonical key so orientation indices don't matter."""
    positions = _move_positions(generator, move)
    return (move.piece_id, tuple(sorted((p.row, p.col) for p in positions)))


def _move_sets_equal(generator, board, player):
    naive = {_move_key(generator, m)
             for m in generator._get_legal_moves_naive(board, player)}
    frontier = {_move_key(generator, m)
                for m in generator._get_legal_moves_frontier(board, player)}
    return naive, frontier


def _legality_agrees(generator, board, player, move):
    positions = _move_positions(generator, move)
    grid_ok = board.can_place_piece(positions, player)
    coords = [(p.row, p.col) for p in positions]
    bitboard_ok = generator.is_placement_legal_bitboard_coords(
        board, player, coords, is_first_move=board.player_first_move[player]
    )
    return grid_ok == bitboard_ok, grid_ok, bitboard_ok


class TestFullGameDifferential:
    def test_reference_and_optimized_agree_across_full_games(self):
        generator = LegalMoveGenerator()
        positions_checked = 0
        legality_checked = 0

        for game_index in range(NUM_GAMES):
            seed = BASE_SEED + game_index
            rng = random.Random(seed)
            board = Board()
            ply = 0
            consecutive_passes = 0

            while consecutive_passes < len(_PLAYERS):
                player = board.current_player

                # Move-set equivalence for the player about to act (every ply)
                # and for ALL players on a stride.
                players_to_check = (
                    list(Player) if ply % ALL_PLAYER_STRIDE == 0 else [player]
                )
                for p in players_to_check:
                    naive, frontier = _move_sets_equal(generator, board, p)
                    assert naive == frontier, (
                        f"seed {seed} ply {ply}: naive vs frontier move sets "
                        f"differ for {p.name}: only-naive="
                        f"{sorted(naive - frontier)[:3]} only-frontier="
                        f"{sorted(frontier - naive)[:3]}"
                    )
                    positions_checked += 1

                # Pass-detection equivalence for the mover.
                frontier_moves = generator.get_legal_moves(board, player)
                assert bool(frontier_moves) == generator.has_legal_moves(board, player)

                if not frontier_moves:
                    board._update_current_player()
                    consecutive_passes += 1
                    continue
                consecutive_passes = 0

                # Legality equivalence: a sample of legal moves plus perturbed
                # (mostly illegal) variants must agree between grid and
                # bitboard checkers.
                for move in rng.sample(frontier_moves, min(3, len(frontier_moves))):
                    agrees, grid_ok, bb_ok = _legality_agrees(
                        generator, board, player, move
                    )
                    assert agrees and grid_ok and bb_ok, (
                        f"seed {seed} ply {ply}: legality mismatch on generated "
                        f"move {move} (grid={grid_ok}, bitboard={bb_ok})"
                    )
                    legality_checked += 1

                    shifted = type(move)(
                        move.piece_id,
                        move.orientation,
                        min(move.anchor_row + 1, Board.SIZE - 1),
                        move.anchor_col,
                    )
                    try:
                        agrees, grid_ok, bb_ok = _legality_agrees(
                            generator, board, player, shifted
                        )
                    except (IndexError, KeyError):
                        continue  # perturbation fell off the board entirely
                    assert agrees, (
                        f"seed {seed} ply {ply}: legality mismatch on perturbed "
                        f"move {shifted} (grid={grid_ok}, bitboard={bb_ok})"
                    )
                    legality_checked += 1

                move = rng.choice(frontier_moves)
                orientations = generator.piece_orientations_cache[move.piece_id]
                assert board.place_piece(
                    move.get_positions(orientations), player, move.piece_id
                )
                ply += 1

            # Terminal cross-checks: both paths agree nobody can move, and the
            # final scores recomputed from the grid match get_score.
            for p in Player:
                assert generator._get_legal_moves_naive(board, p) == []
                assert not generator.has_legal_moves(board, p)
                base = int(np.count_nonzero(board.grid == p.value))
                expected = base
                if len(board.player_pieces_used[p]) == 21:
                    expected += 15
                    if board.player_last_piece[p] == 1:  # monomino
                        expected += 5
                assert board.get_score(p) == expected

            assert ply >= 20, f"seed {seed}: degenerate game ({ply} plies)"

        # The harness must actually have exercised a meaningful sample.
        assert positions_checked >= NUM_GAMES * 80, (
            f"only {positions_checked} move-set comparisons ran"
        )
        assert legality_checked >= NUM_GAMES * 100, (
            f"only {legality_checked} legality comparisons ran"
        )
