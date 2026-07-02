"""Never-overwritten SQLite rating timeline.

This is the durable, append-only record of *every* rating measurement across the
entire history of the project — the thing you can graph months from now. Two
tables:

* ``rating_history`` — one row per agent per nightly run (Elo + TrueSkill).
* ``run_summary``    — one row per nightly run summarising champion progress
  (fast queries for trends + human-strength estimation).
* ``game_elo``       — one row **per individual game** holding the champion's
  Elo recomputed after that game. This is the fine-grained trajectory the
  nightly email plots so you can see whether the rating distribution is actually
  drifting upward, rather than only seeing one coarse point per generation.

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

SCHEMA_VERSION = 2

# ---------------------------------------------------------------------------
# Multi-agent epoch
# ---------------------------------------------------------------------------
# The nightly pipeline switched from the legacy single-line self-play generation
# loop to the multi-agent approach-comparison framework in commit 3b36f7c
# (2026-06-26 05:57 UTC). Every run recorded *before* that is a legacy run whose
# Elo trajectory is not comparable to the current approach, so the morning report
# must not mix the two: doing so dragged a stale, much higher legacy "best
# historical" into the deltas and made the trend look far worse than the
# multi-agent era actually is.
#
# Run ids are minted as ``%Y%m%dT%H%M%SZ`` (see ``nightly_run._new_run_id``), so
# they sort lexicographically by wall-clock time. Filtering ``run_id >= EPOCH``
# therefore keeps exactly the multi-agent-era rows. The boundary is intentionally
# a single constant: change it here and every report (trend table, deltas, plot)
# re-bases consistently.
MULTI_AGENT_EPOCH_RUN_ID = "20260626T055723Z"


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

CREATE TABLE IF NOT EXISTS game_elo (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL,
    generation  INTEGER NOT NULL,
    game_number INTEGER NOT NULL,  -- cumulative game index across all history
    agent       TEXT    NOT NULL,
    elo         REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_game_elo_agent_num ON game_elo(agent, game_number);
CREATE INDEX IF NOT EXISTS idx_game_elo_run       ON game_elo(run_id);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables/indexes (idempotent) and stamp the schema version."""
    conn.executescript(_SCHEMA)
    cur = conn.execute("SELECT COUNT(*) FROM schema_version")
    if cur.fetchone()[0] == 0:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()


def connect(path: Path | str) -> sqlite3.Connection:
    """Open (creating dirs/file) the ratings DB with schema initialised.

    Durability over concurrency: the nightly pipeline has a single writer, so we
    deliberately use SQLite's rollback journal (``journal_mode=DELETE``) rather
    than WAL. WAL kept committed inserts in a ``ratings.sqlite-wal`` sidecar that
    is **gitignored** — so whenever a CI job was killed before the connection
    closed and checkpointed, every ``record_run`` since the last checkpoint was
    lost and the committed ``ratings.sqlite`` froze at an old run. With the
    rollback journal, each committed transaction lands in the single
    ``ratings.sqlite`` file that is committed to git, so the timeline survives a
    killed job. Opening an existing WAL database with this pragma checkpoints and
    converts it in place.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    # Convert any pre-existing WAL database back to the single-file rollback
    # journal (checkpoints outstanding WAL frames into the main file first).
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=FULL")
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


def record_game_elos(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    timestamp: str,
    generation: int,
    samples: List[tuple],
    agent: str = "champion",
) -> None:
    """Append one row per individual game with ``agent``'s Elo after that game.

    ``samples`` is an ordered ``[(game_number, elo), ...]`` list — the champion's
    running Elo recomputed after each game in this generation. Append-only and a
    no-op for an empty list. ``game_number`` is the cumulative index across the
    whole history (see :func:`max_game_number`) so the plotted x-axis is monotonic
    across runs.
    """
    if not samples:
        return
    with conn:  # transaction
        conn.executemany(
            """
            INSERT INTO game_elo
                (run_id, timestamp, generation, game_number, agent, elo)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (run_id, timestamp, int(generation), int(gn), agent, float(elo))
                for gn, elo in samples
            ],
        )


