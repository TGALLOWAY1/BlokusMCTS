"""Tests for the append-only SQLite rating timeline."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import ratings_db as rdb


def _agent_rows(elo_champ=1210.0, games=10):
    return [
        rdb.AgentRatingRow("champion", elo_champ, 26.0, 7.0, 5.0, games),
        rdb.AgentRatingRow("heuristic", 1190.0, 24.0, 7.0, 3.0, games),
    ]


def _summary(gen=1, total=10, elo=1210.0, promoted=False, days=1):
    return rdb.RunSummaryRow(
        generation=gen,
        games_today=10,
        total_games=total,
        champion_elo=elo,
        champion_mu=26.0,
        champion_sigma=7.0,
        promoted=promoted,
        days_trained=days,
    )


def test_init_schema_idempotent(tmp_path):
    db = tmp_path / "r.sqlite"
    conn = rdb.connect(db)
    rdb.init_schema(conn)  # second call must not raise / duplicate
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == rdb.SCHEMA_VERSION
    assert conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 1


def test_record_run_is_append_only_across_runs(tmp_path):
    conn = rdb.connect(tmp_path / "r.sqlite")
    rdb.record_run(
        conn, run_id="run1", timestamp="2026-06-20T03:00:00Z", generation=1,
        agent_rows=_agent_rows(1210.0, 10), run_summary=_summary(1, 10, 1210.0),
    )
    rdb.record_run(
        conn, run_id="run2", timestamp="2026-06-21T03:00:00Z", generation=2,
        agent_rows=_agent_rows(1225.0, 20), run_summary=_summary(2, 20, 1225.0),
    )
    # History accumulated, nothing overwritten: 2 runs x 2 agents = 4 rows.
    assert conn.execute("SELECT COUNT(*) FROM rating_history").fetchone()[0] == 4
    assert rdb.run_count(conn) == 2


def test_latest_ratings_returns_most_recent_per_agent(tmp_path):
    conn = rdb.connect(tmp_path / "r.sqlite")
    rdb.record_run(
        conn, run_id="run1", timestamp="2026-06-20T03:00:00Z", generation=1,
        agent_rows=_agent_rows(1210.0, 10), run_summary=_summary(1, 10, 1210.0),
    )
    rdb.record_run(
        conn, run_id="run2", timestamp="2026-06-21T03:00:00Z", generation=2,
        agent_rows=_agent_rows(1225.0, 20), run_summary=_summary(2, 20, 1225.0),
    )
    latest = rdb.latest_ratings(conn)
    assert latest["champion"]["elo"] == 1225.0
    assert latest["champion"]["games_played"] == 20


def test_champion_elo_series_oldest_first(tmp_path):
    conn = rdb.connect(tmp_path / "r.sqlite")
    rdb.record_run(
        conn, run_id="run1", timestamp="2026-06-20T03:00:00Z", generation=1,
        agent_rows=_agent_rows(1210.0, 10), run_summary=_summary(1, 10, 1210.0),
    )
    rdb.record_run(
        conn, run_id="run2", timestamp="2026-06-21T03:00:00Z", generation=2,
        agent_rows=_agent_rows(1225.0, 20), run_summary=_summary(2, 20, 1225.0),
    )
    series = rdb.champion_elo_series(conn)
    assert [p["elo"] for p in series] == [1210.0, 1225.0]
    assert [p["total_games"] for p in series] == [10, 20]


def test_persists_across_reconnect(tmp_path):
    db = tmp_path / "r.sqlite"
    conn = rdb.connect(db)
    rdb.record_run(
        conn, run_id="run1", timestamp="2026-06-20T03:00:00Z", generation=1,
        agent_rows=_agent_rows(), run_summary=_summary(),
    )
    conn.close()
    # Simulate a fresh CI container reopening the committed DB file.
    conn2 = rdb.connect(db)
    assert rdb.run_count(conn2) == 1
    assert rdb.latest_ratings(conn2)["champion"]["elo"] == 1210.0
