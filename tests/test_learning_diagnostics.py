"""Tests for learning-process diagnostics (training/learning_diagnostics.py)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import learning_diagnostics as ld


def _artifact(weights_by_phase):
    return {
        "rich_phase_weights": {
            phase: {"weights": w, "bias": 0.0, "trained": True}
            for phase, w in weights_by_phase.items()
        }
    }


def test_feature_importance_ranks_by_abs_weight():
    art = _artifact({"early": {"a": 0.1, "b": -0.9, "c": 0.3}})
    ranked = ld.feature_importance(art, "early")
    assert ranked[0][0] == "b"  # largest magnitude
    assert ranked[0][1] == 0.9
    assert [n for n, _ in ranked] == ["b", "c", "a"]


def test_feature_importance_top_k():
    art = _artifact({"mid": {"a": 0.5, "b": 0.4, "c": 0.3}})
    assert len(ld.feature_importance(art, "mid", top=2)) == 2


def test_weight_drift_measures_movement():
    prev = _artifact({"early": {"a": 0.0, "b": 1.0}})
    new = _artifact({"early": {"a": 0.5, "b": 1.0}})
    drift = ld.weight_drift(prev, new, "early")
    assert abs(drift.l2_drift - 0.5) < 1e-9
    assert drift.fastest_changing[0][0] == "a"
    assert drift.cosine_similarity <= 1.0 + 1e-9


def test_history_roundtrip_and_correlation(tmp_path):
    path = tmp_path / "learning_history.jsonl"
    # Construct a clean negative relationship: lower loss → higher mu.
    data = [(0.9, 20.0), (0.7, 22.0), (0.5, 24.0), (0.3, 26.0)]
    for i, (loss, mu) in enumerate(data):
        ld.record_learning_event(
            path, run_id=f"r{i}", learning_method="td", td_loss=loss,
            candidate_trueskill_mu=mu, promoted=(mu > 23),
        )
    hist = ld.load_learning_history(path)
    assert len(hist) == 4
    corr = ld.loss_to_strength_correlation(hist)
    assert corr["n"] == 4
    assert corr["pearson"] < -0.9  # strong negative (loss down, strength up)


def test_correlation_insufficient_data():
    corr = ld.loss_to_strength_correlation([{"td_loss": 0.5, "candidate_trueskill_mu": 20}])
    assert corr["pearson"] is None
    assert corr["n"] == 1


def test_render_feature_importance_smoke():
    art = _artifact({"early": {"a": 0.5}, "mid": {"b": 0.2}, "late": {"c": 0.1}})
    md = ld.render_feature_importance(art, top=5)
    assert "Feature Importance" in md and "early" in md
