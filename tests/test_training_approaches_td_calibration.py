"""Integration: the `td` approach trains with the calibrated score normalisation.

The label-score calibration lives in ``training.td_learning`` as the default
``TDConfig.score_center`` / ``score_spread`` ``(82, 19)``. The nightly framework's
``td`` approach builds ``TDConfig(min_rows_per_phase=...)`` with all other fields at
their defaults, so the calibration must ride through automatically — the artifact it
writes (and therefore the candidate it serves) is trained on the calibrated targets.

These tests pin that contract so a future change to the approach (or to the defaults)
cannot silently revert the calibration.
"""

from __future__ import annotations

import copy
import json

import pytest

from training import approaches as ap
from training import td_learning as td
from training import trajectory_store
from training.approaches.base import ApproachContext, validate_candidate_artifact

CHAMPION_PARAMS = {
    "type": "mcts",
    "thinking_time_ms": 500,
    "params": {
        "rollout_policy": "random",
        "rollout_cutoff_depth": 5,
        "iterations_per_ms": 0.5,
        "exploration_constant": 1.414,
        "deterministic_time_budget": True,
    },
}


def _ctx(tmp_path, td_path):
    state = {"champion_params": copy.deepcopy(CHAMPION_PARAMS), "checkpoints": []}
    return ApproachContext(
        state=state, repo_root=tmp_path, run_id="CALIBRATION",
        now_iso="2026-06-26T00:00:00Z", time_budget_s=120,
        td_weights_path=str(td_path),
    )


def test_td_config_default_is_calibrated():
    # The defaults the approach relies on are the calibrated values, not the old (40, 20).
    cfg = td.TDConfig()
    assert (cfg.score_center, cfg.score_spread) == (
        td.DEFAULT_SCORE_CENTER, td.DEFAULT_SCORE_SPREAD) == (82.0, 19.0)


def test_td_approach_trains_with_calibrated_normalisation(tmp_path):
    """End-to-end: run the real `td` approach on the committed corpus."""
    if not trajectory_store.DEFAULT_TRAJECTORY_CSV.exists():
        pytest.skip("no committed trajectory corpus to train on")

    out = tmp_path / "td_weights.json"
    cand = ap.get_approach("td").generate(_ctx(tmp_path, out))

    # A created candidate that explains itself and passes artifact validation.
    assert cand.created, cand.reason
    assert cand.metrics.get("learning_method") == "temporal_difference"
    ok, why = validate_candidate_artifact(cand.to_artifact("CALIBRATION", "t"))
    assert ok, why

    # The written artifact records the calibrated centre/spread — proof the approach
    # trained through the calibrated terminal value (not the old hardcoded 40/20).
    artifact = json.loads(out.read_text())
    assert artifact["config"]["score_center"] == 82.0
    assert artifact["config"]["score_spread"] == 19.0
    # And the served agent is an MCTS clone carrying learned phase weights.
    assert cand.agent_config["type"] == "mcts"
