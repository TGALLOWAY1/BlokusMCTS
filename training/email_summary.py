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
import html as _html
import os
import smtplib
import sys
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
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

def _elo_recent_summary(history: List[Dict[str, Any]], *, limit: int = 6) -> List[str]:
    """Compact per-generation Elo bullets (newest last) — the plain-text fallback.

    The full visualisation is the attached/inline plot; this is just a short,
    readable digest of the most recent generations for text-only mail clients,
    deliberately *not* the old wall-of-numbers table.
    """
    rows = history[-limit:]
    lines: List[str] = []
    for i, r in enumerate(rows):
        # Global index in the full history so deltas reference the true series.
        gi = len(history) - len(rows) + i
        elo = float(r["champion_elo"])
        d_prev = (elo - float(history[gi - 1]["champion_elo"])) if gi >= 1 else None
        flag = "  ⬆ promoted" if r.get("promoted") else ""
        delta = f" ({d_prev:+.1f})" if d_prev is not None else " (baseline)"
        lines.append(f"- gen {r.get('generation')}: {elo:.1f}{delta}{flag}")
    return lines


def _approach_lines(record: Optional[Dict[str, Any]]) -> List[str]:
    """Render the approach-comparison table for the email body."""
    if not record or not record.get("rows"):
        return ["_No approach comparison ran this cycle._"]
    lines: List[str] = []
    winner = record.get("winner")
    lines.append(f"- Promoted this run: {winner if winner else 'none'}")
    pool = record.get("pool") or {}
    if pool:
        lines.append(f"- Benchmark pool: {pool.get('version')} "
                     f"(opponents: {', '.join(pool.get('opponents', []))})")
    traj = record.get("trajectory") or {}
    if traj:
        sig = "real (beyond noise)" if traj.get("significant") else "within noise floor"
        lines.append(f"- Elo move vs best: {_fmt(traj.get('gap_to_best'), '+.1f')} ({sig})")
    lines += ["", "| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |",
              "|---|---|---|---|---|---|---|---|"]
    for r in record["rows"]:
        wr = r.get("win_rate_vs_champion")
        lines.append(
            f"| {r['approach']} | {'Yes' if r.get('created') else 'No'} "
            f"| {_fmt(r.get('games'))} "
            f"| {(format(wr * 100, '.0f') + '%') if wr is not None else '—'} "
            f"| {_fmt(r.get('elo_delta'), '+.1f')} | {_fmt(r.get('trueskill_delta'), '+.2f')} "
            f"| {'Yes' if r.get('promoted') else 'No'} | {r.get('gate_reason') or r.get('reason')} |"
        )
    return lines


