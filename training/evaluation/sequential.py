"""Sequential, variance-reduced champion-vs-candidate evaluation (SPRT screen).

Why this exists
---------------
The fixed-N screen (:mod:`training.evaluation.head_to_head`) rated a candidate from a
*fresh* Elo tracker over ~20 four-player games. Two things made that signal almost
useless for detecting the small, real gains a mature champion produces:

1. **Unpaired, high-variance metric.** A 4-player free-for-all win rate (chance = 25%)
   is dominated by seat luck, opponent behaviour and opening variance. Re-rating a
   *fixed* agent this way swings its Elo by ~±70 run to run (the reported "noise
   floor"), which swamps a genuine +10..+30 Elo improvement.
2. **A fixed game budget.** 20 games is far too few to resolve a real edge, yet it is
   spent in full even on a candidate that is obviously equal (or obviously better).

This module fixes both, using infrastructure that already exists in the repo:

* **Paired comparison.** The champion and the candidate are co-present in *every*
  evaluation game (same board, same opponents, same seed — the arena keys agent RNG
  by *name*, not seat). So each game yields a paired outcome ``sign(candidate_score −
  champion_score) ∈ {win, draw, loss}`` in which the shared nuisance variance cancels.
* **Seat balancing.** Games are played with ``seat_policy="round_robin"`` so each agent
  visits each seat once per four games — first-move advantage cancels by construction
  rather than "in expectation".
* **Sequential stopping (SPRT).** A Wald Sequential Probability Ratio Test on the paired
  W/D/L stream stops as soon as the evidence is conclusive. A clearly-better candidate
  is accepted in a handful of games; a clone / regressor is *rejected* in a handful
  (freeing budget); only genuinely borderline candidates cost many games — exactly where
  the games should go. This is the standard method from computer-chess engine testing
  (Stockfish / fishtest) and is what makes "effective daily training with fewer games"
  possible.

The SPRT math (:func:`sprt_llr`, :func:`sprt_decision`) is pure and unit-tested; the
driver (:func:`sequential_paired_eval`) plays games in seat-balanced blocks, re-checks
the test after each block, and returns the accumulated games so the caller can fold them
into the usual pooled ratings / reports.
"""

from __future__ import annotations

import math
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from analytics.tournament.statistics import (
    bootstrap_score_ci,
    paired_permutation_test,
    wilson_score_interval,
)
from training import TrainingPaths
from training import selfplay_core as sc
from training.evaluation.benchmark_pool import BenchmarkPool
from training.evaluation.head_to_head import (
    HeadToHeadResult,
    _candidate_arenas,
    aggregate_candidate_eval,
)

# --- Defaults ---------------------------------------------------------------
# H0: candidate is no stronger than the champion (pairwise Elo 0).
# H1: candidate is at least ``DEFAULT_ELO1`` Elo stronger — the smallest edge worth
# promoting. This choice sets the game budget: distinguishing a *small* edge from
# zero is fundamentally expensive, so a larger H1 means far fewer games (the whole
# point), at the cost of not chasing sub-threshold gains. Honest expected sample
# sizes for the paired trinomial test at α=β=0.05 (games to reject a no-op clone /
# to confirm a clearly-strong candidate):
#
#     elo1=20  → ~1800 / ~800     elo1=50  → ~285 / ~130
#     elo1=70  → ~145 / ~70       elo1=100 → ~70 / ~35
#
# 70 is the sweet spot for a daily budget: it rules out the current no-op / regressor
# candidates in ~150 games and confirms a genuinely strong new candidate in ~70,
# versus the old fixed 20-game screen that could resolve *nothing*. Marginal
# candidates hit ``max_games`` → "inconclusive" → hold (conservative); run a longer
# confirmation for those. Tune elo1 down (more games) only with more compute/day.
DEFAULT_ELO0 = 0.0
DEFAULT_ELO1 = 70.0
DEFAULT_ALPHA = 0.05  # P(accept H1 | H0 true) — false-promotion rate
DEFAULT_BETA = 0.05   # P(accept H0 | H1 true) — missed-improvement rate

