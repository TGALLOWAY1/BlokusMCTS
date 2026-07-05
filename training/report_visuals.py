"""Extra report graphics for the nightly email — matchup matrix, approach
comparison, recent Elo deltas, and a human-readable champion composition summary.

These sit alongside :mod:`training.elo_plot` (the headline Elo trajectory) and make
the raw report tables interpretable at a glance. Every renderer follows the same
two rules as ``elo_plot``:

* **Never crash the workflow.** matplotlib is imported lazily; any ImportError,
  empty/partial data, or draw error returns ``None`` (the email just ships without
  that image) instead of failing the nightly run.
* **Every image is self-describing** — clear title, axis labels, legend, and a
  footer stamping the run id + reporting era so a reader always knows what they are
  looking at.

Data sources (all already persisted; no new training behaviour):

* ``ratings.sqlite`` — per-agent Elo / TrueSkill per run (``ratings_for_run``).
* ``state['last_approach_comparison']`` — per-approach head-to-head vs the champion.
* ``state['champion_params']`` / ``champion.json`` — the champion's actual config.
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from training import ratings_db

# Shared palette (kept consistent with elo_plot.py).
_BLUE = "#2563eb"
_GREEN = "#16a34a"
_RED = "#dc2626"
_AMBER = "#f59e0b"
_PURPLE = "#9333ea"
_GRAY = "#6b7280"
_LIGHT = "#e5e7eb"


def _matplotlib():
    """Lazy, headless matplotlib or ``None`` if unavailable."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: F401

        return matplotlib
    except Exception:  # noqa: BLE001 — missing matplotlib -> no image, not a crash
        return None


def _expected_score(elo_a: float, elo_b: float) -> float:
    """Logistic Elo win expectation of A vs B (standard 400-point scale)."""
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def _footer(fig, run_id: Optional[str], era_label: Optional[str]) -> None:
    """Stamp every figure with run id + era so images are never ambiguous."""
    bits = []
    if run_id:
        bits.append(f"run {run_id}")
    if era_label:
        bits.append(era_label)
    if bits:
        fig.text(0.995, 0.005, " · ".join(bits), ha="right", va="bottom",
                 fontsize=7, color=_GRAY, alpha=0.9)


# ---------------------------------------------------------------------------
# A. Champion matchup matrix
# ---------------------------------------------------------------------------

def build_matchup_rows(
    conn: sqlite3.Connection,
    approach_record: Optional[Dict[str, Any]],
    *,
    run_id: Optional[str] = None,
    since_run_id: Optional[str] = None,
) -> Tuple[Optional[float], List[Dict[str, Any]]]:
    """Assemble champion-vs-opponent rows for the matchup matrix (pure-ish).

    Returns ``(champion_elo, rows)``. Each row has: ``agent``, ``elo``, ``mu``,
    ``games``, ``elo_delta`` (champion − opponent), ``expected`` (Elo-implied
    champion win prob), and ``h2h`` (measured head-to-head win% *for the champion*
    vs this agent, when the approach comparison measured it this run, else ``None``).

    Opponents are the benchmark pool + this run's candidates. Ratings come from the
    most recent run that recorded them (``run_id`` if given), falling back to the
    latest era rating so an opponent that sat out this run still appears.
    """
    run_ratings = ratings_db.ratings_for_run(conn, run_id) if run_id else {}
    # Fall back to the latest *in-era* rating (not all-time) for agents that sat out
    # this run — otherwise a benchmark capped out of the pool could drag a pre-cutoff
    # rating into an era-scoped matrix that claims earlier runs are excluded.
    latest = ratings_db.latest_ratings(conn, since_run_id=since_run_id)

    def rating_of(agent: str) -> Optional[Dict[str, Any]]:
        return run_ratings.get(agent) or latest.get(agent)

    champ = rating_of("champion")
    champion_elo = champ["elo"] if champ else None

    record = approach_record or {}
    pool = record.get("pool") or {}
    opponents: List[str] = list(pool.get("opponents") or [])

    # Head-to-head win% for the champion vs each candidate (candidate row stores its
    # own win% vs champion, so the champion's is the complement).
    h2h_by_agent: Dict[str, Optional[float]] = {}
    candidate_names: List[str] = []
    for r in record.get("rows") or []:
        if not r.get("created"):
            continue
        name = r.get("name") or r.get("approach")
        candidate_names.append(name)
        wr = r.get("win_rate_vs_champion")
        h2h_by_agent[name] = (1.0 - float(wr)) if wr is not None else None

    seen = set()
    ordered: List[str] = []
    for a in opponents + candidate_names:
        if a and a not in seen and a != "champion":
            seen.add(a)
            ordered.append(a)

    rows: List[Dict[str, Any]] = []
    for agent in ordered:
        rating = rating_of(agent)
        if rating is None:
            continue
        elo = rating["elo"]
        rows.append({
            "agent": agent,
            "elo": elo,
            "mu": rating.get("mu"),
            "games": rating.get("games_played"),
            "elo_delta": (champion_elo - elo) if champion_elo is not None else None,
            "expected": (_expected_score(champion_elo, elo)
                         if champion_elo is not None else None),
            "h2h": h2h_by_agent.get(agent),
        })
    # Strongest opponents first (largest Elo) so the toughest matchups lead.
    rows.sort(key=lambda r: r["elo"], reverse=True)
    return champion_elo, rows


