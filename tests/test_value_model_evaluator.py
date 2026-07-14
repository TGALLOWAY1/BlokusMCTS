"""Model-artifact leaf evaluator plumbing (D-015 gate 3)."""

import joblib
import numpy as np
import pytest

from analytics.tournament.arena_runner import AgentConfig, build_agent
from engine.board import Board, Player
from mcts.mcts_agent import MCTSAgent
from mcts.value_model_evaluator import ValueModelLeafEvaluator


@pytest.fixture(scope="module")
def artifact_path(tmp_path_factory):
    from sklearn.linear_model import Ridge

    from training.rich_features import RICH_FEATURE_NAMES

    rng = np.random.RandomState(0)
    x = rng.rand(64, len(RICH_FEATURE_NAMES))
    y = x[:, 0] * 0.5 + 0.3  # deterministic synthetic target
    model = Ridge(alpha=1.0).fit(x, y)
    path = tmp_path_factory.mktemp("vm") / "value_test.joblib"
    joblib.dump({
        "model": model,
        "feature_names": list(RICH_FEATURE_NAMES),
        "target": "final_score / 100",
    }, path)
    return str(path)


def test_artifact_round_trip_and_finite_values(artifact_path):
    evaluator = ValueModelLeafEvaluator(artifact_path)
    board = Board()
    values = {p: evaluator.evaluate(board, p) for p in Player}
    assert all(np.isfinite(v) for v in values.values())
    # Cached path returns identical values on repeat.
    assert evaluator.evaluate(board, Player.RED) == values[Player.RED]


def test_unknown_feature_names_rejected(artifact_path, tmp_path):
    data = joblib.load(artifact_path)
    data["feature_names"] = ["not_a_feature"]
    bad = tmp_path / "bad.joblib"
    joblib.dump(data, bad)
    with pytest.raises(ValueError, match="unknown feature"):
        ValueModelLeafEvaluator(str(bad))


def test_mcts_agent_constructs_and_uses_model_leaf(artifact_path):
    agent = MCTSAgent(iterations=8, seed=3, value_model_path=artifact_path,
                      use_transposition_table=False)
    assert agent.rich_leaf_eval_enabled
    assert isinstance(agent.rich_leaf_evaluator, ValueModelLeafEvaluator)
    board = Board()
    gen_moves = agent.move_generator.get_legal_moves(board, Player.RED)
    move = agent.select_action(board, Player.RED, gen_moves)
    legal_keys = {(m.piece_id, m.orientation, m.anchor_row, m.anchor_col)
                  for m in gen_moves}
    assert (move.piece_id, move.orientation, move.anchor_row, move.anchor_col) in legal_keys


def test_build_agent_plumbs_value_model_path(artifact_path):
    config = AgentConfig(
        name="vm_test", type="mcts", thinking_time_ms=None,
        params={"iterations": 4, "value_model_path": artifact_path,
                "num_workers": 1},
    )
    adapter = build_agent(config, seed=5)
    inner = adapter.agent
    assert isinstance(inner.rich_leaf_evaluator, ValueModelLeafEvaluator)
    assert inner.value_model_path == artifact_path
