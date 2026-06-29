"""Tests for the email digest.

Covers the regression that motivated the rewrite (every email reporting the same
Elo) plus the new guarantees: the headline Elo / deltas come from the latest
recorded run, the ELO-trend table is rendered, missing/stale metrics produce an
honest "no fresh ELO" email instead of a misleading success, and the SMTP
transport stays injectable.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import email_summary as es


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _state(run_id="run4", generation=4, **over):
    base = {
        "run_id": run_id,
        "generation": generation,
        "total_games": 2000,
        "games_today": 500,
        "elo": 1042.7,
        "trueskill_mu": 28.1,
        "trueskill_sigma": 2.3,
        "champion": {"name": "champion", "version": f"gen{generation}"},
        "human_target_elo": 1700,
        "estimated_days_to_target": 9,
        "estimate_confidence": "low",
        "last_error": None,
        "last_promoted_generation": None,
        # Mark the state as a completed multi-agent run by default so the subject
        # /body are not flagged INCOMPLETE; legacy-state tests override this.
        "last_approach_comparison": {"run_id": run_id, "rows": [], "winner": None},
        "last_eval": {
            "run_id": run_id, "total_games": 240, "n_seeds": 2, "seeds": [1, 2],
            "promoted": False,
            "baselines": [
                {"agent": "candidate", "win_rate": 0.55, "games": 120},
                {"agent": "heuristic", "win_rate": 0.71, "games": 120},
            ],
        },
    }
    base.update(over)
    return base


def _summary_row(run_id, ts, gen, elo, *, promoted=False, games_today=500, total=2000):
    return {
        "id": gen, "run_id": run_id, "timestamp": ts, "generation": gen,
        "games_today": games_today, "total_games": total, "champion_elo": elo,
        "champion_mu": 28.0, "champion_sigma": 2.3, "promoted": promoted,
        "days_trained": gen,
    }


def _history():
    """Four runs with a rising, then jiggling, Elo — oldest first."""
    return [
        _summary_row("run1", "2026-06-20T04:00:00Z", 1, 1000.0),
        _summary_row("run2", "2026-06-21T04:00:00Z", 2, 1018.4),
        _summary_row("run3", "2026-06-22T04:00:00Z", 3, 1030.3),
        _summary_row("run4", "2026-06-23T04:00:00Z", 4, 1042.7),
    ]


# ---------------------------------------------------------------------------
# RunView — deltas + freshness
# ---------------------------------------------------------------------------

def test_view_picks_latest_run_not_first():
    view = es.build_run_view(_history(), _state())
    assert view.current["run_id"] == "run4"
    assert view.current_elo == 1042.7
    assert view.fresh is True


def test_delta_previous_is_correct():
    view = es.build_run_view(_history(), _state())
    assert round(view.elo_delta_previous, 1) == 12.4  # 1042.7 - 1030.3


def test_delta_best_is_vs_prior_best():
    view = es.build_run_view(_history(), _state())
    # run4 is a new all-time high; prior best was run3 (1030.3).
    assert round(view.elo_delta_best, 1) == 12.4
    assert float(view.best["champion_elo"]) == 1042.7


def test_delta_best_negative_when_regressed():
    hist = _history()
    hist.append(_summary_row("run5", "2026-06-24T04:00:00Z", 5, 1020.0))
    view = es.build_run_view(hist, _state(run_id="run5", generation=5, elo=1020.0))
    assert view.elo_delta_previous < 0  # 1020.0 - 1042.7
    assert view.elo_delta_best < 0      # below the 1042.7 prior best


def test_empty_history_is_not_fresh():
    view = es.build_run_view([], _state())
    assert view.fresh is False
    assert "empty or missing" in view.stale_reason


def test_run_id_mismatch_is_not_fresh():
    # state advanced to run5 but the timeline's latest is still run4.
    view = es.build_run_view(_history(), _state(run_id="run5", generation=5))
    assert view.fresh is False
    assert "not updated" in view.stale_reason


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------

def test_subject_success_is_multi_agent_branded_with_elo_and_delta():
    view = es.build_run_view(_history(), _state())
    subj = es.build_subject(_state(), view, failed=False)
    assert subj.startswith("MCTS Lab Multi-Agent Training Report — ")
    assert subj.endswith("ELO 1042.7 (+12.4)")


def test_subject_regression_shows_negative_delta():
    hist = _history()
    hist.append(_summary_row("run5", "2026-06-24T04:00:00Z", 5, 1030.3))
    view = es.build_run_view(hist, _state(run_id="run5", generation=5))
    subj = es.build_subject(_state(run_id="run5"), view, failed=False)
    assert subj.startswith("MCTS Lab Multi-Agent Training Report — ")
    assert subj.endswith("ELO 1030.3 (-12.4)")


def test_subject_failed_is_branded_failed():
    # A crash is an operational alert -> 🚨 prefix so it's obvious from the inbox.
    subj = es.build_subject(_state(), None, failed=True)
    assert subj.startswith("🚨 MCTS Lab Multi-Agent Training — FAILED — ")


def test_subject_stale_says_incomplete():
    view = es.build_run_view([], _state())  # not fresh
    subj = es.build_subject(_state(), view, failed=False)
    assert subj.startswith("🚨 MCTS Lab Multi-Agent Training — INCOMPLETE")


def test_subject_legacy_state_says_incomplete():
    # State WITHOUT a completed approach comparison must never look like a success,
    # even with a fresh Elo — this is the regression the user reported.
    legacy = _state()
    legacy.pop("last_approach_comparison")
    view = es.build_run_view(_history(), legacy)
    subj = es.build_subject(legacy, view, failed=False)
    assert subj.startswith("🚨 MCTS Lab Multi-Agent Training — INCOMPLETE")


def test_subject_alert_flag_prepends_siren():
    view = es.build_run_view(_history(), _state())
    subj = es.build_subject(_state(), view, failed=False, alert=True)
    assert subj.startswith("🚨 MCTS Lab Multi-Agent Training Report — ")


def test_subject_no_alert_has_no_siren():
    view = es.build_run_view(_history(), _state())
    subj = es.build_subject(_state(), view, failed=False, alert=False)
    assert subj.startswith("MCTS Lab Multi-Agent Training Report — ")


# ---------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------

def test_body_has_trend_section_and_recent_generations():
    view = es.build_run_view(_history(), _state())
    body = es.build_body(_state(), view, failed=False)
    assert "## ELO Trend" in body
    # The verbose per-run table is gone; a compact recent-generations digest stays.
    assert "Recent generations" in body
    # Newest generations appear as bullets with deltas.
    assert "- gen 4: 1042.7 (+12.4)" in body
    assert "- gen 3: 1030.3" in body
    # Headline current Elo present.
    assert "Current ELO: 1042.7" in body
    assert "Change vs previous run: +12.4" in body


def test_body_plot_callout_when_attached():
    view = es.build_run_view(_history(), _state())
    body = es.build_body(_state(), view, failed=False, plot_attached=True,
                         plot_game_count=288)
    assert "elo_trend.png" in body
    assert "288 per-game ratings" in body


def test_body_plot_fallback_note_when_no_plot():
    view = es.build_run_view(_history(), _state())
    body = es.build_body(_state(), view, failed=False, plot_attached=False)
    assert "No plot was generated" in body
    # The recent-generations digest still gives the trend in text.
    assert "Recent generations" in body


def test_body_match_breakdown_uses_last_eval():
    view = es.build_run_view(_history(), _state())
    body = es.build_body(_state(), view, failed=False)
    assert "## Match Breakdown" in body
    assert "heuristic" in body and "71.0%" in body


def test_body_stale_says_no_fresh_elo():
    view = es.build_run_view([], _state())
    body = es.build_body(_state(), view, failed=False)
    assert "No fresh ELO was calculated for this run." in body


def test_body_failure_has_crash_summary():
    state = _state(last_error={
        "generation": 4,
        "message": "RuntimeError: arena exploded",
        "traceback": "Traceback...\nRuntimeError: arena exploded",
    })
    view = es.build_run_view(_history(), state)
    body = es.build_body(state, view, failed=True)
    assert "Status: FAILED" in body
    assert "arena exploded" in body
    assert "resumes" in body


def test_body_diagnostics_surface_findings():
    class _F:
        severity = "warn"
        code = "stale_elo"
        message = "Champion Elo has been identical for the last 3 runs."

    view = es.build_run_view(_history(), _state())
    body = es.build_body(_state(), view, failed=False, findings=[_F()])
    assert "stale_elo" in body
    assert "## Diagnostics" in body


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

def test_send_email_uses_injected_transport():
    sent = {}

    def fake_send(config, msg):
        sent["to"] = msg["To"]
        sent["subject"] = msg["Subject"]
        sent["body"] = msg.get_content()

    cfg = es.SmtpConfig("smtp.test", 587, "u", "p", "to@test", "from@test")
    es.send_email("Hi", "Body here", config=cfg, send_fn=fake_send)
    assert sent["to"] == "to@test"
    assert sent["subject"] == "Hi"
    assert "Body here" in sent["body"]


def test_build_message_text_only_without_plot():
    msg = es.build_message("Subj", "Body here", email_from="f@t", email_to="t@t")
    # No plot -> single-part text/plain, get_content works.
    assert msg.get_content_type() == "text/plain"
    assert "Body here" in msg.get_content()


def test_build_message_embeds_and_attaches_plot(tmp_path):
    png = tmp_path / "elo_trend.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nFAKEDATA")  # build_message only reads bytes
    msg = es.build_message(
        "Subj", "Body here", email_from="f@t", email_to="t@t", plot_path=png
    )
    types = [p.get_content_type() for p in msg.walk()]
    assert "multipart/mixed" in types
    assert "text/plain" in types       # plain-text fallback always present
    assert "text/html" in types        # inline HTML alternative
    assert types.count("image/png") == 2  # one inline (cid) + one attachment
    # The inline image carries the cid the HTML references.
    cids = [p.get("Content-ID") for p in msg.walk() if p.get("Content-ID")]
    assert any("elo-plot" in (c or "") for c in cids)
    filenames = [p.get_filename() for p in msg.walk() if p.get_filename()]
    assert "elo_trend.png" in filenames


def test_build_message_missing_plot_file_is_text_only(tmp_path):
    msg = es.build_message(
        "Subj", "Body", email_from="f@t", email_to="t@t",
        plot_path=tmp_path / "does_not_exist.png",
    )
    assert msg.get_content_type() == "text/plain"


def test_send_email_passes_plot_through(tmp_path):
    png = tmp_path / "p.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nX")
    captured = {}

    def fake_send(config, msg):
        captured["types"] = [p.get_content_type() for p in msg.walk()]

    cfg = es.SmtpConfig("smtp.test", 587, "u", "p", "to@test", "from@test")
    es.send_email("S", "B", config=cfg, plot_path=png, send_fn=fake_send)
    assert "image/png" in captured["types"]


def test_smtp_config_missing_env_returns_none(monkeypatch):
    for var in ("SMTP_SERVER", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD",
                "TRAINING_EMAIL_TO", "TRAINING_EMAIL_FROM"):
        monkeypatch.delenv(var, raising=False)
    assert es.SmtpConfig.from_env() is None


def test_smtp_config_from_env_complete(monkeypatch):
    monkeypatch.setenv("SMTP_SERVER", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("TRAINING_EMAIL_TO", "to@test")
    monkeypatch.setenv("TRAINING_EMAIL_FROM", "from@test")
    cfg = es.SmtpConfig.from_env()
    assert cfg is not None and cfg.port == 587


# ---------------------------------------------------------------------------
# End-to-end compose against a real on-disk DB (the regression guard)
# ---------------------------------------------------------------------------

def test_compose_reads_latest_recorded_elo(tmp_path):
    """Two recorded runs with different Elo → email reflects the *latest*, with a delta."""
    from training import TrainingPaths, ratings_db, state_store

    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()

    conn = ratings_db.connect(paths.ratings_db)
    rows = lambda elo: [ratings_db.AgentRatingRow("champion", elo, 28.0, 2.3, 23.0, 50)]
    ratings_db.record_run(
        conn, run_id="runA", timestamp="2026-06-22T04:00:00Z", generation=1,
        agent_rows=rows(1000.0),
        run_summary=ratings_db.RunSummaryRow(1, 50, 50, 1000.0, 28.0, 2.3, False, 1),
    )
    ratings_db.record_run(
        conn, run_id="runB", timestamp="2026-06-23T04:00:00Z", generation=2,
        agent_rows=rows(1025.0),
        run_summary=ratings_db.RunSummaryRow(2, 50, 100, 1025.0, 28.0, 2.3, False, 2),
    )
    conn.close()

    state = state_store.default_latest_state()
    state["run_id"] = "runB"
    state["generation"] = 2
    state["elo"] = 1025.0
    state["last_approach_comparison"] = {"run_id": "runB", "rows": [], "winner": None}
    state_store.save_latest(paths, state)

    composed = es.compose(paths)
    assert composed["subject"].startswith("MCTS Lab Multi-Agent Training Report — ")
    assert composed["subject"].endswith("ELO 1025.0 (+25.0)")
    assert "Current ELO: 1025.0" in composed["body"]
    assert composed["view"].fresh is True


def test_compose_legacy_state_flags_incomplete(tmp_path):
    """State without an approach comparison (the reported bug) → INCOMPLETE + banner."""
    from training import TrainingPaths, ratings_db, state_store

    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    conn = ratings_db.connect(paths.ratings_db)
    ratings_db.record_run(
        conn, run_id="legacy", timestamp="2026-06-22T04:00:00Z", generation=1,
        agent_rows=[ratings_db.AgentRatingRow("champion", 1175.0, 24.6, 8.2, 0.0, 2)],
        run_summary=ratings_db.RunSummaryRow(1, 2, 2, 1175.0, 24.6, 8.2, False, 1),
    )
    conn.close()

    state = state_store.default_latest_state()
    state["run_id"] = "legacy"
    state["generation"] = 1
    state["elo"] = 1175.0
    state.pop("last_approach_comparison", None)  # the pre-migration shape
    state_store.save_latest(paths, state)

    composed = es.compose(paths)
    assert composed["subject"].startswith("🚨 MCTS Lab Multi-Agent Training — INCOMPLETE")
    assert "LEGACY / INCOMPLETE REPORT" in composed["body"]
    assert composed["provenance"].multi_agent is False


# ---------------------------------------------------------------------------
# Provenance header + multi-agent branding
# ---------------------------------------------------------------------------

def test_body_has_provenance_header():
    view = es.build_run_view(_history(), _state())
    body = es.build_body(_state(), view, failed=False)
    assert body.startswith("# MCTS Lab Multi-Agent Training Report")
    assert "## Run Provenance" in body
    assert "Training mode: **multi-agent-approach-comparison**" in body
    assert es.CANONICAL_WORKFLOW_FILE in body


def test_body_legacy_state_has_banner():
    legacy = _state()
    legacy.pop("last_approach_comparison")
    view = es.build_run_view(_history(), legacy)
    body = es.build_body(legacy, view, failed=False)
    assert "LEGACY / INCOMPLETE REPORT" in body
    assert "Training mode: **legacy/incomplete" in body


# ---------------------------------------------------------------------------
# Verdict + Alerts — explicit good/bad and 🚨/❌ for operational problems
# ---------------------------------------------------------------------------

def _prov(multi_agent=True):
    return es.build_provenance(
        _state() if multi_agent else {k: v for k, v in _state().items()
                                      if k != "last_approach_comparison"}
    )


def test_alerts_empty_on_clean_run():
    view = es.build_run_view(_history(), _state())
    record = {"run_id": "run4", "rows": [
        {"approach": "td_learning", "created": True, "games": 20, "reason": "ok"}],
        "winner": None, "trajectory": {}}
    alerts = es.collect_alerts(_state(), view, record, failed=False,
                               provenance=_prov(True))
    assert alerts == []
    verdict = es.overall_verdict(view, record, alerts)
    assert verdict.emoji == "✅"  # Elo rose +12.4 vs previous


def test_alert_on_crash_is_siren():
    state = _state(last_error={"generation": 9, "message": "RuntimeError: boom"})
    view = es.build_run_view(_history(), state)
    alerts = es.collect_alerts(state, view, None, failed=True, provenance=_prov(True))
    assert len(alerts) == 1 and alerts[0].level == "alert"
    assert es.overall_verdict(view, None, alerts).emoji == "🚨"


def test_alert_on_missing_multi_agent_result_is_timeout_siren():
    legacy = _state()
    legacy.pop("last_approach_comparison")
    view = es.build_run_view(_history(), legacy)
    alerts = es.collect_alerts(legacy, view, None, failed=False,
                               provenance=_prov(False))
    assert any(a.level == "alert" and "did not finish" in a.title for a in alerts)


def test_alert_on_arena_terminated_early():
    view = es.build_run_view(_history(), _state())
    record = {"run_id": "run4", "winner": None, "trajectory": {}, "rows": [
        {"approach": "td_learning", "created": True, "games": 20, "reason": "ok"},
        {"approach": "heuristic_tuning", "created": True, "games": 0,
         "reason": "candidate not evaluated this run (time budget exhausted)"},
    ]}
    alerts = es.collect_alerts(_state(), view, record, failed=False,
                               provenance=_prov(True))
    assert any(a.level == "alert" and "terminated early" in a.title for a in alerts)
    assert es.overall_verdict(view, record, alerts).emoji == "🚨"


def test_error_on_no_candidate_trained():
    view = es.build_run_view(_history(), _state())
    record = {"run_id": "run4", "winner": None, "trajectory": {}, "rows": [
        {"approach": "td_learning", "created": False, "reason": "no trajectories yet"},
        {"approach": "baseline_mcts", "created": False, "reason": "nothing to do"},
    ]}
    alerts = es.collect_alerts(_state(), view, record, failed=False,
                               provenance=_prov(True))
    assert any(a.level == "error" and "No candidate" in a.title for a in alerts)
    assert es.overall_verdict(view, record, alerts).emoji == "❌"


def test_error_on_regression_beyond_noise():
    view = es.build_run_view(_history(), _state())
    record = {"run_id": "run4", "winner": None, "rows": [
        {"approach": "td_learning", "created": True, "games": 20, "reason": "ok"}],
        "trajectory": {"significant": True, "gap_to_best": -200.0}}
    alerts = es.collect_alerts(_state(), view, record, failed=False,
                               provenance=_prov(True))
    assert any(a.level == "error" and "regression" in a.title.lower() for a in alerts)


def test_body_leads_with_verdict_and_alerts_section():
    view = es.build_run_view(_history(), _state())
    body = es.build_body(_state(), view, failed=False)
    assert "## Alerts" in body
    # The verdict banner is the first section after the H1.
    head = body.split("## Run Provenance")[0]
    assert "Overall:" in head
    # A clean run states the all-clear explicitly.
    assert "No alerts" in body


def test_body_alerts_section_is_loud_on_problem():
    view = es.build_run_view(_history(), _state())
    state = _state()
    state["last_approach_comparison"] = {
        "run_id": "run4", "winner": None, "trajectory": {}, "rows": [
            {"approach": "heuristic_tuning", "created": True, "games": 0,
             "reason": "not evaluated this run (time budget exhausted)"}]}
    body = es.build_body(state, view, failed=False)
    assert "🚨" in body
    assert "terminated early" in body


def test_provenance_reads_github_env(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "abcdef1234567890")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.setenv("GITHUB_RUN_ID", "999")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_WORKFLOW", "nightly-mcts-training")
    prov = es.build_provenance(_state())
    assert prov.short_sha == "abcdef1"
    assert prov.branch == "main"
    assert prov.run_url == "https://github.com/owner/repo/actions/runs/999"
    assert prov.multi_agent is True
