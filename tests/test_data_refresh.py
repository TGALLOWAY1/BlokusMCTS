"""Tests for the P1 nightly data-refresh step (training.data_refresh) and the
P4 snapshot recency cap (scripts.champion_loop.accumulate_snapshots)."""

from __future__ import annotations

import os
import sys
import time

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import champion_loop
from training import TrainingPaths
from training import data_refresh as dr
from training import teacher_roster as tr
from training.td_selfplay import collect_trajectories

# A cheap 4-seat roster (random movers) shaped like teacher_roster()'s output:
# two capture seats named champion/champion2 plus two opponents. Random agents
# keep each game to well under a second so the tests exercise the plumbing
# (deadlines, provenance, corpus writes), not MCTS strength.
_FAST_ROSTER = [
    {"name": "champion", "type": "random", "thinking_time_ms": 5},
    {"name": "heuristic", "type": "random"},
    {"name": "champion2", "type": "random", "thinking_time_ms": 5},
    {"name": "random", "type": "random"},
]


def _fast_roster(profile=None):
    import copy

    return copy.deepcopy(_FAST_ROSTER)


# ---------------------------------------------------------------------------
# collect_trajectories deadline behaviour
# ---------------------------------------------------------------------------


def test_collect_trajectories_respects_deadline_with_min_games(tmp_path):
    out = tmp_path / "td.csv"
    # Deadline already passed: min_games=1 still guarantees one game of rows.
    rows = collect_trajectories(
        _fast_roster(),
        run_id="deadline_test",
        num_games=50,
        seed=99,
        agent_version="test@fast:5",
        output_path=out,
        capture_agents=("champion", "champion2"),
        deadline=time.monotonic() - 1.0,
        min_games=1,
    )
    assert rows > 0
    df = pd.read_csv(out)
    assert set(df["game_id"].unique()) == {"deadline_test_g0000"}


def test_collect_trajectories_strict_deadline_plays_nothing(tmp_path):
    out = tmp_path / "td.csv"
    rows = collect_trajectories(
        _fast_roster(),
        run_id="strict",
        num_games=50,
        seed=99,
        output_path=out,
        deadline=time.monotonic() - 1.0,
        min_games=0,
    )
    assert rows == 0
    assert not out.exists()


# ---------------------------------------------------------------------------
# refresh_training_data end-to-end (cheap agents, tmp corpora)
# ---------------------------------------------------------------------------


def test_refresh_training_data_writes_fresh_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "teacher_roster", _fast_roster)
    monkeypatch.setattr(tr, "champion_version", lambda: "genTEST")
    # Keep the test fast: one TD game (rich-feature capture makes even random-
    # agent games cost tens of seconds) and a tiny snapshot arena. The budget is
    # generous so game caps, not the deadline, bound the work here.
    monkeypatch.setattr(dr, "_MAX_TD_GAMES", 1)
    monkeypatch.setattr(dr, "_MAX_SNAPSHOT_GAMES", 2)

    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    state = {}

    summary = dr.refresh_training_data(
        state, paths,
        run_id="RTEST",
        budget_s=600.0,
        seed=7,
        teacher_profile="teacher",
        verbose=False,
    )

    # Acceptance (plan P1): rows stamped with the current champion + profile +
    # budget, and both corpora actually grew — under the SUPPLIED root, not the
    # repo-global corpora (td_output_path/snapshot target default to
    # <paths.root>/data/…, so an isolated TrainingPaths stays isolated).
    assert summary["agent_version"] == "genTEST@teacher:5"
    assert summary["td_rows"] > 0
    df = pd.read_csv(tmp_path / "data" / "td_trajectories.csv")
    assert set(df["agent_version"].unique()) == {"genTEST@teacher:5"}
    # Champion seats only: no rows labelled with the weak seats' outcomes.
    assert set(df["agent_name"].unique()) <= {"champion", "champion2"}

    assert summary["snapshot_new_rows"] > 0
    assert (tmp_path / "data" / "champion_snapshots.csv").exists()
    assert summary["snapshot_corpus_rows"] == state["total_snapshot_rows"]


def test_refresh_training_data_td_only(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "teacher_roster", _fast_roster)
    monkeypatch.setattr(tr, "champion_version", lambda: "genTEST")
    monkeypatch.setattr(dr, "_MAX_TD_GAMES", 1)

    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    summary = dr.refresh_training_data(
        {}, paths,
        run_id="RTD",
        budget_s=600.0,
        seed=7,
        td_output_path=tmp_path / "td.csv",  # explicit override still honoured
        collect_snapshots=False,
    )
    assert summary["td_rows"] > 0
    assert (tmp_path / "td.csv").exists()
    assert summary["snapshot_new_rows"] == 0
    assert not (tmp_path / "data" / "champion_snapshots.csv").exists()


# ---------------------------------------------------------------------------
# Snapshot corpus recency cap (P4)
# ---------------------------------------------------------------------------


def test_accumulate_snapshots_trims_to_recency_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(champion_loop, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(champion_loop, "SNAPSHOT_CSV", tmp_path / "data" / "snap.csv")
    monkeypatch.setattr(champion_loop, "SNAPSHOT_MAX_ROWS", 10)

    (tmp_path / "data").mkdir()
    old = pd.DataFrame({"final_score": range(8), "marker": ["old"] * 8})
    old.to_csv(champion_loop.SNAPSHOT_CSV, index=False)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    new = pd.DataFrame({"final_score": range(100, 105), "marker": ["new"] * 5})
    new.to_csv(run_dir / "snapshots.csv", index=False)

    total = champion_loop.accumulate_snapshots(str(run_dir))
    assert total == 10  # 8 + 5 = 13 -> trimmed to the cap

    kept = pd.read_csv(champion_loop.SNAPSHOT_CSV)
    assert len(kept) == 10
    # The trim drops the OLDEST rows: all 5 new rows survive.
    assert (kept["marker"] == "new").sum() == 5
    assert list(kept["marker"])[:5] == ["old"] * 5


# ---------------------------------------------------------------------------
# CLI flags exist and default sanely
# ---------------------------------------------------------------------------


def test_nightly_cli_refresh_flags():
    from training.nightly_run import parse_args

    args = parse_args(["--approaches", "rich_leaf", "--refresh-data",
                       "--refresh-minutes", "30", "--teacher-profile", "strong"])
    assert args.refresh_data is True
    assert args.refresh_minutes == 30.0
    assert args.teacher_profile == "strong"

    default = parse_args(["--approaches", "rich_leaf"])
    assert default.refresh_data is False
    assert default.teacher_profile == "teacher"
