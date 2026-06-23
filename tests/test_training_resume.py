"""Resume proof: a second run must build on the first, never start over.

The arena is mocked so no real MCTS games run — the focus is the durable
orchestration: atomic per-generation persistence, the append-only rating
timeline, and full state reconstruction from disk between runs.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import TrainingPaths, ratings_db, state_store
from training import nightly_run
from training import selfplay_core as sc


def _install_fast_mocks(monkeypatch, paths):
    """Replace generation/candidate with deterministic, instant fakes."""

    def fake_run_generation(state, p, *, generation, games_per_arena, seed, rng,
                            tracker, thinking_time_ms=None, verbose=False):
        # Mirror production: games.jsonl lives directly in the returned run_dir
        # (run_experiment returns the leaf dir that contains games.jsonl), so the
        # orchestrator's per-generation Elo replay finds the games.
        gen_dir = p.selfplay_runs_dir / f"gen{generation:04d}" / "run0"
        gen_dir.mkdir(parents=True, exist_ok=True)
        game = {"agent_scores": {"champion": 50, "heuristic": 30, "random": 20, "mcts_low_c": 10}}
        (gen_dir / "games.jsonl").write_text(json.dumps(game) + "\n", encoding="utf-8")
        tracker.update_game(game["agent_scores"])
        state["total_snapshot_rows"] = state.get("total_snapshot_rows", 0) + 50
        return sc.GenerationResult(
            games_run=games_per_arena,
            snapshot_rows=state["total_snapshot_rows"],
            champion_rating=tracker.get_rating("champion"),
            challengers=["heuristic", "random", "mcts_low_c"],
            run_dir=str(gen_dir),  # leaf dir containing games.jsonl (as in prod)
            elapsed_s=99999.0,  # forces exactly one generation per run
        )

    monkeypatch.setattr(sc, "run_generation", fake_run_generation)
    # No candidate -> skip the (heavy) evaluation battery entirely.
    monkeypatch.setattr(sc, "build_candidate", lambda state: (None, None))


def _run_once(paths):
    return nightly_run.run(
        paths=paths,
        hours=1.0,
        seeds=[1, 2],
        games_per_arena=4,
        thinking_time_ms=10,
        promote_registry=False,
        dry_run=False,
        verbose=False,
    )


def test_two_runs_accumulate(tmp_path, monkeypatch):
    paths = TrainingPaths.under(tmp_path)
    _install_fast_mocks(monkeypatch, paths)

    state1 = _run_once(paths)
    gen1 = state1["generation"]
    games1 = state1["total_games"]
    assert gen1 == 1
    assert games1 == 4

    # Second run resumes from disk.
    state2 = _run_once(paths)
    assert state2["generation"] == gen1 + 1          # generation advanced
    assert state2["total_games"] > games1            # games accumulated
    assert state2["days_trained"] == 2               # day counter advanced


def test_rating_timeline_is_append_only(tmp_path, monkeypatch):
    paths = TrainingPaths.under(tmp_path)
    _install_fast_mocks(monkeypatch, paths)
    _run_once(paths)
    _run_once(paths)

    conn = ratings_db.connect(paths.ratings_db)
    assert ratings_db.run_count(conn) == 2           # two runs recorded
    # champion appears in both runs' history (timeline preserved).
    champ_rows = conn.execute(
        "SELECT COUNT(*) FROM rating_history WHERE agent='champion'"
    ).fetchone()[0]
    assert champ_rows == 2


def test_fresh_elo_recorded_every_run(tmp_path, monkeypatch):
    """The repeated-Elo regression guard: each run must persist a fresh Elo.

    With the champion winning every mocked game, its Elo must rise run-over-run
    and the latest recorded DB Elo must match latest.json — never freeze at the
    first run's value while generation/games advance.
    """
    paths = TrainingPaths.under(tmp_path)
    _install_fast_mocks(monkeypatch, paths)

    state1 = _run_once(paths)
    elo1 = state1["elo"]
    state2 = _run_once(paths)
    elo2 = state2["elo"]

    # Champion keeps winning => Elo strictly increases, not frozen.
    assert elo2 > elo1

    conn = ratings_db.connect(paths.ratings_db)
    series = ratings_db.champion_elo_series(conn)
    assert len(series) == 2
    assert series[-1]["elo"] == elo2                     # DB matches state
    assert series[-1]["elo"] != series[0]["elo"]         # not stale
    # latest.json's persisted Elo equals the latest recorded DB Elo.
    reloaded = state_store.load_latest(paths)
    assert reloaded["elo"] == series[-1]["elo"]


def test_state_fully_reconstructed_from_disk(tmp_path, monkeypatch):
    paths = TrainingPaths.under(tmp_path)
    _install_fast_mocks(monkeypatch, paths)
    _run_once(paths)

    # Reload purely from disk — everything the next run needs must be present.
    reloaded = state_store.load_latest(paths)
    assert reloaded["generation"] == 1
    assert reloaded["champion_params"] is not None
    assert reloaded["trueskill_ratings"]            # persisted tracker state
    # No leftover temp files from atomic writes.
    assert not list(paths.state_dir.glob("*.tmp"))


def test_artifacts_written(tmp_path, monkeypatch):
    paths = TrainingPaths.under(tmp_path)
    _install_fast_mocks(monkeypatch, paths)
    _run_once(paths)
    assert paths.latest_json.exists()
    assert paths.champion_json.exists()
    assert paths.ratings_db.exists()
    assert paths.history_jsonl.exists()
    assert paths.status_md.exists()
    assert paths.diagnosis_md.exists()


def test_failure_preserves_state_and_records_error(tmp_path, monkeypatch):
    paths = TrainingPaths.under(tmp_path)
    _install_fast_mocks(monkeypatch, paths)
    # First, a clean run so there is prior state to preserve.
    _run_once(paths)

    # Now make generation explode mid-run.
    def boom(*args, **kwargs):
        raise RuntimeError("arena exploded")

    monkeypatch.setattr(sc, "run_generation", boom)
    try:
        _run_once(paths)
    except RuntimeError:
        pass

    state = state_store.load_latest(paths)
    assert state["last_error"] is not None
    assert "arena exploded" in state["last_error"]["message"]
    # Prior progress preserved (generation didn't get wiped).
    assert state["generation"] >= 1
