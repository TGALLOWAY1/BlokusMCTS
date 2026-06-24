"""Quality diagnostics for the TD trajectory corpus (``data/td_trajectories.csv``).

Bad training data is the most common silent cause of a TD model that "trains
cleanly" but never improves play: too few rows in a phase (so that phase keeps the
prior weights), a corpus dominated by one outcome (the value model learns the
roster, not the game), or a missing terminal transition per trajectory (no
grounded target). This module surfaces all of that as plain counts plus a set of
findings, so a human (or the nightly report) can spot a degenerate corpus before
spending compute training on it.

Pure core (:func:`diagnose_rows`) takes loaded rows so it is unit-tested without
disk I/O; :func:`diagnose_csv` and the CLI wrap it.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from mcts.state_evaluator import PHASE_EARLY_THRESHOLD, PHASE_LATE_THRESHOLD

# Default minimum rows a phase needs before TD will train it (mirrors
# TDConfig.min_rows_per_phase) — used to flag under-populated phases.
_MIN_ROWS_PER_PHASE = 200
# A single outcome (rank / winner) holding more than this share of rows means the
# corpus is unbalanced and the value targets carry little signal diversity.
_OUTCOME_DOMINANCE = 0.70
PHASES = ("early", "mid", "late")


def _phase_of(row: Dict[str, Any]) -> str:
    p = str(row.get("phase") or "").strip()
    if p in PHASES:
        return p
    occ = float(row.get("board_occupancy", 0.0) or 0.0)
    if occ < PHASE_EARLY_THRESHOLD:
        return "early"
    if occ < PHASE_LATE_THRESHOLD:
        return "mid"
    return "late"


@dataclass
class TrajectoryReport:
    total_rows: int
    n_games: int
    n_trajectories: int  # distinct (game_id, player_id) with >=1 row
    rows_by_phase: Dict[str, int]
    rows_by_player: Dict[int, int]
    rows_by_agent: Dict[str, int]
    rows_by_rank: Dict[int, int]
    rows_by_outcome: Dict[str, int]  # won / lost / top2 split
    terminal_rows: int
    nonterminal_rows: int
    trajectories_missing_terminal: int
    next_phase_coverage: float  # fraction of non-terminal rows with a valid next_phase
    avg_transitions_per_trajectory: float
    findings: List[Dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(f["severity"] in ("warn", "critical") for f in self.findings)

    def to_dict(self) -> Dict[str, Any]:
        d = {k: getattr(self, k) for k in (
            "total_rows", "n_games", "n_trajectories", "rows_by_phase",
            "rows_by_player", "rows_by_agent", "rows_by_rank", "rows_by_outcome",
            "terminal_rows", "nonterminal_rows", "trajectories_missing_terminal",
            "next_phase_coverage", "avg_transitions_per_trajectory", "findings",
        )}
        d["ok"] = self.ok
        return d


def diagnose_rows(
    rows: Sequence[Dict[str, Any]], *, min_rows_per_phase: int = _MIN_ROWS_PER_PHASE
) -> TrajectoryReport:
    """Compute trajectory-quality diagnostics over loaded rows. Pure (no I/O)."""
    rows_by_phase = {p: 0 for p in PHASES}
    rows_by_player: Counter = Counter()
    rows_by_agent: Counter = Counter()
    rows_by_rank: Counter = Counter()
    won = lost = top2 = 0
    terminal_rows = 0
    nonterminal_rows = 0
    next_phase_valid = 0
    games: set = set()
    by_traj: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)

    for row in rows:
        rows_by_phase[_phase_of(row)] += 1
        pid = int(row.get("player_id", 0) or 0)
        rows_by_player[pid] += 1
        rows_by_agent[str(row.get("agent_name", "?"))] += 1
        rows_by_rank[int(row.get("final_rank", 0) or 0)] += 1
        if int(row.get("won_game", 0) or 0):
            won += 1
        else:
            lost += 1
        if int(row.get("top_2_finish", 0) or 0):
            top2 += 1
        is_term = bool(int(row.get("terminal", 0) or 0))
        if is_term:
            terminal_rows += 1
        else:
            nonterminal_rows += 1
            if str(row.get("next_phase") or "").strip() in PHASES:
                next_phase_valid += 1
        games.add(str(row.get("game_id", "")))
        by_traj[(str(row.get("game_id", "")), pid)].append(row)

    n_traj = len(by_traj)
    missing_terminal = sum(
        1 for rs in by_traj.values()
        if not any(int(r.get("terminal", 0) or 0) for r in rs)
    )
    total = len(rows)
    next_phase_cov = (next_phase_valid / nonterminal_rows) if nonterminal_rows else 1.0
    avg_trans = (total / n_traj) if n_traj else 0.0

    report = TrajectoryReport(
        total_rows=total,
        n_games=len({g for g in games if g}),
        n_trajectories=n_traj,
        rows_by_phase=rows_by_phase,
        rows_by_player=dict(sorted(rows_by_player.items())),
        rows_by_agent=dict(rows_by_agent.most_common()),
        rows_by_rank=dict(sorted(rows_by_rank.items())),
        rows_by_outcome={"won": won, "lost": lost, "top2": top2},
        terminal_rows=terminal_rows,
        nonterminal_rows=nonterminal_rows,
        trajectories_missing_terminal=missing_terminal,
        next_phase_coverage=next_phase_cov,
        avg_transitions_per_trajectory=avg_trans,
    )
    report.findings = _derive_findings(report, min_rows_per_phase)
    return report


def _derive_findings(r: TrajectoryReport, min_rows_per_phase: int) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if r.total_rows == 0:
        out.append({"severity": "critical", "code": "empty",
                    "message": "No trajectory rows — collect self-play first "
                               "(python -m training.td_selfplay)."})
        return out

    for phase in PHASES:
        n = r.rows_by_phase.get(phase, 0)
        if n < min_rows_per_phase:
            out.append({"severity": "warn", "code": "under_populated_phase",
                        "message": f"Phase '{phase}' has {n} rows (< {min_rows_per_phase}); "
                                   "TD will keep the prior weights for it (no learning)."})

    if r.trajectories_missing_terminal:
        out.append({"severity": "warn", "code": "missing_terminal",
                    "message": f"{r.trajectories_missing_terminal}/{r.n_trajectories} "
                               "trajectories have no terminal row — those targets are "
                               "never grounded in an outcome."})

    if r.nonterminal_rows and r.next_phase_coverage < 0.999:
        out.append({"severity": "info", "code": "next_phase_gaps",
                    "message": f"{r.next_phase_coverage * 100:.1f}% of non-terminal rows "
                               "carry an explicit next_phase; the rest fall back to the "
                               "current phase (legacy data — re-collect to fix)."})

    # Outcome dominance: champion-only rosters or all-win corpora carry little signal.
    if r.total_rows:
        rank_counts = r.rows_by_rank
        if rank_counts:
            top_rank, top_n = max(rank_counts.items(), key=lambda kv: kv[1])
            frac = top_n / r.total_rows
            if frac > _OUTCOME_DOMINANCE:
                out.append({"severity": "warn", "code": "rank_skew",
                            "message": f"{frac * 100:.0f}% of rows are final_rank={top_rank}; "
                                       "outcome targets lack diversity (vary the opponent "
                                       "roster / seats to balance ranks)."})
        won_frac = r.rows_by_outcome.get("won", 0) / r.total_rows
        if won_frac > _OUTCOME_DOMINANCE or won_frac < (1 - _OUTCOME_DOMINANCE):
            out.append({"severity": "info", "code": "win_imbalance",
                        "message": f"win-labelled rows = {won_frac * 100:.0f}% of corpus; "
                                   "a balanced corpus sits nearer 25% (4-player)."})

    # Per-player imbalance (seat coverage).
    if r.rows_by_player:
        counts = list(r.rows_by_player.values())
        if min(counts) and max(counts) / max(min(counts), 1) > 3.0:
            out.append({"severity": "info", "code": "seat_imbalance",
                        "message": f"player row counts vary widely ({r.rows_by_player}); "
                                   "value targets may inherit a seat bias."})
    return out


def diagnose_csv(
    path: Path | str, *, min_rows_per_phase: int = _MIN_ROWS_PER_PHASE
) -> TrajectoryReport:
    from training import trajectory_store

    rows = trajectory_store.load_trajectories(path)
    return diagnose_rows(rows, min_rows_per_phase=min_rows_per_phase)


def render_report(r: TrajectoryReport) -> str:
    lines = [
        "# TD Trajectory Quality Diagnostics",
        "",
        f"_Rows: {r.total_rows:,} · games: {r.n_games} · trajectories: {r.n_trajectories} "
        f"· status: {'✅ OK' if r.ok else '⚠️ issues found'}_",
        "",
    ]
    if r.findings:
        icon = {"critical": "🔴", "warn": "🟠", "info": "🔵"}
        lines += ["## Findings", ""]
        for f in r.findings:
            lines.append(f"- {icon.get(f['severity'], '•')} **[{f['severity']}] "
                         f"{f['code']}** — {f['message']}")
        lines.append("")
    else:
        lines += ["**No issues detected.** Corpus looks healthy.", ""]

    def _kv_table(title: str, d: Dict[Any, Any]) -> List[str]:
        rows = [f"## {title}", "", "| key | rows |", "|---|---|"]
        for k, v in d.items():
            rows.append(f"| {k} | {v:,} |")
        rows.append("")
        return rows

    lines += _kv_table("Rows by phase", r.rows_by_phase)
    lines += _kv_table("Rows by final rank", r.rows_by_rank)
    lines += _kv_table("Rows by player (seat)", r.rows_by_player)
    lines += _kv_table("Rows by agent", r.rows_by_agent)
    lines += [
        "## Transitions",
        "",
        f"- **Terminal rows:** {r.terminal_rows:,}",
        f"- **Non-terminal rows:** {r.nonterminal_rows:,}",
        f"- **Trajectories missing a terminal row:** {r.trajectories_missing_terminal}",
        f"- **next_phase coverage:** {r.next_phase_coverage * 100:.1f}%",
        f"- **Avg transitions / trajectory:** {r.avg_transitions_per_trajectory:.1f}",
        f"- **Outcome split:** won={r.rows_by_outcome.get('won', 0):,}, "
        f"lost={r.rows_by_outcome.get('lost', 0):,}, "
        f"top2={r.rows_by_outcome.get('top2', 0):,}",
        "",
    ]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    from training.trajectory_store import DEFAULT_TRAJECTORY_CSV

    p = argparse.ArgumentParser(description="Diagnose TD trajectory corpus quality.")
    p.add_argument("--input", default=str(DEFAULT_TRAJECTORY_CSV))
    p.add_argument("--min-rows-per-phase", type=int, default=_MIN_ROWS_PER_PHASE)
    p.add_argument("--output", default=None, help="Write the markdown report here.")
    args = p.parse_args(argv)

    report = diagnose_csv(args.input, min_rows_per_phase=args.min_rows_per_phase)
    md = render_report(report)
    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"[trajectory_diagnostics] wrote {args.output}")
    else:
        print(md)
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
