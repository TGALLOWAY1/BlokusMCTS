"""Markdown experiment reports — summary, ranking, recommendation.

Renders a :class:`~training.experiments.manifest.ExperimentManifest` plus a
:class:`~training.experiments.compare.ComparisonResult` into a human-readable
report. Pure (no I/O) so it is unit-tested directly.
"""

from __future__ import annotations

from typing import Any, List

from training.experiments.compare import ComparisonResult
from training.experiments.manifest import ExperimentManifest


def render_experiment_report(
    manifest: ExperimentManifest, result: ComparisonResult
) -> str:
    lines: List[str] = [
        f"# Experiment Report — `{manifest.experiment_id}`",
        "",
        f"_{manifest.description}_",
        "",
        "## Setup",
        "",
        f"- **Date:** {manifest.date}",
        f"- **Code version:** `{manifest.code_version or 'unknown'}`",
        f"- **Seeds:** {manifest.seeds} ({result.n_seeds})",
        f"- **Games per arena/seed:** {manifest.games_per_arena}",
        f"- **Total pooled games:** {result.total_games:,}",
        f"- **Thinking time:** {manifest.thinking_time_ms} ms"
        if manifest.thinking_time_ms is not None else "- **Thinking time:** config default",
        f"- **Competitors:** {', '.join(result.competitors)}",
        "",
    ]

    # --- Ranking table (by TrueSkill μ, then win rate) -----------------------
    rows = sorted(
        result.per_agent.values(),
        key=lambda a: (a.trueskill_mu if a.trueskill_mu is not None else -1e9, a.win_rate),
        reverse=True,
    )
    lines += [
        "## Ranking",
        "",
        "| # | Agent | Win% (95% CI) | Avg rank | Score margin | TrueSkill μ±σ | Elo | W/L/D |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, a in enumerate(rows, start=1):
        ts = (f"{a.trueskill_mu:.2f}±{a.trueskill_sigma:.2f}"
              if a.trueskill_mu is not None else "—")
        lines.append(
            f"| {i} | `{a.name}` | {a.win_rate * 100:.1f}% "
            f"({a.win_rate_ci[0] * 100:.0f}–{a.win_rate_ci[1] * 100:.0f}) "
            f"| {a.avg_rank:.2f} | {a.avg_score_margin:+.1f} "
            f"| {ts} | {a.elo:.0f} | {a.wins}/{a.losses}/{a.draws} |"
        )
    lines.append("")

    # --- Rank distributions --------------------------------------------------
    lines += ["## Rank distribution", "", "| Agent | 1st | 2nd | 3rd | 4th |", "|---|---|---|---|---|"]
    for a in rows:
        rd = a.rank_distribution
        lines.append(f"| `{a.name}` | {rd.get(1, 0)} | {rd.get(2, 0)} "
                     f"| {rd.get(3, 0)} | {rd.get(4, 0)} |")
    lines.append("")

    # --- Head-to-head + recommendation --------------------------------------
    h2h = result.head_to_head
    if h2h:
        lines += [
            "## Head-to-head: candidate vs baseline",
            "",
            f"- **Candidate:** `{h2h['candidate']}` · **Baseline:** `{h2h['baseline']}`",
            f"- **Direct record (cand/base/tie):** {h2h['candidate_wins']}/"
            f"{h2h['baseline_wins']}/{h2h['ties']}",
            f"- **Win rate:** candidate {h2h['candidate_win_rate'] * 100:.1f}% vs "
            f"baseline {h2h['baseline_win_rate'] * 100:.1f}%",
            f"- **Avg rank:** candidate {h2h['candidate_avg_rank']:.2f} vs "
            f"baseline {h2h['baseline_avg_rank']:.2f}",
            f"- **TrueSkill Δμ:** {_fmt_delta(h2h.get('trueskill_mu_delta'))}",
            f"- **Elo Δ:** {h2h.get('elo_delta', 0.0):+.0f}",
            "",
            f"### Recommendation\n\n**{h2h.get('recommendation')}**",
            "",
        ]
    else:
        lines += ["## Head-to-head", "",
                  "_Baseline or candidate not present in this run._", ""]

    # --- Reproducibility -----------------------------------------------------
    lines += [
        "## Reproducibility",
        "",
        "Re-run with the saved manifest (`manifest.json`). Per-game seeds derive "
        "deterministically from the manifest seeds and arena index, so the same "
        "manifest reproduces the same games.",
        "",
        "Competitor config hashes:",
        "",
    ]
    for name, h in manifest.competitors.items():
        lines.append(f"- `{name}`: `{h}` ({manifest.learning_modes.get(name, 'baseline')})")
    lines.append("")
    return "\n".join(lines)


def _fmt_delta(v: Any) -> str:
    return "—" if v is None else f"{float(v):+.3f}"
