"""Tests for deterministic diagnostics detectors + always-writes-a-file."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import TrainingPaths, diagnostics, ratings_db
from training import state_store


def _series(elos):
    return [{"elo": e, "total_games": (i + 1) * 100} for i, e in enumerate(elos)]


def test_detect_regression_fires_on_drop():
    findings = diagnostics.detect_regression(_series([1400, 1410, 1420, 1380]))
    assert any(f.code == "regression" for f in findings)


def test_detect_regression_quiet_when_stable():
    assert diagnostics.detect_regression(_series([1400, 1405, 1410, 1412])) == []


def test_detect_stagnation_fires_on_flat():
    findings = diagnostics.detect_stagnation(_series([1500] * 7))
    assert any(f.code == "stagnation" for f in findings)


def test_detect_stagnation_quiet_when_moving():
    findings = diagnostics.detect_stagnation(_series([1500, 1510, 1520, 1530, 1540, 1550, 1560]))
    assert findings == []


def test_detect_promotion_drought():
    assert diagnostics.detect_promotion_drought(5, 20) != []
    assert diagnostics.detect_promotion_drought(18, 20) == []


def test_detect_refit_pending():
    findings = diagnostics.detect_refit_health({"total_snapshot_rows": 10})
    assert any(f.code == "refit_pending" for f in findings)
    assert diagnostics.detect_refit_health({"total_snapshot_rows": 9999}) == []


def test_write_diagnosis_always_writes(tmp_path):
    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    conn = ratings_db.connect(paths.ratings_db)
    state = state_store.default_latest_state()
    state["run_id"] = "testrun"
    findings = diagnostics.write_diagnosis(paths, conn, state)
    assert paths.diagnosis_md.exists()
    text = paths.diagnosis_md.read_text()
    # Empty timeline => mostly info findings; file still written with content.
    assert "Diagnosis" in text
    assert isinstance(findings, list)


def test_render_diagnosis_no_findings():
    text = diagnostics.render_diagnosis([], {"run_id": "r", "generation": 0})
    assert "No issues detected" in text
