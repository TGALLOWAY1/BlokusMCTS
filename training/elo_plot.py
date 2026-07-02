"""Render the champion's Elo trajectory as a PNG for the nightly email.

The nightly report used to ship an *unformed table* of one Elo per generation,
which made it hard to tell whether the rating distribution was actually drifting
upward or just bouncing. This module draws the **per-game** Elo trajectory (the
fine-grained ``game_elo`` table) as a single curve with a linear trend line, so a
glance answers "is it moving in the right direction?".

Design notes:

* **Per-game first, per-generation fallback.** Historical runs only have the
  coarse per-generation ``run_summary`` series, so when no per-game samples exist
  yet we degrade gracefully to plotting one point per generation (x = cumulative
  total games). Going forward the per-game table accumulates the smooth curve.
* **Never crash the workflow.** matplotlib is imported lazily inside the renderer;
  any ImportError (or empty timeline) returns ``None`` and the email simply ships
  without the image instead of failing the nightly run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from training import ratings_db

# Cap the number of plotted points so a months-long timeline stays legible and the
# PNG small enough to email comfortably.
_MAX_POINTS = 600


def _load_series(
    conn: sqlite3.Connection, *, agent: str = "champion",
    since_run_id: Optional[str] = None,
) -> Tuple[List[float], List[float], str]:
    """Return ``(x, y, granularity)`` for the champion Elo curve.

    Prefers the per-game trajectory (x = cumulative game number); falls back to the
    per-generation run summary (x = cumulative total games). ``granularity`` is
    ``"per-game"`` or ``"per-generation"`` for the caption/title. ``since_run_id``
    restricts the curve to the multi-agent era (see
    :data:`ratings_db.MULTI_AGENT_EPOCH_RUN_ID`).
    """
    game_series = ratings_db.champion_game_elo_series(
        conn, agent=agent, limit=_MAX_POINTS, since_run_id=since_run_id
    )
    if game_series:
        x = [float(p["game_number"]) for p in game_series]
        y = [float(p["elo"]) for p in game_series]
        return x, y, "per-game"

    run_series = ratings_db.champion_elo_series(conn, agent=agent, since_run_id=since_run_id)
    if run_series:
        x = [float(p["total_games"]) for p in run_series]
        y = [float(p["elo"]) for p in run_series]
        return x, y, "per-generation"

    return [], [], "per-game"


def _trend_line(x: List[float], y: List[float]) -> Optional[Tuple[List[float], List[float], float]]:
    """Least-squares trend over ``(x, y)``; returns ``(xs, ys, slope)`` or None.

    Slope is Elo-per-game (or Elo-per-game-of-progress for the fallback series) so
    the caption can state the direction explicitly.
    """
    if len(x) < 2:
        return None
    try:
        import numpy as np

        coeffs = np.polyfit(x, y, 1)
        slope = float(coeffs[0])
        xs = [x[0], x[-1]]
        ys = [float(coeffs[0] * xi + coeffs[1]) for xi in xs]
        return xs, ys, slope
    except Exception:  # noqa: BLE001 — trend line is optional polish
        return None


def _rolling_average(y: List[float], window: int) -> List[float]:
    """Trailing rolling mean (window shrinks at the start)."""
    out: List[float] = []
    for i in range(len(y)):
        lo = max(0, i - window + 1)
        chunk = y[lo:i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def _promotion_points(
    conn: sqlite3.Connection, *, since_run_id: Optional[str] = None
) -> List[Tuple[float, float]]:
    """``(total_games, champion_elo)`` for each promoted run (for plot markers)."""
    try:
        if since_run_id:
            rows = conn.execute(
                "SELECT total_games, champion_elo FROM run_summary "
                "WHERE promoted=1 AND run_id >= ? ORDER BY total_games ASC",
                (since_run_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT total_games, champion_elo FROM run_summary WHERE promoted=1 "
                "ORDER BY total_games ASC"
            ).fetchall()
    except sqlite3.Error:
        return []
    return [(float(r["total_games"]), float(r["champion_elo"])) for r in rows
            if r["total_games"] is not None and r["champion_elo"] is not None]


def render_elo_plot(
    conn: sqlite3.Connection,
    out_path: Path | str,
    *,
    agent: str = "champion",
    target_elo: Optional[float] = None,
    since_run_id: Optional[str] = None,
    era_label: Optional[str] = None,
) -> Optional[Path]:
    """Render the champion Elo trajectory to ``out_path`` (PNG). Returns the path.

    Returns ``None`` — without raising — when there is nothing to plot or
    matplotlib is unavailable, so callers can treat a missing plot as "ship the
    email without it". ``since_run_id`` restricts the plot to a reporting era (see
    :mod:`training.reporting_era`); ``era_label`` names that era in the title.
    """
    out_path = Path(out_path)
    x, y, granularity = _load_series(conn, agent=agent, since_run_id=since_run_id)
    if not x:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")  # headless: no display needed in CI
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001 — matplotlib missing -> no plot, not a crash
        return None

    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=130)
    ax.plot(x, y, color="#2563eb", linewidth=1.4, alpha=0.9,
            marker="o" if len(x) <= 60 else None, markersize=3,
            label=f"Champion Elo ({granularity})")

    # Rolling average — smooths matchup/seed noise so the real drift is visible.
    if len(y) >= 5:
        window = max(5, min(25, len(y) // 5))
        roll = _rolling_average(y, window)
        ax.plot(x, roll, color="#f59e0b", linewidth=1.6, alpha=0.9,
                label=f"Rolling avg (w={window})")

    # Best historical reference line.
    best = max(y)
    ax.axhline(best, color="#16a34a", linewidth=1.0, linestyle="--", alpha=0.7,
               label=f"Best historical ({best:.0f})")

    # Promotion markers — where the champion actually changed.
    promos = _promotion_points(conn, since_run_id=since_run_id)
    if promos:
        px = [p[0] for p in promos]
        py = [p[1] for p in promos]
        ax.scatter(px, py, color="#9333ea", marker="^", s=55, zorder=5,
                   label=f"Promotions ({len(promos)})")
        for gx in px:
            ax.axvline(gx, color="#9333ea", linewidth=0.7, linestyle=":", alpha=0.4)

    # Linear trend line — the headline "is it moving up?" signal.
    caption_bits: List[str] = []
    trend = _trend_line(x, y)
    if trend is not None:
        xs, ys, slope = trend
        direction = "rising" if slope > 0 else ("flat" if slope == 0 else "declining")
        ax.plot(xs, ys, color="#dc2626", linewidth=1.6, linestyle="-",
                label=f"Trend ({direction})")
        caption_bits.append(f"trend {slope:+.2f} Elo/game" if granularity == "per-game"
                            else f"trend {slope:+.2f} Elo/game-of-progress")

    if target_elo:
        ax.axhline(float(target_elo), color="#9333ea", linewidth=1.0,
                   linestyle=":", alpha=0.6, label=f"Human target ({target_elo:.0f})")

    # Annotate the latest value.
    ax.annotate(f"{y[-1]:.0f}", xy=(x[-1], y[-1]),
                xytext=(6, 0), textcoords="offset points",
                fontsize=9, fontweight="bold", color="#2563eb",
                va="center")

    xlabel = "Cumulative game" if granularity == "per-game" else "Cumulative games played"
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel("Champion Elo", fontsize=10)
    if era_label:
        title = f"Champion Elo trajectory ({era_label})"
    elif since_run_id:
        title = "Champion Elo trajectory (filtered era)"
    else:
        title = "Champion Elo trajectory"
    if caption_bits:
        title += "  —  " + ", ".join(caption_bits)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.legend(fontsize=8, loc="best", framealpha=0.9)
    fig.tight_layout()

    fig.savefig(out_path, format="png")
    plt.close(fig)
    return out_path


def render_default(
    target_elo: Optional[float] = None,
    *,
    since_run_id: Optional[str] = None,
    era_label: Optional[str] = None,
) -> Optional[Path]:
    """Render the plot for the real repo DB into ``training/reports/elo_trend.png``.

    Convenience entry point for the workflow's report step and the email composer.
    Defaults to the active reporting era (:func:`reporting_era.resolve_era`) so the
    committed PNG matches the email.
    """
    from training import TrainingPaths, reporting_era

    if since_run_id is None and era_label is None:
        era = reporting_era.resolve_era()
        since_run_id, era_label = era.since_run_id, era.label

    paths = TrainingPaths.default()
    paths.ensure_dirs()
    conn = ratings_db.connect(paths.ratings_db)
    try:
        return render_elo_plot(
            conn, paths.reports_dir / "elo_trend.png", target_elo=target_elo,
            since_run_id=since_run_id, era_label=era_label,
        )
    finally:
        conn.close()


def main() -> int:
    # 1700 is the project's documented human-strength anchor (state.human_target_elo
    # default); the email regenerates with the same target so the two PNGs match.
    out = render_default(target_elo=1700.0)
    if out is None:
        print("[elo_plot] No plot rendered (empty timeline or matplotlib missing).")
        return 0
    print(f"[elo_plot] Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
