"""Deterministic, no-LLM diagnostics over the training timeline.

Inspects the rating timeline + run history and surfaces anything worth a human's
attention: regressions, stalled learning, rating instability, an unhealthy or
never-triggering evaluator re-fit, and promotion droughts. Output is
``training/reports/latest_diagnosis.md`` — **always written**, even when nothing is
wrong ("No issues detected."), so the workflow's commit/email steps always have a
file to attach.

The findings list is returned so the status report's Risks section and the email
digest can reuse it without re-deriving anything. A separate optional Claude Code
workflow step may append richer commentary, but is never required for this to work.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

from training import TrainingPaths, ratings_db

# Thresholds (Elo points / counts). Conservative so we don't cry wolf.
_REGRESSION_ELO_DROP = 25.0
_STAGNATION_ELO_BAND = 3.0
_INSTABILITY_SIGMA_RISE = 1.5
_PROMOTION_DROUGHT_RUNS = 10
_REFIT_MIN_ROWS = 200  # mirrors champion_loop.MIN_ROWS_FOR_REFIT


@dataclass(frozen=True)
class Finding:
    """A single diagnostic observation."""

    severity: str  # "info" | "warn" | "critical"
    code: str
    message: str
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "evidence": self.evidence,
        }


# ---------------------------------------------------------------------------
# Detectors (pure; take plain data so they're trivially unit-tested)
# ---------------------------------------------------------------------------

def detect_regression(elo_series: List[Dict[str, Any]], *, window: int = 5) -> List[Finding]:
    pts = elo_series[-(window + 1):]
    if len(pts) < 2:
        return []
    peak = max(p["elo"] for p in pts)
    current = pts[-1]["elo"]
    drop = peak - current
    if drop >= _REGRESSION_ELO_DROP:
        return [Finding(
            "warn", "regression",
            f"Champion Elo dropped {drop:.0f} from a recent peak of {peak:.0f} to {current:.0f}.",
            f"last {len(pts)} points: {[round(p['elo']) for p in pts]}",
        )]
    return []


def detect_stagnation(elo_series: List[Dict[str, Any]], *, window: int = 7) -> List[Finding]:
    pts = elo_series[-window:]
    if len(pts) < window:
        return []
    spread = max(p["elo"] for p in pts) - min(p["elo"] for p in pts)
    if spread <= _STAGNATION_ELO_BAND:
        return [Finding(
            "warn", "stagnation",
            f"Champion Elo has moved only {spread:.1f} points over the last {window} runs — "
            "learning may have stalled.",
            f"range over window: {round(min(p['elo'] for p in pts))}–{round(max(p['elo'] for p in pts))}",
        )]
    return []


def detect_rating_instability(rating_rows: List[Dict[str, Any]]) -> List[Finding]:
    """Champion sigma rising run-over-run signals unstable / noisy ratings."""
    champ = [r for r in rating_rows if r.get("agent") == "champion"]
    if len(champ) < 2:
        return []
    sig_rise = champ[-1]["trueskill_sigma"] - champ[-2]["trueskill_sigma"]
    if sig_rise >= _INSTABILITY_SIGMA_RISE:
        return [Finding(
            "info", "rating_instability",
            f"Champion TrueSkill σ rose {sig_rise:.2f} since the previous run "
            "(expected right after a promotion, where σ is intentionally reset).",
            f"σ: {champ[-2]['trueskill_sigma']:.2f} → {champ[-1]['trueskill_sigma']:.2f}",
        )]
    return []


def detect_refit_health(state: Dict[str, Any]) -> List[Finding]:
    rows = int(state.get("total_snapshot_rows", 0))
    if rows < _REFIT_MIN_ROWS:
        return [Finding(
            "info", "refit_pending",
            f"Only {rows} snapshot rows accumulated (need {_REFIT_MIN_ROWS} before the "
            "evaluator can re-fit) — no candidate will be generated until then.",
            f"rows={rows}",
        )]
    return []


def detect_promotion_drought(
    last_promoted_gen: Any, current_gen: int, *, threshold: int = _PROMOTION_DROUGHT_RUNS
) -> List[Finding]:
    if last_promoted_gen is None:
        if current_gen >= threshold:
            return [Finding(
                "info", "no_promotion_yet",
                f"No champion promotion in {current_gen} generations. The seed champion "
                "may already be near-optimal, or candidates aren't clearing the gates.",
            )]
        return []
    gap = current_gen - int(last_promoted_gen)
    if gap >= threshold:
        return [Finding(
            "warn", "promotion_drought",
            f"{gap} generations since the last promotion (gen {last_promoted_gen}).",
        )]
    return []


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def collect_findings(conn: sqlite3.Connection, state: Dict[str, Any]) -> List[Finding]:
    """Run every detector against the current DB + state."""
    elo_series = ratings_db.champion_elo_series(conn)
    rating_rows = [
        dict(r) for r in conn.execute(
            "SELECT * FROM rating_history WHERE agent='champion' ORDER BY id ASC"
        ).fetchall()
    ]
    findings: List[Finding] = []
    findings += detect_regression(elo_series)
    findings += detect_stagnation(elo_series)
    findings += detect_rating_instability(rating_rows)
    findings += detect_refit_health(state)
    findings += detect_promotion_drought(
        state.get("last_promoted_generation"), int(state.get("generation", 0))
    )
    return findings


def render_diagnosis(findings: List[Finding], state: Dict[str, Any]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Nightly Training Diagnosis",
        "",
        f"_Generated: {now} · run `{state.get('run_id')}` · generation "
        f"{state.get('generation')}_",
        "",
    ]
    if not findings:
        lines += ["**No issues detected.** Training is progressing normally.", ""]
        return "\n".join(lines)

    order = {"critical": 0, "warn": 1, "info": 2}
    findings = sorted(findings, key=lambda f: order.get(f.severity, 3))
    icon = {"critical": "🔴", "warn": "🟠", "info": "🔵"}
    lines.append(f"**{len(findings)} finding(s):**")
    lines.append("")
    for f in findings:
        lines.append(f"- {icon.get(f.severity, '•')} **[{f.severity}] {f.code}** — {f.message}")
        if f.evidence:
            lines.append(f"  - _evidence: {f.evidence}_")
    lines.append("")
    return "\n".join(lines)


def write_diagnosis(
    paths: TrainingPaths, conn: sqlite3.Connection, state: Dict[str, Any]
) -> List[Finding]:
    """Collect findings, write latest_diagnosis.md (always), and return findings."""
    findings = collect_findings(conn, state)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)
    paths.diagnosis_md.write_text(render_diagnosis(findings, state), encoding="utf-8")
    return findings
