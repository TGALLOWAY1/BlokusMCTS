"""move_encoding_v1 — shape-aware per-move input encoding (Phase 6, D-017).

Encodes one candidate move as a 518-vector:

  * 9x9 board patch centered on the placement centroid, 6 channels:
    [0] own occupied  [1] opponent occupied  [2] off-board
    [3] new-piece cells  [4] own frontier  [5] opponent frontier   (486)
  * piece one-hot (21)
  * the 10 move_features_v2 scalars + game phase                   (11)

The patch channels are built once per (board, player) as padded full-board
planes (`EncodingContext`), so encoding a move is numpy slicing plus the
scalar features — cheap enough for per-node prior computation in search.

Validated by EXP-011 (training/experiments/move_scorer_mlp.py trains over
exactly this encoding; tests pin single-move equivalence between the batch
and reference paths).
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np

from engine.board import Board, Player
from engine.move_generator import LegalMoveGenerator, Move
from mcts.move_heuristic import _get_piece_positions

MOVE_ENCODING_VERSION = "move_encoding_v1"
PATCH = 9  # odd; centered on the placement centroid
HALF = PATCH // 2
N_CHANNELS = 6
N_PIECES = 21
N_SCALARS = 11  # 10 move_features_v2 + phase
INPUT_DIM = N_CHANNELS * PATCH * PATCH + N_PIECES + N_SCALARS

# The six move-varying extensions beyond MOVE_FEATURE_NAMES (D-017). Order is
# part of move_encoding_v1 — append-only, never reorder.
MOVE_FEATURES_V2_EXTENSIONS = (
    "own_frontier_consumed",   # my corner-anchor cells this move occupies
    "opp_frontier_occupied",   # opponents' corner-anchor cells this move occupies
    "opp_contact",             # orthogonal adjacency to opponent cells (walling)
    "own_diag_links",          # diagonal links to my own pieces beyond the required 1
    "phase_x_size",            # game-phase x piece-size interaction
    "edge_fraction",           # fraction of cells on the outer border
)


def compute_move_features_v2(board: Board, player: Player, move: Move,
                             generator: LegalMoveGenerator) -> np.ndarray:
    """The four MOVE_FEATURE_NAMES followed by the six D-017 extensions."""
    from mcts.move_heuristic import compute_move_features

    base = compute_move_features(board, player, move, generator)
    positions = _get_piece_positions(move, generator)
    cells = {(p.row, p.col) for p in positions}
    size = board.SIZE

    own_frontier = board.player_frontiers[player]
    own_frontier_consumed = sum(1 for c in cells if c in own_frontier)
    opp_frontier_occupied = 0
    for opp in Player:
        if opp is player:
            continue
        frontier = board.player_frontiers[opp]
        opp_frontier_occupied += sum(1 for c in cells if c in frontier)

    opp_contact = 0
    own_diag = 0
    for r, c in cells:
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < size and 0 <= nc < size:
                v = board.grid[nr, nc]
                if v != 0 and v != player.value:
                    opp_contact += 1
        for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < size and 0 <= nc < size and (nr, nc) not in cells:
                if board.grid[nr, nc] == player.value:
                    own_diag += 1

    phase = min(board.move_count / 60.0, 1.0)
    edge_cells = sum(1 for r, c in cells
                     if r == 0 or c == 0 or r == size - 1 or c == size - 1)

    ext = (
        min(own_frontier_consumed / 4.0, 1.0),
        min(opp_frontier_occupied / 4.0, 1.0),
        min(opp_contact / 8.0, 1.0),
        min(max(own_diag - 1, 0) / 4.0, 1.0),
        phase * base[0],
        edge_cells / len(cells),
    )
    return np.array(tuple(base) + ext, dtype=float)


class EncodingContext:
    """Per-(board, player) padded channel planes for fast per-move encoding."""

    def __init__(self, board: Board, player: Player) -> None:
        self.board = board
        self.player = player
        size = board.SIZE
        pad = HALF
        self.pad = pad
        n = size + 2 * pad

        # Channels 0/1/2/4/5 as padded planes; channel 3 (new piece) is per-move.
        self.own = np.zeros((n, n), dtype=np.float32)
        self.opp = np.zeros((n, n), dtype=np.float32)
        self.off = np.ones((n, n), dtype=np.float32)
        self.own_frontier = np.zeros((n, n), dtype=np.float32)
        self.opp_frontier = np.zeros((n, n), dtype=np.float32)

        inner = slice(pad, pad + size)
        self.own[inner, inner] = (board.grid == player.value)
        self.opp[inner, inner] = (board.grid != 0) & (board.grid != player.value)
        self.off[inner, inner] = 0.0
        for r, c in board.player_frontiers[player]:
            self.own_frontier[r + pad, c + pad] = 1.0
        for other in Player:
            if other is player:
                continue
            for r, c in board.player_frontiers[other]:
                self.opp_frontier[r + pad, c + pad] = 1.0

        self.phase = min(board.move_count / 60.0, 1.0)


def encode_move(context: EncodingContext, move: Move,
                move_generator: LegalMoveGenerator) -> np.ndarray:
    """Encode one candidate move against a prepared context."""
    positions = _get_piece_positions(move, move_generator)
    rows = [p.row for p in positions]
    cols = [p.col for p in positions]
    cr = int(round(sum(rows) / len(rows)))
    cc = int(round(sum(cols) / len(cols)))
    pad = context.pad
    r0, c0 = cr - HALF + pad, cc - HALF + pad
    rs, cs = slice(r0, r0 + PATCH), slice(c0, c0 + PATCH)

    patch = np.zeros((N_CHANNELS, PATCH, PATCH), dtype=np.float32)
    patch[0] = context.own[rs, cs]
    patch[1] = context.opp[rs, cs]
    patch[2] = context.off[rs, cs]
    patch[4] = context.own_frontier[rs, cs]
    patch[5] = context.opp_frontier[rs, cs]
    for p in positions:
        pr, pc = p.row + pad - r0, p.col + pad - c0
        if 0 <= pr < PATCH and 0 <= pc < PATCH:
            patch[3, pr, pc] = 1.0

    piece_onehot = np.zeros(N_PIECES, dtype=np.float32)
    if 1 <= move.piece_id <= N_PIECES:
        piece_onehot[move.piece_id - 1] = 1.0

    scalars = compute_move_features_v2(
        context.board, context.player, move, move_generator)
    return np.concatenate([
        patch.ravel(), piece_onehot,
        np.asarray(list(scalars) + [context.phase], dtype=np.float32),
    ]).astype(np.float32)


def encode_moves(board: Board, player: Player, moves: Sequence[Optional[Move]],
                 move_generator: LegalMoveGenerator) -> List[Optional[np.ndarray]]:
    """Encode a list of moves (None entries — pass — stay None)."""
    context = EncodingContext(board, player)
    return [None if m is None else encode_move(context, m, move_generator)
            for m in moves]
