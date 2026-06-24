"""Tests for the rich-feature normalisation audit (training/feature_audit.py)."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import feature_audit as fa
from training.rich_features import RICH_FEATURE_NAMES

N = len(RICH_FEATURE_NAMES)


def test_clean_matrix_has_no_warnings():
    rng = np.random.default_rng(0)
    matrix = rng.uniform(0.0, 1.0, size=(300, N))
    report = fa.summarize_features(matrix)
    assert report.ok
    assert report.n_samples == 300
    assert len(report.stats) == N


def test_detects_nan_and_inf():
    matrix = np.zeros((10, N))
    matrix[0, 3] = np.nan
    matrix[1, 3] = np.inf
    report = fa.summarize_features(matrix)
    assert not report.ok
    crit = [f for f in report.findings if f["severity"] == "critical"]
    assert any(f["feature"] == RICH_FEATURE_NAMES[3] for f in crit)


def test_detects_out_of_range():
    matrix = np.zeros((10, N))
    matrix[:, 5] = 50.0  # way outside [-1, 1]
    report = fa.summarize_features(matrix)
    assert not report.ok
    assert any(f["feature"] == RICH_FEATURE_NAMES[5] and f["severity"] == "warn"
               for f in report.findings)


def test_detects_dominant_feature():
    rng = np.random.default_rng(1)
    matrix = rng.uniform(0.0, 0.01, size=(300, N))  # tiny variance everywhere
    matrix[:, 7] = rng.uniform(-1.0, 1.0, size=300)  # one big-variance feature
    report = fa.summarize_features(matrix)
    assert any(f["feature"] == RICH_FEATURE_NAMES[7]
               and "variance" in f["message"] for f in report.findings)


def test_name_count_mismatch_raises():
    try:
        fa.summarize_features(np.zeros((3, 4)), names=["a", "b"])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_real_features_are_well_normalised():
    # The actual rich feature extractor on random boards must satisfy the
    # bounded-and-finite contract — no NaN/inf, no out-of-range, no dominance.
    report = fa.audit_random_states(num_boards=120, seed=7)
    assert report.n_samples > 0
    critical = [f for f in report.findings if f["severity"] == "critical"]
    assert not critical, f"non-finite features leaked: {critical}"
    warns = [f for f in report.findings if f["severity"] == "warn"]
    assert not warns, f"normalisation regressions: {warns}"


def test_render_report_smoke():
    rng = np.random.default_rng(2)
    report = fa.summarize_features(rng.uniform(0, 1, size=(50, N)))
    md = fa.render_report(report, top=5)
    assert "Feature statistics" in md