# One round_robin block = 4 games covers a full seat rotation per arena.
DEFAULT_BLOCK_GAMES = 4
DEFAULT_MIN_GAMES = 24    # never decide before this many paired games
DEFAULT_MAX_GAMES = 200   # give up (inconclusive → hold) beyond this many


def elo_to_score(elo: float) -> float:
    """Expected pairwise score (win=1, draw=0.5, loss=0) for an Elo advantage."""
    return 1.0 / (1.0 + math.pow(10.0, -elo / 400.0))


def score_to_elo(score: float) -> float:
    """Inverse of :func:`elo_to_score`, clamped away from the 0/1 singularities."""
    s = min(max(score, 1e-6), 1.0 - 1e-6)
    return -400.0 * math.log10(1.0 / s - 1.0)


def sprt_bounds(alpha: float, beta: float) -> Tuple[float, float]:
    """Wald's log-likelihood-ratio decision bounds ``(lower_B, upper_A)``.

    Cross ``upper`` ⇒ accept H1; cross ``lower`` ⇒ accept H0.
    """
    upper_a = math.log((1.0 - beta) / alpha)
    lower_b = math.log(beta / (1.0 - alpha))
    return lower_b, upper_a


def sprt_llr(
    wins: int,
    draws: int,
    losses: int,
    *,
    elo0: float = DEFAULT_ELO0,
    elo1: float = DEFAULT_ELO1,
) -> float:
    """Log-likelihood ratio of the paired W/D/L counts under H1 vs H0.

    Uses the standard "fixed observed draw ratio" trinomial model (Van den Bergh /
    fishtest): with the empirical draw rate ``d`` held equal under both hypotheses,
    the win/loss probabilities are ``w(elo) = p(elo) − d/2`` and ``l(elo) =
    1 − p(elo) − d/2`` where ``p(elo)`` is the expected pairwise score. Draw terms
    cancel (same ``d`` under H0 and H1), so

        LLR = wins · log(w1/w0) + losses · log(l1/l0).

    Probabilities are floored at a small epsilon so an early all-wins / all-losses
    streak yields a large-but-finite LLR instead of ``±inf``.
    """
    n = wins + draws + losses
    if n <= 0:
        return 0.0
    eps = 1e-9
    d = draws / n
    p0, p1 = elo_to_score(elo0), elo_to_score(elo1)

    def wl(p: float) -> Tuple[float, float]:
        w = max(eps, p - d / 2.0)
        loss = max(eps, 1.0 - p - d / 2.0)
        return w, loss

    w0, l0 = wl(p0)
    w1, l1 = wl(p1)
    return wins * math.log(w1 / w0) + losses * math.log(l1 / l0)


@dataclass
class SprtStatus:
    decision: str  # "accept_h1" | "accept_h0" | "continue"
    llr: float
    lower: float
    upper: float
    n: int


def sprt_decision(
    wins: int,
    draws: int,
    losses: int,
    *,
    elo0: float = DEFAULT_ELO0,
    elo1: float = DEFAULT_ELO1,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    min_games: int = DEFAULT_MIN_GAMES,
) -> SprtStatus:
    """Evaluate the SPRT on the current paired counts.

    Returns ``"continue"`` until ``min_games`` paired games have accumulated so a
    lucky opening streak cannot decide on its own.
    """
    n = wins + draws + losses
    llr = sprt_llr(wins, draws, losses, elo0=elo0, elo1=elo1)
    lower, upper = sprt_bounds(alpha, beta)
    if n < max(1, min_games):
        decision = "continue"
    elif llr >= upper:
        decision = "accept_h1"
    elif llr <= lower:
        decision = "accept_h0"
    else:
        decision = "continue"
    return SprtStatus(decision=decision, llr=llr, lower=lower, upper=upper, n=n)