def render_matchup_matrix(
    conn: sqlite3.Connection,
    out_path: Path | str,
    approach_record: Optional[Dict[str, Any]],
    *,
    run_id: Optional[str] = None,
    since_run_id: Optional[str] = None,
    era_label: Optional[str] = None,
) -> Optional[Path]:
    """Render the champion-vs-opponent matrix PNG. Returns the path or ``None``.

    A true pairwise win/loss grid is not persisted (per-game opponent breakdowns are
    not stored), so this is a **champion-vs-opponent** matrix: each opponent's Elo,
    TrueSkill μ, games, the Elo gap to the champion, and the champion's expected win
    probability from that gap. Where the approach comparison actually played the
    champion head-to-head this run (the candidates), the *measured* champion win% is
    shown too; other rows are labelled as rating-implied.
    """
    champion_elo, rows = build_matchup_rows(
        conn, approach_record, run_id=run_id, since_run_id=since_run_id
    )
    if not rows or champion_elo is None:
        return None
    mpl = _matplotlib()
    if mpl is None:
        return None
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    headers = ["Opponent", "Elo", "TrueSkill μ", "Games", "Elo Δ\n(champ−opp)",
               "Champ win%\n(measured)", "Champ win%\n(Elo-implied)"]
    cell_text: List[List[str]] = []
    cell_colors: List[List[str]] = []
    for r in rows:
        h2h = r["h2h"]
        exp = r["expected"]
        measured = f"{h2h * 100:.0f}%" if h2h is not None else "—"
        implied = f"{exp * 100:.0f}%" if exp is not None else "—"
        cell_text.append([
            r["agent"],
            f"{r['elo']:.0f}",
            f"{r['mu']:.1f}" if r["mu"] is not None else "—",
            f"{r['games']:,}" if r["games"] is not None else "—",
            f"{r['elo_delta']:+.0f}" if r["elo_delta"] is not None else "—",
            measured,
            implied,
        ])
        # Green when the champion is favoured, red when it is the underdog.
        shade = _LIGHT
        if exp is not None:
            shade = "#dcfce7" if exp >= 0.5 else "#fee2e2"
        cell_colors.append([shade] * len(headers))

    n = len(rows)
    fig, ax = plt.subplots(figsize=(10, 1.1 + 0.42 * (n + 1)), dpi=130)
    ax.axis("off")
    table = ax.table(cellText=cell_text, colLabels=headers,
                     cellColours=cell_colors, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.5)
    for (row_i, _col), cell in table.get_celld().items():
        cell.set_edgecolor("white")
        if row_i == 0:
            cell.set_facecolor(_BLUE)
            cell.set_text_props(color="white", fontweight="bold")

    ax.set_title(
        f"Champion matchup matrix — champion Elo {champion_elo:.0f}\n"
        "green = champion favoured · red = underdog · measured win% shown "
        "where head-to-head games ran this run",
        fontsize=12, fontweight="bold", pad=14,
    )
    _footer(fig, run_id, era_label)
    fig.tight_layout()
    fig.savefig(out_path, format="png", bbox_inches="tight")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# B. Approach comparison chart
# ---------------------------------------------------------------------------

