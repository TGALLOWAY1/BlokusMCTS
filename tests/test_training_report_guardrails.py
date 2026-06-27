"""Guardrails proving an old-style / incomplete report can't ship silently.

These lock in the fixes for the post-migration regression where the nightly job
timed out mid-evaluation, never persisted ``last_approach_comparison``, and the
``always()`` email step then rendered a stale old-style report:

1. ``training.verify_report_freshness`` fails when the durable state has no
   completed multi-agent approach comparison (or a stale one).
2. Exactly one scheduled (cron) training workflow exists — no duplicate nightly
   workflows can both fire and email.
3. The head-to-head battery honours the wall-clock deadline *mid-battery* so a
   single candidate can no longer blow the budget and get the job cancelled.
"""

from __future__ import annotations

import glob
import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# 1. verify_report_freshness exit-code contract
# ---------------------------------------------------------------------------

from training import verify_report_freshness as vrf


def _write_state(tmp_path, **fields):
    p = tmp_path / "latest.json"
    p.write_text(json.dumps(fields))
    return str(p)


def test_verify_fails_when_no_approach_comparison(tmp_path):
    sp = _write_state(tmp_path, run_id="r1")  # no last_approach_comparison
    assert vrf.check(sp) == 1


def test_verify_fails_on_stale_record(tmp_path):
    sp = _write_state(
        tmp_path, run_id="r2",
        last_approach_comparison={"run_id": "r1", "rows": [{}], "winner": None},
    )
    assert vrf.check(sp) == 2


def test_verify_ok_when_fresh_record(tmp_path):
    sp = _write_state(
        tmp_path, run_id="r2",
        last_approach_comparison={"run_id": "r2", "rows": [{}], "winner": "td"},
    )
    assert vrf.check(sp) == 0


def test_verify_fails_when_state_missing(tmp_path):
    assert vrf.check(str(tmp_path / "nope.json")) == 1


# ---------------------------------------------------------------------------
# 2. Exactly one scheduled training workflow
# ---------------------------------------------------------------------------

def _scheduled_workflows():
    """Return workflow files that declare a `schedule:`/cron trigger."""
    scheduled = []
    for path in glob.glob(os.path.join(_REPO, ".github/workflows/*.yml")) + \
            glob.glob(os.path.join(_REPO, ".github/workflows/*.yaml")):
        text = open(path).read()
        if "schedule:" in text and "cron:" in text:
            scheduled.append(os.path.basename(path))
    return scheduled

def test_exactly_one_scheduled_workflow():
    scheduled = _scheduled_workflows()
    assert scheduled == ["nightly-mcts-training.yml"], (
        "Exactly one scheduled (cron) training workflow must exist so two "
        f"workflows cannot both train + email. Found: {scheduled}"
    )


def test_canonical_workflow_emails_via_email_summary():
    wf = open(os.path.join(_REPO, ".github/workflows/nightly-mcts-training.yml")).read()
    assert "training.email_summary" in wf
    assert "training.nightly_run" in wf
    assert "--approaches" in wf  # the multi-agent framework, not the legacy loop


# ---------------------------------------------------------------------------
# 3. Head-to-head honours the deadline mid-battery
# ---------------------------------------------------------------------------

from training.evaluation import head_to_head as hh


def _fake_candidate(name="cand_a"):
    return SimpleNamespace(
        name=name, approach="baseline", created=True,
        agent_config={"type": "mcts"},
    )


def test_evaluate_candidates_skips_all_when_deadline_already_passed(monkeypatch):
    # A deadline in the past → every created candidate is skipped, no arena runs.
    called = {"n": 0}
    monkeypatch.setattr(hh, "evaluate_candidate_vs_pool",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    pool = SimpleNamespace(seeds=[1, 2], describe=lambda: {"version": "v"})
    res = hh.evaluate_candidates(
        {}, [_fake_candidate("a"), _fake_candidate("b")], pool, None,
        games_per_arena=10, seeds=[1, 2], deadline=-1.0,
    )
    assert called["n"] == 0
    assert set(res.skipped_for_budget) == {"a", "b"}


def test_battery_stops_launching_arenas_after_deadline(monkeypatch):
    """The inner (arena, seed) loop must break once the deadline passes."""
    runs = {"n": 0}

    def fake_arena(agents, **kwargs):
        runs["n"] += 1
        return {"run_dir": f"d{runs['n']}"}

    # Fake monotonic clock: t0=100, first sub-battery check=100 (<150, runs),
    # second check=200 (>=150, breaks). deadline=150 → exactly one arena run.
    ticks = iter([100, 100, 200, 200, 200, 200, 200])
    last = {"v": 200}

    def clock():
        try:
            last["v"] = next(ticks)
        except StopIteration:
            pass
        return last["v"]

    monkeypatch.setattr(hh.time, "monotonic", clock)
    monkeypatch.setattr(hh.sc, "run_arena_inproc", fake_arena)
    monkeypatch.setattr(hh.sc, "_load_games", lambda d: [])
    monkeypatch.setattr(hh.sc, "_apply_thinking_override", lambda *a, **k: None)
    monkeypatch.setattr(hh, "_candidate_arenas", lambda *a, **k: [
        [{"name": "champion"}, {"name": "cand"}, {"name": "x"}, {"name": "y"}],
        [{"name": "champion"}, {"name": "cand"}, {"name": "z"}, {"name": "w"}],
    ])
    # Stub the post-loop aggregation so the function returns without real games.
    monkeypatch.setattr(hh.gauntlet, "aggregate_summary", lambda *a, **k: {"completed_games": 0})
    monkeypatch.setattr(hh.gauntlet, "build_leaderboard", lambda *a, **k: [])
    monkeypatch.setattr(hh.gauntlet, "rank_candidates", lambda *a, **k: [])
    monkeypatch.setattr(hh.gauntlet, "evaluate_promotion", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr(hh.gauntlet, "pairwise_record", lambda *a, **k: {})
    import training.experiments.compare as cmp
    monkeypatch.setattr(cmp, "per_agent_game_stats", lambda games, names: {
        n: {"games": 0, "wins": 0, "rank_sum": 0, "rank_dist": {}, "score_sum": 0.0}
        for n in names
    })

    pool = SimpleNamespace(seeds=[1, 2], describe=lambda: {"version": "v"})
    hh.evaluate_candidate_vs_pool(
        {}, "cand", "baseline", {"type": "mcts"}, pool, None,
        games_per_arena=5, seeds=[1, 2], deadline=150.0,
    )
    # 2 arenas x 2 seeds = 4 possible runs, but the deadline trips after the first.
    assert runs["n"] == 1
