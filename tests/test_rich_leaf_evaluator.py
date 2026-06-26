"""Tests for the rich leaf evaluator (mcts/rich_leaf_evaluator.py) and the
leaf-subset feature extraction it relies on (training/rich_features.py)."""

from __future__ import annotations

import json
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.board import Board, Player, Position
from engine.game import BlokusGame
from engine.move_generator import get_shared_generator
from mcts.mcts_agent import MCTSAgent
from mcts.rich_leaf_evaluator import (
    DEFAULT_RICH_LEAF_WEIGHTS_PATH,
    RichLeafEvaluator,
)
from mcts.state_evaluator import (
    BlokusStateEvaluator,
    PHASE_EARLY_THRESHOLD,
    PHASE_LATE_THRESHOLD,
)
import training.rich_features as rf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _play_board(plies: int, seed: int = 0) -> Board:
    """Play *plies* heuristic-ish (deterministic median) moves and return board."""
    random.seed(seed)
    np.random.seed(seed)
    game = BlokusGame()
    for _ in range(plies):
        p = game.get_current_player()
        moves = game.get_legal_moves(p)
        if not moves:
            game.board._update_current_player()
            game._check_game_over()
            continue
        game.make_move(moves[len(moves) // 2], p)
        if game.is_game_over():
            break
    return game.board


def _occupy(board: Board, fraction: float) -> None:
    """Fill empty cells with RED until at least *fraction* of the board is full."""
    target = int(fraction * board.SIZE * board.SIZE)
    for r in range(board.SIZE):
        for c in range(board.SIZE):
            if int(np.count_nonzero(board.grid)) >= target:
                return
            if board.grid[r, c] == 0:
                board.grid[r, c] = Player.RED.value


# ---------------------------------------------------------------------------
# Leaf-subset feature extraction
# ---------------------------------------------------------------------------


def test_leaf_subsets_are_defined_and_nested():
    subs = rf.LEAF_FEATURE_SUBSETS
    assert set(subs) == {"full", "no_opp_mobility", "score"}
    # Nesting: score ⊂ no_opp_mobility ⊂ full.
    assert subs["score"] <= subs["no_opp_mobility"] <= subs["full"]
    assert subs["full"] == frozenset(rf.RICH_FEATURE_NAMES)
    # The cheap "score" subset must exclude every enumeration/BFS feature.
    assert not (subs["score"] & rf.OPPONENT_MOBILITY_FEATURES)
    assert not (subs["score"] & rf.FOCAL_MOBILITY_FEATURES)
    assert not (subs["score"] & rf.TERRITORY_FEATURES)
    # ...but must keep the highest-signal score/rank features.
    for name in ("score_margin_vs_leader", "rank_so_far", "score_margin_vs_next_player"):
        assert name in subs["score"]


def test_leaf_features_match_full_for_included_and_zero_for_excluded():
    board = _play_board(14, seed=1)
    for player in Player:
        full = rf.extract_rich_features(board, player)
        for subset in ("full", "no_opp_mobility", "score"):
            leaf = rf.extract_leaf_features(board, player, subset=subset)
            # Always the complete ordered name set.
            assert set(leaf) == set(rf.RICH_FEATURE_NAMES)
            include = rf.LEAF_FEATURE_SUBSETS[subset]
            for name in rf.RICH_FEATURE_NAMES:
                if name in include:
                    assert leaf[name] == full[name], (subset, name)
                else:
                    assert leaf[name] == 0.0, (subset, name)


def test_extract_leaf_features_rejects_unknown_subset():
    board = Board()
    try:
        rf.extract_leaf_features(board, Player.RED, subset="nope")
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Evaluator math
# ---------------------------------------------------------------------------


def test_evaluate_equals_manual_dot_product():
    """The evaluator output must equal Σ w_i·f_i + bias for the selected phase."""
    board = _play_board(12, seed=2)
    ev = RichLeafEvaluator(DEFAULT_RICH_LEAF_WEIGHTS_PATH, feature_subset="full")
    assert ev.available

    with open(DEFAULT_RICH_LEAF_WEIGHTS_PATH, "r", encoding="utf-8") as fh:
        artifact = json.load(fh)
    rich = artifact["rich_phase_weights"]

    for player in Player:
        phase = BlokusStateEvaluator.get_phase(board)
        feats = rf.extract_leaf_features(board, player, subset="full")
        weights_map = rich[phase]["weights"]
        bias = rich[phase]["bias"]
        expected = bias + sum(
            float(weights_map[name]) * feats[name] for name in rf.RICH_FEATURE_NAMES
        )
        got = ev.evaluate(board, player)
        assert abs(got - expected) < 1e-9, (player, phase, got, expected)


def test_score_subset_drops_excluded_weight_terms():
    """The score subset value must omit excluded features' contributions."""
    board = _play_board(16, seed=5)
    ev_full = RichLeafEvaluator(DEFAULT_RICH_LEAF_WEIGHTS_PATH, feature_subset="full")
    ev_score = RichLeafEvaluator(DEFAULT_RICH_LEAF_WEIGHTS_PATH, feature_subset="score")
    assert ev_full.available and ev_score.available

    with open(DEFAULT_RICH_LEAF_WEIGHTS_PATH, "r", encoding="utf-8") as fh:
        rich = json.load(fh)["rich_phase_weights"]

    player = Player.RED
    phase = BlokusStateEvaluator.get_phase(board)
    feats = rf.extract_rich_features(board, player)
    include = rf.LEAF_FEATURE_SUBSETS["score"]
    weights_map = rich[phase]["weights"]
    bias = rich[phase]["bias"]
    expected = bias + sum(
        float(weights_map[name]) * feats[name]
        for name in rf.RICH_FEATURE_NAMES
        if name in include
    )
    assert abs(ev_score.evaluate(board, player) - expected) < 1e-9


# ---------------------------------------------------------------------------
# Phase selection
# ---------------------------------------------------------------------------


def test_phase_selection_uses_occupancy_thresholds():
    ev = RichLeafEvaluator(DEFAULT_RICH_LEAF_WEIGHTS_PATH, feature_subset="full")
    assert ev.available

    # Early board (empty).
    early = Board()
    assert BlokusStateEvaluator.get_phase(early) == "early"

    # Mid board (between early and late thresholds).
    mid = Board()
    _occupy(mid, (PHASE_EARLY_THRESHOLD + PHASE_LATE_THRESHOLD) / 2.0)
    assert BlokusStateEvaluator.get_phase(mid) == "mid"

    # Late board.
    late = Board()
    _occupy(late, PHASE_LATE_THRESHOLD + 0.1)
    assert BlokusStateEvaluator.get_phase(late) == "late"

    # The evaluator must apply the phase-matching weight vector.
    for board, phase in ((early, "early"), (mid, "mid"), (late, "late")):
        feats = rf.extract_leaf_features(board, Player.RED, subset="full")
        x = np.array([feats[n] for n in rf.RICH_FEATURE_NAMES], dtype=float)
        expected = float(np.dot(ev._phase_weights[phase], x) + ev._phase_bias[phase])
        assert abs(ev.evaluate(board, Player.RED) - expected) < 1e-9


# ---------------------------------------------------------------------------
# Graceful fallback
# ---------------------------------------------------------------------------


def test_missing_artifact_falls_back_to_eight_feature_evaluator():
    ev = RichLeafEvaluator("definitely/missing/file.json", feature_subset="score")
    assert ev.available is False
    assert ev.load_error is not None

    board = _play_board(10, seed=3)
    fallback = BlokusStateEvaluator()
    for player in Player:
        # Fallback returns exactly the 8-feature evaluator score in [0, 1].
        got = ev.evaluate(board, player)
        assert got == fallback.evaluate(board, player)
        assert 0.0 <= got <= 1.0


def test_empty_rich_weights_marks_unavailable(tmp_path):
    artifact = {"rich_phase_weights": {}}
    path = tmp_path / "empty.json"
    path.write_text(json.dumps(artifact))
    ev = RichLeafEvaluator(str(path), feature_subset="score")
    assert ev.available is False


def test_invalid_feature_subset_rejected():
    try:
        RichLeafEvaluator(DEFAULT_RICH_LEAF_WEIGHTS_PATH, feature_subset="bogus")
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Leaf-only invocation in the agent
# ---------------------------------------------------------------------------


def _midgame_board_and_moves(seed: int = 7):
    board = _play_board(10, seed=seed)
    gen = get_shared_generator()
    moves = gen.get_legal_moves(board, Player.RED)
    return board, moves


def test_agent_calls_rich_leaf_exactly_once_per_simulation():
    """Rich leaf eval is LEAF-ONLY: at most one call per MCTS iteration."""
    board, moves = _midgame_board_and_moves()
    assert len(moves) > 1
    iters = 150
    agent = MCTSAgent(
        iterations=iters,
        seed=11,
        use_transposition_table=False,
        rich_leaf_eval_enabled=True,
        rich_leaf_feature_subset="score",
    )
    assert agent.rich_leaf_evaluator.available
    move = agent.select_action(board, Player.RED, moves)
    assert move is not None
    # One rich-leaf evaluation per iteration — never per rollout step.
    assert agent.stats["rich_leaf_eval_calls"] == iters
    assert agent.stats["iterations_run"] == iters
    assert agent.stats["evaluator_errors"] == 0


def test_rich_leaf_eval_does_not_touch_rollout_step_path():
    """With rich leaf eval on, the per-rollout cutoff/two-ply counters stay zero."""
    board, moves = _midgame_board_and_moves(seed=4)
    agent = MCTSAgent(
        iterations=80,
        seed=2,
        use_transposition_table=False,
        rich_leaf_eval_enabled=True,
        rich_leaf_feature_subset="score",
    )
    agent.select_action(board, Player.RED, moves)
    # The rollout-step static-eval and two-ply paths must be untouched.
    assert agent.stats["cutoff_evals"] == 0
    assert agent.stats["two_ply_evals"] == 0


def test_agent_default_is_backward_compatible():
    """Default agent (rich leaf off) must not construct the evaluator."""
    agent = MCTSAgent(iterations=20, seed=1, use_transposition_table=False)
    assert agent.rich_leaf_eval_enabled is False
    assert agent.rich_leaf_evaluator is None
    board, moves = _midgame_board_and_moves(seed=1)
    agent.select_action(board, Player.RED, moves)
    assert agent.stats["rich_leaf_eval_calls"] == 0
    # Rollouts ran instead.
    assert len(agent.stats["rollout_rewards"]) > 0
