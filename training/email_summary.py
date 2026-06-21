"""Concise email digest of a nightly run (SMTP via repository secrets).

The morning email must be readable without opening GitHub. It works for both
success and failure (the failure branch includes the crash summary captured in
``latest.json['last_error']``). Credentials come exclusively from environment
variables / repo secrets — **never hardcoded**. If the SMTP config is incomplete
the body is still printed to stdout (so a CI log / local run is useful) and the
send is skipped gracefully rather than crashing the workflow.
"""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import TrainingPaths, state_store


@dataclass(frozen=True)
class SmtpConfig:
    server: str
    port: int
    username: str
    password: str
    email_to: str
    email_from: str

    @classmethod
    def from_env(cls) -> Optional["SmtpConfig"]:
        """Build config from env vars; return None if any required var is missing."""
        required = {
            "SMTP_SERVER": os.getenv("SMTP_SERVER"),
            "SMTP_PORT": os.getenv("SMTP_PORT"),
            "SMTP_USERNAME": os.getenv("SMTP_USERNAME"),
            "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD"),
            "TRAINING_EMAIL_TO": os.getenv("TRAINING_EMAIL_TO"),
            "TRAINING_EMAIL_FROM": os.getenv("TRAINING_EMAIL_FROM"),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            print(f"[email] SMTP not configured (missing: {', '.join(missing)}); "
                  "skipping send.")
            return None
        try:
            port = int(required["SMTP_PORT"])  # type: ignore[arg-type]
        except (TypeError, ValueError):
            print(f"[email] Invalid SMTP_PORT {required['SMTP_PORT']!r}; skipping send.")
            return None
        return cls(
            server=required["SMTP_SERVER"],  # type: ignore[arg-type]
            port=port,
            username=required["SMTP_USERNAME"],  # type: ignore[arg-type]
            password=required["SMTP_PASSWORD"],  # type: ignore[arg-type]
            email_to=required["TRAINING_EMAIL_TO"],  # type: ignore[arg-type]
            email_from=required["TRAINING_EMAIL_FROM"],  # type: ignore[arg-type]
        )


def _fmt(value: Any, spec: str = "", dash: str = "n/a") -> str:
    if value is None:
        return dash
    if spec:
        try:
            return format(value, spec)
        except (ValueError, TypeError):
            return str(value)
    return str(value)


def build_subject(state: Dict[str, Any], *, promoted: bool, failed: bool) -> str:
    if failed:
        gen = (state.get("last_error") or {}).get("generation", state.get("generation"))
        return f"MCTS Nightly Training: FAILED — gen {gen}"
    elo = _fmt(state.get("elo"), ".0f")
    total = _fmt(state.get("total_games"), ",")
    tag = " — PROMOTED" if promoted else ""
    return f"MCTS Nightly Training: SUCCESS — Elo {elo} — {total} Games{tag}"


def build_body(
    state: Dict[str, Any],
    *,
    failed: bool,
    promoted: bool = False,
    baselines: Optional[List[Dict[str, Any]]] = None,
    findings: Optional[List[Any]] = None,
) -> str:
    champ = state.get("champion", {})
    lines: List[str] = []

    if failed:
        err = state.get("last_error") or {}
        lines += [
            "Status: FAILED",
            "",
            f"Failed at generation: {err.get('generation', state.get('generation'))}",
            f"Error: {err.get('message', 'unknown error')}",
            "",
            "Partial progress was preserved; the next nightly run resumes from the "
            "last valid state. Recent traceback:",
            "",
            (err.get("traceback") or "")[-1200:],
            "",
            f"Total games so far: {_fmt(state.get('total_games'), ',')}",
            f"Champion: {champ.get('name')} ({champ.get('version')})",
        ]
        return "\n".join(lines)

    lines += [
        "Status: SUCCESS",
        "",
        f"Champion: {champ.get('name')} ({champ.get('version')})"
        + ("  [PROMOTED this run]" if promoted else ""),
        f"Games This Run: {_fmt(state.get('games_today'), ',')}",
        f"Total Games: {_fmt(state.get('total_games'), ',')}",
        f"Generation: {state.get('generation')}",
        f"Elo: {_fmt(state.get('elo'), '.0f')}",
        f"TrueSkill: {_fmt(state.get('trueskill_mu'), '.1f')} ± "
        f"{_fmt(state.get('trueskill_sigma'), '.1f')}",
        "",
    ]

    if baselines:
        lines.append("Win Rates:")
        for b in baselines:
            lines.append(f"  {b['agent']}: {b['win_rate'] * 100:.0f}%")
        lines.append("")

    lines += [
        "Human Estimate:",
        f"  Target: {_fmt(state.get('human_target_elo'), '.0f')} Elo",
        f"  Current Gap: {_fmt((state.get('human_target_elo') or 0) - (state.get('elo') or 0), '+.0f')} Elo",
        f"  Projected Days Remaining: {_fmt(state.get('estimated_days_to_target'))}",
        f"  Estimate Confidence: {state.get('estimate_confidence')}",
        "",
    ]

    risk_findings = [f for f in (findings or []) if getattr(f, "severity", "info") != "info"]
    lines.append("Notes:")
    if risk_findings:
        for f in risk_findings:
            lines.append(f"  [{f.severity}] {f.message}")
    else:
        lines.append("  No regressions detected.")

    return "\n".join(lines)


def send_email(
    subject: str,
    body: str,
    *,
    config: SmtpConfig,
    send_fn: Optional[Callable[[SmtpConfig, EmailMessage], None]] = None,
) -> None:
    """Send the digest. ``send_fn`` is injectable so tests never open a socket."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.email_from
    msg["To"] = config.email_to
    msg.set_content(body)
    (send_fn or _smtp_send)(config, msg)


def _smtp_send(config: SmtpConfig, msg: EmailMessage) -> None:
    with smtplib.SMTP(config.server, config.port, timeout=60) as smtp:
        smtp.ehlo()
        try:
            smtp.starttls()
            smtp.ehlo()
        except smtplib.SMTPException:
            pass  # server may not support STARTTLS (e.g. local test relays)
        if config.username:
            smtp.login(config.username, config.password)
        smtp.send_message(msg)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Send the nightly training email digest.")
    parser.add_argument("--failed", action="store_true",
                        help="Compose a failure email (used by the workflow when training errored).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print subject/body, never send.")
    args = parser.parse_args(argv)

    paths = TrainingPaths.default()
    state = state_store.load_latest(paths)
    failed = args.failed or bool(state.get("last_error"))
    promoted = state.get("last_promoted_generation") == state.get("generation")

    subject = build_subject(state, promoted=promoted, failed=failed)
    body = build_body(state, failed=failed, promoted=promoted)

    print("=" * 70)
    print(f"Subject: {subject}")
    print("-" * 70)
    print(body)
    print("=" * 70)

    if args.dry_run:
        return 0

    config = SmtpConfig.from_env()
    if config is None:
        return 0  # graceful skip; body already printed
    try:
        send_email(subject, body, config=config)
        print(f"[email] Sent to {config.email_to}")
    except Exception as exc:  # noqa: BLE001 — never fail the workflow on email
        print(f"[email] Send failed: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
