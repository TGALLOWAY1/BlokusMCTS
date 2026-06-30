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
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training import TrainingPaths, diagnostics, ratings_db, state_store

# ---------------------------------------------------------------------------
# Canonical pipeline identity (see docs/training_workflows.md). The email always
# stamps these so a reader can prove which workflow/mode produced the report and
# spot immediately if an old-style report ever slips through again.
# ---------------------------------------------------------------------------

CANONICAL_WORKFLOW_FILE = ".github/workflows/nightly-mcts-training.yml"
TRAINING_MODE_MULTI_AGENT = "multi-agent-approach-comparison"
TRAINING_MODE_LEGACY = "legacy/incomplete (no approach comparison)"

# The canonical new-framework output. Its presence in the durable state is the
# single source of truth for "this report reflects a completed multi-agent run".
APPROACH_COMPARISON_KEY = "last_approach_comparison"


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


def champion_is_fixed(state: Dict[str, Any]) -> bool:
    """True when the champion has never been promoted (``last_promoted_generation``
    is null) — Elo movement is then drift of a fixed agent, not a strength change."""
    return state.get("last_promoted_generation") is None


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
# Provenance — proves which workflow/commit/mode produced this email
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Provenance:
    """Where this report came from. Stamped into the subject and a header block.

    ``multi_agent`` is the guardrail: it is True iff the durable state carries a
    completed approach-comparison record. When it is False the report is flagged
    LEGACY/INCOMPLETE everywhere (subject + banner) so an old-style email can
    never again masquerade as a fresh multi-agent result.
    """

    workflow_file: str
    workflow_name: Optional[str]
    run_id: Optional[str]
    run_url: Optional[str]
    commit_sha: Optional[str]
    branch: Optional[str]
    state_timestamp: Optional[str]
    generated_at: str
    mode: str
    multi_agent: bool

    @property
    def short_sha(self) -> str:
        return (self.commit_sha or "")[:7] or "nosha"

    @property
    def date(self) -> str:
        return self.generated_at[:10]


def build_provenance(state: Dict[str, Any]) -> Provenance:
    """Assemble provenance from the GitHub Actions env + the durable state.

    Everything degrades gracefully off-CI (env vars absent) so a local
    ``--dry-run`` still renders a complete, honest header.
    """
    server = os.getenv("GITHUB_SERVER_URL")
    repo = os.getenv("GITHUB_REPOSITORY")
    run_id = os.getenv("GITHUB_RUN_ID")
    run_url = (
        f"{server}/{repo}/actions/runs/{run_id}"
        if server and repo and run_id else None
    )
    multi_agent = bool(state.get(APPROACH_COMPARISON_KEY))
    return Provenance(
        workflow_file=CANONICAL_WORKFLOW_FILE,
        workflow_name=os.getenv("GITHUB_WORKFLOW"),
        run_id=run_id or state.get("run_id"),
        run_url=run_url,
        commit_sha=os.getenv("GITHUB_SHA"),
        branch=os.getenv("GITHUB_REF_NAME"),
        state_timestamp=state.get("updated_at"),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        mode=TRAINING_MODE_MULTI_AGENT if multi_agent else TRAINING_MODE_LEGACY,
        multi_agent=multi_agent,
    )


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
    state: Dict[str, Any],
    view: Optional[RunView] = None,
    *,
    failed: bool = False,
    provenance: Optional[Provenance] = None,
    alert: bool = False,
) -> str:
    """Compose the subject line, branded for the multi-agent framework.

    The subject distinguishes new vs old/incomplete reports at a glance and
    carries the date + short commit SHA so two reports are never confused. When
    ``alert`` is set (an arena terminated early, training could not run, a timeout,
    or a regression beyond noise) the subject is prefixed with 🚨 so a problem is
    obvious from the inbox without opening the mail::

        MCTS Lab Multi-Agent Training Report — 2026-06-27 — a1b2c3d — ELO 1042.7 (+12.4)
        🚨 MCTS Lab Multi-Agent Training Report — 2026-06-27 — a1b2c3d — ELO 1042.7 (-12.4)
        MCTS Lab Multi-Agent Training — INCOMPLETE (no multi-agent result) — 2026-06-27 — a1b2c3d
        MCTS Lab Multi-Agent Training — FAILED — 2026-06-27 — a1b2c3d
    """
    prov = provenance or build_provenance(state)
    tag = f"{prov.date} — {prov.short_sha}"
    prefix = "🚨 " if alert else ""

    if failed:
        return f"🚨 MCTS Lab Multi-Agent Training — FAILED — {tag}"
    # No completed multi-agent comparison, or no fresh Elo → never look like a
    # normal success. This is the guardrail against silent old-style reports.
    if not prov.multi_agent or view is None or not view.fresh or view.current_elo is None:
        return f"🚨 MCTS Lab Multi-Agent Training — INCOMPLETE (no multi-agent result) — {tag}"
    elo = view.current_elo
    if view.elo_delta_previous is None:
        return f"{prefix}MCTS Lab Multi-Agent Training Report — {tag} — ELO {elo:.1f} (baseline)"
    # A fixed champion (never promoted) means the delta is measurement drift, not a
    # strength change — say so in the headline rather than implying improvement (#5).
    drift = ", drift" if champion_is_fixed(state) else ""
    return (f"{prefix}MCTS Lab Multi-Agent Training Report — {tag} — "
            f"ELO {elo:.1f} ({view.elo_delta_previous:+.1f}{drift})")


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
    status = record.get("champion_status") or {}
    if status.get("measurement_drift"):
        lines.append("- ⚠️ Fixed-champion measurement drift: the champion has never been "
                     "promoted, so the Elo numbers below are rating variance of an unchanged "
                     "agent, not a strength change.")
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
    view: RunView, findings: Optional[List[Any]], failed: bool,
    *, has_alerts: bool = False,
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
        # Never claim "progressing normally" while the Alerts section is shouting —
        # this is the diagnostic *engine's* findings only, so say so explicitly.
        if has_alerts:
            out.append("- No additional diagnostic-engine findings beyond the "
                       "**Alerts** section above.")
        else:
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


