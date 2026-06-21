"""Never-overwritten SQLite rating timeline.

This is the durable, append-only record of *every* rating measurement across the
entire history of the project — the thing you can graph months from now. Two
tables:

* ``rating_history`` — one row per agent per nightly run (Elo + TrueSkill).
* ``run_summary``    — one row per nightly run summarising champion progress
  (fast queries for trends + human-strength estimation).

History is **append-only**: ``record_run`` only ``INSERT``s. There is no UPDATE or
DELETE path. If GitHub Actions is destroyed and recreated, this file (committed to
the repo) lets training continue seamlessly — the cross-run rating seed comes from
:func:`latest_ratings`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AgentRatingRow:
    """One agent's rating snapshot for a single nightly run."""

    agent: str
    elo: float
    trueskill_mu: float
    trueskill_sigma: float
    conservative: float
    games_played: int


@dataclass(frozen=True)
class RunSummaryRow:
    """Champion-centric summary of a single nightly run."""

    generation: int
    games_today: int
    total_games: int
    champion_elo: float
    champion_mu: float
    champion_sigma: float
    promoted: bool
    days_trained: int


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS rating_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT    NOT NULL,
    timestamp       TEXT    NOT NULL,
    generation      INTEGER NOT NULL,
    agent           TEXT    NOT NULL,
    elo             REAL    NOT NULL,
    trueskill_mu    REAL    NOT NULL,
    trueskill_sigma REAL    NOT NULL,
    conservative    REAL    NOT NULL,
    games_played    INTEGER NOT NULL,
    total_games     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rating_agent_ts ON rating_history(agent, timestamp);
CREATE INDEX IF NOT EXISTS idx_rating_run      ON rating_history(run_id);

CREATE TABLE IF NOT EXISTS run_summary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    generation      INTEGER NOT NULL,
    games_today     INTEGER NOT NULL,
    total_games     INTEGER NOT NULL,
    champion_elo    REAL NOT NULL,
    champion_mu     REAL NOT NULL,
    champion_sigma  REAL NOT NULL,
    promoted        INTEGER NOT NULL,
    days_trained    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_summary_ts ON run_summary(timestamp);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables/indexes (idempotent) and stamp the schema version."""
    conn.executescript(_SCHEMA)
    cur = conn.execute("SELECT COUNT(*) FROM schema_version")
    if cur.fetchone()[0] == 0:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()


def connect(path: Path | str) -> sqlite3.Connection:
    """Open (creating dirs/file) the ratings DB with WAL + schema initialised."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    init_schema(conn)
    return conn


def record_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    timestamp: str,
    generation: int,
    agent_rows: List[AgentRatingRow],
    run_summary: RunSummaryRow,
) -> None:
    """Append one run's ratings + summary in a single transaction (append-only).

    Both tables are append-only: every call adds rows and nothing is ever updated
    or deleted, so the timeline is a permanent record even across re-runs.
    """
    with conn:  # transaction
        conn.executemany(
            """
            INSERT INTO rating_history
                (run_id, timestamp, generation, agent, elo, trueskill_mu,
                 trueskill_sigma, conservative, games_played, total_games)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    timestamp,
                    generation,
                    r.agent,
                    float(r.elo),
                    float(r.trueskill_mu),
                    float(r.trueskill_sigma),
                    float(r.conservative),
                    int(r.games_played),
                    int(run_summary.total_games),
                )
                for r in agent_rows
            ],
        )
        conn.execute(
            """
            INSERT INTO run_summary
                (run_id, timestamp, generation, games_today, total_games,
                 champion_elo, champion_mu, champion_sigma, promoted, days_trained)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                timestamp,
                int(run_summary.generation),
                int(run_summary.games_today),
                int(run_summary.total_games),
                float(run_summary.champion_elo),
                float(run_summary.champion_mu),
                float(run_summary.champion_sigma),
                1 if run_summary.promoted else 0,
                int(run_summary.days_trained),
            ),
        )


def latest_ratings(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Most-recent rating row per agent — the cross-run seed for both trackers.

    Returns ``{agent: {elo, mu, sigma, conservative, games_played}}``. Elo has no
    serialization of its own, so this is how Elo (and TrueSkill) persist across
    runs.
    """
    rows = conn.execute(
        """
        SELECT agent, elo, trueskill_mu, trueskill_sigma, conservative, games_played
        FROM rating_history
        WHERE id IN (
            SELECT MAX(id) FROM rating_history GROUP BY agent
        )
        """
    ).fetchall()
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        out[row["agent"]] = {
            "elo": float(row["elo"]),
            "mu": float(row["trueskill_mu"]),
            "sigma": float(row["trueskill_sigma"]),
            "conservative": float(row["conservative"]),
            "games_played": int(row["games_played"]),
        }
    return out


def champion_elo_series(
    conn: sqlite3.Connection, *, agent: str = "champion"
) -> List[Dict[str, Any]]:
    """Ordered (oldest-first) Elo timeline for ``agent`` with cumulative games.

    Pulls from ``run_summary`` for the champion (one point per run) so the
    human-strength estimator sees a clean per-run series.
    """
    rows = conn.execute(
        """
        SELECT timestamp, champion_elo AS elo, total_games, generation
        FROM run_summary
        ORDER BY timestamp ASC, id ASC
        """
    ).fetchall()
    return [
        {
            "timestamp": row["timestamp"],
            "elo": float(row["elo"]),
            "total_games": int(row["total_games"]),
            "generation": int(row["generation"]),
        }
        for row in rows
    ]


def recent_window(conn: sqlite3.Connection, *, limit: int) -> List[Dict[str, Any]]:
    """Most-recent ``limit`` run summaries, oldest-first (for 7d/30d trends)."""
    rows = conn.execute(
        """
        SELECT * FROM run_summary ORDER BY timestamp DESC, id DESC LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    out = [dict(row) for row in rows]
    out.reverse()  # oldest-first
    return out


def run_count(conn: sqlite3.Connection) -> int:
    """Number of recorded nightly runs (used for resume/trend sanity checks)."""
    return int(conn.execute("SELECT COUNT(*) FROM run_summary").fetchone()[0])


def last_run_summary(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
    """The most recent run_summary row, or None if the timeline is empty."""
    row = conn.execute(
        "SELECT * FROM run_summary ORDER BY timestamp DESC, id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None