def render_approach_comparison(
    out_path: Path | str,
    approach_record: Optional[Dict[str, Any]],
    *,
    run_id: Optional[str] = None,
    era_label: Optional[str] = None,
) -> Optional[Path]:
    """Render the approach-comparison chart PNG (candidates that ran this cycle).

    Two panels sharing the approach axis: (1) head-to-head win% vs the champion with
    a 50% reference line, (2) Elo Δ vs champion. Bars are green when the gate
    promoted the approach, amber when it beat the champion head-to-head but did not
    pass the gate, and gray when it did not improve — so improving / close / failed
    approaches are visually obvious. Returns ``None`` when no candidate ran.
    """
    record = approach_record or {}
    created = [r for r in (record.get("rows") or []) if r.get("created")]
    if not created:
        return None
    mpl = _matplotlib()
    if mpl is None:
        return None
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    labels = [r.get("approach", "?") for r in created]
    win = [(r.get("win_rate_vs_champion") or 0.0) * 100 for r in created]
    elo_delta = [r.get("elo_delta") or 0.0 for r in created]
    games = [int(r.get("games") or 0) for r in created]

    def bar_color(r: Dict[str, Any]) -> str:
        if r.get("promoted"):
            return _GREEN
        wr = r.get("win_rate_vs_champion")
        if wr is not None and wr > 0.5:
            return _AMBER  # beat champion head-to-head but failed the gate
        return _GRAY

    colors = [bar_color(r) for r in created]
    y = list(range(len(created)))

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(11, 1.4 + 0.6 * len(created)), dpi=130, sharey=True
    )

    ax1.barh(y, win, color=colors)
    ax1.axvline(50, color=_RED, linewidth=1.0, linestyle="--", alpha=0.7,
                label="50% (parity vs champion)")
    ax1.set_yticks(y)
    ax1.set_yticklabels(labels)
    ax1.invert_yaxis()
    ax1.set_xlabel("Head-to-head win % vs champion")
    ax1.set_xlim(0, 100)
    for yi, (w, g) in enumerate(zip(win, games)):
        ax1.text(min(w + 1, 97), yi, f"{w:.0f}%  (n={g})", va="center", fontsize=8)
    ax1.legend(fontsize=8, loc="lower right")
    ax1.set_title("Win rate vs champion", fontsize=11, fontweight="bold")

    ax2.barh(y, elo_delta, color=colors)
    ax2.axvline(0, color=_GRAY, linewidth=1.0)
    ax2.set_xlabel("Elo Δ vs champion")
    for yi, d in enumerate(elo_delta):
        off = 1 if d >= 0 else -1
        ax2.text(d + off, yi, f"{d:+.0f}", va="center",
                 ha="left" if d >= 0 else "right", fontsize=8)
    ax2.set_title("Elo delta vs champion", fontsize=11, fontweight="bold")

    # Legend for the colour semantics.
    from matplotlib.patches import Patch

    legend_items = [
        Patch(facecolor=_GREEN, label="promoted (passed gate)"),
        Patch(facecolor=_AMBER, label="beat champion, held by gate"),
        Patch(facecolor=_GRAY, label="did not improve"),
    ]
    fig.legend(handles=legend_items, loc="upper center", ncol=3, fontsize=8,
               frameon=False, bbox_to_anchor=(0.5, 1.0))
    winner = record.get("winner")
    sub = f"promoted this run: {winner}" if winner else "no promotion this run"
    fig.suptitle(f"Approach comparison — {sub}", fontsize=13, fontweight="bold", y=1.06)
    _footer(fig, run_id, era_label)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, format="png", bbox_inches="tight")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# D. Recent Elo delta bar chart (optional high-value visual)
# ---------------------------------------------------------------------------

