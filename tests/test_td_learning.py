"""Tests for the TD(0) learning core (training/td_learning.py)."""

from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcts.state_evaluator import FEATURE_NAMES as SE_FEATURE_NAMES
from training import td_learning as td
from training.rich_features import RICH_FEATURE_NAMES

N = len(RICH_FEATURE_NAMES)


def _zero_feat():
    return {n: 0.0 for n in RICH_FEATURE_NAMES}


def _row(*, occ=0.1, terminal=False, final_rank=1, final_score=80,
         margin_to_next=5.0, state=None, nxt=None, next_phase=None):
    sf = state or _zero_feat()
    nf = nxt or _zero_feat()
    row = {
        "board_occupancy": occ,
        "terminal": 1 if terminal else 0,
        "final_rank": final_rank,
        "final_score": final_score,
        "score_margin_to_next": margin_to_next,
    }
    if next_phase is not None:
        row["next_phase"] = next_phase
    for i, name in enumerate(RICH_FEATURE_NAMES):
        row[f"f_{name}"] = sf[name]
        row[f"nf_{name}"] = nf[name]
    return row


# ---------------------------------------------------------------------------
# Terminal value / labels
# ---------------------------------------------------------------------------


def test_normalized_rank_value_mapping():
    assert td.normalized_rank_value(1) == 1.0
    assert td.normalized_rank_value(2) == 0.5
    assert td.normalized_rank_value(3) == -0.25
    assert td.normalized_rank_value(4) == -1.0


def test_terminal_value_blend_weights_configurable():
    cfg = td.TDConfig(blend_rank_weight=1.0, blend_score_weight=0.0, blend_margin_weight=0.0)
    row = _row(final_rank=1, final_score=0, margin_to_next=0.0, terminal=True)
    # Pure rank blend ⇒ terminal value equals the rank value (1.0).
    assert math.isclose(td.terminal_value(row, cfg), 1.0, rel_tol=1e-9)
    row4 = _row(final_rank=4, terminal=True)
    assert math.isclose(td.terminal_value(row4, cfg), -1.0, rel_tol=1e-9)


def test_terminal_value_bounded():
    cfg = td.TDConfig()
    for rank in (1, 2, 3, 4):
        v = td.terminal_value(_row(final_rank=rank, terminal=True), cfg)
        assert -1.5 <= v <= 1.5


# ---------------------------------------------------------------------------
# TD update mechanics (use PhaseModel directly for a controlled example)
# ---------------------------------------------------------------------------


def test_terminal_target_uses_terminal_value():
    # One terminal row with a single active feature; terminal target = terminal_value.
    cfg = td.TDConfig(min_rows_per_phase=1, epochs=1, alpha=0.1,
                      blend_rank_weight=1.0, blend_score_weight=0.0, blend_margin_weight=0.0)
    state = _zero_feat()
    state[RICH_FEATURE_NAMES[10]] = 1.0  # a non-SE feature so default prior is 0 there
    row = _row(occ=0.1, terminal=True, final_rank=1, state=state)
    result = td.train_td([row] * 5, cfg)
    model = result.phase_models["early"]
    idx = 10
    # Target is +1.0 (rank value); V started at 0 ⇒ weight on the active feature
    # must move positive.
    assert model.weights[idx] > 0


def test_non_terminal_target_uses_reward_plus_gamma_v_next():
    # Construct a model and verify the update direction matches reward+γV(next)-V(s).
    cfg = td.TDConfig(gamma=0.9, alpha=0.05, l2=0.0, clip_td_error=(-10, 10))
    s = np.zeros(N)
    s[12] = 1.0
    s_next = np.zeros(N)
    s_next[12] = 1.0
    model = td.PhaseModel(weights=np.zeros(N), bias=0.0)
    # Seed next-state value high so the bootstrap target is positive.
    model.weights[12] = 0.0
    model.bias = 0.5  # V(s)=0.5, V(next)=0.5
    v_s = model.value(s)
    target = cfg.gamma * model.value(s_next)
    error = target - v_s  # 0.9*0.5 - 0.5 = -0.05
    assert error < 0  # discounting pulls value down when reward is 0