def paired_outcomes(
    games: Sequence[Dict[str, Any]], candidate: str, champion: str
) -> Tuple[int, int, int, List[float], List[float]]:
    """Reduce pooled games to paired champion-vs-candidate counts + score lists.

    Only games in which *both* agents played contribute. Returns
    ``(wins, draws, losses, candidate_scores, champion_scores)`` where a "win" is a
    game the candidate outscored the champion.
    """
    wins = draws = losses = 0
    cand_scores: List[float] = []
    champ_scores: List[float] = []
    for g in games:
        scores = g.get("agent_scores") or {}
        if candidate not in scores or champion not in scores:
            continue
        cs = float(scores[candidate])
        hs = float(scores[champion])
        cand_scores.append(cs)
        champ_scores.append(hs)
        if cs > hs:
            wins += 1
        elif cs < hs:
            losses += 1
        else:
            draws += 1
    return wins, draws, losses, cand_scores, champ_scores


@dataclass
class SequentialEvalResult:
    """Outcome of a sequential paired evaluation of one candidate vs the champion."""

    name: str
    approach: str
    decision: str  # "accept_h1" | "accept_h0" | "inconclusive"
    is_improvement: bool  # decision == accept_h1
    n_games: int
    wins: int
    draws: int
    losses: int
    pairwise_win_rate: float  # (wins + 0.5·draws) / n — expected pairwise score
    pairwise_win_rate_ci: Tuple[float, float]
    elo_estimate: float  # candidate − champion pairwise Elo (point estimate)
    llr: float
    lower_bound: float
    upper_bound: float
    elo0: float
    elo1: float
    mean_score_diff: float
    score_diff_ci: Tuple[float, float]
    permutation_p_value: float
    blocks_run: int
    runtime_s: float
    games: List[Dict[str, Any]] = field(default_factory=list)
    run_dirs: List[str] = field(default_factory=list)

    def summary_line(self) -> str:
        dec = {"accept_h1": "IMPROVEMENT", "accept_h0": "no improvement",
               "inconclusive": "inconclusive"}.get(self.decision, self.decision)
        return (
            f"[sprt] {self.name}: {dec} after {self.n_games} paired games "
            f"({self.wins}W-{self.draws}D-{self.losses}L, pairwise "
            f"{self.pairwise_win_rate*100:.0f}%, Δelo≈{self.elo_estimate:+.0f}, "
            f"LLR={self.llr:+.2f} in [{self.lower_bound:.2f},{self.upper_bound:.2f}])"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "approach": self.approach,
            "decision": self.decision,
            "is_improvement": self.is_improvement,
            "n_games": self.n_games,
            "record": {"wins": self.wins, "draws": self.draws, "losses": self.losses},
            "pairwise_win_rate": round(self.pairwise_win_rate, 4),
            "pairwise_win_rate_ci": [round(c, 4) for c in self.pairwise_win_rate_ci],
            "elo_estimate": round(self.elo_estimate, 1),
            "llr": round(self.llr, 3),
            "bounds": [round(self.lower_bound, 3), round(self.upper_bound, 3)],
            "hypotheses_elo": [self.elo0, self.elo1],
            "mean_score_diff": round(self.mean_score_diff, 3),
            "score_diff_ci": [round(c, 3) for c in self.score_diff_ci],
            "permutation_p_value": round(self.permutation_p_value, 4),
            "blocks_run": self.blocks_run,
            "runtime_s": round(self.runtime_s, 2),
        }


# Prime strides so successive blocks (and the two pool arenas) never replay the
# same games; run_experiment derives per-game seeds from the run seed.
_BLOCK_SEED_STRIDE = 100003
_ARENA_SEED_STRIDE = 7919


