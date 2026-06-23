"""Concise email digest of a nightly run (SMTP via repository secrets).

The morning email must be readable without opening GitHub *and* it must never
silently report stale data. It now reads the durable, append-only rating timeline
(``training/state/ratings.sqlite``) — the same file the training run records a
fresh Elo into every generation — so the headline Elo, the run-over-run delta, and
the multi-run ELO trend are always derived from the latest recorded measurement.

Three guarantees:

* **Fresh or honest.** If a fresh Elo could not be calculated/persisted for the
  current run (empty timeline, or the latest recorded run_id ≠ the current run),
  the email says so plainly ("No fresh ELO was calculated for this run") and
  explains why, instead of echoing an old value as if it were new.
* **Trend, not a scalar.** The body includes a readable ELO-progression table and
  Δ-vs-previous / Δ-vs-best so a flat or regressing run is obvious at a glance.
* **No secrets in code.** SMTP credentials come exclusively from environment
  variables / repo secrets. If they are incomplete the body is still printed to
  stdout and the send is skipped gracefully rather than crashing the workflow.
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

from training import TrainingPaths, diagnostics, ratings_db, state_store


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


# ---------------------------------------------------------------------------
# Run view — derives the headline Elo + deltas from the recorded timeline
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RunView:
    """Everything the email needs about *where the latest Elo sits*.

    Built purely from the recorded ``run_summary`` timeline (oldest-first) plus
    the in-memory ``state`` so it is trivially unit-tested. ``fresh`` is the
    single source of truth for "did this run actually produce a new Elo?".
    """

    fresh: bool
    current: Optional[Dict[str, Any]]
    previous: Optional[Dict[str, Any]]
    best: Optional[Dict[str, Any]]
    best_prior: Optional[Dict[str, Any]]
    elo_delta_previous: Optional[float]
    elo_delta_best: Optional[float]
    history: List[Dict[str, Any]]
    stale_reason: Optional[str]

    @property
    def current_elo(self) -> Optional[float]:
        return None if self.current is None else float(self.current["champion_elo"])


def build_run_view(history: List[Dict[str, Any]], state: Dict[str, Any]) -> RunView:
    """Compute the headline Elo, Δ-vs-previous, and Δ-vs-best from the timeline.

    ``history`` is the ``run_summary`` window oldest-first (``recent_window``).
    Freshness fails — with an explanatory ``stale_reason`` — when the timeline is
    empty or when the most recent recorded run does not match the current
    ``state['run_id']`` (i.e. the metrics DB was not updated this cycle).
    """
    history = list(history or [])
    if not history:
        return RunView(
            fresh=False, current=None, previous=None, best=None, best_prior=None,
            elo_delta_previous=None, elo_delta_best=None, history=[],
            stale_reason="No runs are recorded in the ratings timeline "
                         "(the metrics database is empty or missing).",
        )

    current = history[-1]
    previous = history[-2] if len(history) >= 2 else None
    best = max(history, key=lambda r: float(r["champion_elo"]))
    prior = history[:-1]
    best_prior = max(prior, key=lambda r: float(r["champion_elo"])) if prior else None

    cur_elo = float(current["champion_elo"])
    delta_prev = (cur_elo - float(previous["champion_elo"])) if previous else None
    delta_best = (cur_elo - float(best_prior["champion_elo"])) if best_prior else None

    fresh = True
    stale_reason: Optional[str] = None
    run_id = state.get("run_id")
    if run_id and current.get("run_id") != run_id:
        fresh = False
        stale_reason = (
            f"The metrics timeline was not updated for the current run "
            f"`{run_id}` — the latest recorded run is `{current.get('run_id')}`, "
            "so the Elo below is from an earlier run."
        )

    return RunView(
        fresh=fresh, current=current, previous=previous, best=best,
        best_prior=best_prior, elo_delta_previous=delta_prev,
        elo_delta_best=delta_best, history=history, stale_reason=stale_reason,
    )


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------

def build_subject(
    state: Dict[str, Any], view: Optional[RunView] = None, *, failed: bool = False
) -> str:
    """Compose the subject line.

    Success with a fresh Elo →  ``MCTS Nightly Training Report — ELO 1042.7 (+12.4)``
    Failure / no fresh Elo    →  ``MCTS Nightly Training Failed — No New ELO Calculated``
    """
    if failed or view is None or not view.fresh or view.current_elo is None:
        return "MCTS Nightly Training Failed — No New ELO Calculated"
    elo = view.current_elo
    if view.elo_delta_previous is None:
        return f"MCTS Nightly Training Report — ELO {elo:.1f} (baseline)"
    return f"MCTS Nightly Training Report — ELO {elo:.1f} ({view.elo_delta_previous:+.1f})"


# ---------------------------------------------------------------------------
# Body sections
# ---------------------------------------------------------------------------

def _elo_trend_table(history: List[Dict[str, Any]], *, limit: int = 8) -> List[str]:
    """Render the ELO progression table (most recent ``limit`` measurements)."""
    rows = history[-limit:]
    lines = [
        "| Run | Date | Gen | Games | ELO | Δ Previous | Δ Best | Status |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for i, r in enumerate(rows):
        # Global index in the full history so deltas reference the true series.
        gi = len(history) - len(rows) + i
        elo = float(r["champion_elo"])
        d_prev = (elo - float(history[gi - 1]["champion_elo"])) if gi >= 1 else None
        prior = history[:gi]
        best_prior = max((float(p["champion_elo"]) for p in prior), default=None)
        d_best = (elo - best_prior) if best_prior is not None else None
        date = str(r.get("timestamp", ""))[:10]
        run = str(r.get("run_id", ""))[:16]
        status = "promoted" if r.get("promoted") else "completed"
        lines.append(
            f"| {run} | {date} | {r.get('generation')} | "
            f"{_fmt(r.get('games_today'), ',', dash='—')} | {elo:.1f} | "
            f"{_fmt(d_prev, '+.1f', dash='—')} | {_fmt(d_best, '+.1f', dash='—')} | "
            f"{status} |"
        )
    return lines


def _match_breakdown(last_eval: Optional[Dict[str, Any]]) -> List[str]:
    if not last_eval:
        return [
            "_No candidate evaluation ran this cycle (the evaluator could not "
            "re-fit yet, or the time budget was exhausted). No fresh head-to-head "
            "win rates are available._",
        ]
    lines = [
        f"Evaluation games: {_fmt(last_eval.get('total_games'), ',')} "
        f"across {_fmt(last_eval.get('n_seeds'))} seed(s) "
        f"{last_eval.get('seeds')}",
        "",
        "| Agent | Win rate | Games |",
        "|---|---:|---:|",
    ]
    for b in last_eval.get("baselines", []):
        lines.append(
            f"| `{b['agent']}` | {b['win_rate'] * 100:.1f}% | {b.get('games', 0)} |"
        )
    return lines


def _diagnostics_lines(
    view: RunView, findings: Optional[List[Any]], failed: bool
) -> List[str]:
    out: List[str] = []
    if failed:
        out.append("- ⚠️ Training step reported a failure (see crash summary above).")
    if not view.fresh and view.stale_reason:
        out.append(f"- 🔴 No fresh ELO was calculated for this run. {view.stale_reason}")
    risk = [f for f in (findings or []) if getattr(f, "severity", "info") != "info"]
    for f in risk:
        out.append(f"- [{getattr(f, 'severity', 'info')}] {getattr(f, 'code', '')}: "
                   f"{getattr(f, 'message', '')}")
    if not out:
        out.append("- No diagnostic warnings. Training is progressing normally.")
    return out


def _links_lines(paths: TrainingPaths, state: Dict[str, Any]) -> List[str]:
    def rel(p: Any) -> str:
        try:
            return str(os.path.relpath(str(p), str(paths.root)))
        except ValueError:
            return str(p)

    checkpoints = state_store.list_checkpoints(paths)
    latest_ckpt = (
        rel(paths.checkpoints_dir / f"champion_gen{checkpoints[-1].get('generation')}.json")
        if checkpoints else "none yet (no promotion has occurred)"
    )
    lines = [
        f"- Latest checkpoint: {latest_ckpt}",
        f"- Metrics / history DB: {rel(paths.ratings_db)}",
        f"- Per-generation history: {rel(paths.history_jsonl)}",
        f"- Status report: {rel(paths.status_md)}",
        f"- Diagnosis: {rel(paths.diagnosis_md)}",
        f"- Arena results: {rel(paths.selfplay_runs_dir)}",
    ]
    server = os.getenv("GITHUB_SERVER_URL")
    repo = os.getenv("GITHUB_REPOSITORY")
    run_id = os.getenv("GITHUB_RUN_ID")
    if server and repo and run_id:
        lines.append(f"- GitHub Actions run: {server}/{repo}/actions/runs/{run_id}")
    return lines


def build_body(
    state: Dict[str, Any],
    view: Optional[RunView] = None,
    *,
    failed: bool = False,
    promoted: bool = False,
    findings: Optional[List[Any]] = None,
    paths: Optional[TrainingPaths] = None,
) -> str:
    """Render the full markdown email body."""
    if view is None:
        view = build_run_view([], state)
    if paths is None:
        paths = TrainingPaths.default()

    champ = state.get("champion", {})
    cur = view.current or {}
    cur_elo = view.current_elo
    best_elo = float(view.best["champion_elo"]) if view.best else None
    last_eval = state.get("last_eval")

    lines: List[str] = ["# MCTS Nightly Training Report", ""]

    # --- Failure / no-fresh-Elo banner --------------------------------------
    if failed:
        err = state.get("last_error") or {}
        lines += [
            "**Status: FAILED — No New ELO Calculated.**",
            "",
            f"Failed at generation: {err.get('generation', state.get('generation'))}",
            f"Error: {err.get('message', 'unknown error')}",
            "",
            "Partial progress was preserved; the next nightly run resumes from the "
            "last valid state. Recent traceback:",
            "",
            "```",
            (err.get("traceback") or "")[-1200:],
            "```",
            "",
        ]
    elif not view.fresh:
        lines += [
            "**No fresh ELO was calculated for this run.**",
            "",
            view.stale_reason or "The metrics timeline did not advance this cycle.",
            "",
            "The figures below reflect the most recent *recorded* run, not a new "
            "measurement.",
            "",
        ]

    # --- Summary -------------------------------------------------------------
    lines += [
        "## Summary",
        "",
        f"- Run ID: {state.get('run_id')}",
        f"- Status: {'FAILED' if failed else ('STALE — no fresh Elo' if not view.fresh else 'completed')}"
        + ("  [PROMOTED this run]" if promoted else ""),
        f"- Agent evaluated: {champ.get('name')} ({champ.get('version')})",
        f"- Games played (this run): {_fmt(state.get('games_today'), ',')}",
        f"- Current ELO: {_fmt(cur_elo, '.1f')}",
        f"- Change vs previous run: {_fmt(view.elo_delta_previous, '+.1f', dash='— (first run)')}",
        f"- Change vs best historical run: {_fmt(view.elo_delta_best, '+.1f', dash='— (first run)')}",
        f"- Best historical ELO: {_fmt(best_elo, '.1f')}",
        f"- TrueSkill: {_fmt(state.get('trueskill_mu'), '.1f')} ± "
        f"{_fmt(state.get('trueskill_sigma'), '.1f')}",
        f"- Total games: {_fmt(state.get('total_games'), ',')}",
        f"- Generation: {cur.get('generation', state.get('generation'))}",
        "",
    ]

    # --- ELO Trend -----------------------------------------------------------
    lines += ["## ELO Trend", ""]
    if view.history:
        lines += _elo_trend_table(view.history)
    else:
        lines.append("_No recorded runs yet._")
    lines.append("")

    # --- Match Breakdown -----------------------------------------------------
    lines += ["## Match Breakdown", ""]
    lines += _match_breakdown(last_eval)
    lines.append("")

    # --- Human Estimate -------------------------------------------------------
    lines += [
        "## Human Strength Estimate",
        "",
        f"- Target: {_fmt(state.get('human_target_elo'), '.0f')} Elo",
        f"- Current gap: {_fmt((state.get('human_target_elo') or 0) - (cur_elo or 0), '+.0f')} Elo",
        f"- Projected days remaining: {_fmt(state.get('estimated_days_to_target'))}",
        f"- Estimate confidence: {state.get('estimate_confidence')}",
        "",
    ]

    # --- Diagnostics ---------------------------------------------------------
    lines += ["## Diagnostics", ""]
    lines += _diagnostics_lines(view, findings, failed)
    lines.append("")

    # --- Links / Artifacts ---------------------------------------------------
    lines += ["## Links / Artifacts", ""]
    lines += _links_lines(paths, state)
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

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


def compose(
    paths: Optional[TrainingPaths] = None, *, failed: bool = False
) -> Dict[str, Any]:
    """Load state + timeline and return ``{subject, body, view, ...}`` (pure-ish).

    Factored out of :func:`main` so a local preview / test can render the exact
    email without touching SMTP.
    """
    paths = paths or TrainingPaths.default()
    state = state_store.load_latest(paths)
    failed = failed or bool(state.get("last_error"))
    promoted = (
        state.get("last_promoted_generation") is not None
        and state.get("last_promoted_generation") == state.get("generation")
    )

    conn = ratings_db.connect(paths.ratings_db)
    try:
        history = ratings_db.recent_window(conn, limit=30)
        findings = diagnostics.collect_findings(conn, state)
    finally:
        conn.close()

    view = build_run_view(history, state)
    subject = build_subject(state, view, failed=failed)
    body = build_body(
        state, view, failed=failed, promoted=promoted, findings=findings, paths=paths
    )
    return {"subject": subject, "body": body, "view": view, "state": state}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Send the nightly training email digest.")
    parser.add_argument("--failed", action="store_true",
                        help="Compose a failure email (used by the workflow when training errored).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print subject/body, never send.")
    args = parser.parse_args(argv)

    composed = compose(failed=args.failed)
    subject, body = composed["subject"], composed["body"]

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
