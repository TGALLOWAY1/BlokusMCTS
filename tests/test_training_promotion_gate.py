"""Tests for the promotion gate + benchmark pool + winner selection."""

from __future__ import annotations

from types import SimpleNamespace

from training.evaluation.benchmark_pool import build_benchmark_pool
from training.evaluation.head_to_head import _candidate_arenas
from training.evaluation.head_to_head import (
    EVAL_CONFIRM_TOTAL_GAMES,
    EVAL_MIN_TOTAL_GAMES,
    CandidateEval,
    confirm_games_per_arena,
)
from training.evaluation.promotion_gate import (
    GateThresholds,
    evaluate_gate,
    select_winner,
)


def _decision(promote: bool, champion: str):
    crit = [{"name": "highest_ranking", "passed": promote, "detail": ""}]
    return SimpleNamespace(promote=promote, champion=champion, criteria=crit,
                           summary_line="x")


def _eval(name="cand", *, promote=True, cand_wins=30, champ_wins=10,
          elo_delta=20.0, mu_delta=1.0, games=80, n_seeds=2) -> CandidateEval:
    return CandidateEval(
        name=name, approach=f"{name}_approach", games=games, n_seeds=n_seeds,
        win_rate=0.5, win_rate_ci=(0.4, 0.6), avg_rank=1.5, rank_distribution={1: 40},
        avg_score=50.0, trueskill_mu=30.0, trueskill_sigma=2.0, elo=1300.0,
        champion_win_rate=0.3, champion_elo=1300.0 - elo_delta, champion_trueskill_mu=29.0,
        vs_champion={"candidate_wins": cand_wins, "champion_wins": champ_wins, "ties": 0},
        elo_delta_vs_champion=elo_delta, trueskill_mu_delta_vs_champion=mu_delta,
        decision=_decision(promote, name), runtime_s=1.0,
    )


def test_gate_passes_when_all_criteria_met():
    gr = evaluate_gate(_eval())
    assert gr.passed, gr.reason
    assert gr.reason.startswith("PROMOTE")


def test_gate_fails_when_conservative_decision_fails():
    gr = evaluate_gate(_eval(promote=False))
    assert not gr.passed
    assert "HOLD" in gr.reason
    assert "conservative_promotes_candidate" in gr.reason


def test_gate_explains_empty_failed_conservative_list():
    """Regression guard for reports that said ``failed []``.

    The lower-level gauntlet can return promote=False with no failed criterion
    when its top-ranked agent is not the candidate being evaluated. The wrapper
    must surface that as an explicit failed criterion.
    """
    ev = _eval(promote=False, games=20)
    ev.decision.criteria = []
    gr = evaluate_gate(ev, GateThresholds(min_total_games=20))
    failed = [c["name"] for c in gr.criteria if not c["passed"]]
    assert failed == ["conservative_promotes_candidate"]
    assert "failed ['conservative_promotes_candidate']" in gr.reason


def test_gate_fails_on_negative_elo_delta():
    gr = evaluate_gate(_eval(elo_delta=-5.0))
    assert not gr.passed
    names = [c["name"] for c in gr.criteria if not c["passed"]]
    assert "elo_improvement" in names


def test_gate_fails_when_not_beating_champion_head_to_head():
    gr = evaluate_gate(_eval(cand_wins=10, champ_wins=20))
    assert not gr.passed
    names = [c["name"] for c in gr.criteria if not c["passed"]]
    assert "beats_champion_head_to_head" in names


def test_gate_fails_on_insufficient_games():
    gr = evaluate_gate(_eval(games=10), GateThresholds(min_total_games=40))
    assert not gr.passed
    names = [c["name"] for c in gr.criteria if not c["passed"]]
    assert "min_total_games" in names


def test_positive_candidate_with_insufficient_games_does_not_promote():
    gr = evaluate_gate(
        _eval(cand_wins=2, champ_wins=0, elo_delta=80.0, mu_delta=2.0, games=2),
        GateThresholds(min_total_games=20),
    )
    assert not gr.passed
    assert "min_total_games" in [c["name"] for c in gr.criteria if not c["passed"]]


def test_candidate_with_enough_games_and_clear_win_rate_promotes():
    gr = evaluate_gate(
        _eval(cand_wins=16, champ_wins=4, elo_delta=90.0, mu_delta=3.0, games=20),
        GateThresholds(min_total_games=20),
    )
    assert gr.passed


def test_noop_promotion_when_result_inconclusive():
    gr = evaluate_gate(
        _eval(cand_wins=10, champ_wins=10, elo_delta=0.0, mu_delta=0.0, games=20),
        GateThresholds(min_total_games=20),
    )
    assert not gr.passed
    failed = [c["name"] for c in gr.criteria if not c["passed"]]
    assert "beats_champion_head_to_head" in failed
    assert "trueskill_improvement" in failed


def test_gate_fails_on_weak_trueskill_delta():
    gr = evaluate_gate(_eval(mu_delta=0.1), GateThresholds(min_mu_delta=0.5))
    assert not gr.passed
    names = [c["name"] for c in gr.criteria if not c["passed"]]
    assert "trueskill_improvement" in names


