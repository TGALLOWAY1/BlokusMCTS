"""Tests for the champion gauntlet harness (analytics.tournament.gauntlet).

These exercise the pure logic — config loading, confidence intervals, ranking,
promotion gates, and registry updates — with small deterministic mocks. They
never run a real tournament.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analytics.tournament.gauntlet import (
    DEFAULT_CANDIDATES,
    PromotionThresholds,
    aggregate_summary,
    build_leaderboard,
    build_registry_entry,
    config_hash,
    evaluate_promotion,
    load_candidate_config,
    pairwise_record,
    rank_candidates,
    update_registry,
)
from analytics.tournament.statistics import wilson_score_interval


# ---------------------------------------------------------------------------
# Mock game builders
# ---------------------------------------------------------------------------

AGENTS = ["alpha", "beta", "gamma", "delta"]


def _make_game(scores: dict[str, int], seat_order: list[str] | None = None) -> dict:
    """Build a minimal arena game record from a name->score mapping."""
    seat_order = seat_order or list(scores.keys())
    seat_assignment = {str(i + 1): name for i, name in enumerate(seat_order)}
    top = max(scores.values())
    winners = [name for name, s in scores.items() if s == top]
    final_scores = {
        str(i + 1): scores[name] for i, name in enumerate(seat_order)
    }
    return {
        "agent_scores": dict(scores),
        "final_scores": final_scores,
        "seat_assignment": seat_assignment,
        "winner_agents": winners,
        "is_tie": len(winners) > 1,
        "error": None,
    }


def _dominant_games(n: int = 20) -> list[dict]:
    """alpha wins outright every game; clear separation from the rest."""
    games = []
    for i in range(n):
        scores = {"alpha": 90, "beta": 70, "gamma": 60, "delta": 50}
        # rotate seats so seat bias isn't a confound
        order = AGENTS[i % 4:] + AGENTS[: i % 4]
        games.append(_make_game(scores, seat_order=order))
    return games


def _tied_games(n: int = 20) -> list[dict]:
    """Everyone scores identically — fully inconclusive."""
    games = []
    for i in range(n):
        scores = {"alpha": 70, "beta": 70, "gamma": 70, "delta": 70}
        order = AGENTS[i % 4:] + AGENTS[: i % 4]
        games.append(_make_game(scores, seat_order=order))
    return games


def _summary(games: list[dict]) -> dict:
    return aggregate_summary(
        games,
        agent_names=AGENTS,
        thinking_time_ms_by_agent={a: 500 for a in AGENTS},
        seeds=[1, 2],
    )


# ---------------------------------------------------------------------------
# Wilson confidence interval
# ---------------------------------------------------------------------------

def test_wilson_zero_trials_is_safe():
    ci = wilson_score_interval(0, 0)
    assert ci == {"lower": 0.0, "upper": 0.0, "center": 0.0}


def test_wilson_center_is_point_estimate():
    ci = wilson_score_interval(15, 30)
    assert ci["center"] == pytest.approx(0.5)
    assert 0.0 <= ci["lower"] < ci["center"] < ci["upper"] <= 1.0


def test_wilson_tightens_with_more_data():
    narrow = wilson_score_interval(60, 120)
    wide = wilson_score_interval(5, 10)
    narrow_width = narrow["upper"] - narrow["lower"]
    wide_width = wide["upper"] - wide["lower"]
    assert narrow_width < wide_width


def test_wilson_accepts_fractional_wins():
    # shared-win accounting can produce fractional win_points
    ci = wilson_score_interval(2.5, 10)
    assert ci["center"] == pytest.approx(0.25)
    assert ci["lower"] >= 0.0


# ---------------------------------------------------------------------------
# Candidate config loading
# ---------------------------------------------------------------------------

def test_default_candidate_configs_exist_and_load():
    repo_root = Path(__file__).resolve().parent.parent
    assert len(DEFAULT_CANDIDATES) == 4
    for name, rel_path in DEFAULT_CANDIDATES.items():
        agent = load_candidate_config(name, repo_root / rel_path)
        assert agent["name"] == name
        assert agent["type"] == "mcts"
        assert agent["thinking_time_ms"] == 500
        # metadata keys must be stripped out of params
        assert "description" not in agent["params"]
        assert "champion_version" not in agent["params"]
        assert "thinking_time_ms" not in agent["params"]
        # behavioural params survived
        assert agent["params"]["rollout_policy"] == "random"
        assert agent["config_hash"]


def test_config_hash_ignores_name():
    a = {"type": "mcts", "thinking_time_ms": 500, "params": {"x": 1}, "name": "a"}
    b = {"type": "mcts", "thinking_time_ms": 500, "params": {"x": 1}, "name": "b"}
    assert config_hash(a) == config_hash(b)


def test_config_hash_changes_with_params():
    a = {"type": "mcts", "thinking_time_ms": 500, "params": {"x": 1}}
    b = {"type": "mcts", "thinking_time_ms": 500, "params": {"x": 2}}
    assert config_hash(a) != config_hash(b)


def test_load_candidate_config_tmp(tmp_path):
    cfg = tmp_path / "cand.json"
    cfg.write_text(
        json.dumps(
            {
                "description": "meta",
                "champion_version": "z",
                "thinking_time_ms": 250,
                "rollout_policy": "random",
                "rave_k": 1000,
                "_private": "ignored",
            }
        )
    )
    agent = load_candidate_config("z", cfg)
    assert agent["thinking_time_ms"] == 250
    assert agent["params"] == {"rollout_policy": "random", "rave_k": 1000}


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def test_ranking_orders_by_conservative_then_win_rate():
    leaderboard = [
        {"name": "low", "trueskill_conservative": 1.0, "win_rate": 0.1},
        {"name": "high", "trueskill_conservative": 9.0, "win_rate": 0.9},
        {"name": "mid", "trueskill_conservative": 5.0, "win_rate": 0.5},
    ]
    ranked = rank_candidates(leaderboard)
    assert [r["name"] for r in ranked] == ["high", "mid", "low"]
    assert [r["rank"] for r in ranked] == [1, 2, 3]


def test_ranking_win_rate_tiebreak():
    leaderboard = [
        {"name": "a", "trueskill_conservative": 5.0, "win_rate": 0.3},
        {"name": "b", "trueskill_conservative": 5.0, "win_rate": 0.7},
    ]
    ranked = rank_candidates(leaderboard)
    assert ranked[0]["name"] == "b"


def test_dominant_agent_ranks_first_from_real_summary():
    summary = _summary(_dominant_games(24))
    ranked = rank_candidates(build_leaderboard(summary))
    assert ranked[0]["name"] == "alpha"
    assert ranked[0]["win_rate"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Pairwise records
# ---------------------------------------------------------------------------

def test_pairwise_record_orientation():
    summary = _summary(_dominant_games(20))
    rec = pairwise_record(summary, "alpha", "beta")
    assert rec["a_wins"] == 20
    assert rec["b_wins"] == 0
    # reversed orientation flips the counts
    rec_rev = pairwise_record(summary, "beta", "alpha")
    assert rec_rev["a_wins"] == 0
    assert rec_rev["b_wins"] == 20


def test_pairwise_record_missing_pair():
    rec = pairwise_record({"pairwise_matchups": {}}, "x", "y")
    assert rec == {"a_wins": 0, "b_wins": 0, "tie": 0, "total": 0}


# ---------------------------------------------------------------------------
# Promotion logic
# ---------------------------------------------------------------------------

def test_promotion_succeeds_for_dominant_candidate():
    summary = _summary(_dominant_games(50))
    ranked = rank_candidates(build_leaderboard(summary))
    decision = evaluate_promotion(
        ranked, summary, n_seeds=3, total_games=50, thresholds=PromotionThresholds()
    )
    assert decision.promote is True
    assert decision.champion == "alpha"
    assert all(c["passed"] for c in decision.criteria)


def test_promotion_refused_when_all_tied():
    summary = _summary(_tied_games(30))
    ranked = rank_candidates(build_leaderboard(summary))
    decision = evaluate_promotion(
        ranked, summary, n_seeds=3, total_games=30, thresholds=PromotionThresholds()
    )
    assert decision.promote is False
    assert decision.champion is None
    assert "No validated champion promoted" in decision.summary_line


def test_promotion_refused_with_single_seed():
    summary = _summary(_dominant_games(30))
    ranked = rank_candidates(build_leaderboard(summary))
    decision = evaluate_promotion(
        ranked, summary, n_seeds=1, total_games=30, thresholds=PromotionThresholds()
    )
    assert decision.promote is False
    failed = {c["name"] for c in decision.criteria if not c["passed"]}
    assert "multiple_seeds" in failed


def test_promotion_refused_with_too_few_games():
    summary = _summary(_dominant_games(10))
    ranked = rank_candidates(build_leaderboard(summary))
    decision = evaluate_promotion(
        ranked, summary, n_seeds=3, total_games=10, thresholds=PromotionThresholds()
    )
    assert decision.promote is False
    failed = {c["name"] for c in decision.criteria if not c["passed"]}
    assert "enough_games" in failed


def test_promotion_refused_without_runner_up():
    decision = evaluate_promotion(
        [{"name": "solo", "rank": 1}], {}, n_seeds=3, total_games=50
    )
    assert decision.promote is False
    assert decision.champion is None


# ---------------------------------------------------------------------------
# Registry update behaviour
# ---------------------------------------------------------------------------

def _champion_row():
    return {
        "name": "champion_minimal",
        "win_rate": 0.42,
        "win_rate_ci_lower": 0.30,
        "win_rate_ci_upper": 0.55,
        "trueskill_mu": 30.0,
        "trueskill_sigma": 4.0,
        "trueskill_conservative": 18.0,
        "avg_score": 88.5,
        "games_played": 90,
    }


def test_registry_update_preserves_history_and_bumps_version(tmp_path):
    registry_path = tmp_path / "champion_registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "current_version": "v1",
                "versions": {"v1": {"avg_win_rate": None}},
                "iterations": [],
                "snapshot_csv_paths": [],
                "total_games_played": 0,
            }
        )
    )
    entry = build_registry_entry(
        champion_row=_champion_row(),
        config_path="config/champion_minimal_params.json",
        params={"rollout_policy": "random"},
        seeds=[1, 2, 3],
        total_games=90,
        gauntlet_run_path="arena_runs/gauntlets/gauntlet_x",
        comparison_opponents=["champion_v1", "pool_peer_500ms", "key_findings_best"],
        promoted_from="v1",
        promotion_reason="test",
        notes="test note",
    )
    version = update_registry(registry_path, entry)

    data = json.loads(registry_path.read_text())
    assert version == "v2"
    assert data["current_version"] == "v2"
    # history preserved
    assert "v1" in data["versions"]
    assert data["versions"]["v2"]["champion_name"] == "champion_minimal"
    assert data["versions"]["v2"]["avg_win_rate"] == 0.42
    assert data["versions"]["v2"]["gate_pass"] is True
    assert data["total_games_played"] == 90
    assert data["iterations"][-1]["version"] == "v2"
    # a backup of the previous registry was written
    assert (tmp_path / "champion_registry.json.bak").exists()


def test_registry_entry_has_all_required_fields():
    entry = build_registry_entry(
        champion_row=_champion_row(),
        config_path="config/champion_minimal_params.json",
        params={"rollout_policy": "random"},
        seeds=[1, 2],
        total_games=60,
        gauntlet_run_path="arena_runs/gauntlets/g",
        comparison_opponents=["champion_v1"],
        promoted_from="v1",
        promotion_reason="reason",
        notes="notes",
    )
    required = {
        "champion_name",
        "config_path",
        "avg_win_rate",
        "avg_trueskill_mu",
        "avg_score",
        "total_games_played",
        "validation_date",
        "gauntlet_run_path",
        "notes",
        "comparison_opponents",
        "win_rate_ci",
    }
    assert required.issubset(entry.keys())


def test_registry_creates_file_when_missing(tmp_path):
    registry_path = tmp_path / "nested" / "registry.json"
    entry = build_registry_entry(
        champion_row=_champion_row(),
        config_path="c.json",
        params={},
        seeds=[1, 2],
        total_games=60,
        gauntlet_run_path="g",
        comparison_opponents=[],
        promoted_from=None,
        promotion_reason="r",
    )
    version = update_registry(registry_path, entry)
    assert version == "v1"
    assert registry_path.exists()
