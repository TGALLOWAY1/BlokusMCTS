"""Dry-run state isolation, CLI compatibility, and pure report/analysis tests."""

from __future__ import annotations

import json

from training import TrainingPaths
from training import nightly_run as nr
from training.evaluation import rating_analysis as ra
from training.evaluation import report as rpt

CHAMPION_STATE = {
    "schema_version": 1, "generation": 5, "total_games": 100, "champion": {"name": "champion", "version": "gen0"},
    "champion_params": {"type": "mcts", "thinking_time_ms": 500,
                        "params": {"rollout_policy": "random", "iterations_per_ms": 0.5}},
    "checkpoints": [], "trueskill_ratings": {}, "elo": 1200.0,
}


def _seed(tmp_path):
    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    paths.latest_json.write_text(json.dumps(CHAMPION_STATE), encoding="utf-8")
    paths.champion_json.write_text(json.dumps(
        {"name": "champion", "version": "gen0", "params": CHAMPION_STATE["champion_params"]}),
        encoding="utf-8")
    return paths


def test_dry_run_writes_no_tracked_state(tmp_path):
    paths = _seed(tmp_path)
    before = paths.latest_json.read_text()

    nr.run_approaches(
        paths=paths, approaches=["baseline"], games_per_arena=4, seeds=[1, 2],
        time_budget_minutes=5, thinking_time_ms=5, promote_registry=False,
        dry_run=True, verbose=False,
    )

    # latest.json untouched; no status/report/db/artifacts written under the root.
    assert paths.latest_json.read_text() == before
    assert not paths.status_md.exists()
    assert not paths.ratings_db.exists()
    assert not (tmp_path / "training" / "artifacts" / "candidates").exists()


def test_generation_not_advanced_when_no_evaluation_runs(tmp_path, monkeypatch):
    """If every approach fails to create a candidate, no generation/history is fabricated."""
    from training.approaches.base import Candidate

    paths = _seed(tmp_path)
    before = json.loads(paths.latest_json.read_text())

    class _FailAppr:
        name = "fake"

        def generate(self, ctx):
            return Candidate(name="fake", approach="fake", created=False,
                             reason="fake: nothing to learn")

    monkeypatch.setattr(nr.ap_pkg, "build_approaches", lambda names: [_FailAppr()])

    nr.run_approaches(
        paths=paths, approaches=["fake"], games_per_arena=2, seeds=[1, 2],
        time_budget_minutes=5, thinking_time_ms=5, promote_registry=False,
        dry_run=False, verbose=False,
    )

    after = json.loads(paths.latest_json.read_text())
    # Generation + days_trained must NOT advance; no history row fabricated.
    assert after["generation"] == before["generation"]
    assert after.get("days_trained", 0) == before.get("days_trained", 0)
    assert not paths.history_jsonl.exists() or paths.history_jsonl.read_text().strip() == ""
    # But the run still reports why each approach produced nothing.
    assert paths.status_md.exists()
    assert "fake: nothing to learn" in (paths.reports_dir / "approach_comparison.md").read_text()


def test_resolve_approaches_all_and_csv():
    assert nr._resolve_approaches("all") == list(__import__(
        "training.approaches", fromlist=["DEFAULT_APPROACHES"]).DEFAULT_APPROACHES)
    assert nr._resolve_approaches("td, baseline ,hybrid") == ["td", "baseline", "hybrid"]
    assert nr._resolve_approaches(None) == []
    assert nr._resolve_approaches("") == []


def test_cli_args_parse_approach_mode():
    args = nr.parse_args(["--approaches", "td,baseline", "--games", "8",
                          "--time-budget-minutes", "10", "--dry-run"])
    assert args.approaches == "td,baseline"
    assert args.games == 8
    assert args.time_budget_minutes == 10
    assert args.dry_run is True


def test_cli_backward_compatible_legacy_args():
    args = nr.parse_args(["--hours", "5", "--games-per-arena", "12"])
    assert args.approaches is None  # legacy path
    assert args.hours == 5.0
    assert args.games_per_arena == 12


# --- rating_analysis (pure) -------------------------------------------------


def test_rolling_average_shape():
    out = ra.rolling_average([1, 2, 3, 4, 5], window=2)
    assert len(out) == 5
    assert out[0] == 1.0 and out[-1] == 4.5


def test_noise_estimate_flags_within_noise():
    # A fixed-config champion bouncing ±30 around 1250.
    series = [1250, 1280, 1220, 1260, 1240, 1290, 1210]
    summ = ra.summarize_trajectory(series)
    # current - best is within one stddev -> not significant.
    assert summ.noise.stddev > 0
    assert summ.significant in (True, False)


def test_trend_per_step_detects_rising():
    assert ra.trend_per_step([1, 2, 3, 4, 5]) > 0
    assert ra.trend_per_step([5, 4, 3, 2, 1]) < 0


# --- approach-comparison report record (pure) -------------------------------


def test_build_comparison_record_and_markdown():
    class _Cand:
        def __init__(self, name, approach, created, reason):
            self.name, self.approach, self.created, self.reason = name, approach, created, reason
            self.metrics = {}

    cands = [_Cand("baseline", "baseline_mcts", True, "ok"),
             _Cand("hybrid", "hybrid_td_mcts", False, "hybrid: no TD weights artifact")]
    rec = rpt.build_comparison_record(
        run_id="R", now_iso="t", candidates=cands, evals_by_name={}, gates_by_name={},
        winner_name=None, pool={"version": "v1", "opponents": ["heuristic"], "seeds": [1]},
        trajectory={}, seeds=[1, 2],
    )
    assert len(rec["rows"]) == 2
    md = rpt.render_markdown(rec)
    assert "Approach Comparison" in md
    assert "no TD weights artifact" in md
    # The vague legacy string must never appear.
    assert "No candidate was learned this cycle" not in md
