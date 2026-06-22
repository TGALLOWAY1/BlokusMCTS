"""Tests for selfplay_core helpers (no real arena games)."""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import selfplay_core as sc


def _state(checkpoints=None):
    return {
        "champion_params": {
            "type": "mcts",
            "thinking_time_ms": 500,
            "params": {"exploration_constant": 1.414},
        },
        "checkpoints": checkpoints or [],
    }


def _candidate():
    return {
        "type": "mcts",
        "thinking_time_ms": 500,
        "params": {"exploration_constant": 1.414, "state_eval_phase_weights": {"early": {}}},
    }


def test_eval_arenas_always_four_unique_agents_cold_start():
    arenas = sc.build_eval_arenas(_state(), _candidate(), random.Random(1))
    assert len(arenas) == 3
    for arena in arenas:
        names = [a["name"] for a in arena]
        assert len(names) == 4
        assert len(set(names)) == 4
        assert "champion" in names and "candidate" in names


def test_eval_arenas_cover_all_opponent_classes():
    arenas = sc.build_eval_arenas(_state(), _candidate(), random.Random(1))
    all_names = {a["name"] for arena in arenas for a in arena}
    assert {"heuristic", "random", "prev_champion"} <= all_names
    assert any(n.startswith("hist_champ") for n in all_names)


def test_eval_arenas_use_checkpoints_when_available():
    ckpts = [
        {"generation": 1, "id": "ckpt_gen1", "params": _state()["champion_params"]},
        {"generation": 2, "id": "ckpt_gen2", "params": _state()["champion_params"]},
        {"generation": 3, "id": "ckpt_gen3", "params": _state()["champion_params"]},
    ]
    arenas = sc.build_eval_arenas(_state(ckpts), _candidate(), random.Random(1))
    for arena in arenas:
        names = [a["name"] for a in arena]
        assert len(set(names)) == 4


def test_candidate_to_champion_config_emits_flat_weights():
    flat = sc.candidate_to_champion_config(
        _candidate(),
        {"single_weights": {"squares_placed": 0.1}, "phase_weights": {"early": {}}},
    )
    assert flat["state_eval_weights"] == {"squares_placed": 0.1}
    assert "state_eval_phase_weights" in flat
    assert flat["type"] == "mcts"


def test_build_candidate_none_when_refit_none(monkeypatch):
    monkeypatch.setattr(sc, "refit_evaluator_weights", lambda: None)
    cand, refit = sc.build_candidate(_state())
    assert cand is None and refit is None


def test_build_candidate_applies_phase_weights(monkeypatch):
    monkeypatch.setattr(
        sc, "refit_evaluator_weights",
        lambda: {"phase_weights": {"early": {"a": 1.0}}, "single_weights": {"a": 1.0}},
    )
    cand, refit = sc.build_candidate(_state())
    assert cand is not None
    assert cand["name"] == "candidate"
    assert cand["params"]["state_eval_phase_weights"] == {"early": {"a": 1.0}}


def test_thinking_override_only_affects_mcts():
    agents = [
        {"name": "champion", "type": "mcts", "thinking_time_ms": 500, "params": {}},
        {"name": "random", "type": "random", "thinking_time_ms": None, "params": {}},
    ]
    sc._apply_thinking_override(agents, 10)
    assert agents[0]["thinking_time_ms"] == 10
    assert agents[1]["thinking_time_ms"] is None
