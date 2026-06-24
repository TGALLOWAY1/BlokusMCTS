"""Tests for the experiment framework (training/experiments/)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training.experiments import compare as cmp
from training.experiments import manifest as mf
from training.experiments import report as rp


def _game(scores, winners, tie=False):
    ranks = {}
    for r, (name, _) in enumerate(sorted(scores.items(), key=lambda kv: kv[1], reverse=True), 1):
        ranks[name] = r
    return {"agent_scores": scores, "agent_ranks": ranks,
            "winner_agents": winners, "is_tie": tie}


def test_per_agent_game_stats_basic():
    games = [
        _game({"a": 80, "b": 60, "c": 40, "d": 20}, ["a"]),
        _game({"a": 30, "b": 70, "c": 50, "d": 10}, ["b"]),
    ]
    stats = cmp.per_agent_game_stats(games, ["a", "b", "c", "d"])
    assert stats["a"]["wins"] == 1 and stats["a"]["losses"] == 1
    assert stats["a"]["games"] == 2
    # a: rank 1 (game1) then rank 3 (game2: b>c>a>d) -> rank_sum 4
    assert stats["a"]["rank_sum"] == 4
    # margins for a: 80-60=20, 30-70=-40
    assert stats["a"]["margins"] == [20.0, -40.0]


def test_per_agent_game_stats_draw():
    games = [_game({"a": 50, "b": 50, "c": 30, "d": 10}, ["a", "b"], tie=True)]
    stats = cmp.per_agent_game_stats(games, ["a", "b", "c", "d"])
    assert stats["a"]["draws"] == 1
    assert stats["a"]["wins"] == 0
    assert stats["c"]["losses"] == 1


def test_mean_ci():
    mean, ci = cmp._mean_ci([1.0, 1.0, 1.0])
    assert mean == 1.0
    assert ci[0] <= 1.0 <= ci[1]
    mean0, ci0 = cmp._mean_ci([])
    assert mean0 == 0.0


def test_build_arenas_four_competitors():
    cfgs = {n: {"type": "random"} for n in ("a", "b", "c", "d")}
    arenas = cmp.build_arenas(cfgs)
    assert len(arenas) == 1
    assert len(arenas[0]) == 4


def test_build_arenas_five_competitors_combinations():
    cfgs = {n: {"type": "random"} for n in ("a", "b", "c", "d", "e")}
    arenas = cmp.build_arenas(cfgs)
    assert len(arenas) == 5  # C(5,4)
    for arena in arenas:
        assert len({a["name"] for a in arena}) == 4


def test_build_arenas_pads_when_too_few():
    cfgs = {"a": {"type": "mcts"}, "b": {"type": "heuristic"}}
    arenas = cmp.build_arenas(cfgs)
    assert len(arenas) == 1 and len(arenas[0]) == 4
    names = {a["name"] for a in arenas[0]}
    assert "a" in names and "b" in names


def test_aggregate_comparison_end_to_end():
    games = []
    # candidate 'td' consistently beats 'regression'.
    for _ in range(8):
        games.append(_game({"td": 90, "regression": 70, "heuristic": 50, "random": 20},
                           ["td"]))
    cfg = cmp.CompareConfig(games_per_arena=8, seeds=[1])
    result = cmp.aggregate_comparison(
        games, ["td", "regression", "heuristic", "random"], cfg,
        baseline="regression", candidate="td",
    )
    assert result.total_games == 8
    assert result.per_agent["td"].wins == 8
    assert result.per_agent["td"].avg_rank == 1.0
    assert result.head_to_head["candidate"] == "td"
    assert result.head_to_head["candidate_wins"] == 8
    # Report renders.
    manifest = mf.build_manifest(
        description="t", competitor_configs={n: {"type": "x"} for n in result.competitors},
        seeds=[1], games_per_arena=8, thinking_time_ms=None, now="2026-06-24T00:00:00Z",
    )
    md = rp.render_experiment_report(manifest, result)
    assert "Experiment Report" in md and "Recommendation" in md


def test_manifest_roundtrip(tmp_path):
    manifest = mf.build_manifest(
        description="demo", competitor_configs={"a": {"type": "mcts"}, "b": {"type": "random"}},
        seeds=[1, 2], games_per_arena=10, thinking_time_ms=50, now="2026-06-24T00:00:00Z",
    )
    path = mf.save_manifest(manifest, tmp_path / "manifest.json")
    loaded = mf.load_manifest(path)
    assert loaded.experiment_id == manifest.experiment_id
    assert loaded.seeds == [1, 2]
    assert loaded.competitors == manifest.competitors


def test_manifest_id_is_deterministic():
    kw = dict(description="d", competitor_configs={"a": {"type": "mcts"}},
              seeds=[1], games_per_arena=5, thinking_time_ms=None, now="2026-01-01T00:00:00Z")
    m1 = mf.build_manifest(**kw)
    m2 = mf.build_manifest(**kw)
    assert m1.experiment_id == m2.experiment_id
