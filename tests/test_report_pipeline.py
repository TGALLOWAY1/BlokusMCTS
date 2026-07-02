"""Tests for the post-bug-fix reporting pipeline.

Covers the reporting-era filter (the debugged-backprop cut-off), that trend / best
historical / windows exclude pre-cutoff rows by default, the extra report graphics
degrade gracefully on empty/partial data, the champion-composition summary, the
email HTML sections + artifact references, the plain-text fallback, and the local
preview command.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import TrainingPaths, email_summary as es
from training import ratings_db, reporting_era, report_visuals

matplotlib = pytest.importorskip("matplotlib")


# ---------------------------------------------------------------------------
# Helpers — seed a ratings DB straddling the backprop-fix cut-off.
# ---------------------------------------------------------------------------

CUTOFF = reporting_era.DEBUGGED_BACKPROP_EPOCH_RUN_ID  # "20260701T204805Z"
PRE = "20260628T000000Z"   # sorts before the cut-off
POST1 = "20260702T000000Z"  # sorts after the cut-off
POST2 = "20260702T120000Z"  # after the cut-off, latest


def _record(conn, run_id, gen, elo, total, *, promoted=False, agents=None):
    agent_rows = [ratings_db.AgentRatingRow("champion", elo, 26.0, 6.0, 8.0, total)]
    for name, a_elo in (agents or {}).items():
        agent_rows.append(ratings_db.AgentRatingRow(name, a_elo, 20.0, 6.0, 2.0, 50))
    ratings_db.record_run(
        conn, run_id=run_id, timestamp=f"{run_id[:4]}-01-01T00:00:00Z",
        generation=gen, agent_rows=agent_rows,
        run_summary=ratings_db.RunSummaryRow(gen, 40, total, elo, 26.0, 6.0, promoted, gen),
    )


def _seeded_db(tmp_path):
    conn = ratings_db.connect(tmp_path / "r.sqlite")
    # Pre-fix: high, invalid Elo that must NOT leak into the default report.
    _record(conn, PRE, 100, 1600.0, 500)
    # Post-fix era.
    _record(conn, CUTOFF, 139, 1224.0, 1300)
    _record(conn, POST1, 140, 1200.0, 1400, promoted=True,
            agents={"heuristic": 950.0, "random": 760.0})
    _record(conn, POST2, 142, 1377.0, 1500,
            agents={"heuristic": 950.0, "random": 760.0})
    return conn


# ---------------------------------------------------------------------------
# Reporting era resolution
# ---------------------------------------------------------------------------

def test_default_era_is_debugged_backprop():
    era = reporting_era.resolve_era()
    assert era.key == "debugged-backprop"
    assert era.since_run_id == CUTOFF
    assert not era.is_all_time


def test_env_override_selects_named_era(monkeypatch):
    monkeypatch.setenv(reporting_era.ENV_ERA_KEY, "all-time")
    era = reporting_era.resolve_era()
    assert era.is_all_time and era.since_run_id is None


def test_env_override_custom_run_id_wins(monkeypatch):
    monkeypatch.setenv(reporting_era.ENV_ERA_KEY, "all-time")
    monkeypatch.setenv(reporting_era.ENV_ERA_RUN_ID, "20260705T000000Z")
    era = reporting_era.resolve_era()
    assert era.since_run_id == "20260705T000000Z"
    assert era.key == "custom"


def test_unknown_era_falls_back_to_default():
    era = reporting_era.resolve_era("nonsense-era")
    assert era.key == "debugged-backprop"


def test_banner_mentions_preservation():
    assert "preserved" in reporting_era.DEBUGGED_BACKPROP.banner().lower()


# ---------------------------------------------------------------------------
# Era filtering excludes pre-cutoff records
# ---------------------------------------------------------------------------

def test_filter_excludes_pre_cutoff_runs(tmp_path):
    conn = _seeded_db(tmp_path)
    all_series = ratings_db.champion_elo_series(conn)
    era_series = ratings_db.champion_elo_series(conn, since_run_id=CUTOFF)
    assert len(all_series) == 4
    assert len(era_series) == 3
    assert all(p["run_id"] >= CUTOFF for p in era_series)
    assert PRE not in {p["run_id"] for p in era_series}


def test_best_historical_from_filtered_era(tmp_path):
    conn = _seeded_db(tmp_path)
    era_series = ratings_db.champion_elo_series(conn, since_run_id=CUTOFF)
    all_series = ratings_db.champion_elo_series(conn)
    best_all = max(p["elo"] for p in all_series)
    best_era = max(p["elo"] for p in era_series)
    # The pre-fix 1600 is the all-time best but must be excluded from the era best.
    assert best_all == 1600.0
    assert best_era == 1377.0


def test_recent_window_respects_cutoff(tmp_path):
    conn = _seeded_db(tmp_path)
    window = ratings_db.recent_window(conn, limit=30, since_run_id=CUTOFF)
    assert {r["run_id"] for r in window} == {CUTOFF, POST1, POST2}


def test_trend_series_from_filtered_era(tmp_path):
    from training import elo_plot

    conn = _seeded_db(tmp_path)
    x, y, gran = elo_plot._load_series(conn, since_run_id=CUTOFF)
    assert gran == "per-generation"  # no per-game rows seeded
    assert 1600.0 not in y  # the pre-fix high never enters the trend


# ---------------------------------------------------------------------------
# Extra graphics — empty / partial data must not crash
# ---------------------------------------------------------------------------

def test_matchup_matrix_empty_record_returns_none(tmp_path):
    conn = ratings_db.connect(tmp_path / "r.sqlite")
    out = report_visuals.render_matchup_matrix(
        conn, tmp_path / "m.png", None, run_id=None
    )
    assert out is None  # no champion rating, no rows -> no crash, no image


def test_matchup_matrix_partial_pool_renders(tmp_path):
    conn = _seeded_db(tmp_path)
    record = {
        "run_id": POST2,
        "pool": {"opponents": ["heuristic", "random", "ghost_agent"]},
        "rows": [{"approach": "baseline", "name": "baseline", "created": True,
                  "games": 20, "win_rate_vs_champion": 0.4}],
    }
    out = report_visuals.render_matchup_matrix(
        conn, tmp_path / "m.png", record, run_id=POST2, era_label="test era"
    )
    # ghost_agent has no rating (dropped); the rest still render.
    assert out is not None and out.exists()


def test_build_matchup_rows_skips_agents_without_ratings(tmp_path):
    conn = _seeded_db(tmp_path)
    record = {"pool": {"opponents": ["heuristic", "ghost_agent"]}, "rows": []}
    champ_elo, rows = report_visuals.build_matchup_rows(conn, record, run_id=POST2)
    names = {r["agent"] for r in rows}
    assert "heuristic" in names
    assert "ghost_agent" not in names
    assert champ_elo == 1377.0


def test_approach_comparison_no_candidates_returns_none(tmp_path):
    out = report_visuals.render_approach_comparison(
        tmp_path / "a.png", {"rows": [{"approach": "x", "created": False}]}
    )
    assert out is None


def test_recent_deltas_too_few_runs_returns_none(tmp_path):
    conn = ratings_db.connect(tmp_path / "r.sqlite")
    _record(conn, POST1, 140, 1200.0, 100)
    out = report_visuals.render_recent_deltas(conn, tmp_path / "d.png")
    assert out is None


# ---------------------------------------------------------------------------
# Champion composition summary
# ---------------------------------------------------------------------------

def test_champion_composition_minimal_state_does_not_crash():
    lines = report_visuals.champion_composition_lines({})
    assert isinstance(lines, list) and lines


def test_champion_composition_reports_key_config():
    state = {
        "champion": {"name": "champion", "version": "gen140"},
        "generation": 142,
        "elo": 1377.0, "trueskill_mu": 48.0, "trueskill_sigma": 6.5,
        "last_promoted_generation": 140,
        "champion_params": {
            "type": "mcts", "thinking_time_ms": 500,
            "params": {
                "rollout_policy": "greedy_sample", "exploration_constant": 1.414,
                "rave_enabled": False, "heuristic_move_ordering": True,
                "iterations_per_ms": 0.5, "rollout_cutoff_depth": 12,
                "state_eval_weights": {"accessible_corners": 0.243, "center_proximity": 0.0},
            },
        },
        "last_approach_comparison": {
            "run_id": "20260702T120000Z",
            "pool": {"version": "benchmark_v2", "opponents": ["heuristic"], "seeds": [1]},
            "rows": [],
        },
    }
    text = "\n".join(report_visuals.champion_composition_lines(state))
    assert "greedy_sample" in text
    assert "gen140" in text
    assert "1.414" in text
    assert "generation 140" in text  # promotion source
    assert "benchmark_v2" in text


# ---------------------------------------------------------------------------
# Email HTML sections + plain-text fallback
# ---------------------------------------------------------------------------

def _state_with_approach():
    return {
        "run_id": POST2, "generation": 142, "total_games": 1500, "games_today": 40,
        "elo": 1377.0, "trueskill_mu": 48.0, "trueskill_sigma": 6.5,
        "champion": {"name": "champion", "version": "gen140"},
        "human_target_elo": 1700, "last_error": None,
        "last_promoted_generation": 140,
        "champion_params": {"type": "mcts", "thinking_time_ms": 500,
                            "params": {"rollout_policy": "greedy_sample",
                                       "exploration_constant": 1.414}},
        "last_approach_comparison": {
            "run_id": POST2, "winner": None,
            "seeds": [1, 2],
            "pool": {"version": "benchmark_v2", "opponents": ["heuristic", "random"]},
            "trajectory": {"noise": {"stddev": 100.0}, "significant": False},
            "rows": [
                {"approach": "baseline", "name": "baseline", "created": True,
                 "games": 20, "win_rate_vs_champion": 0.47, "elo_delta": -80.0,
                 "trueskill_delta": -6.0, "promoted": False, "gate_reason": "held"},
            ],
        },
        "last_eval": None,
    }


def _view_for(state):
    history = [
        {"id": 1, "run_id": CUTOFF, "timestamp": "t1", "generation": 139,
         "champion_elo": 1224.0, "total_games": 1300, "promoted": False,
         "champion_mu": 48.0, "champion_sigma": 6.5, "games_today": 40, "days_trained": 1},
        {"id": 2, "run_id": POST1, "timestamp": "t2", "generation": 140,
         "champion_elo": 1200.0, "total_games": 1400, "promoted": True,
         "champion_mu": 48.0, "champion_sigma": 6.5, "games_today": 40, "days_trained": 2},
        {"id": 3, "run_id": POST2, "timestamp": "t3", "generation": 142,
         "champion_elo": 1377.0, "total_games": 1500, "promoted": False,
         "champion_mu": 48.0, "champion_sigma": 6.5, "games_today": 40, "days_trained": 3},
    ]
    return es.build_run_view(history, state)


def test_body_has_no_contradictory_no_eval_line():
    state = _state_with_approach()
    body = es.build_body(state, _view_for(state), era=reporting_era.DEBUGGED_BACKPROP)
    # The old contradiction: claim no eval ran while showing candidate rows.
    assert "No candidate evaluation ran this cycle" not in body
    # Match Breakdown must reference the approach-comparison arena instead.
    assert "approach-comparison" in body


def test_body_includes_expected_sections_and_era_banner():
    state = _state_with_approach()
    body = es.build_body(state, _view_for(state), era=reporting_era.DEBUGGED_BACKPROP)
    for section in ("## Champion Composition", "## Approach Comparison",
                    "## Match Breakdown", "## Human Strength Estimate",
                    "Reporting era: Debugged MCTS backprop era"):
        assert section in body


def test_body_lists_graphic_artifacts_when_present(tmp_path):
    state = _state_with_approach()
    graphics = {
        "matchup_matrix": tmp_path / "matchup_matrix.png",
        "approach_comparison": tmp_path / "approach_comparison.png",
    }
    body = es.build_body(state, _view_for(state), era=reporting_era.DEBUGGED_BACKPROP,
                         graphics=graphics)
    assert "## Report Graphics" in body
    assert "matchup_matrix.png" in body
    assert "approach_comparison.png" in body


def test_human_estimate_labelled_approximate_and_confidence_scored():
    state = _state_with_approach()
    body = es.build_body(state, _view_for(state), era=reporting_era.DEBUGGED_BACKPROP)
    assert "Approximate" in body
    assert "Estimate confidence" in body


def test_plaintext_fallback_has_key_metrics():
    """The plain-text body (used by text-only clients) keeps the headline numbers."""
    state = _state_with_approach()
    body = es.build_body(state, _view_for(state), era=reporting_era.DEBUGGED_BACKPROP)
    assert "1377" in body                # current Elo
    assert "Generation: 142" in body
    assert "within noise floor" in body  # small change honestly labelled


def test_html_body_embeds_all_graphics_inline():
    graphics = {"matchup_matrix": "x.png", "approach_comparison": "y.png",
                "recent_deltas": "z.png"}
    html = es._html_body("body text", plot_inline=True, graphics=graphics)
    assert 'cid:elo-plot' in html
    assert 'cid:matchup-matrix' in html
    assert 'cid:approach-comparison' in html
    assert 'viewport' in html  # responsive on mobile-width clients


# ---------------------------------------------------------------------------
# Local preview command
# ---------------------------------------------------------------------------

def test_preview_generates_files_without_sending(tmp_path, monkeypatch):
    from training.reports import generate_latest_report as glr

    # Build a repo-shaped state tree the preview can load.
    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    conn = _seeded_db_at(paths)
    conn.close()
    import json
    paths.latest_json.write_text(json.dumps(_state_with_approach()), encoding="utf-8")

    out_dir = tmp_path / "preview_out"
    manifest = glr.generate_preview(out_dir, era=reporting_era.DEBUGGED_BACKPROP,
                                    paths=paths)
    assert manifest["html"].exists()
    assert manifest["body_md"].exists()
    html = manifest["html"].read_text(encoding="utf-8")
    assert "Champion Elo trajectory" in html or "preview" in html.lower()
    # Plain-text markdown carries the subject + body.
    assert "Subject:" in manifest["body_md"].read_text(encoding="utf-8")


def _seeded_db_at(paths):
    conn = ratings_db.connect(paths.ratings_db)
    _record(conn, PRE, 100, 1600.0, 500)
    _record(conn, CUTOFF, 139, 1224.0, 1300)
    _record(conn, POST1, 140, 1200.0, 1400, promoted=True,
            agents={"heuristic": 950.0, "random": 760.0})
    _record(conn, POST2, 142, 1377.0, 1500,
            agents={"heuristic": 950.0, "random": 760.0})
    return conn
