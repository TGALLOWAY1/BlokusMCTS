"""Tests for atomic durable persistence + path resolution."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import TrainingPaths, state_store


def test_paths_under_tmp(tmp_path):
    paths = TrainingPaths.under(tmp_path)
    assert paths.latest_json == tmp_path / "training" / "state" / "latest.json"
    assert paths.diagnosis_md == tmp_path / "training" / "reports" / "latest_diagnosis.md"
    paths.ensure_dirs()
    assert paths.checkpoints_dir.is_dir()
    assert paths.selfplay_runs_dir.is_dir()


def test_atomic_write_leaves_no_tmp(tmp_path):
    paths = TrainingPaths.under(tmp_path)
    state_store.atomic_write_json(paths.latest_json, {"a": 1})
    assert paths.latest_json.exists()
    assert not paths.latest_json.with_suffix(paths.latest_json.suffix + ".tmp").exists()
    assert state_store.read_json(paths.latest_json) == {"a": 1}


def test_load_latest_cold_start_returns_full_default(tmp_path):
    paths = TrainingPaths.under(tmp_path)
    state = state_store.load_latest(paths)
    # All keys the pipeline relies on must exist on a cold start.
    for key in (
        "generation", "total_games", "trueskill_ratings", "checkpoints",
        "champion_params", "human_target_elo", "last_error",
    ):
        assert key in state
    assert state["generation"] == 0


def test_save_then_load_roundtrip_with_backfill(tmp_path):
    paths = TrainingPaths.under(tmp_path)
    state = state_store.default_latest_state()
    state["generation"] = 5
    # Simulate an older file missing a newer key.
    del state["estimate_confidence"]
    state_store.save_latest(paths, state)
    loaded = state_store.load_latest(paths)
    assert loaded["generation"] == 5
    assert "estimate_confidence" in loaded  # backfilled from defaults
    assert "updated_at" in loaded


def test_append_jsonl_accumulates(tmp_path):
    paths = TrainingPaths.under(tmp_path)
    state_store.append_jsonl(paths.history_jsonl, {"generation": 1})
    state_store.append_jsonl(paths.history_jsonl, {"generation": 2})
    rows = state_store.read_jsonl(paths.history_jsonl)
    assert [r["generation"] for r in rows] == [1, 2]


def test_checkpoint_write_and_list(tmp_path):
    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    state_store.write_checkpoint(paths, 3, {"generation": 3, "id": "ckpt_gen3", "params": {}})
    state_store.write_checkpoint(paths, 1, {"generation": 1, "id": "ckpt_gen1", "params": {}})
    ckpts = state_store.list_checkpoints(paths)
    assert [c["generation"] for c in ckpts] == [1, 3]  # sorted oldest-first