# ---------------------------------------------------------------------------
# Verdict + Alerts — the at-a-glance "is this going well or not?" layer
# ---------------------------------------------------------------------------
#
# The user's standing requirement: the morning report must say *explicitly*
# whether things are going well, and any operational problem — an arena that
# terminated early, a training that could not be done, or a timeout — must be a
# loud 🚨 or ❌, never something you have to infer from a table.

# Substrings (case-insensitive) in an approach's reason / gate_reason that mean
# the evaluation arena was cut short or never ran to completion.
_BUDGET_MARKERS = (
    "time budget", "budget exhausted", "not evaluated", "deadline",
    "timed out", "timeout", "cut short",
)
# Substrings that mean the arena did not play enough games for a conclusive gate.
_INSUFFICIENT_MARKERS = ("enough_games", "min_total_games", "min_games", "insufficient")


@dataclass(frozen=True)
class Alert:
    """One operational problem worth shouting about. ``level`` picks the emoji."""

    level: str  # "alert" -> 🚨 (run did not complete) | "error" -> ❌ (bad result)
    title: str
    detail: str

    @property
    def emoji(self) -> str:
        return "🚨" if self.level == "alert" else "❌"


@dataclass(frozen=True)
class Verdict:
    """The headline good/bad call, rendered as the very first thing in the body."""

    emoji: str
    headline: str
    reasons: List[str]


def _row_text(row: Dict[str, Any]) -> str:
    return f"{row.get('reason') or ''} {row.get('gate_reason') or ''}".lower()


def _matches(row: Dict[str, Any], markers: tuple) -> bool:
    text = _row_text(row)
    return any(m in text for m in markers)