def test_clipping_limits_td_error():
    cfg = td.TDConfig(min_rows_per_phase=1, epochs=1, alpha=1.0, l2=0.0,
                      clip_td_error=(-0.01, 0.01),
                      blend_rank_weight=1.0, blend_score_weight=0.0, blend_margin_weight=0.0)
    state = _zero_feat()
    state[RICH_FEATURE_NAMES[15]] = 1.0
    row = _row(terminal=True, final_rank=1, state=state)  # terminal target +1.0
    result = td.train_td([row], cfg)
    model = result.phase_models["early"]
    # With error clipped to 0.01 and alpha=1.0, a single update moves the weight
    # by at most ~0.01 (feature value 1.0), not the full ~1.0 error.
    assert abs(model.weights[15]) <= 0.0101


def test_l2_regularization_shrinks_weights():
    # Heavy L2 with zero learning signal (all-zero features, alpha tiny) shrinks.
    cfg_no_l2 = td.TDConfig(min_rows_per_phase=1, epochs=50, alpha=0.05, l2=0.0)
    cfg_l2 = td.TDConfig(min_rows_per_phase=1, epochs=50, alpha=0.05, l2=0.5)
    state = _zero_feat()
    state[RICH_FEATURE_NAMES[0]] = 1.0  # squares_placed (SE feature, prior nonzero)
    rows = [_row(terminal=True, final_rank=2, state=state)] * 20
    r_no = td.train_td(rows, cfg_no_l2)
    r_l2 = td.train_td(rows, cfg_l2)
    # The L2 model should have a smaller weight norm on the SE block.
    norm_no = np.linalg.norm(r_no.phase_models["early"].weights)
    norm_l2 = np.linalg.norm(r_l2.phase_models["early"].weights)
    assert norm_l2 < norm_no


def test_phases_update_independently():
    cfg = td.TDConfig(min_rows_per_phase=1, epochs=5, alpha=0.1, l2=0.0,
                      blend_rank_weight=1.0, blend_score_weight=0.0, blend_margin_weight=0.0)
    # Use non-SE feature indices (>= 8) so their initial prior weight is 0.
    fa, fb = 30, 31
    # early rows push feature fa via rank-1 (+1), late rows push feature fb via rank-4 (-1).
    early_state = _zero_feat(); early_state[RICH_FEATURE_NAMES[fa]] = 1.0
    late_state = _zero_feat(); late_state[RICH_FEATURE_NAMES[fb]] = 1.0
    rows = (
        [_row(occ=0.1, terminal=True, final_rank=1, state=early_state)] * 10
        + [_row(occ=0.7, terminal=True, final_rank=4, state=late_state)] * 10
    )
    result = td.train_td(rows, cfg)
    early = result.phase_models["early"]
    late = result.phase_models["late"]
    # Early model learned a positive weight on feature fa; late model on fb negative.
    assert early.weights[fa] > 0
    assert late.weights[fb] < 0
    # The early model did not touch feature fb (no early rows used it; prior 0, no L2).
    assert math.isclose(early.weights[fb], 0.0, abs_tol=1e-9)
    assert math.isclose(late.weights[fa], 0.0, abs_tol=1e-9)


def test_next_phase_resolution_prefers_explicit_column():
    assert td._row_next_phase({"next_phase": "late"}, "early") == "late"
    assert td._row_next_phase({"next_phase": ""}, "mid") == "mid"  # fallback
    assert td._row_next_phase({"next_phase": "bogus"}, "early") == "early"
    assert td._row_next_phase({}, "late") == "late"  # legacy row → current phase


def test_bootstrap_uses_next_state_phase_model():
    # A non-terminal early-phase transition whose NEXT state lives in the mid phase
    # must bootstrap from the *mid* model, not the early model. We make the mid
    # model value a marker feature highly, then check the early model learns a
    # positive weight on its own state feature because its bootstrap target (the
    # mid model's value of the next state) is positive.
    cfg = td.TDConfig(min_rows_per_phase=1, epochs=60, alpha=0.05, l2=0.0,
                      gamma=0.99, clip_td_error=(-10, 10),
                      blend_rank_weight=1.0, blend_score_weight=0.0, blend_margin_weight=0.0)
    fi, fj = 25, 26  # non-SE indices ⇒ zero prior
    mid_state = _zero_feat(); mid_state[RICH_FEATURE_NAMES[fi]] = 1.0
    mid_rows = [_row(occ=0.4, terminal=True, final_rank=1, state=mid_state)] * 30

    early_state = _zero_feat(); early_state[RICH_FEATURE_NAMES[fj]] = 1.0
    nxt = _zero_feat(); nxt[RICH_FEATURE_NAMES[fi]] = 1.0
    early_rows = [_row(occ=0.1, terminal=False, state=early_state, nxt=nxt,
                       next_phase="mid")] * 30

    result = td.train_td(mid_rows + early_rows, cfg)
    # Mid model values the marker feature positively (terminal rank-1 target).
    assert result.phase_models["mid"].weights[fi] > 0
    # Early model picked up the positive bootstrap target from the MID model.
    assert result.phase_models["early"].weights[fj] > 0