def _learning_lines(last_eval: Optional[Dict[str, Any]]) -> List[str]:
    """Render the learning-method block (regression vs temporal difference)."""
    if not last_eval:
        return ["_No candidate was learned this cycle. Champion retained._"]
    learning = last_eval.get("learning") or {}
    method = learning.get("learning_method")
    if not method:
        return ["_Learning method not recorded for this run._"]
    pretty = "Temporal Difference (TD)" if method == "temporal_difference" else "Linear Regression"
    out = [f"- Method: **{pretty}**"]
    if learning.get("feature_set_version"):
        out.append(f"- Feature set: `{learning['feature_set_version']}`")
    if learning.get("training_rows") is not None:
        out.append(f"- Training rows used: {_fmt(learning.get('training_rows'), ',')}")
    if method == "temporal_difference":
        out.append(f"- TD loss: {_fmt(learning.get('td_loss'), '.5f')}")
        out.append(f"- Mean abs TD error: {_fmt(learning.get('mean_abs_td_error'), '.5f')}")
        rbp = learning.get("rows_by_phase") or {}
        if rbp:
            out.append("- Rows by phase: "
                       + ", ".join(f"{k}={rbp.get(k)}" for k in ("early", "mid", "late") if k in rbp))
    else:
        out.append(f"- Global R²: {_fmt(learning.get('r2_global'), '.4f')}")
    promoted = bool(last_eval.get("promoted"))
    out.append(f"- Result: {'✅ candidate promoted' if promoted else '❌ not improved — champion retained'}")

    failure = last_eval.get("promotion_failure")
    if failure and not promoted:
        out += [
            "",
            "**Why it did not improve:**",
            f"- Failed gate: `{failure.get('failed_gate') or 'n/a'}`",
            f"- Runner-up: `{failure.get('runner_up') or 'n/a'}`",
            f"- Head-to-head: candidate {failure.get('candidate_win_rate', 0.0) * 100:.1f}% "
            f"vs champion {failure.get('champion_win_rate', 0.0) * 100:.1f}%",
            f"- TrueSkill μ margin: {_fmt(failure.get('trueskill_mu_margin'), '+.3f')}",
            f"- Games: {_fmt(failure.get('n_games'), ',')}, seeds: {failure.get('seeds')}",
        ]
    return out


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
    plot_attached: bool = False,
    plot_game_count: Optional[int] = None,
) -> str:
    """Render the full markdown email body.

    ``plot_attached`` toggles the "see the attached Elo plot" callout; the plot
    itself (per-game trajectory) is the headline visualisation and replaces the old
    Elo-progression table. ``plot_game_count`` is the number of per-game points
    behind the plot (for the callout text).
    """
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
    if plot_attached:
        if plot_game_count:
            detail = (
                f"The champion's Elo is now recomputed after every individual game — "
                f"the plot draws all {plot_game_count:,} per-game ratings as one "
                "trajectory with a trend line, so whether the distribution is moving "
                "in the right direction is obvious at a glance."
            )
        else:
            detail = (
                "It plots one point per generation for now; once the next runs record "
                "per-game ratings, the curve fills in after every individual game so "
                "the trend is visible at a glance."
            )
        lines += [
            "📈 **See the attached `elo_trend.png`** (shown inline above in HTML mail "
            f"clients). {detail}",
            "",
        ]
    else:
        lines += [
            "_(No plot was generated this cycle — matplotlib unavailable or the "
            "per-game timeline is empty. The recent generations below summarise the "
            "trend.)_",
            "",
        ]
    if view.history:
        lines += ["Recent generations (newest last):", ""]
        lines += _elo_recent_summary(view.history)
    else:
        lines.append("_No recorded runs yet._")
    lines.append("")

    # --- Approach Comparison (new framework) ---------------------------------
    approach_record = state.get("last_approach_comparison")
    if approach_record:
        lines += ["## Approach Comparison", ""]
        lines += _approach_lines(approach_record)
        lines.append("")

    # --- Learning Method -----------------------------------------------------
    lines += ["## Learning Method", ""]
    if last_eval is None and approach_record:
        lines.append("_See the Approach Comparison section above for each approach's "
                     "candidate, result, and specific reason._")
    else:
        lines += _learning_lines(last_eval)
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

_PLOT_CID = "elo-plot"


def _html_body(text_body: str, *, plot_inline: bool) -> str:
    """Wrap the plain-text body in minimal HTML, embedding the plot inline on top.

    Kept deliberately simple (a leading ``<img>`` + the escaped text in a ``<pre>``)
    so it renders consistently across mail clients without a markdown dependency.
    """
    img = (
        f'<img src="cid:{_PLOT_CID}" alt="Champion Elo trajectory" '
        'style="max-width:100%;height:auto;margin-bottom:16px;" />'
        if plot_inline else ""
    )
    escaped = _html.escape(text_body)
    return (
        "<!DOCTYPE html><html><body "
        'style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">'
        f"{img}"
        '<pre style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;'
        'white-space:pre-wrap;font-size:13px;line-height:1.45;">'
        f"{escaped}</pre></body></html>"
    )