def collect_alerts(
    state: Dict[str, Any],
    view: RunView,
    approach_record: Optional[Dict[str, Any]],
    *,
    failed: bool,
    provenance: Provenance,
) -> List[Alert]:
    """Surface every operational problem as a 🚨/❌ alert (empty list == clean run).

    Detects, in order of severity: a hard crash, a run that never persisted a
    multi-agent result (timeout / cancellation), a stale Elo, every approach
    failing to produce a candidate, an arena terminated early for budget, a zero-
    game evaluation, too-few-games gates, and a real Elo regression beyond noise.
    """
    alerts: List[Alert] = []

    # 1. Hard crash — dominates; the rest of the state is unreliable after it.
    if failed:
        err = state.get("last_error") or {}
        alerts.append(Alert(
            "alert", "Training run crashed before completing",
            f"Failed at generation {err.get('generation', state.get('generation'))}: "
            f"{err.get('message', 'unknown error')}. Partial progress was preserved; "
            "the next run resumes from the last valid state.",
        ))
        return alerts

    # 2. No fresh multi-agent result persisted -> almost certainly a timeout.
    if not provenance.multi_agent:
        alerts.append(Alert(
            "alert", "Run did not finish — no multi-agent result was persisted",
            "No completed approach comparison was written to the durable state "
            f"(`{APPROACH_COMPARISON_KEY}` is absent). The most likely cause is that "
            "the run hit the job timeout or was cancelled before it could evaluate "
            "and persist. Every figure below reflects an earlier run, not this one.",
        ))
        return alerts

    # 3. Stale Elo — the record exists but the metrics DB did not advance this run.
    if not view.fresh:
        alerts.append(Alert(
            "error", "No fresh Elo was recorded this run",
            view.stale_reason or "The metrics timeline did not advance this cycle.",
        ))

    # 4. Approach-comparison health.
    rows = (approach_record or {}).get("rows") or []
    created = [r for r in rows if r.get("created")]
    if rows and not created:
        names = ", ".join(sorted({str(r.get("approach", "?")) for r in rows}))
        alerts.append(Alert(
            "error", "No candidate could be trained this run",
            f"Every approach failed to produce a valid candidate ({names}). No new "
            "agent was learned; the champion was retained by default.",
        ))
    elif created:
        cut = [r for r in created if _matches(r, _BUDGET_MARKERS)]
        if cut:
            names = ", ".join(sorted({str(r.get("approach", "?")) for r in cut}))
            alerts.append(Alert(
                "alert", "Arena terminated early — evaluation time budget exhausted",
                f"{len(cut)} approach(es) were not fully evaluated before the wall-clock "
                f"budget ran out: {names}. Their head-to-head results are missing or partial.",
            ))
        if all(int(r.get("games") or 0) == 0 for r in created):
            alerts.append(Alert(
                "alert", "Evaluation arena played zero games",
                "Candidates were generated but no head-to-head games ran, so there is no "
                "fresh win-rate or Elo measurement this cycle.",
            ))
        else:
            thin = [r for r in created if _matches(r, _INSUFFICIENT_MARKERS)]
            if thin:
                names = ", ".join(sorted({str(r.get("approach", "?")) for r in thin}))
                alerts.append(Alert(
                    "error", "Too few games to reach a verdict",
                    f"The arena did not play enough games for a conclusive promotion gate "
                    f"on: {names}. Raise --games / the time budget or the result stays "
                    "inconclusive.",
                ))

    # 5. Real Elo regression (declining beyond the measurement noise floor).
    traj = (approach_record or {}).get("trajectory") or {}
    gap = traj.get("gap_to_best")
    if traj.get("significant") and isinstance(gap, (int, float)) and gap < 0:
        alerts.append(Alert(
            "error", "Elo regression beyond the noise floor",
            f"The champion is {abs(gap):.1f} Elo below its multi-agent-era best — a move "
            "larger than the measurement noise, so the trend is genuinely declining.",
        ))

    return alerts


