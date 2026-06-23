"""Tests for deterministic diagnostics detectors + always-writes-a-file."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import TrainingPaths, diagnostics, ratings_db
from training import state_store


def _series(elos):
    return [
        {"elo": e, "total_games": (i + 1) * 100, "run_id": f"run{i + 1}"}
        for i, e in enumerate(elos)
    ]


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


def test_detect_stale_elo_fires_on_identical_values():
    # Exactly identical Elo across 3 runs = the repeated-Elo bug signature.
    findings = diagnostics.detect_stale_elo(_series([1174.56, 1174.56, 1174.56]))
    assert any(f.code == "stale_elo" for f in findings)


def test_detect_stale_elo_quiet_on_tiny_jitter():
    # A genuinely live-but-flat agent still jitters; that must NOT trip the alarm.
    findings = diagnostics.detect_stale_elo(_series([1174.5, 1174.7, 1174.4]))
    assert findings == []


def test_detect_stale_elo_quiet_with_too_few_runs():
    assert diagnostics.detect_stale_elo(_series([1200.0, 1200.0])) == []


def test_detect_metrics_not_updated_fires_when_run_missing():
    series = _series([1000.0, 1010.0])  # latest run_id == "run2"
    findings = diagnostics.detect_metrics_not_updated(series, {"run_id": "run3"})
    assert any(f.code == "metrics_not_updated" for f in findings)


def test_detect_metrics_not_updated_quiet_when_recorded():
    series = _series([1000.0, 1010.0])
    assert diagnostics.detect_metrics_not_updated(series, {"run_id": "run2"}) == []


def test_collect_findings_flags_stale_elo_end_to_end(tmp_path):
    """A DB with three byte-identical champion Elos must surface a stale_elo warn."""
    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    conn = ratings_db.connect(paths.ratings_db)
    for i in range(3):
        ratings_db.record_run(
            conn, run_id=f"run{i + 1}", timestamp=f"2026-06-2{i}T04:00:00Z",
            generation=i + 1,
            agent_rows=[ratings_db.AgentRatingRow("champion", 1174.56, 28.0, 2.3, 23.0, 10)],
            run_summary=ratings_db.RunSummaryRow(i + 1, 10, 10 * (i + 1), 1174.56, 28.0, 2.3, False, 1),
        )
    state = state_store.default_latest_state()
    state["run_id"] = "run3"
    findings = diagnostics.collect_findings(conn, state)
    assert any(f.code == "stale_elo" for f in findings)


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
