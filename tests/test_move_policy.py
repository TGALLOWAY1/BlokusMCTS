"""Tests for the learned move policy (model, training, MCTS integration, wiring)."""

from __future__ import annotations

import numpy as np
import pytest

from engine.board import Board, Player
from engine.move_generator import get_shared_generator
from mcts.mcts_agent import MCTSAgent
from mcts.move_heuristic import (
    MOVE_FEATURE_NAMES,
    compute_move_features,
    compute_move_heuristic,
)
from mcts.move_policy import (
    NUM_MOVE_FEATURES,
    MovePolicy,
    PolicySample,
    PolicyTrainConfig,
    default_move_policy,
    train_move_policy,
)


def _opening_moves(n=40):
    b = Board()
    gen = get_shared_generator()
    moves = gen.get_legal_moves(b, Player.RED)
    return b, gen, moves[:n]


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


def test_feature_vector_shape():
    b, gen, moves = _opening_moves(5)
    feats = compute_move_features(b, Player.RED, moves[0], gen)
    assert len(feats) == NUM_MOVE_FEATURES == len(MOVE_FEATURE_NAMES)


def test_default_policy_matches_heuristic_ranking():
    """The untrained default policy's logit equals the fixed heuristic score."""
    b, gen, moves = _opening_moves(40)
    pol = default_move_policy()
    for m in moves:
        h = compute_move_heuristic(b, Player.RED, m, gen)
        p = pol.score_move(b, Player.RED, m, gen)
        assert p == pytest.approx(h, abs=1e-9)


def test_priors_are_a_distribution():
    b, gen, moves = _opening_moves()
    pol = default_move_policy()
    pr = pol.priors(b, Player.RED, moves, gen)
    assert pr.shape[0] == len(moves)
    assert float(pr.sum()) == pytest.approx(1.0, abs=1e-9)
    assert (pr >= 0).all()


def test_priors_handle_pass_moves():
    """A ``None`` (pass) move gets ~zero prior and never NaNs the softmax."""
    b, gen, moves = _opening_moves(10)
    pol = default_move_policy()
    mixed = list(moves) + [None]
    pr = pol.priors(b, Player.RED, mixed, gen)
    assert float(pr.sum()) == pytest.approx(1.0, abs=1e-9)
    assert pr[-1] == pytest.approx(0.0, abs=1e-12)


def test_serialization_round_trip():
    pol = MovePolicy(feature_weights=np.array([0.3, 1.1, -0.2, 0.7]),
                     piece_bias={5: 0.4, 12: -0.9}, temperature=0.8)
    back = MovePolicy.from_dict(pol.to_dict())
    assert np.allclose(back.feature_weights, pol.feature_weights)
    assert back.piece_bias == pol.piece_bias
    assert back.temperature == pytest.approx(0.8)


def test_bad_feature_weight_length_rejected():
    with pytest.raises(ValueError):
        MovePolicy(feature_weights=np.array([1.0, 2.0]))


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def _synthetic_samples(n_decisions=300, moves_per=6, seed=0):
    """Targets favour the 'corners' feature (index 1): the visit mass concentrates
    on the highest-corner move, so training should raise that weight."""
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(n_decisions):
        feats = rng.random((moves_per, NUM_MOVE_FEATURES))
        pids = rng.integers(1, 22, size=moves_per)
        # Visit target strongly proportional to corners feature.
        logits = 6.0 * feats[:, 1]
        t = np.exp(logits - logits.max())
        t = t / t.sum()
        samples.append(PolicySample(features=feats, piece_ids=pids, target=t))
    return samples


def test_training_reduces_loss_and_learns_signal():
    samples = _synthetic_samples()
    cfg = PolicyTrainConfig(epochs=60, learning_rate=0.5)
    result = train_move_policy(samples, cfg)
    assert result.n_samples == len(samples)
    # Loss decreased over training.
    assert result.loss_history[-1] < result.loss_history[0]
    # The corners weight (index 1) is the dominant learned direction.
    w = result.policy.feature_weights
    assert int(np.argmax(w)) == 1
    # Model recovers the argmax move most of the time.
    assert result.top1_agreement > 0.75


def test_training_handles_empty_and_degenerate():
    # No samples -> returns default-seeded policy, zero loss, no crash.
    result = train_move_policy([], PolicyTrainConfig(epochs=3))
    assert result.n_samples == 0
    assert result.policy.feature_weights.shape[0] == NUM_MOVE_FEATURES


# ---------------------------------------------------------------------------
# MCTS integration
# ---------------------------------------------------------------------------


def test_agent_runs_with_policy_prior_enabled():
    b, gen, moves = _opening_moves(0)
    lm = gen.get_legal_moves(b, Player.RED)
    keys = {(m.piece_id, m.orientation, m.anchor_row, m.anchor_col) for m in lm}
    agent = MCTSAgent(iterations=80, seed=1, rollout_policy="greedy_sample",
                      rollout_cutoff_depth=6, heuristic_move_ordering=True,
                      policy_prior_enabled=True)
    assert agent._policy_prior_active is True
    mv = agent.select_action(b, Player.RED, lm)
    assert (mv.piece_id, mv.orientation, mv.anchor_row, mv.anchor_col) in keys


def test_policy_prior_disabled_by_default():
    agent = MCTSAgent(iterations=10, seed=1)
    assert agent._policy_prior_active is False
    assert agent.move_policy is None


def test_agent_deterministic_with_policy():
    def run():
        b = Board()
        gen = get_shared_generator()
        lm = gen.get_legal_moves(b, Player.RED)
        agent = MCTSAgent(iterations=80, seed=7, rollout_policy="greedy_sample",
                          rollout_cutoff_depth=6, heuristic_move_ordering=True,
                          policy_prior_enabled=True)
        return agent.select_action(b, Player.RED, lm)

    a, b = run(), run()
    assert (a.piece_id, a.orientation, a.anchor_row, a.anchor_col) == \
           (b.piece_id, b.orientation, b.anchor_row, b.anchor_col)


def test_capture_hook_records_visit_distribution():
    b = Board()
    gen = get_shared_generator()
    lm = gen.get_legal_moves(b, Player.RED)
    agent = MCTSAgent(iterations=100, seed=3, rollout_policy="greedy_sample",
                      rollout_cutoff_depth=6, heuristic_move_ordering=True)
    agent._capture_root_moves = True
    agent.select_action(b, Player.RED, lm)
    assert agent._last_root_move_visits is not None
    total = sum(v for _, v in agent._last_root_move_visits)
    assert total == 100  # every iteration expands/visits a root child


def test_arena_build_agent_round_trips_policy_params():
    from analytics.tournament.arena_runner import AgentConfig, build_agent

    pol = default_move_policy().to_dict()
    cfg = AgentConfig.from_dict({
        "name": "policy", "type": "mcts", "thinking_time_ms": None,
        "params": {
            "iterations": 40, "rollout_policy": "greedy_sample",
            "rollout_cutoff_depth": 6, "heuristic_move_ordering": True,
            "policy_prior_enabled": True, "policy_prior_c": 2.0,
            "policy_weights": pol,
        },
    })
    adapter = build_agent(cfg, seed=1)
    agent = adapter.agent
    assert isinstance(agent, MCTSAgent)
    assert agent._policy_prior_active is True
    assert agent.policy_prior_c == pytest.approx(2.0)
    assert np.allclose(agent.move_policy.feature_weights,
                       default_move_policy().feature_weights)
