"""Tests for trajectory persistence and self-play trajectory shaping."""

from __future__ import annotations

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import trajectory_store as ts
from training.rich_features import RICH_FEATURE_NAMES
from training.td_selfplay import (
    GameTrajectory,
    _DecisionPoint,
    compute_ranks,
    margin_labels,
    trajectory_to_rows,
)


def _feat(value: float = 0.5):
    return {n: value for n in RICH_FEATURE_NAMES}


def _make_row(game_id="g0", pid=1, ply=0, terminal=False):
    return ts.TrajectoryRow(
        run_id="run",
        game_id=game_id,
        seed=42,
        ply=ply,
        player_id=pid,
        phase="early",
        board_occupancy=0.1,
        current_player=pid,
        state_features=_feat(0.3),
        next_state_features=_feat(0.4),
        reward=0.0,
        terminal=terminal,
        final_rank=1,
        final_score=80,
        score_margin_to_winner=0.0,
        score_margin_to_next=5.0,
        score_margin_over_last=20.0,
        winner_id=pid,
        won_game=True,
        top_2_finish=True,
        agent_name="champion",
        agent_version="gen1",
        created_at="2026-06-24T00:00:00Z",
    )


def test_append_and_load_roundtrip(tmp_path):
    path = tmp_path / "traj.csv"
    rows = [_make_row(ply=0), _make_row(ply=1, terminal=True)]
    n = ts.append_trajectories(rows, path)
    assert n == 2
    loaded = ts.load_trajectories(path)
    assert len(loaded) == 2
    # Numeric coercion.
    assert loaded[0]["seed"] == 42
    assert loaded[1]["terminal"] == 1
    assert isinstance(loaded[0]["board_occupancy"], float)
    # Feature vectors round-trip.
    sv = ts.state_vector(loaded[0])
    assert len(sv) == len(RICH_FEATURE_NAMES)
    assert all(abs(v - 0.3) < 1e-9 for v in sv)


def test_append_is_additive(tmp_path):
    path = tmp_path / "traj.csv"
    ts.append_trajectories([_make_row(ply=0)], path)
    ts.append_trajectories([_make_row(ply=1, terminal=True)], path)
    assert len(ts.load_trajectories(path)) == 2


def test_sort_trajectories_orders_by_game_player_ply():
    rows = [
        {"game_id": "g1", "player_id": 2, "ply": 5},
        {"game_id": "g0", "player_id": 1, "ply": 3},
        {"game_id": "g0", "player_id": 1, "ply": 1},
        {"game_id": "g0", "player_id": 2, "ply": 0},
    ]
    out = ts.sort_trajectories(rows)
    keys = [(r["game_id"], r["player_id"], r["ply"]) for r in out]
    assert keys == sorted(keys)


def test_compute_ranks_handles_ties():
    ranks = compute_ranks({1: 50, 2: 50, 3: 30, 4: 10})
    assert ranks[1] == 1 and ranks[2] == 1  # tie for first
    assert ranks[3] == 3  # competition ranking skips 2
    assert ranks[4] == 4


def test_margin_labels_signs():
    scores = {1: 80, 2: 60, 3: 40, 4: 20}
    m = margin_labels(1, scores)  # leader
    assert m["score_margin_to_winner"] == 0.0
    assert m["score_margin_to_next"] > 0  # leading ⇒ positive gap to runner-up
    m3 = margin_labels(3, scores)  # third
    assert m3["score_margin_to_winner"] < 0
    assert m3["score_margin_to_next"] < 0


def test_trajectory_to_rows_terminal_and_ordering():
    traj = GameTrajectory(game_id="g0", seed=1)
    # Player 1 has three decision points; player 2 has one.
    traj.decisions = {
        1: [
            _DecisionPoint(0, "early", 0.05, 1, _feat(0.1)),
            _DecisionPoint(4, "early", 0.15, 1, _feat(0.2)),
            _DecisionPoint(8, "mid", 0.30, 1, _feat(0.3)),
        ],
        2: [_DecisionPoint(2, "early", 0.10, 2, _feat(0.5))],
        3: [],
        4: [],
    }
    traj.terminal_features = {p: _feat(0.9) for p in (1, 2, 3, 4)}
    traj.final_scores = {1: 80, 2: 60, 3: 40, 4: 20}
    traj.final_ranks = compute_ranks(traj.final_scores)
    traj.winner_id = 1
    traj.seat_agent = {1: "champion", 2: "candidate", 3: "h", 4: "r"}

    rows = trajectory_to_rows(traj, run_id="run", agent_version="gen1")

    p1 = [r for r in rows if r.player_id == 1]
    assert [r.ply for r in p1] == [0, 4, 8]
    # Only the last row for each player is terminal.
    assert [r.terminal for r in p1] == [False, False, True]
    # Non-terminal next-state equals the following decision's features.
    assert p1[0].next_state_features == p1[1].state_features
    # Terminal next-state equals the terminal-board features.
    assert p1[2].next_state_features == traj.terminal_features[1]
    # Players with no decisions emit no rows.
    assert all(r.player_id != 3 for r in rows)
    # Outcome labels propagated.
    assert p1[0].final_rank == 1 and p1[0].won_game is True


def test_each_non_terminal_row_has_next_state_row():
    traj = GameTrajectory(game_id="g0", seed=1)
    traj.decisions = {
        1: [
            _DecisionPoint(0, "early", 0.05, 1, _feat(0.1)),
            _DecisionPoint(4, "early", 0.15, 1, _feat(0.2)),
        ],
        2: [], 3: [], 4: [],
    }
    traj.terminal_features = {p: _feat(0.9) for p in (1, 2, 3, 4)}
    traj.final_scores = {1: 80, 2: 60, 3: 40, 4: 20}
    traj.final_ranks = compute_ranks(traj.final_scores)
    traj.seat_agent = {1: "champion", 2: "c", 3: "h", 4: "r"}
    rows = trajectory_to_rows(traj, run_id="run", agent_version="gen1")
    by_player = defaultdict(list)
    for r in rows:
        by_player[r.player_id].append(r)
    for plist in by_player.values():
        plist.sort(key=lambda r: r.ply)
        for i, r in enumerate(plist):
            if not r.terminal:
                assert i + 1 < len(plist)  # a following row exists