def render_recent_deltas(
    conn: sqlite3.Connection,
    out_path: Path | str,
    *,
    since_run_id: Optional[str] = None,
    era_label: Optional[str] = None,
    limit: int = 12,
) -> Optional[Path]:
    """Render a per-generation Elo-delta bar chart for the era (last ``limit`` runs).

    Green bars rose, red fell; a ▲ marks generations where a candidate was promoted.
    Returns ``None`` when there are too few runs to show a delta.
    """
    window = ratings_db.recent_window(conn, limit=limit + 1, since_run_id=since_run_id)
    if len(window) < 2:
        return None
    mpl = _matplotlib()
    if mpl is None:
        return None
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    gens, deltas, promoted = [], [], []
    for prev, cur in zip(window, window[1:]):
        gens.append(cur.get("generation"))
        deltas.append(float(cur["champion_elo"]) - float(prev["champion_elo"]))
        promoted.append(bool(cur.get("promoted")))

    colors = [_GREEN if d >= 0 else _RED for d in deltas]
    x = list(range(len(deltas)))
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=130)
    ax.bar(x, deltas, color=colors)
    ax.axhline(0, color=_GRAY, linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels([f"gen {g}" for g in gens], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Elo Δ vs previous run")
    for xi, (d, promo) in enumerate(zip(deltas, promoted)):
        if promo:
            top = d + (2 if d >= 0 else -2)
            ax.annotate("▲ promoted", xy=(xi, d), xytext=(xi, top),
                        ha="center", fontsize=8, color=_PURPLE,
                        va="bottom" if d >= 0 else "top")
    ax.set_title("Recent Elo change by generation", fontsize=12, fontweight="bold")
    ax.grid(True, axis="y", alpha=0.25, linewidth=0.6)
    # Spans multiple runs, so stamp only the era (no single run id).
    _footer(fig, None, era_label)
    fig.tight_layout()
    fig.savefig(out_path, format="png", bbox_inches="tight")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# C. Champion composition / config summary (human-readable text)
# ---------------------------------------------------------------------------

def _flatten_params(champion_params: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the flat MCTS param dict out of the nested champion_params envelope."""
    if not champion_params:
        return {}
    inner = champion_params.get("params")
    if isinstance(inner, dict) and "params" in inner:
        inner = inner["params"]
    if isinstance(inner, dict):
        return inner
    return champion_params if isinstance(champion_params, dict) else {}


def _on_off(value: Any) -> str:
    return "on" if value else "off"


def champion_composition_lines(state: Dict[str, Any]) -> List[str]:
    """A compact, human-readable description of *what the champion actually is*.

    Reads the durable state (champion_params + lineage + approach comparison) so a
    reader understands the agent's search budget, rollout policy, learned evaluator,
    and where it came from without opening any JSON. Never raises on missing fields.
    """
    champ = state.get("champion", {}) or {}
    params_env = state.get("champion_params") or {}
    params = _flatten_params(params_env)
    record = state.get("last_approach_comparison") or {}
    pool = record.get("pool") or {}

    ttm = params_env.get("thinking_time_ms")
    ipms = params.get("iterations_per_ms")
    est_iters = None
    if isinstance(ttm, (int, float)) and isinstance(ipms, (int, float)):
        # iterations_per_ms is per-ms, so sims/move ≈ thinking_time_ms * iterations_per_ms.
        est_iters = int(ttm * ipms)

    lines: List[str] = []
    lines.append(f"- **Identity:** `{champ.get('name', 'champion')}` "
                 f"({champ.get('version', 'n/a')}), generation "
                 f"{state.get('generation', 'n/a')}")
    lines.append(f"- **Agent type:** {params_env.get('type', 'mcts')} "
                 f"(current Elo {state.get('elo', float('nan')):.0f}, "
                 f"TrueSkill {state.get('trueskill_mu', float('nan')):.1f} ± "
                 f"{state.get('trueskill_sigma', float('nan')):.1f})")

    # Search budget.
    budget_bits = []
    if ttm is not None:
        budget_bits.append(f"{ttm} ms/move")
    if ipms is not None:
        budget_bits.append(f"{ipms} iters/ms")
    if est_iters:
        budget_bits.append(f"≈{est_iters:,} sims/move")
    if params.get("deterministic_time_budget"):
        budget_bits.append("deterministic budget")
    if budget_bits:
        lines.append(f"- **Search budget:** {', '.join(budget_bits)}")

    lines.append(f"- **Exploration constant (c):** {params.get('exploration_constant', 'n/a')}")

    # Rollout.
    rollout_bits = [f"policy `{params.get('rollout_policy', 'n/a')}`"]
    if params.get("rollout_cutoff_depth") is not None:
        rollout_bits.append(f"cutoff depth {params.get('rollout_cutoff_depth')}")
    if params.get("greedy_sample_size") is not None:
        rollout_bits.append(f"greedy sample {params.get('greedy_sample_size')}")
    lines.append(f"- **Rollout:** {', '.join(rollout_bits)}")

    # Feature toggles.
    lines.append(
        "- **Enhancements:** "
        f"RAVE {_on_off(params.get('rave_enabled'))}, "
        f"heuristic move-ordering {_on_off(params.get('heuristic_move_ordering'))}, "
        f"learned policy prior {_on_off(params.get('policy_prior_enabled'))}, "
        f"minimax-backup α {params.get('minimax_backup_alpha', 0.0)}, "
        f"transposition table {_on_off(params.get('use_transposition_table'))}, "
        f"adaptive rollout depth {_on_off(params.get('adaptive_rollout_depth_enabled'))}"
    )

    # Learned move policy (PUCT prior) — surface it as its own line when active,
    # mirroring how the learned evaluator is called out below.
    if params.get("policy_prior_enabled") and isinstance(params.get("policy_weights"), dict):
        pol = params["policy_weights"]
        n_bias = len(pol.get("piece_bias") or {})
        lines.append(
            "- **Learned move policy:** visit-count-distilled PUCT prior "
            f"(c={params.get('policy_prior_c', 1.5)}, {n_bias} per-piece biases)"
        )

    # Learned evaluator (Layer-6 weights) — the "brain" if present.
    weights = params.get("state_eval_weights")
    if isinstance(weights, dict) and weights:
        nonzero = {k: v for k, v in weights.items() if v}
        top = sorted(nonzero.items(), key=lambda kv: abs(kv[1]), reverse=True)[:4]
        top_str = ", ".join(f"{k}={v:+.3f}" for k, v in top)
        lines.append(f"- **Learned evaluator:** Layer-6 static eval, "
                     f"{len(nonzero)} active weights (top: {top_str})")

    # TD learning: infer from lineage / approach metrics.
    td_note = "not the active learning method for the current champion"
    for row in record.get("rows") or []:
        metrics = row.get("metrics") or {}
        if metrics.get("learning_method") == "temporal_difference":
            td_note = "a TD-learning candidate ran this cycle (see approach comparison)"
            break
    lines.append(f"- **TD learning:** {td_note}")

    # Provenance: how this champion got here.
    lineage = (state.get("champion") or {})
    lpg = state.get("last_promoted_generation")
    if lpg is not None:
        lines.append(f"- **Promotion source:** last promoted at generation {lpg}")
    else:
        lines.append("- **Promotion source:** never promoted (cold-start seed champion; "
                     "Elo movement is measurement drift until a candidate is promoted)")

    if pool:
        lines.append(f"- **Benchmark pool:** {pool.get('version', 'n/a')} — opponents "
                     f"{', '.join(pool.get('opponents', []))}; seeds {pool.get('seeds')}")
    mode = record.get("run_id")
    if mode:
        lines.append("- **Training mode:** multi-agent approach-comparison "
                     f"(latest run `{mode}`)")
    return lines


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def render_all(
    conn: sqlite3.Connection,
    reports_dir: Path,
    state: Dict[str, Any],
    *,
    since_run_id: Optional[str] = None,
    era_label: Optional[str] = None,
) -> Dict[str, Optional[Path]]:
    """Render every extra graphic into ``reports_dir``; return ``{name: path|None}``.

    Never raises — a failed renderer yields ``None`` for its slot so the email
    degrades gracefully (fewer images) rather than failing the run.
    """
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    record = state.get("last_approach_comparison") or {}
    run_id = record.get("run_id") or state.get("run_id")

    out: Dict[str, Optional[Path]] = {}
    try:
        out["matchup_matrix"] = render_matchup_matrix(
            conn, reports_dir / "matchup_matrix.png", record,
            run_id=run_id, since_run_id=since_run_id, era_label=era_label,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[report_visuals] matchup matrix skipped ({type(exc).__name__}: {exc}).")
        out["matchup_matrix"] = None
    try:
        out["approach_comparison"] = render_approach_comparison(
            reports_dir / "approach_comparison.png", record,
            run_id=run_id, era_label=era_label,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[report_visuals] approach comparison skipped ({type(exc).__name__}: {exc}).")
        out["approach_comparison"] = None
    try:
        out["recent_deltas"] = render_recent_deltas(
            conn, reports_dir / "recent_deltas.png",
            since_run_id=since_run_id, era_label=era_label,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[report_visuals] recent deltas skipped ({type(exc).__name__}: {exc}).")
        out["recent_deltas"] = None
    return out


def render_default_all() -> Dict[str, Optional[Path]]:
    """Render every extra graphic for the real repo DB into ``training/reports/``.

    Convenience entry point for the workflow's report step so the PNGs are committed
    with the other artifacts (the email regenerates the same files at send time).
    Scoped to the active reporting era (:func:`reporting_era.resolve_era`).
    """
    from training import TrainingPaths, reporting_era, state_store

    era = reporting_era.resolve_era()
    paths = TrainingPaths.default()
    paths.ensure_dirs()
    state = state_store.load_latest(paths)
    conn = ratings_db.connect(paths.ratings_db)
    try:
        return render_all(
            conn, paths.reports_dir, state,
            since_run_id=era.since_run_id, era_label=era.label,
        )
    finally:
        conn.close()


def main() -> int:
    out = render_default_all()
    rendered = {k: str(v) for k, v in out.items() if v is not None}
    if not rendered:
        print("[report_visuals] No graphics rendered (empty timeline or matplotlib "
              "missing).")
        return 0
    for name, path in rendered.items():
        print(f"[report_visuals] Wrote {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