def test_select_winner_picks_best_passing():
    weak = _eval(name="weak", mu_delta=0.6, elo_delta=5.0)
    strong = _eval(name="strong", mu_delta=2.5, elo_delta=40.0)
    sel = select_winner([weak, strong])
    assert sel["winner"].name == "strong"
    assert sel["winner_gate"].passed


def test_select_winner_none_when_nobody_passes():
    sel = select_winner([_eval(promote=False), _eval(name="b", elo_delta=-1.0)])
    assert sel["winner"] is None


def test_benchmark_pool_has_anchors_and_fixed_seeds():
    pool = build_benchmark_pool({
        "checkpoints": [],
        "champion_params": {"type": "mcts", "thinking_time_ms": 500, "params": {}},
    })
    names = pool.opponent_names()
    assert "heuristic" in names and "random" in names
    assert "baseline_mcts_fast" in names
    assert "baseline_mcts_strong" in names
    assert len(pool.seeds) >= 2
    # No historical checkpoint -> no best_historical opponent.
    assert "best_historical" not in names


def test_evaluate_candidates_skips_when_over_budget(tmp_path):
    """A past deadline must skip every candidate without running any arena."""
    import time
    from types import SimpleNamespace

    from training import TrainingPaths
    from training.evaluation.head_to_head import evaluate_candidates

    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    pool = build_benchmark_pool({"checkpoints": []})
    cand = SimpleNamespace(created=True, name="x", approach="x_approach",
                           agent_config={"type": "mcts", "params": {}})
    state = {"champion_params": {"type": "mcts", "thinking_time_ms": 1, "params": {}}}
    res = evaluate_candidates(state, [cand], pool, paths, games_per_arena=2,
                              seeds=[1, 2], deadline=time.monotonic() - 1)
    assert res.candidate_evals == []
    assert res.skipped_for_budget == ["x"]


def test_benchmark_pool_includes_best_historical_when_present():
    state = {"champion_params": {"type": "mcts", "params": {}}, "checkpoints": [
        {"rating": {"mu": 20.0}, "params": {"type": "mcts", "params": {}}},
        {"rating": {"mu": 35.0}, "params": {"type": "mcts", "params": {"x": 1}}},
    ]}
    pool = build_benchmark_pool(state)
    assert "best_historical" in pool.opponent_names()


def test_confirm_games_per_arena_reaches_target_floor():
    # Two-stage promotion: the confirmation stage must schedule enough games to
    # reach the higher confirmation floor over (arenas × seeds) batteries.
    state = {"champion_params": {"type": "mcts", "thinking_time_ms": 1, "params": {}}}
    pool = build_benchmark_pool(state)
    seeds = [1, 2]
    cfg = {"type": "mcts", "thinking_time_ms": 1, "params": {}}
    gpa = confirm_games_per_arena(state, cfg, "cand", pool, seeds=seeds)
    n_arenas = len(_candidate_arenas(state, cfg, "cand", pool))
    assert gpa * n_arenas * len(seeds) >= EVAL_CONFIRM_TOTAL_GAMES
    # Confirmation is a strictly larger sample than the cheap screen.
    assert EVAL_CONFIRM_TOTAL_GAMES > EVAL_MIN_TOTAL_GAMES


def test_confirmation_gate_holds_short_winner():
    # A candidate that passed the 20-game screen but only has 20 confirmation games
    # must FAIL the confirmation gate (which requires the higher floor).
    screen_ok = _eval(cand_wins=16, champ_wins=4, elo_delta=90.0, mu_delta=3.0, games=20)
    assert evaluate_gate(screen_ok, GateThresholds(min_total_games=20)).passed
    confirm = evaluate_gate(
        screen_ok, GateThresholds(min_total_games=EVAL_CONFIRM_TOTAL_GAMES))
    assert not confirm.passed
    assert "min_total_games" in [c["name"] for c in confirm.criteria if not c["passed"]]


def test_confirmation_gate_passes_with_enough_games():
    strong = _eval(cand_wins=45, champ_wins=15, elo_delta=90.0, mu_delta=3.0,
                   games=EVAL_CONFIRM_TOTAL_GAMES)
    assert evaluate_gate(
        strong, GateThresholds(min_total_games=EVAL_CONFIRM_TOTAL_GAMES)).passed


def test_candidate_arenas_cover_weak_and_mcts_anchor_pairs():
    state = {"champion_params": {"type": "mcts", "thinking_time_ms": 1, "params": {}}}
    pool = build_benchmark_pool(state)
    arenas = _candidate_arenas(
        state,
        {"type": "mcts", "thinking_time_ms": 1, "params": {}},
        "candidate_x",
        pool,
    )
    opponent_pairs = [{arena[2]["name"], arena[3]["name"]} for arena in arenas]
    assert {"heuristic", "random"} in opponent_pairs
    assert {"baseline_mcts_fast", "baseline_mcts_strong"} in opponent_pairs
