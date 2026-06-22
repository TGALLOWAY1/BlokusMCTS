"""Human-readable nightly status report (``training/status.md``).

Renders the six sections from the spec — Summary, Daily Progress, Baseline
Results, Human Strength Estimate, Training Trends (7d/30d), Risks — from the
durable state + SQLite timeline. Rendering is split from disk I/O
(:func:`render_status` is pure) so it is unit-tested without touching the
filesystem. A timestamped snapshot is also written under ``state/reports/``.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from training import TrainingPaths, human_estimate, ratings_db


def _fmt(value: Any, spec: str = "", dash: str = "—") -> str:
    if value is None:
        return dash
    if spec:
        try:
            return format(value, spec)
        except (ValueError, TypeError):
            return str(value)
    return str(value)


def _baseline_rows(eval_result: Any) -> List[Dict[str, Any]]:
    """Extract champion-vs-opponent win rates from a pooled evaluation summary."""
    if eval_result is None:
        return []
    pooled = getattr(eval_result, "pooled_summary", {}) or {}
    win_stats = pooled.get("win_stats", {})
    rows: List[Dict[str, Any]] = []
    for name in ("candidate", "champion", "heuristic", "random", "prev_champion"):
        ws = win_stats.get(name)
        if ws:
            rows.append({
                "agent": name,
                "win_rate": ws.get("win_rate", 0.0),
                "games": int(ws.get("games_played", 0)),
            })
    return rows


def _trend_delta(rows: List[Dict[str, Any]], field: str) -> Optional[float]:
    if len(rows) < 2:
        return None
    return float(rows[-1][field]) - float(rows[0][field])


def render_status(data: Dict[str, Any]) -> str:
    """Render the full status markdown from a plain data bundle (pure)."""
    state = data["state"]
    est = data["human_estimate"]
    window7 = data.get("window7", [])
    window30 = data.get("window30", [])
    findings = data.get("findings", [])
    baselines = data.get("baselines", [])

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    champ = state.get("champion", {})
    lines: List[str] = []

    # --- Summary -------------------------------------------------------------
    lines += [
        "# MCTS Nightly Training — Status",
        "",
        f"_Updated {now} · run `{state.get('run_id')}`_",
        "",
        "## Summary",
        "",
        f"- **Result:** {'⚠️ failed' if state.get('last_error') else '✅ success'}",
        f"- **Champion:** `{champ.get('name')}` ({champ.get('version')})",
        f"- **Elo:** {_fmt(state.get('elo'), '.0f')}",
        f"- **TrueSkill:** {_fmt(state.get('trueskill_mu'), '.1f')} ± "
        f"{_fmt(state.get('trueskill_sigma'), '.1f')}",
        f"- **Total games:** {_fmt(state.get('total_games'), ',')}",
        f"- **Generation:** {state.get('generation')}",
        "",
    ]

    # --- Daily Progress ------------------------------------------------------
    elo_delta = _trend_delta(window7[-2:], "champion_elo") if len(window7) >= 2 else None
    lines += [
        "## Daily Progress",
        "",
        f"- **Games this run:** {_fmt(state.get('games_today'), ',')}",
        f"- **Days trained:** {state.get('days_trained')}",
        f"- **Elo change (last run):** {_fmt(elo_delta, '+.1f')}",
        "",
    ]

    # --- Baseline Results ----------------------------------------------------
    lines += ["## Baseline Results", ""]
    if baselines:
        lines += ["| Agent | Win rate | Games |", "|---|---|---|"]
        for b in baselines:
            lines.append(f"| `{b['agent']}` | {b['win_rate'] * 100:.1f}% | {b['games']} |")
    else:
        lines.append("_No candidate evaluation ran this cycle (insufficient snapshot data "
                     "for a re-fit, or out of time budget)._")
    lines.append("")

    # --- Human Strength Estimate --------------------------------------------
    lines += [
        "## Human Strength Estimate",
        "",
        f"- **Current strength:** {est.get('strength')} "
        f"(Elo {_fmt(est.get('current_elo'), '.0f')})",
        f"- **Target:** {_fmt(est.get('target_elo'), '.0f')} Elo "
        f"(gap {_fmt(est.get('gap'), '+.0f')})",
        f"- **Projected days remaining:** {_fmt(est.get('days_remaining'))}"
        + (f" (range {_fmt(est.get('lower_bound'))}–{_fmt(est.get('upper_bound'))})"
           if est.get('lower_bound') is not None else ""),
        f"- **Projected games remaining:** {_fmt(est.get('games_remaining'), ',')}",
        f"- **Confidence:** {est.get('confidence')}",
    ]
    if est.get("caveat"):
        lines.append(f"- _{est['caveat']}_")
    lines.append("")

    # --- Training Trends -----------------------------------------------------
    lines += ["## Training Trends", ""]
    d7 = _trend_delta(window7, "champion_elo")
    d30 = _trend_delta(window30, "champion_elo")
    mu7 = _trend_delta(window7, "champion_mu")
    lines += [
        f"- **7-day Elo trend:** {_fmt(d7, '+.1f')} over {len(window7)} run(s)",
        f"- **30-day Elo trend:** {_fmt(d30, '+.1f')} over {len(window30)} run(s)",
        f"- **7-day TrueSkill μ trend:** {_fmt(mu7, '+.2f')}",
        "",
    ]

    # --- Risks ---------------------------------------------------------------
    lines += ["## Risks", ""]
    risk_findings = [f for f in findings if getattr(f, "severity", "info") != "info"]
    if risk_findings:
        for f in risk_findings:
            lines.append(f"- **[{f.severity}] {f.code}** — {f.message}")
    else:
        lines.append("_No regressions, stagnation, or rating instability detected._")
    lines.append("")

    return "\n".join(lines)


def write_status(
    paths: TrainingPaths,
    conn: sqlite3.Connection,
    state: Dict[str, Any],
    *,
    findings: Optional[List[Any]] = None,
    eval_result: Any = None,
) -> str:
    """Assemble the data bundle, render, and write status.md (+ a snapshot copy)."""
    series = ratings_db.champion_elo_series(conn)
    est = human_estimate.summarize(
        float(state.get("elo", 1200.0)),
        series,
        target=float(state.get("human_target_elo", 1700)),
    )
    data = {
        "state": state,
        "human_estimate": est,
        "elo_series": series,
        "window7": ratings_db.recent_window(conn, limit=7),
        "window30": ratings_db.recent_window(conn, limit=30),
        "findings": findings or [],
        "baselines": _baseline_rows(eval_result),
    }
    markdown = render_status(data)

    paths.status_md.parent.mkdir(parents=True, exist_ok=True)
    paths.status_md.write_text(markdown, encoding="utf-8")
    # Timestamped immutable snapshot.
    paths.state_reports_dir.mkdir(parents=True, exist_ok=True)
    snapshot = paths.state_reports_dir / f"status_{state.get('run_id')}.md"
    snapshot.write_text(markdown, encoding="utf-8")
    return markdown