def overall_verdict(
    view: RunView,
    approach_record: Optional[Dict[str, Any]],
    alerts: List[Alert],
    *,
    champion_fixed: bool = False,
) -> Verdict:
    """Reduce the alerts + Elo direction to a single, explicit good/bad headline.

    ``champion_fixed`` is True when the champion has never been promoted
    (``last_promoted_generation`` is null). In that regime the agent under
    measurement is byte-for-byte fixed, so Elo movement is rating *drift*, not a
    strength change — judging "GOING WELL / NOT WELL" on its sign is the exact
    misread the audit (#5) called out. We surface a neutral drift verdict instead,
    unless a candidate was actually promoted this run.
    """
    if any(a.level == "alert" for a in alerts):
        return Verdict("🚨", "ALERT — the run did not complete cleanly",
                       [f"{a.emoji} {a.title}" for a in alerts])
    if any(a.level == "error" for a in alerts):
        return Verdict("❌", "NOT GOING WELL",
                       [f"{a.emoji} {a.title}" for a in alerts])

    # Operationally clean -> judge purely on Elo direction.
    reasons: List[str] = []
    winner = (approach_record or {}).get("winner")
    if winner:
        reasons.append(f"A candidate was promoted ({winner}).")
    dp = view.elo_delta_previous

    # Fixed champion + no promotion this run -> the Elo move is measurement drift.
    if champion_fixed and not winner:
        if dp is not None:
            reasons.append(f"Elo moved {dp:+.1f} vs the previous run, but the champion "
                           "has never been promoted — this is rating drift of a fixed "
                           "agent, not a strength change.")
        else:
            reasons.append("The champion has never been promoted; Elo here is a fixed-agent "
                           "measurement, not a strength change.")
        return Verdict("➖", "STEADY — fixed-champion measurement drift "
                       "(no promotion yet; Elo movement is not a strength change)", reasons)

    if dp is not None:
        verb = "rose" if dp > 0 else ("fell" if dp < 0 else "held")
        reasons.append(f"Elo {verb} {dp:+.1f} vs the previous run.")
    if winner or (dp is not None and dp > 0):
        return Verdict("✅", "GOING WELL", reasons or ["Elo is improving; no alerts fired."])
    if dp is not None and dp < 0:
        return Verdict("⚠️", "CAUTION — no alerts, but Elo is not improving "
                       "(within the noise floor)", reasons)
    return Verdict("➖", "STEADY — no material change and no alerts",
                   reasons or ["No change this run."])


def _verdict_lines(verdict: Verdict) -> List[str]:
    """Render the verdict as the prominent banner at the very top of the body."""
    out = [f"## {verdict.emoji} Overall: {verdict.headline}", ""]
    for r in verdict.reasons:
        out.append(f"- {r}")
    out.append("")
    return out


