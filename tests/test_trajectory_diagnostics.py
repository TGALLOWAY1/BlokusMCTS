"""Tests for trajectory quality diagnostics (training/trajectory_diagnostics.py)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import trajectory_diagnostics as tdg


def _row(*, game_id="g0", pid=1, phase="early", terminal=0, final_rank=1,
         won=1, top2=1, next_phase="mid", agent="champion"):
    return {
        "game_id": game_id, "player_id": pid, "phase": phase, "next_phase": next_phase,
        "terminal": terminal, "final_rank": final_rank, "won_game": won,
        "top_2_finish": top2, "agent_name": agent, "board_occupancy": 0.1,
    }


def test_empty_corpus_flags_critical():
    r = tdg.diagnose_rows([])
    assert r.total_rows == 0
    assert any(f["code"] == "empty" and f["severity"] == "critical" for f in r.findings)


def test_counts_by_phase_player_rank():
    rows = [
        _row(pid=1, phase="early", final_rank=1),
        _row(pid=1, phase="mid", terminal=1, final_rank=1, next_phase="mid"),
        _row(pid=2, phase="late", final_rank=3, won=0, top2=0),
    ]
    r = tdg.diagnose_rows(rows, min_rows_per_phase=1)
    assert r.total_rows == 3
    assert r.rows_by_phase == {"early": 1, "mid": 1, "late": 1}
    assert r.rows_by_player == {1: 2, 2: 1}
    assert r.rows_by_rank == {1: 2, 3: 1}
    assert r.terminal_rows == 1
    assert r.nonterminal_rows == 2


def test_under_populated_phase_flagged():
    rows = [_row(phase="early", terminal=1) for _ in range(5)]
    r = tdg.diagnose_rows(rows, min_rows_per_phase=200)
    codes = {f["code"] for f in r.findings}
    assert "under_populated_phase" in codes


def test_missing_terminal_flagged():
    # A trajectory with only non-terminal rows.
    rows = [_row(game_id="g0", pid=1, terminal=0), _row(game_id="g0", pid=1, terminal=0)]
    r = tdg.diagnose_rows(rows, min_rows_per_phase=1)
    assert r.trajectories_missing_terminal == 1
    assert any(f["code"] == "missing_terminal" for f in r.findings)


def test_rank_skew_flagged():
    rows = [_row(final_rank=1, terminal=(i % 2)) for i in range(20)]
    r = tdg.diagnose_rows(rows, min_rows_per_phase=1)
    assert any(f["code"] == "rank_skew" for f in r.findings)


def test_next_phase_coverage():
    rows = [
        _row(terminal=0, next_phase="mid"),
        _row(terminal=0, next_phase=""),  # legacy, no next_phase
        _row(terminal=1, next_phase="late"),
    ]
    r = tdg.diagnose_rows(rows, min_rows_per_phase=1)
    # 1 of 2 non-terminal rows has a valid next_phase.
    assert abs(r.next_phase_coverage - 0.5) < 1e-9


def test_render_smoke():
    rows = [_row(terminal=(i == 9)) for i in range(10)]
    r = tdg.diagnose_rows(rows, min_rows_per_phase=1)
    md = tdg.render_report(r)
    assert "Trajectory Quality Diagnostics" in md
    assert "Rows by phase" in md
