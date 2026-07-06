"""Tests for candidate-generation approaches + artifact validation."""

from __future__ import annotations

import copy

import pytest

from training import approaches as ap
from training.approaches.base import (
    ApproachContext,
    validate_candidate_artifact,
    write_candidate_artifact,
)

# A minimal but valid champion config (the weak-champion shape).
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


def _ctx(tmp_path, td_path=None):
    state = {"champion_params": copy.deepcopy(CHAMPION_PARAMS), "checkpoints": []}
    return ApproachContext(
        state=state, repo_root=tmp_path, run_id="TESTRUN",
        now_iso="2026-06-26T00:00:00Z", time_budget_s=30,
        td_weights_path=str(td_path) if td_path else None,
    )


def test_baseline_always_created_with_strong_overrides(tmp_path):
    cand = ap.get_approach("baseline").generate(_ctx(tmp_path))
    assert cand.created
    p = cand.agent_config["params"]
    # The weak settings must be corrected (greedy_sample rollouts, tactical
    # cutoff depth, corrupted-pre-maxⁿ features off).
    assert p["rollout_policy"] == "greedy_sample"
    assert p["rollout_cutoff_depth"] == 12
    assert p["rave_enabled"] is False
    assert p["minimax_backup_alpha"] == 0.0
    assert p["heuristic_move_ordering"] is True
    ok, why = validate_candidate_artifact(cand.to_artifact("TESTRUN", "t"))
    assert ok, why


def test_mcts_sweep_changes_exploration_constant(tmp_path):
    cand = ap.get_approach("mcts_sweep").generate(_ctx(tmp_path))
    assert cand.created
    assert cand.agent_config["params"]["exploration_constant"] != 1.414
    assert "grid" in cand.metrics


def _strong_champion_ctx(tmp_path):
    """A champion that already carries the strong-search overrides (the gen140 case)."""
    from training.approaches.baseline_mcts import strong_baseline_params

    champ = strong_baseline_params(copy.deepcopy(CHAMPION_PARAMS))
    state = {"champion_params": champ, "checkpoints": []}
    return ApproachContext(state=state, repo_root=tmp_path, run_id="TESTRUN",
                           now_iso="2026-06-26T00:00:00Z", time_budget_s=30)


def test_baseline_self_retires_when_identical_to_champion(tmp_path):
    # Against a champion that already IS the strong baseline, the candidate would be a
    # byte-for-byte clone -> it must NOT be created (it can never beat itself and would
    # only burn evaluation budget). This is the plateau's no-op-candidate fix.
    cand = ap.get_approach("baseline").generate(_strong_champion_ctx(tmp_path))
    assert not cand.created
    assert "identical to the current champion" in cand.reason
    assert cand.metrics.get("identical_to_champion") is True
    ok, _ = validate_candidate_artifact(cand.to_artifact("TESTRUN", "t"))
    assert ok  # a not-created candidate is still a valid, self-explaining artifact


def test_progressive_widening_enables_pw(tmp_path):
    cand = ap.get_approach("progressive_widening").generate(_ctx(tmp_path))
    assert cand.created
    p = cand.agent_config["params"]
    assert p["progressive_widening_enabled"] is True
    assert p["pw_c"] > 0 and 0.0 < p["pw_alpha"] <= 1.0
    # Built on the corrected strong search, not the weak champion settings.
    assert p["rollout_policy"] == "greedy_sample"
    ok, why = validate_candidate_artifact(cand.to_artifact("TESTRUN", "t"))
    assert ok, why


def test_progressive_widening_in_default_roster(tmp_path):
    # The genuinely-different search candidate must be in the nightly roster (guards
    # against a silent revert to the champion-clone roster that caused the plateau).
    assert "progressive_widening" in ap.DEFAULT_APPROACHES
    assert "mcts_sweep" in ap.DEFAULT_APPROACHES


def test_hybrid_fails_specifically_without_td_artifact(tmp_path):
    # Point TD weights at a non-existent path so the artifact is missing.
    missing = tmp_path / "no_td.json"
    cand = ap.get_approach("hybrid").generate(_ctx(tmp_path, td_path=missing))
    assert not cand.created
    assert "no TD weights artifact" in cand.reason
    # A not-created candidate is still a *valid* artifact (it explains itself).
    ok, _ = validate_candidate_artifact(cand.to_artifact("TESTRUN", "t"))
    assert ok


def test_td_fails_specifically_without_trajectories(tmp_path, monkeypatch):
    # Redirect the trajectory CSV to a non-existent path.
    import training.trajectory_store as ts
    monkeypatch.setattr(ts, "DEFAULT_TRAJECTORY_CSV", tmp_path / "nope.csv", raising=False)
    cand = ap.get_approach("td").generate(_ctx(tmp_path, td_path=tmp_path / "out.json"))
    assert not cand.created
    assert "no trajectory CSV" in cand.reason


def test_artifact_validation_rejects_created_without_config():
    bad = {"schema_version": 1, "approach": "x", "name": "x", "created": True,
           "reason": "r", "agent_config": None}
    ok, why = validate_candidate_artifact(bad)
    assert not ok and "agent_config" in why


def test_artifact_validation_rejects_empty_reason():
    bad = {"schema_version": 1, "approach": "x", "name": "x", "created": False, "reason": ""}
    ok, why = validate_candidate_artifact(bad)
    assert not ok and "reason" in why


def test_artifact_validation_rejects_missing_keys():
    ok, why = validate_candidate_artifact({"approach": "x"})
    assert not ok and "missing keys" in why


def test_write_candidate_artifact_roundtrip(tmp_path):
    cand = ap.get_approach("baseline").generate(_ctx(tmp_path))
    path = write_candidate_artifact(cand, repo_root=tmp_path, run_id="TESTRUN", now_iso="t")
    assert path.exists()
    assert path.name == "baseline_mcts_TESTRUN.json"
    import json
    art = json.loads(path.read_text())
    ok, _ = validate_candidate_artifact(art)
    assert ok


def test_default_roster_resolves():
    objs = ap.build_approaches(ap.DEFAULT_APPROACHES)
    assert len(objs) == len(ap.DEFAULT_APPROACHES)


def test_unknown_approach_raises():
    with pytest.raises(KeyError):
        ap.get_approach("does_not_exist")
