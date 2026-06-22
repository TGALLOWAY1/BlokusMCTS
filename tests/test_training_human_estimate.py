"""Tests for human-strength estimation — especially the no-fabrication rule."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import human_estimate as he


def _series(elos, games_step=100):
    return [
        {"elo": e, "total_games": (i + 1) * games_step}
        for i, e in enumerate(elos)
    ]


def test_classify_strength_boundaries():
    assert he.classify_strength(1199) == "below-beginner"
    assert he.classify_strength(1200) == "beginner"
    assert he.classify_strength(1499) == "beginner"
    assert he.classify_strength(1500) == "intermediate"
    assert he.classify_strength(1699) == "intermediate"
    assert he.classify_strength(1700) == "strong-or-above"


def test_current_gap():
    assert he.current_gap(1500, target=1700) == 200
    assert he.current_gap(1750, target=1700) == -50


def test_elo_gain_rate_none_with_too_few_points():
    assert he.elo_gain_rate(_series([1200]), by="day") is None
    assert he.elo_gain_rate([], by="day") is None


def test_elo_gain_rate_positive_trend():
    rate = he.elo_gain_rate(_series([1200, 1210, 1220, 1230]), by="day")
    assert rate is not None
    assert rate.mean_gain == 10.0
    assert rate.is_reliable


def test_estimate_no_fabrication_on_flat_trend():
    series = _series([1300, 1300, 1300, 1300])
    rate = he.elo_gain_rate(series, by="day")
    est = he.estimate_to_target(1300, rate, target=1700)
    assert est["confidence"] == "none"
    assert est["days_remaining"] is None
    assert est["games_remaining"] is None
    assert "No measurable upward" in est["caveat"]


def test_estimate_no_fabrication_on_negative_trend():
    series = _series([1400, 1380, 1360])
    rate = he.elo_gain_rate(series, by="day")
    est = he.estimate_to_target(1360, rate, target=1700)
    assert est["confidence"] == "none"
    assert est["days_remaining"] is None


def test_estimate_low_confidence_with_few_points():
    series = _series([1500, 1520, 1540])  # 2 gains -> low
    rate = he.elo_gain_rate(series, by="day")
    est = he.estimate_to_target(1540, rate, target=1700)
    assert est["confidence"] == "low"
    assert est["days_remaining"] is not None
    assert est["days_remaining"] > 0


def test_estimate_medium_confidence_with_many_points():
    elos = [1400 + 10 * i for i in range(9)]  # 8 gains -> medium
    series = _series(elos)
    current = elos[-1]
    rate = he.elo_gain_rate(series, by="day", window=10)
    est = he.estimate_to_target(current, rate, target=1700)
    assert est["confidence"] == "medium"
    assert est["lower_bound"] is not None or est["days_remaining"] is not None


def test_estimate_already_at_target():
    est = he.estimate_to_target(1750, None, target=1700)
    assert est["confidence"] == "high"
    assert est["days_remaining"] == 0


def test_summarize_bundle():
    series = _series([1450, 1470, 1490])
    out = he.summarize(1490, series, target=1700)
    assert out["strength"] == "beginner"
    assert out["current_elo"] == 1490
    assert "gap" in out
