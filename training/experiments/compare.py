"""Candidate-comparison harness — runs competitors under identical conditions.

    python -m training.experiments.compare \
        --baseline regression --candidate td --games 100 --seeds 10

Runs a battery of 4-agent arenas covering every competitor (regression candidate,
TD candidate, current champion, heuristic baseline, random baseline), pools every
game across all seeds, and reports per-agent wins/losses/draws, average rank, rank
distribution, score margin, TrueSkill, Elo, and win-rate confidence intervals.

Determinism: per-game seeds derive from ``(seed, arena_index, game_index)`` so a
manifest reproduces the same games. Heavy lifting (arena execution, TrueSkill,
score stats) is delegated to the vetted ``analytics.tournament`` code path.
"""

from __future__ import annotations

import argparse
import copy
import itertools
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from analytics.tournament.arena_runner import RunConfig, run_experiment
from analytics.tournament import gauntlet
from analytics.tournament.elo import EloTracker
from training import REPO_ROOT


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class CompareConfig:
    games_per_arena: int = 12
    seeds: List[int] = field(default_factory=lambda: [101, 102])
    thinking_time_ms: Optional[int] = None
    max_turns: int = 2500
    seat_policy: str = "randomized"


@dataclass
class AgentComparison:
    name: str
    games: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    win_rate_ci: Tuple[float, float]
    avg_rank: float
    rank_distribution: Dict[int, int]
    avg_score: float
    avg_score_margin: float
    score_margin_ci: Tuple[float, float]
    trueskill_mu: Optional[float]
    trueskill_sigma: Optional[float]
    elo: float

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d["win_rate_ci"] = list(self.win_rate_ci)
        d["score_margin_ci"] = list(self.score_margin_ci)
        return d


@dataclass
class ComparisonResult:
    total_games: int
    n_seeds: int
    competitors: List[str]
    per_agent: Dict[str, AgentComparison]
    head_to_head: Dict[str, Any] = field(default_factory=dict)
    run_dirs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_games": self.total_games,
            "n_seeds": self.n_seeds,
            "competitors": self.competitors,
            "per_agent": {k: v.to_dict() for k, v in self.per_agent.items()},
            "head_to_head": self.head_to_head,
        }


# ---------------------------------------------------------------------------
# Pure stats over pooled game records
# ---------------------------------------------------------------------------


def per_agent_game_stats(
    games: Sequence[Dict[str, Any]], names: Sequence[str]
) -> Dict[str, Dict[str, Any]]:
    """Compute wins/losses/draws/rank/score stats per agent from game records.

    Pure. A *win* = the agent is among the winners; a *draw* = a shared win
    (``is_tie`` with the agent in the winner set); otherwise a *loss*. Score margin
    is ``own_score − best_opponent_score`` (positive = ahead).
    """
    acc: Dict[str, Dict[str, Any]] = {
        n: {"games": 0, "wins": 0, "losses": 0, "draws": 0,
            "rank_sum": 0, "rank_dist": {}, "score_sum": 0.0, "margins": []}
        for n in names
    }
    for g in games:
        scores = g.get("agent_scores", {})
        ranks = g.get("agent_ranks", {})
        winners = set(g.get("winner_agents", []))
        is_tie = bool(g.get("is_tie", False))
        for n in names:
            if n not in scores:
                continue
            a = acc[n]
            a["games"] += 1
            a["score_sum"] += float(scores[n])
            rank = int(ranks.get(n, 0)) if ranks else 0
            if rank:
                a["rank_sum"] += rank
                a["rank_dist"][rank] = a["rank_dist"].get(rank, 0) + 1
            opp_scores = [float(v) for k, v in scores.items() if k != n]
            if opp_scores:
                a["margins"].append(float(scores[n]) - max(opp_scores))
            if n in winners:
                if is_tie and len(winners) > 1:
                    a["draws"] += 1
                else:
                    a["wins"] += 1
            else:
                a["losses"] += 1
    return acc


def _mean_ci(values: Sequence[float]) -> Tuple[float, Tuple[float, float]]:
    n = len(values)
    if n == 0:
        return 0.0, (0.0, 0.0)
    mean = sum(values) / n
    if n < 2:
        return mean, (mean, mean)
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    half = 1.96 * math.sqrt(var / n)
    return mean, (mean - half, mean + half)


# ---------------------------------------------------------------------------
# Arena construction + execution
# ---------------------------------------------------------------------------


