"""Tests for the champion Elo trajectory plot.

The plot must (a) prefer the fine-grained per-game series, (b) fall back to the
per-generation series when no per-game data exists yet, and (c) never raise when
matplotlib is unavailable — returning ``None`` so the email ships text-only.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import TrainingPaths, ratings_db
from training import elo_plot

matplotlib = pytest.importorskip("matplotlib")  # in requirements.txt; skip if absent


def _seed_run_summary(conn, gen, elo, total):
    ratings_db.record_run(
        conn, run_id=f"run{gen}", timestamp=f"2026-06-2{gen}T03:00:00Z",
        generation=gen,
        agent_rows=[ratings_db.AgentRatingRow("champion", elo, 26.0, 7.0, 5.0, total)],
        run_summary=ratings_db.RunSummaryRow(gen, 12, total, elo, 26.0, 7.0, False, gen),
    )


def test_returns_none_on_empty_timeline(tmp_path):
    conn = ratings_db.connect(tmp_path / "r.sqlite")
    out = elo_plot.render_elo_plot(conn, tmp_path / "elo.png")
    assert out is None
    assert not (tmp_path / "elo.png").exists()


def test_renders_per_game_series(tmp_path):
    conn = ratings_db.connect(tmp_path / "r.sqlite")
    samples = [(i, 1200.0 + i * 0.5) for i in range(1, 41)]
    ratings_db.record_game_elos(
        conn, run_id="run1", timestamp="t", generation=1, samples=samples
    )
    out = elo_plot.render_elo_plot(conn, tmp_path / "elo.png", target_elo=1700)
    assert out is not None
    assert out.exists() and out.stat().st_size > 0


def test_falls_back_to_per_generation_series(tmp_path):
    conn = ratings_db.connect(tmp_path / "r.sqlite")
    for gen, elo in enumerate([1000.0, 1020.0, 1015.0, 1040.0], start=1):
        _seed_run_summary(conn, gen, elo, gen * 12)
    # No per-game rows -> must still render from run_summary.
    assert ratings_db.max_game_number(conn) == 0
    out = elo_plot.render_elo_plot(conn, tmp_path / "elo.png")
    assert out is not None and out.exists()


def test_load_series_prefers_per_game(tmp_path):
    conn = ratings_db.connect(tmp_path / "r.sqlite")
    _seed_run_summary(conn, 1, 1000.0, 12)
    ratings_db.record_game_elos(
        conn, run_id="run1", timestamp="t", generation=1,
        samples=[(1, 1300.0), (2, 1305.0)],
    )
    x, y, granularity = elo_plot._load_series(conn)
    assert granularity == "per-game"
    assert y == [1300.0, 1305.0]


def test_render_default_uses_repo_paths(tmp_path, monkeypatch):
    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    conn = ratings_db.connect(paths.ratings_db)
    ratings_db.record_game_elos(
        conn, run_id="run1", timestamp="t", generation=1,
        samples=[(1, 1200.0), (2, 1210.0)],
    )
    conn.close()
    monkeypatch.setattr(TrainingPaths, "default", classmethod(lambda cls: paths))
    out = elo_plot.render_default(target_elo=1700)
    assert out is not None
    assert out == paths.reports_dir / "elo_trend.png"
    assert out.exists()