def build_message(
    subject: str,
    body: str,
    *,
    email_from: str,
    email_to: str,
    plot_path: Optional[Path | str] = None,
) -> EmailMessage:
    """Assemble the email, embedding the Elo plot inline and as an attachment.

    Structure when a plot is present::

        multipart/mixed
        ├── multipart/alternative
        │   ├── text/plain                (the markdown body)
        │   └── multipart/related
        │       ├── text/html             (escaped body + inline <img>)
        │       └── image/png             (inline, cid:elo-plot)
        └── image/png                     (downloadable attachment)

    The plain-text part is always present, so text-only clients still get the full
    report. Any failure attaching the image degrades to text-only rather than
    raising.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.set_content(body)  # plain-text fallback (always)

    png = Path(plot_path) if plot_path else None
    if png and png.exists():
        try:
            img = png.read_bytes()
            msg.add_alternative(_html_body(body, plot_inline=True), subtype="html")
            # The HTML part is the last payload; embed the image inside it (cid).
            msg.get_payload()[1].add_related(
                img, maintype="image", subtype="png", cid=f"<{_PLOT_CID}>"
            )
            # Also attach as a normal file so text-only clients can open it.
            msg.add_attachment(
                img, maintype="image", subtype="png", filename="elo_trend.png"
            )
        except Exception as exc:  # noqa: BLE001 — never fail the email over the plot
            print(f"[email] Could not attach plot ({type(exc).__name__}: {exc}); "
                  "sending text-only.")
    return msg


def send_email(
    subject: str,
    body: str,
    *,
    config: SmtpConfig,
    plot_path: Optional[Path | str] = None,
    send_fn: Optional[Callable[[SmtpConfig, EmailMessage], None]] = None,
) -> None:
    """Send the digest. ``send_fn`` is injectable so tests never open a socket."""
    msg = build_message(
        subject, body,
        email_from=config.email_from, email_to=config.email_to, plot_path=plot_path,
    )
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
        plot_path, plot_game_count = _render_plot(conn, paths, state)
    finally:
        conn.close()

    view = build_run_view(history, state)
    subject = build_subject(state, view, failed=failed)
    body = build_body(
        state, view, failed=failed, promoted=promoted, findings=findings, paths=paths,
        plot_attached=plot_path is not None, plot_game_count=plot_game_count,
    )
    return {
        "subject": subject, "body": body, "view": view, "state": state,
        "plot_path": plot_path,
    }


def _render_plot(conn, paths: TrainingPaths, state: Dict[str, Any]):
    """Render the Elo trajectory PNG; return ``(path_or_None, game_count)``.

    Failure is non-fatal — a missing plot just means the email ships text-only.
    """
    try:
        from training import elo_plot

        paths.reports_dir.mkdir(parents=True, exist_ok=True)
        out = elo_plot.render_elo_plot(
            conn, paths.reports_dir / "elo_trend.png",
            target_elo=float(state.get("human_target_elo", 1700) or 0) or None,
        )
        count = ratings_db.max_game_number(conn) if out is not None else None
        return (out, count)
    except Exception as exc:  # noqa: BLE001 — plotting must never break the email
        print(f"[email] Plot render skipped ({type(exc).__name__}: {exc}).")
        return (None, None)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Send the nightly training email digest.")
    parser.add_argument("--failed", action="store_true",
                        help="Compose a failure email (used by the workflow when training errored).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print subject/body, never send.")
    args = parser.parse_args(argv)

    composed = compose(failed=args.failed)
    subject, body = composed["subject"], composed["body"]
    plot_path = composed.get("plot_path")

    print("=" * 70)
    print(f"Subject: {subject}")
    print("-" * 70)
    print(body)
    print("=" * 70)
    print(f"[email] Plot: {plot_path if plot_path else 'none (text-only)'}")

    if args.dry_run:
        return 0

    config = SmtpConfig.from_env()
    if config is None:
        return 0  # graceful skip; body already printed
    try:
        send_email(subject, body, config=config, plot_path=plot_path)
        print(f"[email] Sent to {config.email_to}")
    except Exception as exc:  # noqa: BLE001 — never fail the workflow on email
        print(f"[email] Send failed: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
