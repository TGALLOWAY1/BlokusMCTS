"""Tests for the email digest — subject/body for success+failure, fake transport."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import email_summary as es


def _success_state():
    return {
        "run_id": "20260621T0300Z",
        "generation": 41,
        "total_games": 184250,
        "games_today": 1820,
        "elo": 1420.0,
        "trueskill_mu": 28.1,
        "trueskill_sigma": 2.3,
        "champion": {"name": "champion", "version": "gen41"},
        "human_target_elo": 1500,
        "estimated_days_to_target": 9,
        "estimate_confidence": "low",
        "last_error": None,
        "last_promoted_generation": 41,
    }


def _failure_state():
    return {
        "run_id": "20260621T0300Z",
        "generation": 41,
        "total_games": 184250,
        "champion": {"name": "champion", "version": "gen40"},
        "last_error": {
            "generation": 41,
            "message": "RuntimeError: arena exploded",
            "traceback": "Traceback...\nRuntimeError: arena exploded",
        },
    }


def test_subject_success():
    subj = es.build_subject(_success_state(), promoted=True, failed=False)
    assert "SUCCESS" in subj and "1420" in subj and "PROMOTED" in subj


def test_subject_failure():
    subj = es.build_subject(_failure_state(), promoted=False, failed=True)
    assert "FAILED" in subj


def test_body_success_has_key_fields():
    body = es.build_body(
        _success_state(), failed=False, promoted=True,
        baselines=[{"agent": "heuristic", "win_rate": 0.71}],
    )
    assert "Status: SUCCESS" in body
    assert "Total Games: 184,250" in body
    assert "heuristic: 71%" in body
    assert "Human Estimate" in body


def test_body_failure_has_crash_summary():
    body = es.build_body(_failure_state(), failed=True)
    assert "Status: FAILED" in body
    assert "arena exploded" in body
    assert "resumes" in body


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
