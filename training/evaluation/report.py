"""Approach-comparison report: the per-run table + detail the audit asked for.

Builds a machine-readable comparison record (persisted into state for the status/email
reports to reuse) and renders ``training/reports/approach_comparison.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional


def _h2h_win_share(vs_champion: Dict[str, Any]) -> Optional[float]:
    cw = vs_champion.get("candidate_wins")
    chw = vs_champion.get("champion_wins")
    if cw is None or chw is None:
        return None
    total = int(cw) + int(chw)
    return (int(cw) / total) if total else None


def build_comparison_record(
    *,
    run_id: str,
    now_iso: str,
    candidates: List[Any],          # List[approaches.Candidate] (all, created or not)
    evals_by_name: Dict[str, Any],  # name -> head_to_head.CandidateEval
    gates_by_name: Dict[str, Any],  # name -> promotion_gate.GateResult
    winner_name: Optional[str],
    pool: Optional[Dict[str, Any]],
    trajectory: Optional[Dict[str, Any]],
    seeds: List[int],
    generation: Optional[int] = None,
    last_promoted_generation: Optional[int] = None,
    confirmation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble the comparison record (one row per attempted approach).

    ``champion_status`` records whether the champion has *ever* been promoted.
    When it has not (``last_promoted_generation is None``) the agent under
    measurement is byte-for-byte fixed, so any Elo movement is rating *drift* of a
    fixed agent — not a learned strength change. Downstream reports key off
    ``measurement_drift`` to frame the Elo headline honestly (audit follow-up #5)."""
    rows: List[Dict[str, Any]] = []
    for cand in candidates:
        ce = evals_by_name.get(cand.name)
        gate = gates_by_name.get(cand.name)
        vs = getattr(ce, "vs_champion", {}) if ce else {}
        rows.append({
            "approach": cand.approach,
            "name": cand.name,
            "created": bool(cand.created),
            "reason": cand.reason,
            "games": getattr(ce, "games", 0) if ce else 0,
            "win_rate_vs_champion": _h2h_win_share(vs) if ce else None,
            "win_rate": getattr(ce, "win_rate", None) if ce else None,
            "elo_delta": getattr(ce, "elo_delta_vs_champion", None) if ce else None,
            "trueskill_delta": getattr(ce, "trueskill_mu_delta_vs_champion", None) if ce else None,
            "promoted": bool(winner_name == cand.name),
            "gate_passed": bool(getattr(gate, "passed", False)) if gate else False,
            "gate_reason": getattr(gate, "reason", None) if gate else None,
            "runtime_s": getattr(ce, "runtime_s", None) if ce else None,
            "metrics": cand.metrics,
        })
    ever_promoted = last_promoted_generation is not None
    return {
        "run_id": run_id,
        "generated_at": now_iso,
        "seeds": list(seeds),
        "pool": pool or {},
        "winner": winner_name,
        "trajectory": trajectory or {},
        "confirmation": confirmation or {},
        "champion_status": {
            "generation": generation,
            "last_promoted_generation": last_promoted_generation,
            "ever_promoted": ever_promoted,
            "promoted_this_run": bool(winner_name),
            # Fixed champion (never promoted) -> Elo movement is measurement drift,
            # not a strength change. A promotion this run flips it to a real change.
            "measurement_drift": (not ever_promoted) and not bool(winner_name),
        },
        "rows": rows,
    }


def _fmt(v: Any, spec: str = "") -> str:
    if v is None:
        return "—"
    if spec and isinstance(v, (int, float)):
        return format(v, spec)
    return str(v)


