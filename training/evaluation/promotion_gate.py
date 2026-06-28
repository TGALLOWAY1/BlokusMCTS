"""Promotion gate — statistical evidence required before a candidate is promoted.

Wraps the repo's conservative 6-gate decision
(:func:`analytics.tournament.gauntlet.evaluate_promotion`, already computed inside the
head-to-head evaluation) and layers on the extra checks the audit demands so a single
noisy Elo bump can never be read as progress:

* the candidate must **beat the champion head-to-head** (more wins, strictly),
* it must show a **positive Elo and TrueSkill delta** over the champion, and
* it must not regress against the benchmark pool (it is ranked #1, i.e. above every
  benchmark opponent — enforced by the conservative decision's "highest ranking" gate).

Every criterion is reported with a pass/fail and a human-readable detail, so the report
can say exactly why a candidate did or did not promote.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from training.evaluation.head_to_head import (
    EVAL_MIN_SEEDS,
    EVAL_MIN_TOTAL_GAMES,
    CandidateEval,
)


@dataclass
class GateThresholds:
    # Shorter eval gate (see head_to_head.EVAL_MIN_TOTAL_GAMES): start with fewer
    # required games so all four approaches can be evaluated within one CI budget.
    min_total_games: int = EVAL_MIN_TOTAL_GAMES
    min_seeds: int = EVAL_MIN_SEEDS
    min_mu_delta: float = 0.5
    min_elo_delta: float = 0.0
    h2h_strictly_beats_champion: bool = True


@dataclass
class GateResult:
    candidate: str
    approach: str
    passed: bool
    reason: str
    criteria: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate": self.candidate,
            "approach": self.approach,
            "passed": self.passed,
            "reason": self.reason,
            "criteria": self.criteria,
        }


def _crit(name: str, passed: bool, detail: str) -> Dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def evaluate_gate(ce: CandidateEval, thresholds: Optional[GateThresholds] = None) -> GateResult:
    """Combine the conservative decision with the extra evidence checks."""
    t = thresholds or GateThresholds()
    criteria: List[Dict[str, Any]] = []

    # Backbone: the repo's conservative 6-gate decision (rank #1, beats runner-up,
    # Δμ margin, Wilson win-rate, seeds, total games).
    decision = ce.decision
    conservative_pass = bool(getattr(decision, "promote", False)
                             and getattr(decision, "champion", None) == ce.name)
    for c in getattr(decision, "criteria", []) or []:
        criteria.append(_crit(f"conservative:{c.get('name')}", c.get("passed"),
                               str(c.get("detail", ""))))

    # Extra check 1: strictly beats the champion head-to-head.
    cw = int(ce.vs_champion.get("candidate_wins") or 0)
    chw = int(ce.vs_champion.get("champion_wins") or 0)
    h2h_pass = (cw > chw) if t.h2h_strictly_beats_champion else (cw >= chw)
    criteria.append(_crit("beats_champion_head_to_head", h2h_pass,
                          f"candidate {cw} wins vs champion {chw} wins"))

    # Extra check 2: positive Elo delta vs champion.
    elo_pass = ce.elo_delta_vs_champion >= t.min_elo_delta
    criteria.append(_crit("elo_improvement", elo_pass,
                          f"Elo Δ vs champion = {ce.elo_delta_vs_champion:+.1f} "
                          f"(need ≥ {t.min_elo_delta:+.1f})"))

    # Extra check 3: positive TrueSkill μ delta vs champion.
    mu_delta = ce.trueskill_mu_delta_vs_champion
    mu_pass = (mu_delta is not None and mu_delta >= t.min_mu_delta)
    criteria.append(_crit("trueskill_improvement", mu_pass,
                          f"TrueSkill μ Δ vs champion = "
                          f"{(mu_delta if mu_delta is not None else float('nan')):+.2f} "
                          f"(need ≥ {t.min_mu_delta:+.2f})"))

    # Min games / seeds (also covered conservatively, surfaced explicitly here).
    games_pass = ce.games >= t.min_total_games
    criteria.append(_crit("min_total_games", games_pass,
                          f"{ce.games} games (need ≥ {t.min_total_games})"))
    seeds_pass = ce.n_seeds >= t.min_seeds
    criteria.append(_crit("min_seeds", seeds_pass,
                          f"{ce.n_seeds} seeds (need ≥ {t.min_seeds})"))

    passed = conservative_pass and h2h_pass and elo_pass and mu_pass and games_pass and seeds_pass
    if passed:
        reason = (f"PROMOTE {ce.name}: beats champion ({cw}-{chw}), "
                  f"Δμ {mu_delta:+.2f}, ΔElo {ce.elo_delta_vs_champion:+.1f}, "
                  f"{ce.games} games over {ce.n_seeds} seeds.")
    else:
        failed = [c["name"] for c in criteria if not c["passed"]]
        reason = f"HOLD {ce.name}: failed {failed}."
    return GateResult(candidate=ce.name, approach=ce.approach, passed=passed,
                      reason=reason, criteria=criteria)


def select_winner(
    evals: List[CandidateEval], thresholds: Optional[GateThresholds] = None
) -> Dict[str, Any]:
    """Evaluate every candidate's gate and pick the best passing candidate.

    Returns ``{"gates": {name: GateResult}, "winner": Optional[CandidateEval],
    "winner_gate": Optional[GateResult]}``. The winner is the gate-passing candidate
    with the highest TrueSkill μ delta over the champion (most decisive improvement).
    """
    gates: Dict[str, GateResult] = {}
    passing: List[CandidateEval] = []
    for ce in evals:
        gr = evaluate_gate(ce, thresholds)
        gates[ce.name] = gr
        if gr.passed:
            passing.append(ce)
    winner = None
    if passing:
        winner = max(passing, key=lambda e: (e.trueskill_mu_delta_vs_champion or 0.0,
                                             e.elo_delta_vs_champion))
    return {
        "gates": gates,
        "winner": winner,
        "winner_gate": gates[winner.name] if winner else None,
    }
