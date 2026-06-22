"""Human-strength estimation from the Elo timeline.

Answers: *how far is the champion from human-level play, and — if it is actually
improving — how many more games/days until it gets there?* The guiding principle
from the spec is **do not fabricate confidence**: when there is no measurable
upward trend, or too few data points, we say so explicitly and return ``None`` for
the projections rather than inventing a number.

All functions here are pure (operate on plain data) so they are trivially
unit-tested without touching disk or the rating DB.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

# Nominal human-strength Elo anchors (from the spec). These are *assumed* targets:
# the codebase has no measured human-vs-MCTS Elo anchor, which is exactly why every
# estimate produced here carries an explicit confidence/caveat.
BEGINNER_ELO = 1200
INTERMEDIATE_ELO = 1500
STRONG_ELO = 1700

# Minimum distinct data points before we'll call a trend anything but "low".
_MIN_POINTS_LOW = 2
_MIN_POINTS_MEDIUM = 7


@dataclass(frozen=True)
class RateEstimate:
    """A measured Elo-gain rate over a window of recent points."""

    mean_gain: float  # average Elo gained per unit (per day or per game)
    stddev: float
    n_points: int
    unit: str  # "day" or "game"

    @property
    def is_reliable(self) -> bool:
        """True only with a positive trend and enough points to trust it."""
        return self.mean_gain > 0 and self.n_points >= _MIN_POINTS_LOW


def classify_strength(elo: float) -> str:
    """Bucket an Elo into a human-relatable strength label."""
    if elo < BEGINNER_ELO:
        return "below-beginner"
    if elo < INTERMEDIATE_ELO:
        return "beginner"
    if elo < STRONG_ELO:
        return "intermediate"
    return "strong-or-above"


def current_gap(current_elo: float, target: float = STRONG_ELO) -> float:
    """Elo points remaining to ``target`` (negative once the target is passed)."""
    return float(target) - float(current_elo)


def elo_gain_rate(
    series: Sequence[Dict[str, Any]],
    *,
    by: str = "day",
    window: int = 7,
) -> Optional[RateEstimate]:
    """Estimate the per-unit Elo gain over the last ``window`` points.

    ``series`` is an oldest-first list of ``{"elo": float, "total_games": int}``
    points (one per run), as produced by :func:`ratings_db.champion_elo_series`.

    * ``by="day"``  — average per-run Elo delta (one run ≈ one day/night).
    * ``by="game"`` — Elo delta divided by games played between points.

    Returns ``None`` when there are fewer than 2 usable points (no trend can be
    measured at all).
    """
    if by not in ("day", "game"):
        raise ValueError(f"by must be 'day' or 'game', got {by!r}")
    pts = list(series)[-(window + 1):] if window else list(series)
    if len(pts) < 2:
        return None

    gains: List[float] = []
    for prev, cur in zip(pts, pts[1:]):
        delta_elo = float(cur["elo"]) - float(prev["elo"])
        if by == "day":
            gains.append(delta_elo)
        else:  # per-game
            delta_games = float(cur.get("total_games", 0)) - float(prev.get("total_games", 0))
            if delta_games > 0:
                gains.append(delta_elo / delta_games)
    if not gains:
        return None

    mean_gain = statistics.fmean(gains)
    stddev = statistics.pstdev(gains) if len(gains) > 1 else 0.0
    return RateEstimate(mean_gain=mean_gain, stddev=stddev, n_points=len(gains), unit=by)


def estimate_to_target(
    current_elo: float,
    rate: Optional[RateEstimate],
    *,
    target: float = STRONG_ELO,
    games_per_day: Optional[float] = None,
) -> Dict[str, Any]:
    """Project games/days to ``target`` from a measured rate. Never fabricates.

    Returns a dict with ``target_elo``, ``gap``, ``games_remaining``,
    ``days_remaining``, ``lower_bound``/``upper_bound`` (uncertainty band on
    days), ``confidence`` (``"none"|"low"|"medium"``) and a human ``caveat``.

    Confidence rules:
      * already at/past target            -> confidence "high", remaining 0.
      * no rate, or non-positive trend    -> confidence "none", remaining None.
      * positive trend, < 7 points        -> confidence "low".
      * positive trend, >= 7 points       -> confidence "medium".
    """
    gap = current_gap(current_elo, target)
    base: Dict[str, Any] = {
        "target_elo": float(target),
        "gap": gap,
        "games_remaining": None,
        "days_remaining": None,
        "lower_bound": None,
        "upper_bound": None,
        "confidence": "none",
        "caveat": "",
    }

    if gap <= 0:
        base.update(
            confidence="high",
            games_remaining=0,
            days_remaining=0,
            caveat=f"Already at or above the {target:.0f} Elo target.",
        )
        return base

    if rate is None or rate.mean_gain <= 0:
        base["caveat"] = (
            "No measurable upward Elo trend yet; cannot project time to target. "
            "Estimates appear once the champion shows sustained improvement."
        )
        return base

    confidence = "medium" if rate.n_points >= _MIN_POINTS_MEDIUM else "low"

    if rate.unit == "day":
        days = gap / rate.mean_gain
        base["days_remaining"] = round(days, 1)
        # Uncertainty band from the rate's stddev (faster/slower plausible rates).
        fast = rate.mean_gain + rate.stddev
        slow = rate.mean_gain - rate.stddev
        if fast > 0:
            base["lower_bound"] = round(gap / fast, 1)
        if slow > 0:
            base["upper_bound"] = round(gap / slow, 1)
    else:  # per-game
        games = gap / rate.mean_gain
        base["games_remaining"] = int(round(games))
        if games_per_day and games_per_day > 0:
            base["days_remaining"] = round(games / games_per_day, 1)

    caveat_bits = [
        f"Based on {rate.n_points} recent point(s) "
        f"(+{rate.mean_gain:.2f} Elo/{rate.unit}, sd {rate.stddev:.2f})."
    ]
    if confidence == "low":
        caveat_bits.append("Few data points — treat as a rough lower-confidence estimate.")
    base["confidence"] = confidence
    base["caveat"] = " ".join(caveat_bits)
    return base


def summarize(
    current_elo: float,
    series: Sequence[Dict[str, Any]],
    *,
    target: float = STRONG_ELO,
    window: int = 7,
) -> Dict[str, Any]:
    """Convenience bundle: strength label + gap + per-day projection to target."""
    rate = elo_gain_rate(series, by="day", window=window)
    est = estimate_to_target(current_elo, rate, target=target)
    est["strength"] = classify_strength(current_elo)
    est["current_elo"] = float(current_elo)
    return est
