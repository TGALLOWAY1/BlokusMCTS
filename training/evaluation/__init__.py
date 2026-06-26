"""Candidate evaluation: stable benchmark pool, head-to-head battery, promotion gate,
and rating-trajectory analysis. Thin orchestration over the vetted
``analytics.tournament`` code paths.
"""

from __future__ import annotations

from training.evaluation.benchmark_pool import (
    DEFAULT_BENCHMARK_SEEDS,
    BenchmarkPool,
    build_benchmark_pool,
)
from training.evaluation.head_to_head import (
    CandidateEval,
    HeadToHeadResult,
    evaluate_candidate_vs_pool,
    evaluate_candidates,
)
from training.evaluation.promotion_gate import (
    GateResult,
    GateThresholds,
    evaluate_gate,
    select_winner,
)
from training.evaluation.rating_analysis import (
    TrajectorySummary,
    estimate_elo_noise,
    summarize_trajectory,
)

__all__ = [
    "DEFAULT_BENCHMARK_SEEDS",
    "BenchmarkPool",
    "build_benchmark_pool",
    "CandidateEval",
    "HeadToHeadResult",
    "evaluate_candidate_vs_pool",
    "evaluate_candidates",
    "GateResult",
    "GateThresholds",
    "evaluate_gate",
    "select_winner",
    "TrajectorySummary",
    "estimate_elo_noise",
    "summarize_trajectory",
]
