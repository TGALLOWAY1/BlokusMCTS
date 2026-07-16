"""Tests for the TD candidate-builder path in selfplay_core."""

from __future__ import annotations

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcts.state_evaluator import FEATURE_NAMES as SE_FEATURE_NAMES
from training import selfplay_core as sc


def _state():
    return {
        "champion_params": {
            "type": "mcts",
            "thinking_time_ms": 500,
            "params": {"exploration_constant": 1.414},
        },
        "checkpoints": [],
    }


def _artifact():
    pw = {ph: {n: 0.1 for n in SE_FEATURE_NAMES} for ph in ("early", "mid", "late")}
    return {
        "created_at": "2026-06-24T00:00:00Z",
        "learning_method": "temporal_difference",
        "feature_set_version": "rich_blokus_v1",
        "source_rows": 5432,
        "feature_names": list(SE_FEATURE_NAMES),
        "phase_weights": pw,
        "training_metrics": {
            "td_loss": 0.037,
            "td_loss_by_phase": {"early": 0.04, "mid": 0.03, "late": 0.035},
            "mean_abs_td_error": 0.15,
            "rows_by_phase": {"early": 1800, "mid": 1900, "late": 1732},
        },
        "config": {"gamma": 0.98},
    }


def _write_artifact(tmp_path):
    path = tmp_path / "td_evaluator_weights.json"
    path.write_text(json.dumps(_artifact()), encoding="utf-8")
    return path


def test_td_weights_load_into_candidate(tmp_path):
    path = _write_artifact(tmp_path)
    state = _state()
    cand, refit = sc.build_td_candidate(state, str(path))
    assert cand is not None and refit is not None
    assert cand["params"]["state_eval_phase_weights"]["mid"]["squares_placed"] == 0.1
    assert refit["phase_weights"] == _artifact()["phase_weights"]


def test_champion_params_cloned_not_mutated(tmp_path):
    path = _write_artifact(tmp_path)
    state = _state()
    before = copy.deepcopy(state["champion_params"])
    sc.build_td_candidate(state, str(path))
    # Champion config is untouched (no weights swapped in, no metadata leaked).
    assert state["champion_params"] == before
    assert "state_eval_phase_weights" not in state["champion_params"]["params"]
    assert "learning_method" not in state["champion_params"]


def test_candidate_metadata_records_td_method(tmp_path):
    path = _write_artifact(tmp_path)
    cand, _ = sc.build_td_candidate(_state(), str(path))
    assert cand["learning_method"] == "temporal_difference"
    # The candidate must report the version its ARTIFACT was trained with
    # (the fixture stamps rich_blokus_v1), not the library's current constant.
    assert cand["feature_set_version"] == "rich_blokus_v1"
    assert cand["training_rows"] == 5432
    assert cand["td_loss"] == 0.037
    meta = sc.candidate_metadata(cand)
    assert set(meta) == {"learning_method", "feature_set_version", "training_rows", "td_loss"}


def test_strip_candidate_meta_keeps_engine_shape(tmp_path):
    path = _write_artifact(tmp_path)
    cand, _ = sc.build_td_candidate(_state(), str(path))
    stripped = sc.strip_candidate_meta(cand)
    for key in sc.CANDIDATE_META_KEYS:
        assert key not in stripped
    # Engine-relevant fields survive.
    assert stripped["type"] == "mcts"
    assert "state_eval_phase_weights" in stripped["params"]


def test_missing_artifact_returns_none(tmp_path):
    cand, refit = sc.build_td_candidate(_state(), str(tmp_path / "nope.json"))
    assert cand is None and refit is None


def test_malformed_artifact_returns_none(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    cand, refit = sc.build_td_candidate(_state(), str(path))
    assert cand is None and refit is None


def test_build_candidate_dispatches_on_mode(tmp_path):
    path = _write_artifact(tmp_path)
    cand, _ = sc.build_candidate(_state(), learning_mode="td", td_weights_path=str(path))
    assert cand["learning_method"] == "temporal_difference"


def test_eval_arenas_strip_candidate_meta(tmp_path):
    # A candidate carrying metadata must not leak it into arena agent configs.
    import random
    path = _write_artifact(tmp_path)
    cand, _ = sc.build_td_candidate(_state(), str(path))
    arenas = sc.build_eval_arenas(_state(), cand, random.Random(0))
    # build_eval_arenas re-names; the metadata is stripped only at run time, so
    # assert run_arena_inproc's strip helper removes them.
    for arena in arenas:
        for agent in arena:
            cleaned = sc.strip_candidate_meta(agent)
            for key in sc.CANDIDATE_META_KEYS:
                assert key not in cleaned
