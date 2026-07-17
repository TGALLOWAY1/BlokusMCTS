"""Tests for the shape-aware MLP move policy (mcts/move_policy_mlp.py) and its
encoding (mcts/move_encoding.py) — the Phase 6 production wiring gate
(masking, ordering, round-trip, agent integration)."""

from __future__ import annotations

import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.board import Player
from engine.game import BlokusGame
from engine.move_generator import get_shared_generator
from mcts.mcts_agent import MCTSAgent
from mcts.move_encoding import (
    INPUT_DIM,
    MOVE_ENCODING_VERSION,
    EncodingContext,
    encode_move,
    encode_moves,
)
from mcts.move_policy import MovePolicy
from mcts.move_policy_mlp import MLPMovePolicy, is_mlp_policy_dict


def _midgame(plies: int = 12, seed: int = 5):
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
    p = game.get_current_player()
    return game.board, p, game.get_legal_moves(p)


def _tiny_policy(seed: int = 7) -> MLPMovePolicy:
    rng = np.random.default_rng(seed)
    hidden = 8
    return MLPMovePolicy(
        W1=rng.normal(0, 0.05, (INPUT_DIM, hidden)),
        b1=rng.normal(0, 0.01, hidden),
        W2=rng.normal(0, 0.05, hidden),
        b2=0.1,
    )


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


def test_encoding_shape_and_determinism():
    board, player, moves = _midgame()
    assert len(moves) > 3
    gen = get_shared_generator()
    ctx = EncodingContext(board, player)
    a = encode_move(ctx, moves[0], gen)
    b = encode_move(EncodingContext(board, player), moves[0], gen)
    assert a.shape == (INPUT_DIM,)
    assert np.array_equal(a, b)
    # Distinct moves encode distinctly.
    c = encode_move(ctx, moves[1], gen)
    assert not np.array_equal(a, c)


def test_encode_moves_preserves_none_slots():
    board, player, moves = _midgame()
    gen = get_shared_generator()
    encoded = encode_moves(board, player, [moves[0], None, moves[1]], gen)
    assert encoded[1] is None
    assert encoded[0] is not None and encoded[2] is not None


# ---------------------------------------------------------------------------
# Policy math: masking, ordering, round-trip
# ---------------------------------------------------------------------------


def test_pass_moves_masked_and_priors_normalized():
    board, player, moves = _midgame()
    policy = _tiny_policy()
    gen = get_shared_generator()
    with_pass = [moves[0], None, moves[1], moves[2]]
    logits = policy.logits_for_moves(board, player, with_pass, gen)
    assert logits[1] == -np.inf
    priors = policy.priors_from_logits(logits)
    assert abs(priors.sum() - 1.0) < 1e-9
    assert priors[1] == 0.0
    assert (priors[[0, 2, 3]] > 0).all()


def test_all_pass_degenerates_to_uniform():
    policy = _tiny_policy()
    priors = policy.priors_from_logits(np.array([-np.inf, -np.inf]))
    assert np.allclose(priors, [0.5, 0.5])


def test_score_move_matches_batch_logits():
    board, player, moves = _midgame()
    policy = _tiny_policy()
    gen = get_shared_generator()
    batch = policy.logits_for_moves(board, player, moves[:5], gen)
    for i, m in enumerate(moves[:5]):
        assert abs(policy.score_move(board, player, m, gen) - batch[i]) < 1e-9


def test_artifact_round_trip_identical_logits():
    board, player, moves = _midgame()
    policy = _tiny_policy()
    gen = get_shared_generator()
    data = policy.to_dict()
    assert is_mlp_policy_dict(data)
    assert data["encoding_version"] == MOVE_ENCODING_VERSION
    restored = MLPMovePolicy.from_dict(data)
    a = policy.logits_for_moves(board, player, moves[:6], gen)
    b = restored.logits_for_moves(board, player, moves[:6], gen)
    assert np.array_equal(a, b)


def test_from_dict_rejects_wrong_type_and_version():
    policy = _tiny_policy()
    data = policy.to_dict()
    legacy = {"feature_weights": [1, 2, 0.5, 1]}
    assert not is_mlp_policy_dict(legacy)
    try:
        MLPMovePolicy.from_dict(legacy)
        assert False, "expected ValueError"
    except ValueError:
        pass
    bad = dict(data, encoding_version="move_encoding_v999")
    try:
        MLPMovePolicy.from_dict(bad)
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Agent integration
# ---------------------------------------------------------------------------


def test_agent_selects_mlp_policy_from_artifact_dict():
    agent = MCTSAgent(iterations=30, seed=3, use_transposition_table=False,
                      policy_prior_enabled=True,
                      policy_weights=_tiny_policy().to_dict())
    assert isinstance(agent.move_policy, MLPMovePolicy)
    assert agent._policy_prior_active
    board, player, moves = _midgame(seed=2)
    move = agent.select_action(board, player, moves)
    assert move is not None


def test_agent_legacy_dict_still_builds_log_linear_policy():
    legacy = {"feature_weights": [1.0, 2.0, 0.5, 1.0], "piece_bias": {},
              "temperature": 1.0}
    agent = MCTSAgent(iterations=10, seed=3, use_transposition_table=False,
                      policy_prior_enabled=True, policy_weights=legacy)
    assert isinstance(agent.move_policy, MovePolicy)


def test_agent_mlp_prior_deterministic_under_seed():
    board, player, moves = _midgame(seed=9)
    artifact = _tiny_policy().to_dict()
    picks = []
    for _ in range(2):
        agent = MCTSAgent(iterations=40, seed=11, use_transposition_table=False,
                          policy_prior_enabled=True, policy_weights=artifact)
        m = agent.select_action(board, player, moves)
        picks.append((m.piece_id, m.orientation, m.anchor_row, m.anchor_col))
    assert picks[0] == picks[1]
