"""Tactical regression positions: fixed states with a known best move.

These pin search *quality*, not just legality — if a change to the engine,
evaluator, or MCTS makes the agent blunder in positions with an objectively
best move, these fail fast. Positions are constructed directly on the board
(opponent cells painted in, frontiers rebuilt) so they are deterministic.
"""

import unittest

import numpy as np

from engine.board import Board, Player, Position
from engine.move_generator import get_shared_generator
from mcts.mcts_agent import MCTSAgent

I5 = 12   # 1x5 line pentomino
MONO = 1  # monomino


def _endgame_pocket_board():
    """RED to move with only {monomino, I5} left and a single empty 5-cell
    column pocket at (1,1)..(5,1) reachable from RED's lone cell at (0,0).

    Playing the I5 fills the pocket (+5 squares, ends RED's game at maximum).
    Playing the monomino first (the only other legal move) leaves a 4-cell
    hole the I5 can never fit -> strictly worse. The best move is the I5.
    """
    b = Board()
    # RED seed cell at the start corner, placed as the domino piece so the
    # monomino stays available... the domino is 2 cells, so place (0,0)+(0,1)?
    # No: keep RED to exactly one cell by painting the grid directly.
    b.grid[0, 0] = Player.RED.value
    b.player_first_move[Player.RED] = False
    # Every piece used except monomino and I5.
    b.player_pieces_used[Player.RED] = {p for p in range(1, 22)} - {MONO, I5}

    # Fill the whole board BLUE except RED's cell and the pocket column.
    pocket = [(r, 1) for r in range(1, 6)]
    for r in range(b.SIZE):
        for c in range(b.SIZE):
            if (r, c) == (0, 0) or (r, c) in pocket:
                continue
            b.grid[r, c] = Player.BLUE.value
    # BLUE has all pieces "used" so its score bookkeeping stays consistent and
    # the other players simply have no legal cells anywhere.
    for p in (Player.BLUE, Player.YELLOW, Player.GREEN):
        b.player_first_move[p] = False

    # The grid was painted directly, so rebuild the derived state the fast
    # move generator relies on: frontiers and bitboard occupancy masks.
    from engine.bitboard import coords_to_mask

    for p in Player:
        b.player_frontiers[p] = b._compute_full_frontier(p)
        cells = [(int(r), int(c)) for r, c in zip(*np.where(b.grid == p.value))]
        b.player_bits[p] = coords_to_mask(cells)
    b.occupied_bits = coords_to_mask([(int(r), int(c)) for r, c in zip(*np.where(b.grid != 0))])
    return b


class TestEndgamePocket(unittest.TestCase):
    def setUp(self):
        self.board = _endgame_pocket_board()
        self.gen = get_shared_generator()

    def test_position_has_exactly_the_two_expected_moves(self):
        moves = self.gen.get_legal_moves(self.board, Player.RED)
        piece_ids = sorted({m.piece_id for m in moves})
        self.assertEqual(piece_ids, [MONO, I5],
                         f"expected mono+I5 only, got {[(m.piece_id, m.anchor_row, m.anchor_col) for m in moves]}")

    def test_opponents_have_no_moves(self):
        for p in (Player.BLUE, Player.YELLOW, Player.GREEN):
            self.assertFalse(self.gen.get_legal_moves(self.board, p))

    def test_mcts_plays_the_pentomino(self):
        moves = self.gen.get_legal_moves(self.board, Player.RED)
        agent = MCTSAgent(iterations=40, seed=9, rollout_policy="greedy_sample",
                          use_transposition_table=False)
        chosen = agent.select_action(self.board, Player.RED, moves)
        self.assertEqual(chosen.piece_id, I5,
                         "MCTS must fill the 5-cell pocket with the pentomino, "
                         "not waste the monomino inside it")


if __name__ == "__main__":
    unittest.main()