def sequential_paired_eval(
    state: Dict[str, Any],
    candidate_name: str,
    candidate_approach: str,
    candidate_cfg: Dict[str, Any],
    pool: BenchmarkPool,
    paths: TrainingPaths,
    *,
    seeds: Optional[List[int]] = None,
    thinking_time_ms: Optional[int] = None,
    elo0: float = DEFAULT_ELO0,
    elo1: float = DEFAULT_ELO1,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    block_games: int = DEFAULT_BLOCK_GAMES,
    min_games: int = DEFAULT_MIN_GAMES,
    max_games: int = DEFAULT_MAX_GAMES,
    seat_policy: str = "round_robin",
    deadline: Optional[float] = None,
    verbose: bool = False,
) -> SequentialEvalResult:
    """Play seat-balanced blocks of ``[champion, candidate, opp_a, opp_b]`` games and
    run an SPRT on the paired champion-vs-candidate outcome, stopping as soon as the
    test is conclusive (or ``max_games`` / ``deadline`` is reached).

    The candidate is an *improvement* only if the SPRT accepts H1; an inconclusive
    stop is treated conservatively as "not an improvement".
    """
    t0 = time.monotonic()
    seeds = list(seeds) if seeds else list(pool.seeds)
    if not seeds:
        seeds = [20260620, 20260621]
    arenas = _candidate_arenas(state, candidate_cfg, candidate_name, pool)
    for agents in arenas:
        sc._apply_thinking_override(agents, thinking_time_ms)

    games: List[Dict[str, Any]] = []
    run_dirs: List[str] = []
    lower, upper = sprt_bounds(alpha, beta)
    status = SprtStatus(decision="continue", llr=0.0, lower=lower, upper=upper, n=0)
    blocks_run = 0

    block = 0
    while True:
        if deadline is not None and time.monotonic() >= deadline:
            break
        base_seed = seeds[block % len(seeds)] + (block // len(seeds)) * _BLOCK_SEED_STRIDE
        for arena_idx, agents in enumerate(arenas):
            if deadline is not None and time.monotonic() >= deadline:
                break
            result = sc.run_arena_inproc(
                agents, paths=paths,
                run_label=f"sprt_{candidate_name}_b{block}_a{arena_idx}",
                num_games=block_games, seed=base_seed + arena_idx * _ARENA_SEED_STRIDE,
                enable_snapshots=False, verbose=False, deadline=deadline,
                seat_policy=seat_policy,
            )
            run_dirs.append(result["run_dir"])
            games.extend(sc._load_games(result["run_dir"]))
        blocks_run += 1

        w, d, ls, _cand_s, _champ_s = paired_outcomes(games, candidate_name, "champion")
        status = sprt_decision(
            w, d, ls, elo0=elo0, elo1=elo1, alpha=alpha, beta=beta, min_games=min_games,
        )
        if verbose:
            print(f"[sprt] {candidate_name} block {blocks_run}: "
                  f"{w}W-{d}D-{ls}L LLR={status.llr:+.2f} -> {status.decision}", flush=True)
        if status.decision != "continue":
            break
        if (w + d + ls) >= max_games:
            break
        block += 1

    wins, draws, losses, cand_scores, champ_scores = paired_outcomes(
        games, candidate_name, "champion")
    n = wins + draws + losses
    pairwise = ((wins + 0.5 * draws) / n) if n else 0.0
    wilson = wilson_score_interval(wins + 0.5 * draws, n) if n else {"lower": 0.0, "upper": 0.0}
    boot = bootstrap_score_ci(cand_scores, champ_scores, n_resamples=2000, seed=12345)
    perm = paired_permutation_test(games, candidate_name, "champion",
                                   n_permutations=2000, seed=12345)

    if status.decision == "accept_h1":
        decision = "accept_h1"
    elif status.decision == "accept_h0":
        decision = "accept_h0"
    else:
        decision = "inconclusive"

    return SequentialEvalResult(
        name=candidate_name, approach=candidate_approach,
        decision=decision, is_improvement=(decision == "accept_h1"),
        n_games=n, wins=wins, draws=draws, losses=losses,
        pairwise_win_rate=pairwise,
        pairwise_win_rate_ci=(float(wilson["lower"]), float(wilson["upper"])),
        elo_estimate=score_to_elo(pairwise) if n else 0.0,
        llr=status.llr, lower_bound=status.lower, upper_bound=status.upper,
        elo0=elo0, elo1=elo1,
        mean_score_diff=float(boot["mean_diff"]),
        score_diff_ci=(float(boot["ci_lower"]), float(boot["ci_upper"])),
        permutation_p_value=float(perm["p_value"]),
        blocks_run=blocks_run, runtime_s=time.monotonic() - t0,
        games=games, run_dirs=run_dirs,
    )


def evaluate_candidates_sequential(
    state: Dict[str, Any],
    candidates: List[Any],  # List[training.approaches.Candidate], created==True
    pool: BenchmarkPool,
    paths: TrainingPaths,
    *,
    seeds: Optional[List[int]] = None,
    thinking_time_ms: Optional[int] = None,
    min_mu_margin: float = 0.5,
    elo0: float = DEFAULT_ELO0,
    elo1: float = DEFAULT_ELO1,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    block_games: int = DEFAULT_BLOCK_GAMES,
    min_games: int = DEFAULT_MIN_GAMES,
    max_games: int = DEFAULT_MAX_GAMES,
    deadline: Optional[float] = None,
    verbose: bool = False,
) -> Tuple[HeadToHeadResult, Dict[str, SequentialEvalResult]]:
    """Run the SPRT screen on every created candidate and return a
    :class:`HeadToHeadResult` (so the existing report/ratings path is unchanged) plus
    the per-candidate :class:`SequentialEvalResult` map.

    Each candidate's accumulated SPRT games are aggregated into a ``CandidateEval`` via
    :func:`training.evaluation.head_to_head.aggregate_candidate_eval` — the SPRT
    evidence therefore doubles as the conservative-gate evidence. The wall-clock budget
    is split fairly across candidates (a fresh share each iteration) so one candidate's
    long borderline test cannot starve the rest.
    """
    seeds = list(seeds) if seeds else list(pool.seeds)
    pending = [
        c for c in candidates
        if getattr(c, "created", False) and getattr(c, "agent_config", None)
    ]
    candidate_evals: List[Any] = []
    sprt_results: Dict[str, SequentialEvalResult] = {}
    all_games: List[Dict[str, Any]] = []
    all_run_dirs: List[str] = []
    skipped: List[str] = []

    for idx, cand in enumerate(pending):
        now = time.monotonic()
        if deadline is not None and now >= deadline:
            skipped.append(cand.name)
            continue
        cand_deadline = deadline
        if deadline is not None:
            share = (deadline - now) / max(len(pending) - idx, 1)
            cand_deadline = min(deadline, now + share)

        sprt = sequential_paired_eval(
            state, cand.name, cand.approach, cand.agent_config, pool, paths,
            seeds=seeds, thinking_time_ms=thinking_time_ms,
            elo0=elo0, elo1=elo1, alpha=alpha, beta=beta,
            block_games=block_games, min_games=min_games, max_games=max_games,
            deadline=cand_deadline, verbose=verbose,
        )
        sprt_results[cand.name] = sprt
        if verbose:
            print(sprt.summary_line(), flush=True)
        if sprt.n_games == 0:
            skipped.append(cand.name)
            continue

        arenas = _candidate_arenas(state, cand.agent_config, cand.name, pool)
        ce = aggregate_candidate_eval(
            cand.name, cand.approach, sprt.games, arenas,
            seeds=seeds, thinking_time_ms=thinking_time_ms, min_mu_margin=min_mu_margin,
            runtime_s=sprt.runtime_s, seat_policy="round_robin",
        )
        candidate_evals.append(ce)
        all_games.extend(sprt.games)
        all_run_dirs.extend(sprt.run_dirs)

    ht = HeadToHeadResult(
        pool=pool.describe(), seeds=seeds, games_per_arena=block_games,
        candidate_evals=candidate_evals, all_games=all_games, run_dirs=all_run_dirs,
        skipped_for_budget=skipped,
    )
    return ht, sprt_results