def build_arenas(competitor_configs: Dict[str, Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Build 4-agent arenas covering every competitor.

    With exactly 4 competitors → one arena. With >4 → every 4-combination (each
    competitor appears in many arenas, all co-present). With <4 → pad with baseline
    agents so the arena is valid.
    """
    names = list(competitor_configs.keys())
    cfgs = competitor_configs
    if len(names) < 2:
        raise ValueError("need at least 2 competitors")
    if len(names) < 4:
        padded = dict(cfgs)
        pad_pool = [("_pad_heuristic", {"type": "heuristic"}),
                    ("_pad_random", {"type": "random"}),
                    ("_pad_heuristic2", {"type": "heuristic"})]
        i = 0
        while len(padded) < 4:
            pn, pc = pad_pool[i % len(pad_pool)]
            pn = f"{pn}_{i}"
            padded[pn] = {**pc, "name": pn}
            i += 1
        return [[{**v, "name": k} for k, v in padded.items()]]
    arenas: List[List[Dict[str, Any]]] = []
    for combo in itertools.combinations(names, 4):
        arenas.append([{**cfgs[n], "name": n} for n in combo])
    return arenas


def _strip_meta(cfg: Dict[str, Any]) -> Dict[str, Any]:
    from training.selfplay_core import strip_candidate_meta
    return strip_candidate_meta(cfg)


def run_comparison(
    competitor_configs: Dict[str, Dict[str, Any]],
    config: CompareConfig,
    *,
    output_dir: Path | str,
    baseline: Optional[str] = None,
    candidate: Optional[str] = None,
    verbose: bool = False,
) -> ComparisonResult:
    """Run the full battery and return pooled per-agent comparison metrics."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    names = list(competitor_configs.keys())
    arenas = build_arenas(competitor_configs)

    all_games: List[Dict[str, Any]] = []
    run_dirs: List[str] = []
    for arena_idx, agents in enumerate(arenas):
        agents = [_strip_meta(a) for a in agents]
        for seed in config.seeds:
            run_cfg = RunConfig.from_dict({
                "agents": agents,
                "num_games": config.games_per_arena,
                "seed": int(seed) + arena_idx * 100003,
                "seat_policy": config.seat_policy,
                "output_root": str(output_dir / f"a{arena_idx}_s{seed}"),
                "max_turns": config.max_turns,
                "notes": f"experiment compare :: arena {arena_idx} seed {seed}",
                "snapshots": {"enabled": False, "strategy": "fixed_ply", "checkpoints": []},
            })
            result = run_experiment(run_cfg, verbose=verbose)
            run_dirs.append(result["run_dir"])
            all_games.extend(_load_games(result["run_dir"]))

    return aggregate_comparison(
        all_games, names, config,
        baseline=baseline, candidate=candidate, run_dirs=run_dirs,
        competitor_configs=competitor_configs,
    )


def aggregate_comparison(
    games: List[Dict[str, Any]],
    names: Sequence[str],
    config: CompareConfig,
    *,
    baseline: Optional[str] = None,
    candidate: Optional[str] = None,
    run_dirs: Optional[List[str]] = None,
    competitor_configs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> ComparisonResult:
    """Pool games → per-agent comparison rows + head-to-head. Pure-ish (no arena)."""
    names = list(names)
    thinking_by_agent = {n: config.thinking_time_ms for n in names}
    pooled = gauntlet.aggregate_summary(
        games, agent_names=names, thinking_time_ms_by_agent=thinking_by_agent,
        seeds=config.seeds, seat_policy=config.seat_policy,
        run_config={"phase": "experiment_compare"},
    )
    leaderboard = {r["name"]: r for r in gauntlet.build_leaderboard(pooled)}

    elo = EloTracker()
    for g in games:
        sc = g.get("agent_scores", {})
        if sc:
            elo.update_game(sc)

    raw = per_agent_game_stats(games, names)
    per_agent: Dict[str, AgentComparison] = {}
    for n in names:
        a = raw[n]
        lb = leaderboard.get(n, {})
        margin_mean, margin_ci = _mean_ci(a["margins"])
        g = max(a["games"], 1)
        per_agent[n] = AgentComparison(
            name=n,
            games=a["games"],
            wins=a["wins"],
            losses=a["losses"],
            draws=a["draws"],
            win_rate=float(lb.get("win_rate", a["wins"] / g)),
            win_rate_ci=(float(lb.get("win_rate_ci_lower", 0.0)),
                         float(lb.get("win_rate_ci_upper", 0.0))),
            avg_rank=(a["rank_sum"] / g) if a["rank_sum"] else 0.0,
            rank_distribution=dict(sorted(a["rank_dist"].items())),
            avg_score=a["score_sum"] / g,
            avg_score_margin=margin_mean,
            score_margin_ci=margin_ci,
            trueskill_mu=lb.get("trueskill_mu"),
            trueskill_sigma=lb.get("trueskill_sigma"),
            elo=float(elo.get_rating(n)),
        )

    head_to_head: Dict[str, Any] = {}
    if baseline and candidate and baseline in names and candidate in names:
        h2h = gauntlet.pairwise_record(pooled, candidate, baseline)
        cand = per_agent[candidate]
        base = per_agent[baseline]
        head_to_head = {
            "baseline": baseline,
            "candidate": candidate,
            "candidate_wins": h2h["a_wins"],
            "baseline_wins": h2h["b_wins"],
            "ties": h2h["tie"],
            "candidate_win_rate": cand.win_rate,
            "baseline_win_rate": base.win_rate,
            "candidate_avg_rank": cand.avg_rank,
            "baseline_avg_rank": base.avg_rank,
            "trueskill_mu_delta": (
                (cand.trueskill_mu - base.trueskill_mu)
                if cand.trueskill_mu is not None and base.trueskill_mu is not None else None
            ),
            "elo_delta": cand.elo - base.elo,
            "recommendation": _recommend(cand, base),
        }

    total_games = int(pooled.get("completed_games", len(games)))
    return ComparisonResult(
        total_games=total_games,
        n_seeds=len(config.seeds),
        competitors=names,
        per_agent=per_agent,
        head_to_head=head_to_head,
        run_dirs=run_dirs or [],
    )


def _recommend(cand: AgentComparison, base: AgentComparison) -> str:
    """Opinionated, evidence-based verdict from the head-to-head."""
    mu_delta = None
    if cand.trueskill_mu is not None and base.trueskill_mu is not None:
        mu_delta = cand.trueskill_mu - base.trueskill_mu
    # CI overlap on win rate is the honest significance check.
    overlap = not (cand.win_rate_ci[0] > base.win_rate_ci[1]
                   or base.win_rate_ci[0] > cand.win_rate_ci[1])
    if mu_delta is not None and mu_delta >= 0.5 and not overlap:
        return ("ADOPT candidate — higher TrueSkill (Δμ "
                f"{mu_delta:+.2f}) and non-overlapping win-rate CIs.")
    if mu_delta is not None and mu_delta <= -0.5 and not overlap:
        return ("KEEP baseline — candidate is measurably weaker (Δμ "
                f"{mu_delta:+.2f}).")
    return ("INCONCLUSIVE — differences within noise (win-rate CIs overlap); "
            "collect more games/seeds before deciding.")


def _load_games(run_dir: str) -> List[Dict[str, Any]]:
    import json

    games: List[Dict[str, Any]] = []
    path = Path(run_dir) / "games.jsonl"
    if not path.exists():
        return games
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    games.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return games


# ---------------------------------------------------------------------------
# Competitor construction
# ---------------------------------------------------------------------------


def _champion_params() -> Dict[str, Any]:
    """Load the current champion's agent params (state, else seed config)."""
    from training import TrainingPaths, state_store

    paths = TrainingPaths.default()
    try:
        state = state_store.load_latest(paths)
        if state.get("champion_params"):
            return copy.deepcopy(state["champion_params"])
    except Exception:  # noqa: BLE001
        pass
    from training.nightly_run import _seed_champion_params_from_config
    return _seed_champion_params_from_config()


def build_competitors(
    *,
    include_regression: bool = True,
    include_td: bool = True,
    td_weights_path: Optional[str] = None,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str], Dict[str, Any]]:
    """Assemble the competitor roster. Returns (configs, learning_modes, artifacts).

    Always includes champion + heuristic + random. Adds a regression candidate
    (re-fit from snapshots) and/or a TD candidate (from a TD artifact) when
    available. Candidates are champion clones with swapped evaluator weights, so
    any strength delta is attributable to the learned weights alone.
    """
    from training import selfplay_core as sc

    champ = _champion_params()
    state = {"champion_params": copy.deepcopy(champ)}
    configs: Dict[str, Dict[str, Any]] = {
        "champion": {**copy.deepcopy(champ), "name": "champion"},
        "heuristic": {"type": "heuristic", "name": "heuristic"},
        "random": {"type": "random", "name": "random"},
    }
    learning_modes: Dict[str, str] = {"champion": "current"}
    artifacts: Dict[str, Any] = {}

    if include_regression:
        cand, refit = sc.build_regression_candidate(state)
        if cand is not None:
            configs["regression"] = {**sc.strip_candidate_meta(cand), "name": "regression"}
            learning_modes["regression"] = "regression"
            artifacts["regression_rows"] = (refit or {}).get("rows_used")

    if include_td:
        cand, refit = sc.build_td_candidate(state, td_weights_path)
        if cand is not None:
            configs["td"] = {**sc.strip_candidate_meta(cand), "name": "td"}
            learning_modes["td"] = "temporal_difference"
            artifacts["td_weights_path"] = td_weights_path or "training/state/td_evaluator_weights.json"
            artifacts["td_loss"] = (refit or {}).get("td_loss")
            artifacts["td_rows"] = (refit or {}).get("rows_used")

    return configs, learning_modes, artifacts


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------


def compare_learning_modes(
    *,
    baseline: str = "regression",
    candidate: str = "td",
    games_per_arena: int = 12,
    seeds: Sequence[int],
    thinking_time_ms: Optional[int] = None,
    td_weights_path: Optional[str] = None,
    output_root: Optional[Path | str] = None,
    description: str = "TD vs regression candidate comparison",
    verbose: bool = False,
) -> Dict[str, Any]:
    """Top-level: build competitors, run the battery, write manifest + report.

    Returns a bundle ``{manifest, result, manifest_path, report_path}``.
    """
    from training.experiments import manifest as mf
    from training.experiments import report as rp

    seeds = list(seeds)
    configs, learning_modes, artifacts = build_competitors(
        include_regression=True, include_td=True, td_weights_path=td_weights_path
    )
    config = CompareConfig(
        games_per_arena=games_per_arena, seeds=seeds, thinking_time_ms=thinking_time_ms,
    )

    manifest = mf.build_manifest(
        description=description,
        competitor_configs={k: v for k, v in configs.items()},
        seeds=seeds, games_per_arena=games_per_arena, thinking_time_ms=thinking_time_ms,
        learning_modes=learning_modes, artifacts=artifacts,
        code_version=_git_short_sha(),
    )

    out_root = Path(output_root) if output_root else (
        REPO_ROOT / "training" / "reports" / "experiments" / manifest.experiment_id
    )
    out_root.mkdir(parents=True, exist_ok=True)

    result = run_comparison(
        configs, config, output_dir=out_root / "runs",
        baseline=baseline if baseline in configs else None,
        candidate=candidate if candidate in configs else None,
        verbose=verbose,
    )

    manifest_path = mf.save_manifest(manifest, out_root / "manifest.json")
    # Persist the machine-readable result next to the manifest so the nightly
    # status report can surface the most recent comparison without re-running.
    import json as _json
    (out_root / "result.json").write_text(
        _json.dumps({"experiment_id": manifest.experiment_id, "date": manifest.date,
                     "baseline": baseline, "candidate": candidate,
                     **result.to_dict()}, indent=2),
        encoding="utf-8",
    )
    report_md = rp.render_experiment_report(manifest, result)
    report_path = out_root / "report.md"
    report_path.write_text(report_md, encoding="utf-8")
    # Also drop a copy in the flat reports dir for easy discovery.
    flat = REPO_ROOT / "training" / "reports" / f"experiment_{manifest.experiment_id}.md"
    flat.write_text(report_md, encoding="utf-8")

    return {"manifest": manifest, "result": result,
            "manifest_path": str(manifest_path), "report_path": str(report_path)}


def _git_short_sha() -> Optional[str]:
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Compare learning modes under identical conditions.")
    p.add_argument("--baseline", default="regression")
    p.add_argument("--candidate", default="td")
    p.add_argument("--games", type=int, default=12, help="Games per arena per seed.")
    p.add_argument("--seeds", type=int, default=4,
                   help="Number of seeds (a contiguous block from --seed-start).")
    p.add_argument("--seed-start", type=int, default=101)
    p.add_argument("--thinking-time-ms", type=int, default=None)
    p.add_argument("--td-weights-path", default=None)
    p.add_argument("--output-root", default=None)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    bundle = compare_learning_modes(
        baseline=args.baseline, candidate=args.candidate,
        games_per_arena=args.games, seeds=seeds,
        thinking_time_ms=args.thinking_time_ms, td_weights_path=args.td_weights_path,
        output_root=args.output_root, verbose=args.verbose,
    )
    print(f"[compare] manifest: {bundle['manifest_path']}")
    print(f"[compare] report:   {bundle['report_path']}")
    h2h = bundle["result"].head_to_head
    if h2h:
        print(f"[compare] {h2h.get('recommendation')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
