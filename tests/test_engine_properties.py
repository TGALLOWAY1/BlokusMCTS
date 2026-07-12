"""
Engine property/invariant tests over seeded random full-game trajectories
(agent-strength rescue, Phase 2 task 2).

Style follows the repo's existing hand-rolled invariant suites
(tests/test_frontier_basic.py, tests/test_bitboard_basic.py): play real games
with fixed seeds through the PRODUCTION move-generation path and assert the
invariants at every ply. No property-testing framework (see DECISIONS.md).
"""

import random

import numpy as np

from engine.board import Board, Player, _PLAYERS
from engine.move_generator import LegalMoveGenerator

SEEDS = [20260620, 20260621, 20260622]


def _play_full_game(seed, ply_callback=None):
    """Play one full seeded game via the production (frontier) move path.

    Calls ply_callback(board, player, move, positions, pre_state) after every
    successful placement. Returns the terminal board and the ply count.
    """
    rng = random.Random(seed)
    board = Board()
    generator = LegalMoveGenerator()
    plies = 0
    consecutive_passes = 0

    while consecutive_passes < len(_PLAYERS):
        player = board.current_player
        moves = generator.get_legal_moves(board, player)
        if not moves:
            board._update_current_player()
            consecutive_passes += 1
            continue
        consecutive_passes = 0
        move = rng.choice(moves)
        orientations = generator.piece_orientations_cache[move.piece_id]
        positions = move.get_positions(orientations)

        pre_state = _capture_state(board)
        assert board.place_piece(positions, player, move.piece_id), (
            f"seed {seed}: generated move was rejected by place_piece: {move}"
        )
        plies += 1
        if ply_callback is not None:
            ply_callback(board, player, move, positions, pre_state)

    return board, plies


def _capture_state(board):
    return {
        "grid": board.grid.copy(),
        "occupied": int(np.count_nonzero(board.grid)),
        "pieces_used": {p: set(board.player_pieces_used[p]) for p in Player},
        "last_piece": dict(board.player_last_piece),
        "current_player": board.current_player,
        "move_count": board.move_count,
    }


class TestFullGameInvariants:
    """Invariants asserted after EVERY ply of seeded full games."""

    def test_invariants_hold_across_full_games(self):
        for seed in SEEDS:
            checked = {"plies": 0}

            def check(board, player, move, positions, pre):
                checked["plies"] += 1
                grid = board.grid

                # Occupancy monotonicity: previously occupied cells unchanged;
                # exactly len(positions) new cells, all owned by the mover.
                prev = pre["grid"]
                changed = np.argwhere(grid != prev)
                assert len(changed) == len(positions), (
                    f"seed {seed}: expected {len(positions)} new cells, "
                    f"got {len(changed)}"
                )
                for r, c in changed:
                    assert prev[r, c] == 0, "occupied cell was overwritten"
                    assert grid[r, c] == player.value, "new cell owned by wrong player"
                assert int(np.count_nonzero(grid)) == pre["occupied"] + len(positions)

                # Piece-inventory conservation: used set only grows, exactly by
                # the played piece; a used piece never returns.
                for p in Player:
                    before = pre["pieces_used"][p]
                    after = board.player_pieces_used[p]
                    if p is player:
                        assert after == before | {move.piece_id}
                        assert move.piece_id not in before, "piece reused"
                    else:
                        assert after == before, "bystander inventory changed"

                # Last-piece tracking matches the placement just made.
                assert board.player_last_piece[player] == move.piece_id
                for p in Player:
                    if p is not player:
                        assert board.player_last_piece[p] == pre["last_piece"][p]

                # Turn order: strict rotation; move_count increments by one.
                expected_next = _PLAYERS[(_PLAYERS.index(player) + 1) % len(_PLAYERS)]
                assert board.current_player == expected_next
                assert board.move_count == pre["move_count"] + 1

                # Grid/bitboard duality stays consistent; per-player bitmasks
                # are pairwise disjoint and union to occupied_bits.
                board.assert_bitboard_consistent()
                union = 0
                for p in Player:
                    bits = board.player_bits[p]
                    assert bits & union == 0, "two players share a square"
                    union |= bits
                assert union == board.occupied_bits

                # Score recomputed independently from the grid matches
                # get_score (before any completion bonuses apply).
                if len(board.player_pieces_used[player]) < 21:
                    assert board.get_score(player) == int(
                        np.count_nonzero(grid == player.value)
                    )

            board, plies = _play_full_game(seed, check)
            assert checked["plies"] == plies
            assert plies >= 20, f"seed {seed}: game suspiciously short ({plies} plies)"

    def test_terminal_state_has_no_legal_continuation(self):
        generator = LegalMoveGenerator()
        for seed in SEEDS:
            board, _ = _play_full_game(seed)
            for p in Player:
                assert generator.get_legal_moves(board, p) == [], (
                    f"seed {seed}: {p.name} still has moves at terminal state"
                )
                assert not generator.has_legal_moves(board, p)


class TestCloneIndependence:
    """Board.copy() must produce fully independent mutable state."""

    def test_mutating_clone_leaves_original_untouched(self):
        for seed in SEEDS:
            # Build a midgame position, clone it, play a move on the clone.
            rng = random.Random(seed)
            board = Board()
            generator = LegalMoveGenerator()
            for _ in range(12):
                player = board.current_player
                moves = generator.get_legal_moves(board, player)
                if not moves:
                    board._update_current_player()
                    continue
                move = rng.choice(moves)
                orientations = generator.piece_orientations_cache[move.piece_id]
                board.place_piece(move.get_positions(orientations), player, move.piece_id)

            snapshot = _capture_state(board)
            frontiers_before = {p: set(board.player_frontiers[p]) for p in Player}
            bits_before = (board.occupied_bits, {p: board.player_bits[p] for p in Player})

            clone = board.copy()
            player = clone.current_player
            moves = generator.get_legal_moves(clone, player)
            assert moves, f"seed {seed}: no legal move available for clone test"
            move = rng.choice(moves)
            orientations = generator.piece_orientations_cache[move.piece_id]
            assert clone.place_piece(move.get_positions(orientations), player, move.piece_id)

            # Original board unchanged in every mutable field.
            assert np.array_equal(board.grid, snapshot["grid"])
            assert {p: board.player_pieces_used[p] for p in Player} == snapshot["pieces_used"]
            assert dict(board.player_last_piece) == snapshot["last_piece"]
            assert board.current_player == snapshot["current_player"]
            assert board.move_count == snapshot["move_count"]
            assert {p: set(board.player_frontiers[p]) for p in Player} == frontiers_before
            assert (board.occupied_bits, {p: board.player_bits[p] for p in Player}) == bits_before

            # And the clone did change.
            assert clone.move_count == snapshot["move_count"] + 1
            assert clone.player_last_piece[player] == move.piece_id


class TestDeterminism:
    def test_same_seed_reproduces_identical_game(self):
        for seed in SEEDS:
            board_a, plies_a = _play_full_game(seed)
            board_b, plies_b = _play_full_game(seed)
            assert plies_a == plies_b
            assert np.array_equal(board_a.grid, board_b.grid)
            assert dict(board_a.player_last_piece) == dict(board_b.player_last_piece)
            for p in Player:
                assert board_a.get_score(p) == board_b.get_score(p)
