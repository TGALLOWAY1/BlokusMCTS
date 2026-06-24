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


def test_not_in_wal_mode_so_single_file_is_durable(tmp_path):
    """The committed ``ratings.sqlite`` must hold every write with NO -wal sidecar.

    Regression guard: WAL mode kept committed inserts in a gitignored
    ``ratings.sqlite-wal`` file that was lost when a CI job was killed before
    checkpoint, freezing the committed timeline at an old run.
    """
    db = tmp_path / "r.sqlite"
    conn = rdb.connect(db)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() != "wal"
    rdb.record_run(
        conn, run_id="run1", timestamp="2026-06-20T03:00:00Z", generation=1,
        agent_rows=_agent_rows(), run_summary=_summary(),
    )
    # The write is durable in the single file even without closing the conn and
    # even if the -wal sidecar (if any) is removed mid-flight.
    for sidecar in (db.with_name(db.name + "-wal"), db.with_name(db.name + "-shm")):
        if sidecar.exists():
            sidecar.unlink()
    conn2 = rdb.connect(db)
    assert rdb.run_count(conn2) == 1


def test_records_accumulate_per_generation(tmp_path):
    """Recording one row per generation grows the timeline (durability model)."""
    conn = rdb.connect(tmp_path / "r.sqlite")
    for gen in range(1, 6):
        rdb.record_run(
            conn, run_id="nightly1", timestamp=f"2026-06-20T0{gen}:00:00Z",
            generation=gen, agent_rows=_agent_rows(1000.0 + gen, gen * 12),
            run_summary=_summary(gen, gen * 12, 1000.0 + gen),
        )
    assert rdb.run_count(conn) == 5
    series = rdb.champion_elo_series(conn)
    assert [round(p["elo"], 0) for p in series] == [1001, 1002, 1003, 1004, 1005]
    assert series[-1]["run_id"] == "nightly1"


def test_record_game_elos_and_series(tmp_path):
    conn = rdb.connect(tmp_path / "r.sqlite")
    assert rdb.max_game_number(conn) == 0
    rdb.record_game_elos(
        conn, run_id="run1", timestamp="2026-06-20T03:00:00Z", generation=1,
        samples=[(1, 1200.0), (2, 1212.5), (3, 1205.0)],
    )
    assert rdb.max_game_number(conn) == 3
    series = rdb.champion_game_elo_series(conn)
    assert [p["game_number"] for p in series] == [1, 2, 3]
    assert [round(p["elo"], 1) for p in series] == [1200.0, 1212.5, 1205.0]
    assert all(p["generation"] == 1 for p in series)


def test_record_game_elos_empty_is_noop(tmp_path):
    conn = rdb.connect(tmp_path / "r.sqlite")
    rdb.record_game_elos(
        conn, run_id="run1", timestamp="t", generation=1, samples=[],
    )
    assert rdb.max_game_number(conn) == 0
    assert rdb.champion_game_elo_series(conn) == []


def test_game_elo_series_continues_across_runs_and_limit(tmp_path):
    conn = rdb.connect(tmp_path / "r.sqlite")
    rdb.record_game_elos(
        conn, run_id="run1", timestamp="t1", generation=1,
        samples=[(1, 1200.0), (2, 1205.0)],
    )
    # Second run continues numbering from the durable max (mirrors nightly_run).
    start = rdb.max_game_number(conn)
    rdb.record_game_elos(
        conn, run_id="run2", timestamp="t2", generation=2,
        samples=[(start + 1, 1210.0), (start + 2, 1215.0)],
    )
    series = rdb.champion_game_elo_series(conn)
    assert [p["game_number"] for p in series] == [1, 2, 3, 4]
    # limit keeps the most-recent N, still oldest-first.
    tail = rdb.champion_game_elo_series(conn, limit=2)
    assert [p["game_number"] for p in tail] == [3, 4]


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
