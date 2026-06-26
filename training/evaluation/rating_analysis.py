"""Rating-trajectory analysis — distinguish real movement from noise.

Helpers the report uses to keep noisy Elo from masquerading as progress: a rolling
average, a noise estimate (stddev of champion Elo while the champion config was fixed),
a best-vs-current comparison, and a post-promotion regression check.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence


def rolling_average(series: Sequence[float], window: int = 5) -> List[float]:
    """Trailing rolling mean of ``series`` (window shrinks at the start)."""
    out: List[float] = []
    for i in range(len(series)):
        lo = max(0, i - window + 1)
        chunk = series[lo:i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def _stddev(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))


@dataclass
class NoiseEstimate:
    n: int
    mean: float
    stddev: float
    spread: float  # max - min

    def to_dict(self) -> Dict[str, Any]:
        return {"n": self.n, "mean": round(self.mean, 1),
                "stddev": round(self.stddev, 1), "spread": round(self.spread, 1)}


def estimate_elo_noise(elo_series: Sequence[float], tail: int = 20) -> NoiseEstimate:
    """Estimate Elo measurement noise from the recent tail of the champion series.

    When the champion config is unchanged, this stddev is pure matchup/seed variance —
    the floor below which an Elo delta is meaningless.
    """
    vals = list(elo_series)[-tail:]
    if not vals:
        return NoiseEstimate(0, 0.0, 0.0, 0.0)
    return NoiseEstimate(n=len(vals), mean=sum(vals) / len(vals),
                         stddev=_stddev(vals), spread=max(vals) - min(vals))


def trend_per_step(series: Sequence[float]) -> float:
    """Least-squares slope of ``series`` vs index (Elo per step). 0 if too short."""
    n = len(series)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(series) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((xs[i] - mx) * (series[i] - my) for i in range(n)) / denom


@dataclass
class TrajectorySummary:
    current: float
    best: float
    gap_to_best: float
    rolling_last: Optional[float]
    trend_per_step: float
    noise: NoiseEstimate
    significant: bool  # is |current - best| beyond the noise floor?

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current": round(self.current, 1),
            "best": round(self.best, 1),
            "gap_to_best": round(self.gap_to_best, 1),
            "rolling_last": (round(self.rolling_last, 1) if self.rolling_last is not None else None),
            "trend_per_step": round(self.trend_per_step, 4),
            "noise": self.noise.to_dict(),
            "significant": self.significant,
        }


def summarize_trajectory(elo_series: Sequence[float], window: int = 5) -> TrajectorySummary:
    """Compute a noise-aware summary of the champion Elo trajectory."""
    series = [float(x) for x in elo_series]
    if not series:
        return TrajectorySummary(0.0, 0.0, 0.0, None, 0.0,
                                 NoiseEstimate(0, 0.0, 0.0, 0.0), False)
    current = series[-1]
    best = max(series)
    noise = estimate_elo_noise(series)
    roll = rolling_average(series, window)
    gap = current - best
    # "Significant" only if the move exceeds the noise floor (one stddev).
    significant = abs(gap) > max(noise.stddev, 1e-9)
    return TrajectorySummary(
        current=current, best=best, gap_to_best=gap,
        rolling_last=roll[-1] if roll else None,
        trend_per_step=trend_per_step(series), noise=noise, significant=significant,
    )


def detect_post_promotion_regression(
    elo_series: Sequence[float], promotion_indices: Sequence[int], drop: float = 25.0
) -> List[Dict[str, Any]]:
    """Flag promotions followed by an Elo drop ≥ ``drop`` within the next few steps."""
    out: List[Dict[str, Any]] = []
    series = list(elo_series)
    for idx in promotion_indices:
        if 0 <= idx < len(series):
            after = series[idx + 1: idx + 6]
            if after and (min(after) - series[idx]) <= -drop:
                out.append({"promotion_index": idx, "elo_at_promotion": series[idx],
                            "min_after": min(after)})
    return out
