"""Tests for status.md rendering (pure, no disk)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import status_report
from training.diagnostics import Finding


def _data():
    return {
        "state": {
            "run_id": "20260621T0300Z",
            "generation": 41,
            "total_games": 184250,
            "games_today": 1820,
            "days_trained": 41,
            "elo": 1420.0,
            "trueskill_mu": 28.1,
            "trueskill_sigma": 2.3,
            "champion": {"name": "champion", "version": "gen41"},
            "human_target_elo": 1700,
            "last_error": None,
        },
        "human_estimate": {
            "strength": "intermediate",
            "current_elo": 1420.0,
            "target_elo": 1700.0,
            "gap": 280.0,
            "days_remaining": 23.0,
            "games_remaining": None,
            "lower_bound": 18.0,
            "upper_bound": 30.0,
            "confidence": "low",
            "caveat": "Few data points.",
        },
        "elo_series": [{"elo": 1400, "total_games": 1}, {"elo": 1420, "total_games": 2}],
        "window7": [
            {"champion_elo": 1400, "champion_mu": 27.0},
            {"champion_elo": 1420, "champion_mu": 28.1},
        ],
        "window30": [
            {"champion_elo": 1380, "champion_mu": 26.0},
            {"champion_elo": 1420, "champion_mu": 28.1},
        ],
        "findings": [Finding("warn", "regression", "Elo dropped 30.")],
        "baselines": [
            {"agent": "candidate", "win_rate": 0.56, "games": 100},
            {"agent": "heuristic", "win_rate": 0.71, "games": 100},
        ],
    }


def test_render_status_has_all_six_sections():
    md = status_report.render_status(_data())
    for section in (
        "## Summary",
        "## Daily Progress",
        "## Baseline Results",
        "## Human Strength Estimate",
        "## Training Trends",
        "## Risks",
    ):
        assert section in md


def test_render_status_has_strength_and_experiment_sections():
    data = _data()
    data["strength"] = {
        "current_elo": 1420.0, "current_mu": 28.1, "current_sigma": 2.3,
        "best_elo": 1450.0, "best_mu": 29.0, "runs": 10, "promotions": 3,
        "promotion_frequency": 0.3, "improvement_rate": 4.2,
    }
    data["experiment"] = {
        "experiment_id": "exp_abc", "date": "2026-06-24T00:00:00Z",
        "baseline": "regression", "candidate": "td",
        "candidate_win_rate": 0.55, "baseline_win_rate": 0.48,
        "candidate_avg_rank": 1.9, "baseline_avg_rank": 2.1,
        "trueskill_mu_delta": 0.6, "total_games": 200,
        "recommendation": "ADOPT candidate",
    }
    md = status_report.render_status(data)
    assert "## Strength" in md
    assert "## Experiments" in md
    assert "Best historical Elo" in md
    assert "1450" in md                  # best historical elo
    assert "ADOPT candidate" in md       # experiment recommendation
    assert "30.0%" in md                 # promotion frequency


def test_render_status_experiment_absent_message():
    data = _data()
    data["experiment"] = None
    md = status_report.render_status(data)
    assert "No candidate comparison experiment has been run yet" in md


def test_render_status_includes_key_numbers():
    md = status_report.render_status(_data())
    assert "1420" in md          # Elo
    assert "184,250" in md       # total games
    assert "71.0%" in md         # heuristic baseline
    assert "regression" in md    # risk surfaced


def test_render_status_handles_no_baselines():
    data = _data()
    data["baselines"] = []
    md = status_report.render_status(data)
    assert "No candidate evaluation ran" in md


def test_render_status_no_risks_message():
    data = _data()
    data["findings"] = [Finding("info", "refit_pending", "waiting")]
    md = status_report.render_status(data)
    assert "No regressions" in md