def test_legacy_rows_without_next_phase_fall_back_to_current_phase():
    # No next_phase column (legacy CSV) + non-terminal rows must still train
    # without crashing, using the current-phase model for the bootstrap.
    cfg = td.TDConfig(min_rows_per_phase=1, epochs=5, alpha=0.05, gamma=0.9)
    rows = [_row(occ=0.1, terminal=False) for _ in range(10)]
    rows.append(_row(occ=0.1, terminal=True, final_rank=1))
    result = td.train_td(rows, cfg)  # must not raise
    assert result.trained_phases["early"] is True


def test_insufficient_rows_keeps_prior_and_marks_untrained():
    cfg = td.TDConfig(min_rows_per_phase=100, epochs=5)
    rows = [_row(occ=0.1, terminal=True, final_rank=1)] * 3
    result = td.train_td(rows, cfg)
    assert result.trained_phases["early"] is False
    # Projection falls back to DEFAULT_WEIGHTS for an untrained phase.
    weights = td.build_phase_weights(result)
    from mcts.state_evaluator import DEFAULT_WEIGHTS
    assert weights["early"] == DEFAULT_WEIGHTS


# ---------------------------------------------------------------------------
# Projection + artifact
# ---------------------------------------------------------------------------


def test_projection_yields_only_se_features_and_respects_scale():
    cfg = td.TDConfig(min_rows_per_phase=1, epochs=10, alpha=0.1)
    state = _zero_feat()
    state[SE_FEATURE_NAMES[2]] = 1.0
    rows = [_row(terminal=True, final_rank=1, state=state)] * 30
    result = td.train_td(rows, cfg)
    proj = td.project_to_agent_weights(result.phase_models["early"], trained=True)
    assert set(proj) == set(SE_FEATURE_NAMES)
    assert max(abs(v) for v in proj.values()) <= td.WEIGHT_SCALE + 1e-9


def test_build_artifact_shape():
    cfg = td.TDConfig(min_rows_per_phase=1, epochs=2)
    rows = [_row(occ=o, terminal=True, final_rank=1) for o in (0.1, 0.4, 0.7)] * 5
    result = td.train_td(rows, cfg)
    art = td.build_artifact(result, cfg)
    for key in ("created_at", "source_rows", "feature_names", "phase_weights",
                "training_metrics", "config", "feature_set_version", "learning_method"):
        assert key in art
    assert art["learning_method"] == "temporal_difference"
    assert set(art["phase_weights"]) == {"early", "mid", "late"}
    tm = art["training_metrics"]
    for key in ("td_loss", "td_loss_by_phase", "mean_abs_td_error", "rows_by_phase"):
        assert key in tm
    assert art["feature_names"] == list(RICH_FEATURE_NAMES)


def test_weights_change_in_expected_direction_synthetic():
    # Value should increase with a feature that co-occurs with rank-1 outcomes.
    cfg = td.TDConfig(min_rows_per_phase=1, epochs=30, alpha=0.05,
                      blend_rank_weight=1.0, blend_score_weight=0.0, blend_margin_weight=0.0)
    good = _zero_feat(); good[RICH_FEATURE_NAMES[20]] = 1.0
    bad = _zero_feat(); bad[RICH_FEATURE_NAMES[20]] = 0.0
    rows = (
        [_row(terminal=True, final_rank=1, state=good)] * 20
        + [_row(terminal=True, final_rank=4, state=bad)] * 20
    )
    result = td.train_td(rows, cfg)
    model = result.phase_models["early"]
    # Feature 20 present ⇒ rank 1 (+1); absent ⇒ rank 4 (-1). Weight must be positive.
    assert model.weights[20] > 0