def render_markdown(record: Dict[str, Any]) -> str:
    """Render the comparison record as the approach_comparison.md report."""
    lines: List[str] = []
    lines.append("# Nightly Training — Approach Comparison")
    lines.append("")
    lines.append(f"_Run `{record.get('run_id')}` · generated {record.get('generated_at')}_")
    lines.append("")
    winner = record.get("winner")
    lines.append(f"**Promoted this run:** {winner if winner else 'none'}")
    conf = record.get("confirmation") or {}
    if conf:
        verdict = "passed ✅" if conf.get("passed") else "failed ❌ (held)"
        lines.append(f"**Two-stage promotion:** confirmation {verdict} for "
                     f"`{conf.get('candidate')}` — screen {conf.get('screen_games')} games → "
                     f"confirm {conf.get('confirm_games')}/{conf.get('confirm_min_games')} games. "
                     f"{conf.get('reason', '')}")
    pool = record.get("pool") or {}
    if pool:
        lines.append(f"**Benchmark pool:** {pool.get('version')} — opponents "
                     f"{', '.join(pool.get('opponents', []))}; seeds {pool.get('seeds')}")
    lines.append("")

    # Trajectory (noise-aware).
    traj = record.get("trajectory") or {}
    status = record.get("champion_status") or {}
    drift = bool(status.get("measurement_drift"))
    if traj:
        noise = traj.get("noise", {})
        sig = "yes" if traj.get("significant") else "no (within noise)"
        if drift:
            lines.append("## Champion Elo trajectory — ⚠️ fixed-champion measurement drift")
            lines.append("")
            lines.append("> The champion has **never been promoted** "
                         f"(`last_promoted_generation` = {status.get('last_promoted_generation')}), "
                         "so the agent under measurement is byte-for-byte fixed. The Elo numbers "
                         "below are rating **variance of an unchanged agent**, not a learned "
                         "strength change. Read them as measurement deltas until a promotion "
                         "actually changes the champion.")
            lines.append("")
        else:
            lines.append("## Champion Elo trajectory")
            lines.append("")
        lines.append(f"- Current: **{_fmt(traj.get('current'))}** · Best: "
                     f"{_fmt(traj.get('best'))} · Gap to best: {_fmt(traj.get('gap_to_best'))}")
        lines.append(f"- Rolling avg: {_fmt(traj.get('rolling_last'))} · "
                     f"Trend/step: {_fmt(traj.get('trend_per_step'))}")
        lines.append(f"- Elo noise floor (σ over fixed-config tail): "
                     f"±{_fmt(noise.get('stddev'))} (spread {_fmt(noise.get('spread'))}, "
                     f"n={_fmt(noise.get('n'))})")
        lines.append(f"- Move beyond noise floor? **{sig}**")
        lines.append("")

    # Comparison table.
    lines.append("## Approaches")
    lines.append("")
    lines.append("| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in record.get("rows", []):
        wr = r.get("win_rate_vs_champion")
        lines.append(
            f"| {r['approach']} "
            f"| {'Yes' if r['created'] else 'No'} "
            f"| {_fmt(r.get('games'))} "
            f"| {(format(wr*100, '.0f') + '%') if wr is not None else '—'} "
            f"| {_fmt(r.get('elo_delta'), '+.1f')} "
            f"| {_fmt(r.get('trueskill_delta'), '+.2f')} "
            f"| {'Yes' if r['promoted'] else 'No'} "
            f"| {r.get('gate_reason') or r.get('reason')} |"
        )
    lines.append("")

    # Per-approach detail.
    lines.append("## Detail")
    lines.append("")
    for r in record.get("rows", []):
        lines.append(f"### {r['approach']} (`{r['name']}`)")
        lines.append("")
        lines.append(f"- Created: {'yes' if r['created'] else 'no'} — {r['reason']}")
        if r["created"]:
            lines.append(f"- Games: {_fmt(r.get('games'))} · Win rate (battery): "
                         f"{_fmt(r.get('win_rate'), '.2f')} · Runtime: "
                         f"{_fmt(r.get('runtime_s'), '.1f')}s")
            lines.append(f"- Elo Δ vs champion: {_fmt(r.get('elo_delta'), '+.1f')} · "
                         f"TrueSkill μ Δ: {_fmt(r.get('trueskill_delta'), '+.2f')}")
            if r.get("gate_reason"):
                lines.append(f"- Gate: {r['gate_reason']}")
        if r.get("metrics"):
            lines.append(f"- Metrics: `{r['metrics']}`")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_approach_comparison(path: Path | str, record: Dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(record), encoding="utf-8")
    return path