def _alert_lines(alerts: List[Alert]) -> List[str]:
    """Render the dedicated Alerts section (loud, or an explicit all-clear)."""
    out = ["## Alerts", ""]
    if not alerts:
        out += ["✅ No alerts — the run completed cleanly (arena finished, training ran, "
                "no timeout).", ""]
        return out
    for a in alerts:
        out.append(f"- {a.emoji} **{a.title}.** {a.detail}")
    out.append("")
    return out


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
    provenance: Optional[Provenance] = None,
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
    prov = provenance or build_provenance(state)

    champ = state.get("champion", {})
    cur = view.current or {}
    cur_elo = view.current_elo
    best_elo = float(view.best["champion_elo"]) if view.best else None
    last_eval = state.get("last_eval")
    approach_record = state.get("last_approach_comparison")

    # Explicit good/bad verdict + loud alerts, computed up front so they can lead
    # the report (the at-a-glance answer to "is this going well?").
    alerts = collect_alerts(
        state, view, approach_record, failed=failed, provenance=prov
    )
    verdict = overall_verdict(view, approach_record, alerts,
                              champion_fixed=champion_is_fixed(state))

    lines: List[str] = ["# MCTS Lab Multi-Agent Training Report", ""]

    # --- Verdict banner + Alerts (lead the report) ---------------------------
    lines += _verdict_lines(verdict)
    lines += _alert_lines(alerts)

    # --- Run provenance (always — proves which pipeline produced this) -------
    lines += ["## Run Provenance", ""]
    lines += [
        f"- Workflow: `{prov.workflow_name or 'nightly-mcts-training'}` "
        f"(`{prov.workflow_file}`)",
        f"- Training mode: **{prov.mode}**",
        f"- Run ID: {_fmt(prov.run_id)}",
        f"- Commit: `{prov.short_sha}`",
        f"- Branch: {_fmt(prov.branch)}",
        f"- State timestamp: {_fmt(prov.state_timestamp)}",
        f"- Report generated: {prov.generated_at}",
    ]
    if prov.run_url:
        lines.append(f"- GitHub Actions run: {prov.run_url}")
    lines.append("")

    # --- LEGACY / INCOMPLETE guardrail banner --------------------------------
    # If the durable state carries no completed approach-comparison record, the
    # figures below are stale (the run almost certainly timed out / was cancelled
    # before persisting its result). Flag it loudly rather than shipping a report
    # that looks like a normal old-style success.
    if not prov.multi_agent and not failed:
        lines += [
            "> ⚠️ **LEGACY / INCOMPLETE REPORT — NOT A MULTI-AGENT RESULT.**",
            ">",
            f"> No completed multi-agent approach comparison was found in the durable "
            f"state (`{APPROACH_COMPARISON_KEY}` is absent). The most likely cause is "
            "that the training run was cancelled or hit the job timeout before it could "
            "persist its result, so every figure below reflects **stale state from an "
            "earlier run**, not this one. See `docs/email_reporting.md`.",
            "",
        ]

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
    lines += _diagnostics_lines(view, findings, failed, has_alerts=bool(alerts))
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
        # Restrict the trend, deltas, and plot to the multi-agent era so the report
        # reflects the current approach and never drags in pre-multi-agent runs.
        history = ratings_db.recent_window(
            conn, limit=30, since_run_id=ratings_db.MULTI_AGENT_EPOCH_RUN_ID
        )
        findings = diagnostics.collect_findings(conn, state)
        plot_path, plot_game_count = _render_plot(conn, paths, state)
    finally:
        conn.close()

    view = build_run_view(history, state)
    prov = build_provenance(state)
    alerts = collect_alerts(
        state, view, state.get("last_approach_comparison"),
        failed=failed, provenance=prov,
    )
    verdict = overall_verdict(view, state.get("last_approach_comparison"), alerts,
                              champion_fixed=champion_is_fixed(state))
    subject = build_subject(
        state, view, failed=failed, provenance=prov, alert=bool(alerts)
    )
    body = build_body(
        state, view, failed=failed, promoted=promoted, findings=findings, paths=paths,
        plot_attached=plot_path is not None, plot_game_count=plot_game_count,
        provenance=prov,
    )
    return {
        "subject": subject, "body": body, "view": view, "state": state,
        "plot_path": plot_path, "provenance": prov,
        "alerts": alerts, "verdict": verdict,
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
            since_run_id=ratings_db.MULTI_AGENT_EPOCH_RUN_ID,
        )
        # Count only the multi-agent-era games the plot actually drew, for the callout.
        count = (
            len(ratings_db.champion_game_elo_series(
                conn, since_run_id=ratings_db.MULTI_AGENT_EPOCH_RUN_ID))
            if out is not None else None
        )
        return (out, count)
    except Exception as exc:  # noqa: BLE001 — plotting must never break the email
        print(f"[email] Plot render skipped ({type(exc).__name__}: {exc}).")
        return (None, None)


def _emit_github_outputs(composed: Dict[str, Any]) -> None:
    """Mirror the verdict + alerts onto the GitHub Actions run page.

    Writes a verdict/alerts block to ``$GITHUB_STEP_SUMMARY`` (the run's summary
    card) and emits ``::error::`` / ``::warning::`` annotations for each alert, so
    the Actions UI shows explicitly whether things are going well — not only the
    email. A no-op off-CI (env vars absent). Never raises.
    """
    try:
        verdict: Verdict = composed["verdict"]
        alerts: List[Alert] = composed["alerts"]
        summary_path = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_path:
            lines = [
                f"## {verdict.emoji} {verdict.headline}",
                "",
                f"**Subject:** {composed['subject']}",
                "",
            ]
            if alerts:
                lines.append("### Alerts")
                for a in alerts:
                    lines.append(f"- {a.emoji} **{a.title}.** {a.detail}")
            else:
                lines.append("✅ No alerts — the run completed cleanly.")
            lines.append("")
            with open(summary_path, "a", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
        # Inline annotations (show on the job + in the PR checks UI).
        for a in alerts:
            stream = "error" if a.level == "alert" else "warning"
            title = a.title.replace("\n", " ")
            detail = a.detail.replace("\n", " ")
            print(f"::{stream} title={title}::{detail}")
    except Exception as exc:  # noqa: BLE001 — observability must not break the run
        print(f"[email] GitHub summary skipped ({type(exc).__name__}: {exc}).")


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

    # Mirror the verdict/alerts onto the Actions run page (no-op off-CI).
    _emit_github_outputs(composed)

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
