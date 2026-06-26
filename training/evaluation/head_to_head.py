"""Head-to-head evaluation of candidates against the fixed benchmark pool.

For each created candidate this runs a battery of 4-agent arenas of the form
``[champion, candidate, pool_opp_a, pool_opp_b]`` across the pool's fixed seeds, pools
every game, and computes per-agent strength (win rate + Wilson/normal CIs, rank
distribution, score, TrueSkill, Elo) plus the candidate-vs-champion record and the
repo's conservative promotion decision. Arena execution, aggregation, TrueSkill and the
gate are all delegated to the vetted ``analytics.tournament`` / ``training.selfplay_core``
code paths — this module only orchestrates and shapes results for the report.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from analytics.tournament import gauntlet
from analytics.tournament.elo import EloTracker
from training import TrainingPaths, selfplay_core as sc
from training.evaluation.benchmark_pool import BenchmarkPool


def _with_name(cfg: Dict[str, Any], name: str) -> Dict[str, Any]:
    out = copy.deepcopy(cfg)
    out["name"] = name
    return out


@dataclass
class CandidateEval:
    """Pooled evaluation of one candidate against champion + benchmark pool."""

    name: str
    approach: str
    games: int
    n_seeds: int
    win_rate: float
    win_rate_ci: Tuple[float, float]
    avg_rank: float
    rank_distribution: Dict[int, int]
    avg_score: float
    trueskill_mu: Optional[float]
    trueskill_sigma: Optional[float]
    elo: float
    champion_win_rate: float
    champion_elo: float
    champion_trueskill_mu: Optional[float]
    vs_champion: Dict[str, Any]
    elo_delta_vs_champion: float
    trueskill_mu_delta_vs_champion: Optional[float]
    decision: Any  # gauntlet.PromotionDecision
    runtime_s: float
    ranked: List[Dict[str, Any]] = field(default_factory=list)
    pooled_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "approach": self.approach,
            "games": self.games,
            "n_seeds": self.n_seeds,
            "win_rate": self.win_rate,
            "win_rate_ci": list(self.win_rate_ci),
            "avg_rank": self.avg_rank,
            "rank_distribution": self.rank_distribution,
            "avg_score": self.avg_score,
            "trueskill_mu": self.trueskill_mu,
            "trueskill_sigma": self.trueskill_sigma,
            "elo": self.elo,
            "champion_win_rate": self.champion_win_rate,
            "champion_elo": self.champion_elo,
            "champion_trueskill_mu": self.champion_trueskill_mu,
            "vs_champion": self.vs_champion,
            "elo_delta_vs_champion": self.elo_delta_vs_champion,
            "trueskill_mu_delta_vs_champion": self.trueskill_mu_delta_vs_champion,
            "promote": bool(getattr(self.decision, "promote", False)),
            "runtime_s": round(self.runtime_s, 2),
        }


@dataclass
class HeadToHeadResult:
    pool: Dict[str, Any]
    seeds: List[int]
    games_per_arena: int
    candidate_evals: List[CandidateEval]
    all_games: List[Dict[str, Any]] = field(default_factory=list)
    run_dirs: List[str] = field(default_factory=list)
    skipped_for_budget: List[str] = field(default_factory=list)


def _candidate_arenas(
    state: Dict[str, Any],
    candidate_cfg: Dict[str, Any],
    candidate_name: str,
    pool: BenchmarkPool,
) -> List[List[Dict[str, Any]]]:
    """Build ``[champion, candidate, opp_a, opp_b]`` arenas over the pool (≤2 arenas)."""
    champ = _with_name(state["champion_params"], "champion")
    cand = _with_name(candidate_cfg, candidate_name)
    # Defensive: never let an opponent share the candidate's or champion's name
    # (arena requires unique agent names). Relabel any clash.
    reserved = {"champion", candidate_name}
    opps = []
    for o in pool.opponents:
        oc = copy.deepcopy(o)
        if oc.get("name") in reserved:
            oc["name"] = f"{oc.get('name')}_pool"
        reserved.add(oc["name"])
        opps.append(oc)
    if len(opps) < 2:  # guarantee a valid 4-agent arena
        opps = opps + [{"name": "random_pool", "type": "random", "thinking_time_ms": None, "params": {}}]
    n = len(opps)
    if n == 2:
        pairs = [(opps[0], opps[1])]
    else:  # rotate consecutive pairs, capped at 2 arenas to bound cost
        pairs = [(opps[i], opps[(i + 1) % n]) for i in range(n)][:2]
    return [[champ, cand, copy.deepcopy(a), copy.deepcopy(b)] for a, b in pairs]


def evaluate_candidate_vs_pool(
    state: Dict[str, Any],
    candidate_name: str,
    candidate_approach: str,
    candidate_cfg: Dict[str, Any],
    pool: BenchmarkPool,
    paths: TrainingPaths,
    *,
    games_per_arena: int,
    seeds: Optional[List[int]] = None,
    thinking_time_ms: Optional[int] = None,
    min_mu_margin: float = 0.5,
    run_label_prefix: str = "ht",
    verbose: bool = False,
) -> Tuple[CandidateEval, List[Dict[str, Any]], List[str]]:
    """Evaluate one candidate; returns ``(CandidateEval, games, run_dirs)``."""
    from training.experiments.compare import _mean_ci, per_agent_game_stats

    seeds = list(seeds) if seeds else list(pool.seeds)
    t0 = time.monotonic()
    arenas = _candidate_arenas(state, candidate_cfg, candidate_name, pool)
    games: List[Dict[str, Any]] = []
    run_dirs: List[str] = []
    for arena_idx, agents in enumerate(arenas):
        sc._apply_thinking_override(agents, thinking_time_ms)
        for seed in seeds:
            result = sc.run_arena_inproc(
                agents, paths=paths,
                run_label=f"{run_label_prefix}_{candidate_name}_a{arena_idx}_s{seed}",
                num_games=games_per_arena, seed=seed, enable_snapshots=False, verbose=verbose,
            )
            run_dirs.append(result["run_dir"])
            games.extend(sc._load_games(result["run_dir"]))

    agent_names = sorted({a["name"] for arena in arenas for a in arena})
    thinking_by_agent = {
        a["name"]: (thinking_time_ms if thinking_time_ms is not None else a.get("thinking_time_ms"))
        for arena in arenas for a in arena
    }
    pooled = gauntlet.aggregate_summary(
        games, agent_names=agent_names, thinking_time_ms_by_agent=thinking_by_agent,
        seeds=seeds, seat_policy="randomized",
        run_config={"phase": "benchmark_eval", "candidate": candidate_name},
    )
    leaderboard = {r["name"]: r for r in gauntlet.build_leaderboard(pooled)}
    ranked = gauntlet.rank_candidates(gauntlet.build_leaderboard(pooled))
    total_games = int(pooled.get("completed_games", len(games)))

    decision = gauntlet.evaluate_promotion(
        ranked, pooled, n_seeds=len(seeds), total_games=total_games,
        thresholds=gauntlet.PromotionThresholds(
            min_seeds=2, min_total_games=40, min_mu_margin=min_mu_margin, num_agents=4),
    )

    # Per-agent score/rank/Elo from the pooled games.
    raw = per_agent_game_stats(games, [candidate_name, "champion"])
    elo = EloTracker()
    for g in games:
        s = g.get("agent_scores", {})
        if s:
            elo.update_game(s)
    cand_raw = raw[candidate_name]
    g_cand = max(cand_raw["games"], 1)
    cand_lb = leaderboard.get(candidate_name, {})
    champ_lb = leaderboard.get("champion", {})
    h2h = gauntlet.pairwise_record(pooled, candidate_name, "champion")

    cand_mu = cand_lb.get("trueskill_mu")
    champ_mu = champ_lb.get("trueskill_mu")
    cand_eval = CandidateEval(
        name=candidate_name,
        approach=candidate_approach,
        games=cand_raw["games"],
        n_seeds=len(seeds),
        win_rate=float(cand_lb.get("win_rate", cand_raw["wins"] / g_cand)),
        win_rate_ci=(float(cand_lb.get("win_rate_ci_lower", 0.0)),
                     float(cand_lb.get("win_rate_ci_upper", 0.0))),
        avg_rank=(cand_raw["rank_sum"] / g_cand) if cand_raw["rank_sum"] else 0.0,
        rank_distribution=dict(sorted(cand_raw["rank_dist"].items())),
        avg_score=cand_raw["score_sum"] / g_cand,
        trueskill_mu=cand_mu,
        trueskill_sigma=cand_lb.get("trueskill_sigma"),
        elo=float(elo.get_rating(candidate_name)),
        champion_win_rate=float(champ_lb.get("win_rate", 0.0)),
        champion_elo=float(elo.get_rating("champion")),
        champion_trueskill_mu=champ_mu,
        vs_champion={
            "candidate_wins": h2h.get("a_wins"),
            "champion_wins": h2h.get("b_wins"),
            "ties": h2h.get("tie"),
        },
        elo_delta_vs_champion=float(elo.get_rating(candidate_name)) - float(elo.get_rating("champion")),
        trueskill_mu_delta_vs_champion=(
            (cand_mu - champ_mu) if cand_mu is not None and champ_mu is not None else None),
        decision=decision,
        runtime_s=time.monotonic() - t0,
        ranked=ranked,
        pooled_summary=pooled,
    )
    return cand_eval, games, run_dirs


def evaluate_candidates(
    state: Dict[str, Any],
    candidates: List[Any],  # List[training.approaches.Candidate], created==True
    pool: BenchmarkPool,
    paths: TrainingPaths,
    *,
    games_per_arena: int,
    seeds: Optional[List[int]] = None,
    thinking_time_ms: Optional[int] = None,
    min_mu_margin: float = 0.5,
    deadline: Optional[float] = None,
    verbose: bool = False,
) -> HeadToHeadResult:
    """Evaluate every created candidate against the pool; pool all games.

    ``deadline`` is a ``time.monotonic()`` cutoff: it is checked *before* each
    candidate's battery so a multi-candidate run cannot overrun the wall-clock budget
    by more than one candidate. Candidates skipped for budget are listed in
    ``skipped`` (still created, just not evaluated this run).
    """
    seeds = list(seeds) if seeds else list(pool.seeds)
    evals: List[CandidateEval] = []
    all_games: List[Dict[str, Any]] = []
    all_run_dirs: List[str] = []
    skipped: List[str] = []
    for cand in candidates:
        if not getattr(cand, "created", False) or not getattr(cand, "agent_config", None):
            continue
        if deadline is not None and time.monotonic() >= deadline:
            skipped.append(cand.name)
            continue
        ce, games, run_dirs = evaluate_candidate_vs_pool(
            state, cand.name, cand.approach, cand.agent_config, pool, paths,
            games_per_arena=games_per_arena, seeds=seeds,
            thinking_time_ms=thinking_time_ms, min_mu_margin=min_mu_margin, verbose=verbose,
        )
        evals.append(ce)
        all_games.extend(games)
        all_run_dirs.extend(run_dirs)
    return HeadToHeadResult(
        pool=pool.describe(), seeds=seeds, games_per_arena=games_per_arena,
        candidate_evals=evals, all_games=all_games, run_dirs=all_run_dirs,
        skipped_for_budget=skipped,
    )
