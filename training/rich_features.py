"""Rich Blokus-specific state features for temporal-difference learning.

This module extends the eight Layer-6 state-evaluator features
(:data:`mcts.state_evaluator.FEATURE_NAMES`) with a much wider set of
Blokus-strategy features used to train the TD value model
(:mod:`training.td_learning`).

Design goals
------------
* **Versioned & stable.** :data:`FEATURE_SET_VERSION` names this exact feature
  layout. :data:`RICH_FEATURE_NAMES` is an ordered, append-only list — once a
  feature ships it must keep its name and position so persisted training
  artifacts stay readable.
* **Superset of the agent's evaluator features.** Every name in
  ``mcts.state_evaluator.FEATURE_NAMES`` is present here with identical
  semantics, so a TD-learned weight vector can be *projected* back onto the
  eight features the live agent's :class:`BlokusStateEvaluator` understands
  (see :func:`training.td_learning.project_to_agent_weights`).
* **Reuse, not reinvent.** Frontier, mobility, and advanced-metric helpers from
  the engine are reused rather than re-implemented.
* **Cache the expensive bits.** Legal-move enumeration is the dominant cost; a
  per-extraction :class:`FeatureCache` memoises legal moves per player so a
  single snapshot (which touches every player's mobility) enumerates each
  player's moves at most once.

All returned values are floats, finite (never NaN/inf), and normalised to keep
the linear TD value in a sane range.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.board import Board, Player
from engine.move_generator import LegalMoveGenerator
from engine.mobility_metrics import compute_player_mobility_metrics
from mcts.state_evaluator import (
    BlokusStateEvaluator,
    FEATURE_NAMES as SE_FEATURE_NAMES,
    PHASE_EARLY_THRESHOLD,
    PHASE_LATE_THRESHOLD,
)

# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

FEATURE_SET_VERSION = "rich_blokus_v1"

_PLAYERS: List[Player] = list(Player)

# ---------------------------------------------------------------------------
# Piece metadata (ids 1..21). Reuse the same source the engine uses.
# ---------------------------------------------------------------------------

_PIECE_SIZES: Optional[Dict[int, int]] = None
_TOTAL_PIECE_AREA: int = 0
# "Key" / high-value pentominoes that are awkward to place if left late.
_AWKWARD_PIECE_IDS = (17, 19, 20)


def _piece_sizes() -> Dict[int, int]:
    global _PIECE_SIZES, _TOTAL_PIECE_AREA
    if _PIECE_SIZES is None:
        from engine.pieces import PieceGenerator

        sizes: Dict[int, int] = {}
        for piece in PieceGenerator.get_all_pieces():
            sizes[piece.id] = piece.size
        _PIECE_SIZES = sizes
        _TOTAL_PIECE_AREA = int(sum(sizes.values()))  # 89 squares
    return _PIECE_SIZES


def total_piece_area() -> int:
    _piece_sizes()
    return _TOTAL_PIECE_AREA


# ---------------------------------------------------------------------------
# Normalisation constants
# ---------------------------------------------------------------------------

_MAX_FRONTIER = 40.0
_MAX_REACHABLE = 60.0
_MAX_LEGAL_MOVES = 400.0  # rough upper bound on a single player's legal placements
_BOARD_CELLS = float(Board.SIZE * Board.SIZE)  # 400
_MAX_PIECE_DIM = float(Board.SIZE)  # for distance normalisation
_MAX_REGION = _BOARD_CELLS

# ---------------------------------------------------------------------------
# Ordered, append-only feature name list
# ---------------------------------------------------------------------------

# Extra rich features (everything beyond the eight SE features). Keep this list
# append-only; new features go at the end.
_RICH_EXTRA_NAMES: List[str] = [
    # Mobility / move-space
    "legal_move_count",
    "legal_move_count_small_pieces",
    "legal_move_count_medium_pieces",
    "legal_move_count_large_pieces",
    "playable_piece_count",
    "total_playable_piece_area",
    "avg_legal_move_area",
    "max_legal_move_area",
    # Corner / frontier
    "corner_count",
    "corner_quality_score",
    "frontier_size",
    "frontier_density",
    "frontier_to_opponent_distance",
    "new_corner_generation_potential",
    # Piece inventory
    "remaining_piece_count",
    "remaining_singletons",
    "remaining_dominoes",
    "remaining_trominoes",
    "remaining_tetrominoes",
    "remaining_pentominoes",
    "awkward_piece_penalty",
    "piece_diversity_score",
    # Territory and blocking
    "largest_reachable_region",
    "trapped_region_count",
    "trapped_region_area",
    "opponent_mobility_avg",
    "opponent_mobility_max",
    "opponent_mobility_min",
    "opponent_corner_pressure",
    "leader_mobility_pressure",
    # Score / race
    "score_margin_vs_leader",
    "score_margin_vs_next_player",
    "rank_so_far",
    "completion_ratio",
    "remaining_area",
    # Center / board-position
    "edge_pressure",
    "quadrant_balance",
]

# Full ordered list: the eight SE features first (so the projection slice is the
# leading block), then the rich extras. Names are unique.
RICH_FEATURE_NAMES: List[str] = list(SE_FEATURE_NAMES) + [
    n for n in _RICH_EXTRA_NAMES if n not in SE_FEATURE_NAMES
]


# ---------------------------------------------------------------------------
# Per-extraction cache (legal moves are the expensive part)
# ---------------------------------------------------------------------------


@dataclass
class FeatureCache:
    """Memoises per-player legal moves within a single snapshot extraction.

    A snapshot computes mobility for every player (the focal player plus each
    opponent for the opponent-mobility features), so without caching a 4-player
    snapshot would enumerate legal moves up to 16 times. The cache keys on
    ``player.value`` and assumes the board is not mutated while it is alive —
    callers create a fresh cache per board state.
    """

    move_generator: LegalMoveGenerator = field(default_factory=LegalMoveGenerator)
    _legal_moves: Dict[int, List] = field(default_factory=dict)

    def legal_moves(self, board: Board, player: Player) -> List:
        key = int(player.value)
        cached = self._legal_moves.get(key)
        if cached is None:
            cached = self.move_generator.get_legal_moves(board, player)
            self._legal_moves[key] = cached
        return cached


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_phase(board: Board) -> str:
    """Game phase from board occupancy (matches the evaluator's thresholds)."""
    occ = float(np.count_nonzero(board.grid)) / _BOARD_CELLS
    if occ < PHASE_EARLY_THRESHOLD:
        return "early"
    if occ < PHASE_LATE_THRESHOLD:
        return "mid"
    return "late"


def board_occupancy(board: Board) -> float:
    return float(np.count_nonzero(board.grid)) / _BOARD_CELLS


def _remaining_piece_ids(pieces_used) -> List[int]:
    used = {int(p) for p in pieces_used}
    return [pid for pid in range(1, 22) if pid not in used]


def _player_scores(board: Board) -> Dict[int, int]:
    """Squares-covered score proxy per player (cheap; no bonuses)."""
    grid = board.grid
    return {p.value: int(np.count_nonzero(grid == p.value)) for p in _PLAYERS}


def _mobility_count(cache: FeatureCache, board: Board, player: Player) -> int:
    return len(cache.legal_moves(board, player))


def _largest_reachable_region_and_trapped(
    board: Board, frontier
) -> Tuple[int, int, int]:
    """BFS over empty cells from the player's frontier.

    Returns ``(largest_reachable_region, trapped_region_count, trapped_region_area)``.

    * *reachable* = empty cells connected (orthogonally) to a frontier cell.
    * *trapped* = connected components of empty cells that touch **no** frontier
      cell (regions this player can never expand into).
    """
    grid = board.grid
    size = board.SIZE
    frontier_set = set(frontier)

    # Flood from frontier cells to find reachable empties.
    reachable = set()
    queue = deque(frontier_set)
    while queue:
        r, c = queue.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < size and 0 <= nc < size:
                if grid[nr, nc] == 0 and (nr, nc) not in reachable and (nr, nc) not in frontier_set:
                    reachable.add((nr, nc))
                    queue.append((nr, nc))
    largest_reachable = len(reachable) + len(frontier_set)

    # Connected components of all empties; those disjoint from the frontier are
    # "trapped" for this player.
    visited = np.zeros((size, size), dtype=bool)
    trapped_count = 0
    trapped_area = 0
    for r in range(size):
        for c in range(size):
            if grid[r, c] != 0 or visited[r, c]:
                continue
            # BFS this component.
            comp = []
            touches_frontier = False
            q = deque([(r, c)])
            visited[r, c] = True
            while q:
                cr, cc = q.popleft()
                comp.append((cr, cc))
                if (cr, cc) in frontier_set:
                    touches_frontier = True
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < size and 0 <= nc < size and not visited[nr, nc] and grid[nr, nc] == 0:
                        visited[nr, nc] = True
                        q.append((nr, nc))
            if not touches_frontier:
                trapped_count += 1
                trapped_area += len(comp)
    return largest_reachable, trapped_count, trapped_area


def _frontier_to_opponent_distance(board: Board, player: Player, frontier) -> float:
    """Min Manhattan distance from any frontier cell to any opponent cell."""
    if not frontier:
        return 1.0  # normalised max distance (no frontier ⇒ no pressure)
    grid = board.grid
    opp_coords = np.argwhere((grid != 0) & (grid != player.value))
    if opp_coords.size == 0:
        return 1.0
    best = None
    for (fr, fc) in frontier:
        d = np.min(np.abs(opp_coords[:, 0] - fr) + np.abs(opp_coords[:, 1] - fc))
        if best is None or d < best:
            best = int(d)
            if best == 0:
                break
    return min(float(best) / (2.0 * board.SIZE), 1.0)


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------


def extract_rich_features(
    board: Board,
    player: Player,
    *,
    cache: Optional[FeatureCache] = None,
    evaluator: Optional[BlokusStateEvaluator] = None,
) -> Dict[str, float]:
    """Return the full ``rich_blokus_v1`` feature dict for *player*.

    The result always contains exactly :data:`RICH_FEATURE_NAMES`, every value a
    finite float. ``cache`` (optional) shares legal-move enumeration across the
    players evaluated for one board state.
    """
    cache = cache or FeatureCache()
    evaluator = evaluator or _shared_evaluator()
    sizes = _piece_sizes()
    total_area = total_piece_area()

    # --- Eight SE features (identical semantics to the live agent) -----------
    feats: Dict[str, float] = dict(evaluator.extract_features(board, player))

    pieces_used = board.player_pieces_used[player]
    remaining_ids = _remaining_piece_ids(pieces_used)
    frontier = board.get_frontier(player)

    # --- Mobility / move-space ----------------------------------------------
    legal_moves = cache.legal_moves(board, player)
    n_moves = len(legal_moves)
    small = medium = large = 0
    areas: List[int] = []
    playable_ids = set()
    for mv in legal_moves:
        pid = int(getattr(mv, "piece_id"))
        sz = sizes.get(pid, 0)
        areas.append(sz)
        playable_ids.add(pid)
        if sz <= 2:
            small += 1
        elif sz == 3:
            medium += 1
        else:
            large += 1
    playable_area = sum(sizes.get(pid, 0) for pid in playable_ids)
    avg_area = (sum(areas) / len(areas)) if areas else 0.0
    max_area = float(max(areas)) if areas else 0.0

    feats["legal_move_count"] = min(n_moves / _MAX_LEGAL_MOVES, 1.0)
    feats["legal_move_count_small_pieces"] = min(small / _MAX_LEGAL_MOVES, 1.0)
    feats["legal_move_count_medium_pieces"] = min(medium / _MAX_LEGAL_MOVES, 1.0)
    feats["legal_move_count_large_pieces"] = min(large / _MAX_LEGAL_MOVES, 1.0)
    feats["playable_piece_count"] = len(playable_ids) / 21.0
    feats["total_playable_piece_area"] = playable_area / max(total_area, 1)
    feats["avg_legal_move_area"] = avg_area / 5.0
    feats["max_legal_move_area"] = max_area / 5.0

    # --- Corner / frontier ---------------------------------------------------
    feats["frontier_size"] = min(len(frontier) / _MAX_FRONTIER, 1.0)
    feats["corner_count"] = min(len(frontier) / _MAX_FRONTIER, 1.0)
    # corner quality: legal placements available per anchor (anchors that lead to
    # many moves are higher quality).
    feats["corner_quality_score"] = (
        min((n_moves / max(len(frontier), 1)) / 20.0, 1.0) if frontier else 0.0
    )
    largest_reach, trapped_count, trapped_area = _largest_reachable_region_and_trapped(
        board, frontier
    )
    reachable_norm = min((largest_reach) / _MAX_REACHABLE, 1.0)
    feats["frontier_density"] = (
        min(len(frontier) / max(largest_reach, 1), 1.0) if largest_reach else 0.0
    )
    feats["frontier_to_opponent_distance"] = _frontier_to_opponent_distance(
        board, player, frontier
    )
    # new-corner potential: distinct anchor cells reachable by current legal moves,
    # proxied by playable-piece diversity × frontier breadth.
    feats["new_corner_generation_potential"] = min(
        (len(playable_ids) * len(frontier)) / 200.0, 1.0
    )

    # --- Piece inventory -----------------------------------------------------
    rem_by_size = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for pid in remaining_ids:
        sz = sizes.get(pid, 0)
        if sz in rem_by_size:
            rem_by_size[sz] += 1
    feats["remaining_piece_count"] = len(remaining_ids) / 21.0
    feats["remaining_singletons"] = rem_by_size[1] / 1.0  # at most 1 monomino
    feats["remaining_dominoes"] = rem_by_size[2] / 1.0
    feats["remaining_trominoes"] = rem_by_size[3] / 2.0
    feats["remaining_tetrominoes"] = rem_by_size[4] / 5.0
    feats["remaining_pentominoes"] = rem_by_size[5] / 12.0
    awkward = sum(5 if pid in _AWKWARD_PIECE_IDS else (sizes.get(pid, 0))
                  for pid in remaining_ids)
    feats["awkward_piece_penalty"] = min(awkward / max(total_area, 1), 1.0)
    distinct_sizes = sum(1 for v in rem_by_size.values() if v > 0)
    feats["piece_diversity_score"] = distinct_sizes / 5.0

    # --- Territory and blocking ---------------------------------------------
    feats["largest_reachable_region"] = reachable_norm
    feats["trapped_region_count"] = min(trapped_count / 10.0, 1.0)
    feats["trapped_region_area"] = min(trapped_area / _BOARD_CELLS, 1.0)

    opp_mobilities: List[int] = []
    for opp in _PLAYERS:
        if opp == player:
            continue
        opp_mobilities.append(_mobility_count(cache, board, opp))
    if opp_mobilities:
        feats["opponent_mobility_avg"] = min(
            (sum(opp_mobilities) / len(opp_mobilities)) / _MAX_LEGAL_MOVES, 1.0
        )
        feats["opponent_mobility_max"] = min(max(opp_mobilities) / _MAX_LEGAL_MOVES, 1.0)
        feats["opponent_mobility_min"] = min(min(opp_mobilities) / _MAX_LEGAL_MOVES, 1.0)
    else:
        feats["opponent_mobility_avg"] = 0.0
        feats["opponent_mobility_max"] = 0.0
        feats["opponent_mobility_min"] = 0.0

    # opponent corner pressure: total opponent frontier near this player's pieces.
    opp_frontier_total = 0
    for opp in _PLAYERS:
        if opp == player:
            continue
        opp_frontier_total += len(board.get_frontier(opp))
    feats["opponent_corner_pressure"] = min(opp_frontier_total / (3.0 * _MAX_FRONTIER), 1.0)

    # leader mobility pressure: mobility of the current score leader (excluding self).
    scores = _player_scores(board)
    leader = max((p for p in _PLAYERS if p != player), key=lambda p: scores[p.value])
    feats["leader_mobility_pressure"] = min(
        _mobility_count(cache, board, leader) / _MAX_LEGAL_MOVES, 1.0
    )

    # --- Score / race --------------------------------------------------------
    my_score = scores[player.value]
    others = sorted((scores[p.value] for p in _PLAYERS if p != player), reverse=True)
    leader_score = others[0] if others else 0
    # "Next player" = the opponent adjacent to me in the score ranking (the player
    # just above me, or the runner-up if I am leading) — distinct from the leader.
    higher = [s for s in others if s > my_score]
    if higher:
        next_score = min(higher)  # closest opponent ranked above me
    elif len(others) >= 2:
        next_score = others[1]  # I'm leading ⇒ gap to the second-best opponent
    elif others:
        next_score = others[0]
    else:
        next_score = 0
    feats["score_margin_vs_leader"] = float(np.tanh((my_score - leader_score) / 20.0))
    feats["score_margin_vs_next_player"] = float(np.tanh((my_score - next_score) / 20.0))
    rank = 1 + sum(1 for s in others if s > my_score)
    feats["rank_so_far"] = (4 - rank) / 3.0  # 1st⇒1.0, 4th⇒0.0
    feats["completion_ratio"] = (21 - len(remaining_ids)) / 21.0
    rem_area = sum(sizes.get(pid, 0) for pid in remaining_ids)
    feats["remaining_area"] = rem_area / max(total_area, 1)

    # --- Center / board-position --------------------------------------------
    player_mask = board.grid == player.value
    coords = np.argwhere(player_mask)
    if coords.size:
        # edge pressure: fraction of own cells on the outer ring.
        on_edge = np.sum(
            (coords[:, 0] == 0)
            | (coords[:, 0] == board.SIZE - 1)
            | (coords[:, 1] == 0)
            | (coords[:, 1] == board.SIZE - 1)
        )
        feats["edge_pressure"] = float(on_edge) / float(len(coords))
        # quadrant balance: 1 - normalised spread of cell counts across quadrants.
        mid = board.SIZE / 2.0
        q = [0, 0, 0, 0]
        for (r, c) in coords:
            idx = (0 if r < mid else 2) + (0 if c < mid else 1)
            q[idx] += 1
        q_arr = np.array(q, dtype=float)
        mean = q_arr.mean()
        spread = (q_arr.std() / mean) if mean > 0 else 0.0
        feats["quadrant_balance"] = float(max(0.0, 1.0 - spread))
    else:
        feats["edge_pressure"] = 0.0
        feats["quadrant_balance"] = 0.0

    # --- Sanitise: ensure exactly the declared names, all finite -------------
    out: Dict[str, float] = {}
    for name in RICH_FEATURE_NAMES:
        v = feats.get(name, 0.0)
        fv = float(v)
        if not np.isfinite(fv):
            fv = 0.0
        out[name] = fv
    return out


# ---------------------------------------------------------------------------
# Shared evaluator (default weights; only used for raw feature extraction)
# ---------------------------------------------------------------------------

_SHARED_EVALUATOR: Optional[BlokusStateEvaluator] = None


def _shared_evaluator() -> BlokusStateEvaluator:
    global _SHARED_EVALUATOR
    if _SHARED_EVALUATOR is None:
        _SHARED_EVALUATOR = BlokusStateEvaluator()
    return _SHARED_EVALUATOR


def feature_vector(features: Dict[str, float]) -> np.ndarray:
    """Project a feature dict onto the canonical ordered vector."""
    return np.array([float(features.get(n, 0.0)) for n in RICH_FEATURE_NAMES], dtype=float)