def max_game_number(conn: sqlite3.Connection, *, agent: str = "champion") -> int:
    """Highest cumulative ``game_number`` recorded for ``agent`` (0 if none).

    Used to continue per-game numbering across runs so the per-game Elo plot has a
    single, monotonically-increasing x-axis over the whole training history.
    """
    row = conn.execute(
        "SELECT MAX(game_number) FROM game_elo WHERE agent = ?", (agent,)
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def champion_game_elo_series(
    conn: sqlite3.Connection, *, agent: str = "champion", limit: Optional[int] = None,
    since_run_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Per-game Elo trajectory for ``agent``, oldest-first.

    With ``limit`` set, returns the most-recent ``limit`` games (still oldest-first)
    so the email plot can bound how many points it renders without losing the head
    of the series to ordering. With ``since_run_id`` set, only games recorded by
    runs at/after that run id are returned (see :data:`MULTI_AGENT_EPOCH_RUN_ID`),
    so the report can plot the multi-agent era alone.
    """
    where = "agent = ?"
    params: List[Any] = [agent]
    if since_run_id:
        where += " AND run_id >= ?"
        params.append(since_run_id)
    if limit:
        rows = conn.execute(
            f"""
            SELECT game_number, elo, generation, run_id, timestamp
            FROM game_elo WHERE {where}
            ORDER BY game_number DESC, id DESC LIMIT ?
            """,
            (*params, int(limit)),
        ).fetchall()
        rows = list(reversed(rows))
    else:
        rows = conn.execute(
            f"""
            SELECT game_number, elo, generation, run_id, timestamp
            FROM game_elo WHERE {where}
            ORDER BY game_number ASC, id ASC
            """,
            tuple(params),
        ).fetchall()
    return [
        {
            "game_number": int(r["game_number"]),
            "elo": float(r["elo"]),
            "generation": int(r["generation"]),
            "run_id": r["run_id"],
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]


def latest_ratings(
    conn: sqlite3.Connection, *, since_run_id: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """Most-recent rating row per agent — the cross-run seed for both trackers.

    Returns ``{agent: {elo, mu, sigma, conservative, games_played}}``. Elo has no
    serialization of its own, so this is how Elo (and TrueSkill) persist across
    runs. With ``since_run_id`` set, only rows from runs at/after that run id are
    considered (see :data:`MULTI_AGENT_EPOCH_RUN_ID` / the reporting era), so an
    era-scoped caller never falls back to a pre-cutoff rating for an agent that sat
    out the current run.
    """
    if since_run_id:
        rows = conn.execute(
            """
            SELECT agent, elo, trueskill_mu, trueskill_sigma, conservative, games_played
            FROM rating_history
            WHERE id IN (
                SELECT MAX(id) FROM rating_history
                WHERE run_id >= ? GROUP BY agent
            )
            """,
            (since_run_id,),
        ).fetchall()
    else:
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


def ratings_for_run(conn: sqlite3.Connection, run_id: str) -> Dict[str, Dict[str, Any]]:
    """Every agent's rating snapshot recorded by a single run.

    Returns ``{agent: {elo, mu, sigma, conservative, games_played}}`` for the given
    ``run_id`` (empty dict if the run recorded nothing). Used by the matchup matrix
    so the champion and its opponents are compared on ratings measured in the *same*
    run rather than across differently-aged snapshots.
    """
    rows = conn.execute(
        """
        SELECT agent, elo, trueskill_mu, trueskill_sigma, conservative, games_played
        FROM rating_history WHERE run_id = ?
        """,
        (run_id,),
    ).fetchall()
    return {
        row["agent"]: {
            "elo": float(row["elo"]),
            "mu": float(row["trueskill_mu"]),
            "sigma": float(row["trueskill_sigma"]),
            "conservative": float(row["conservative"]),
            "games_played": int(row["games_played"]),
        }
        for row in rows
    }


def champion_elo_series(
    conn: sqlite3.Connection, *, agent: str = "champion",
    since_run_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Ordered (oldest-first) Elo timeline for ``agent`` with cumulative games.

    Pulls from ``run_summary`` for the champion (one point per run) so the
    human-strength estimator sees a clean per-run series. With ``since_run_id``
    set, only runs at/after that run id are returned (see
    :data:`MULTI_AGENT_EPOCH_RUN_ID`).
    """
    where = ""
    params: tuple = ()
    if since_run_id:
        where = "WHERE run_id >= ?"
        params = (since_run_id,)
    rows = conn.execute(
        f"""
        SELECT run_id, timestamp, champion_elo AS elo, total_games, generation,
               promoted, games_today
        FROM run_summary
        {where}
        ORDER BY timestamp ASC, id ASC
        """,
        params,
    ).fetchall()
    return [
        {
            "run_id": row["run_id"],
            "timestamp": row["timestamp"],
            "elo": float(row["elo"]),
            "total_games": int(row["total_games"]),
            "generation": int(row["generation"]),
            "promoted": bool(row["promoted"]),
            "games_today": int(row["games_today"]),
        }
        for row in rows
    ]


def recent_window(
    conn: sqlite3.Connection, *, limit: int, since_run_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Most-recent ``limit`` run summaries, oldest-first (for 7d/30d trends).

    With ``since_run_id`` set, only runs at/after that run id are considered (see
    :data:`MULTI_AGENT_EPOCH_RUN_ID`), so the morning report's trend, deltas, and
    "best historical" never reach back into the pre-multi-agent era.
    """
    if since_run_id:
        rows = conn.execute(
            """
            SELECT * FROM run_summary WHERE run_id >= ?
            ORDER BY timestamp DESC, id DESC LIMIT ?
            """,
            (since_run_id, int(limit)),
        ).fetchall()
    else:
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
