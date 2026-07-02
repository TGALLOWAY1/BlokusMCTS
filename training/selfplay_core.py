"""In-process self-play, candidate generation, and candidate evaluation.

This is the keystone wrapper. It does **not** re-implement MCTS, arena play,
TrueSkill, evaluator-weight fitting, or promotion gates — those are imported from
the existing, tested codebase:

* ``scripts.champion_loop`` — challenger selection, snapshot accumulation,
  TrueSkill replay, and the evaluator-weight re-fit that *is* the candidate
  generator (there is no neural net; "learning" = re-fitting the Layer-6 state
  evaluator on accumulated self-play snapshots).
* ``analytics.tournament.arena_runner`` — ``run_experiment`` (in-process arena).
* ``analytics.tournament.gauntlet`` — pooled aggregation + the conservative
  6-gate promotion decision.

The one thing we re-implement is arena execution: champion_loop shells out via
``subprocess``; we call ``run_experiment`` in-process for speed, testability, and
control over the output directory.

**4-agent constraint.** ``RunConfig`` requires exactly 4 uniquely-named agents per
game. Candidate evaluation therefore runs a *battery* of 4-agent arenas that
rotate the two opponent slots (always co-presenting champion + candidate so the
head-to-head promotion gate has data), then pools every game for a single ranked
decision. See :func:`build_eval_arenas`.
"""

from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from analytics.tournament.arena_runner import RunConfig, run_experiment
from analytics.tournament import gauntlet
from analytics.tournament.trueskill_rating import TrueSkillTracker

# Reuse the existing self-improvement helpers verbatim.
from scripts.champion_loop import (
    CHAMPION_ID,
    MCTS_VARIANTS,
    _build_variant_agent_config,
    accumulate_snapshots,
    refit_evaluator_weights,
    select_challengers,
    update_trueskill_from_run,
)
from training import TrainingPaths

CANDIDATE_ID = "candidate"

# Bookkeeping keys attached to a candidate config (learning method, feature-set
# version, training rows, TD loss). They are *metadata*, never engine params, so
# they are stripped before a config is handed to the arena / persisted as champion.
CANDIDATE_META_KEYS = ("learning_method", "feature_set_version", "training_rows", "td_loss")


def strip_candidate_meta(agent_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copy of *agent_cfg* without the candidate-metadata keys.

    Keeps the agent config to the ``{name, type, thinking_time_ms, params}`` shape
    the arena expects so metadata never leaks into engine parameters.
    """
    cfg = copy.deepcopy(agent_cfg)
    for key in CANDIDATE_META_KEYS:
        cfg.pop(key, None)
    return cfg


def candidate_metadata(candidate_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the candidate-metadata subset from a candidate config."""
    return {k: candidate_cfg.get(k) for k in CANDIDATE_META_KEYS if k in candidate_cfg}

# Default snapshot checkpoints (plies) — match champion_loop / gauntlet so the
# accumulated CSV stays schema-compatible with the existing refit pipeline.
_SNAPSHOT_CHECKPOINTS = [8, 16, 24, 32, 40, 48, 56, 64]


@dataclass
class GenerationResult:
    """Outcome of one self-play generation (champion vs challengers)."""

    games_run: int
    snapshot_rows: int
    champion_rating: Dict[str, float]
    challengers: List[str]
    run_dir: str
    elapsed_s: float


@dataclass
class EvaluationResult:
    """Outcome of the candidate-vs-champion evaluation battery."""

    decision: Any  # gauntlet.PromotionDecision
    pooled_summary: Dict[str, Any]
    ranked: List[Dict[str, Any]]
    games: List[Dict[str, Any]]
    total_games: int
    n_seeds: int
    arena_run_dirs: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent-config helpers
# ---------------------------------------------------------------------------

def _with_name(agent_cfg: Dict[str, Any], name: str) -> Dict[str, Any]:
    cfg = copy.deepcopy(agent_cfg)
    cfg["name"] = name
    return cfg


def _baseline(agent_type: str) -> Dict[str, Any]:
    return {"name": agent_type, "type": agent_type, "thinking_time_ms": None, "params": {}}


def _checkpoint_agent(checkpoint: Dict[str, Any], name: Optional[str] = None) -> Dict[str, Any]:
    """Build an opponent agent from a stored checkpoint (champion_loop format)."""
    cfg = copy.deepcopy(checkpoint["params"])
    cfg["name"] = name or checkpoint["id"]
    return cfg


def _apply_thinking_override(agents: List[Dict[str, Any]], thinking_time_ms: Optional[int]) -> None:
    """Force every MCTS agent's thinking budget (used to keep evaluations fast).

    Also forces ``num_workers`` to 1: root parallelization forks worker
    processes on *every move*, and at reduced uniform budgets (tens of
    iterations) the per-move spawn overhead dominates wall-clock (~11 min/game
    measured) while the split trees are *weaker* than one tree with the same
    iteration total. Single-process search is both faster and stronger here,
    so the override never biases an evaluation in the candidate's favour.
    """
    if thinking_time_ms is None:
        return
    for a in agents:
        if a.get("type", "mcts") == "mcts":
            a["thinking_time_ms"] = int(thinking_time_ms)
            params = a.get("params")
            if isinstance(params, dict) and int(params.get("num_workers", 1) or 1) > 1:
                params["num_workers"] = 1


# ---------------------------------------------------------------------------
# Arena execution (in-process)
# ---------------------------------------------------------------------------

def run_arena_inproc(
    agents: List[Dict[str, Any]],
    *,
    paths: TrainingPaths,
    run_label: str,
    num_games: int,
    seed: int,
    enable_snapshots: bool,
    max_turns: int = 2500,
    verbose: bool = False,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """Run one 4-agent arena in-process and return ``run_experiment``'s result.

    ``result`` = ``{"run_id", "run_dir", "summary", "snapshot_rows"}``.

    ``deadline`` (a ``time.monotonic()`` cutoff) is threaded into ``run_experiment``
    so the arena stops between games once the budget is spent — a long battery can
    no longer overrun the caller's wall-clock budget.
    """
    # Strip candidate-metadata keys so they never reach the engine as params.
    agents = [strip_candidate_meta(a) for a in agents]
    config = {
        "agents": agents,
        "num_games": num_games,
        "seed": seed,
        "seat_policy": "randomized",
        "output_root": str(paths.selfplay_runs_dir / run_label),
        "max_turns": max_turns,
        "notes": f"nightly training :: {run_label}",
        "snapshots": {
            "enabled": enable_snapshots,
            "strategy": "fixed_ply",
            "checkpoints": _SNAPSHOT_CHECKPOINTS if enable_snapshots else [],
        },
    }
    run_config = RunConfig.from_dict(config)
    return run_experiment(run_config, verbose=verbose, deadline=deadline)


# ---------------------------------------------------------------------------
# Self-play generation (grows the ML corpus that drives candidate generation)
# ---------------------------------------------------------------------------

def run_generation(
    state: Dict[str, Any],
    paths: TrainingPaths,
    *,
    generation: int,
    games_per_arena: int,
    seed: int,
    rng: random.Random,
    tracker: TrueSkillTracker,
    thinking_time_ms: Optional[int] = None,
    verbose: bool = False,
) -> GenerationResult:
    """One self-play generation: champion vs 3 selected challengers.

    Reuses ``select_challengers`` for the opponent mix, replays results through the
    persistent TrueSkill tracker, and accumulates snapshots into the shared ML
    corpus (``data/champion_snapshots.csv``) that ``refit_evaluator_weights`` later
    consumes. Snapshots are always enabled here — they are the fuel for learning.
    """
    t0 = time.monotonic()
    champion_params = state["champion_params"]
    champion_cfg = _with_name(champion_params, CHAMPION_ID)
    challengers = select_challengers(state, champion_params, rng)
    agents = [champion_cfg] + challengers
    _apply_thinking_override(agents, thinking_time_ms)

    result = run_arena_inproc(
        agents,
        paths=paths,
        run_label=f"gen{generation:04d}",
        num_games=games_per_arena,
        seed=seed,
        enable_snapshots=True,
        verbose=verbose,
    )
    run_dir = result["run_dir"]

    update_trueskill_from_run(tracker, run_dir)
    total_rows = accumulate_snapshots(run_dir)
    state["total_snapshot_rows"] = total_rows

    summary = result.get("summary", {})
    completed = int(summary.get("completed_games", games_per_arena))

    return GenerationResult(
        games_run=completed,
        snapshot_rows=total_rows,
        champion_rating=tracker.get_rating(CHAMPION_ID),
        challengers=[c["name"] for c in challengers],
        run_dir=run_dir,
        elapsed_s=time.monotonic() - t0,
    )


# ---------------------------------------------------------------------------
# Candidate generation (the "learning" step)
# ---------------------------------------------------------------------------

def build_candidate(
    state: Dict[str, Any],
    *,
    learning_mode: str = "regression",
    td_weights_path: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Produce a candidate by learning evaluator weights from self-play data.

    Two learning modes share the same output shape (a champion clone with fresh
    per-phase ``state_eval_phase_weights``) and the same downstream promotion
    gates:

    * ``"regression"`` (default, unchanged) — per-phase linear regression of
      fixed-ply snapshots onto ``final_score`` via :func:`refit_evaluator_weights`.
    * ``"td"`` — load TD-learned weights produced by :mod:`training.td_learning`
      from ``td_weights_path`` (the artifact written by ``python -m
      training.td_learning``) and swap in its ``state_eval_phase_weights``.

    Returns ``(candidate_cfg, refit_result)`` or ``(None, None)`` when the chosen
    mode has insufficient data / is unavailable. ``refit_result`` carries the
    metrics consumed by reporting and lineage.
    """
    if learning_mode == "td":
        return build_td_candidate(state, td_weights_path)
    return build_regression_candidate(state)


def build_regression_candidate(
    state: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Regression candidate (the original behaviour, factored out)."""
    refit = refit_evaluator_weights()
    if not refit:
        return None, None
    candidate_cfg = copy.deepcopy(state["champion_params"])
    candidate_cfg.setdefault("params", {})
    candidate_cfg["params"]["state_eval_phase_weights"] = refit["phase_weights"]
    candidate_cfg["name"] = CANDIDATE_ID
    candidate_cfg["learning_method"] = "regression"
    candidate_cfg["feature_set_version"] = "layer6_se_v1"
    candidate_cfg["training_rows"] = refit.get("rows_used")
    return candidate_cfg, refit


def build_td_candidate(
    state: Dict[str, Any],
    td_weights_path: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Build a candidate from a TD-learned weights artifact.

    Clones the current champion (never mutating ``state['champion_params']``),
    swaps in the TD-learned ``state_eval_phase_weights``, and records clear
    candidate metadata (learning method, feature-set version, training rows,
    TD loss). Returns ``(None, None)`` when the artifact is missing or malformed
    so the caller can fall back to regression / skip evaluation.
    """
    import json
    from pathlib import Path

    if td_weights_path is None:
        from training.td_learning import DEFAULT_OUTPUT
        td_weights_path = str(DEFAULT_OUTPUT)
    path = Path(td_weights_path)
    if not path.exists():
        print(f"[selfplay_core] TD weights artifact not found: {path}")
        return None, None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[selfplay_core] Could not read TD weights artifact: {exc}")
        return None, None

    phase_weights = artifact.get("phase_weights")
    if not phase_weights:
        print("[selfplay_core] TD artifact has no phase_weights; skipping TD candidate")
        return None, None

    metrics = artifact.get("training_metrics", {})
    candidate_cfg = copy.deepcopy(state["champion_params"])
    candidate_cfg.setdefault("params", {})
    candidate_cfg["params"]["state_eval_phase_weights"] = phase_weights
    candidate_cfg["name"] = CANDIDATE_ID
    candidate_cfg["learning_method"] = "temporal_difference"
    candidate_cfg["feature_set_version"] = artifact.get("feature_set_version", "rich_blokus_v1")
    candidate_cfg["training_rows"] = artifact.get("source_rows")
    candidate_cfg["td_loss"] = metrics.get("td_loss")

    # Present a refit-shaped result so existing reporting/lineage code consumes it
    # uniformly (phase_weights + headline metrics).
    refit_like = {
        "phase_weights": phase_weights,
        "single_weights": phase_weights.get("mid"),
        "rows_used": artifact.get("source_rows"),
        "learning_method": "temporal_difference",
        "feature_set_version": candidate_cfg["feature_set_version"],
        "td_loss": metrics.get("td_loss"),
        "td_loss_by_phase": metrics.get("td_loss_by_phase"),
        "mean_abs_td_error": metrics.get("mean_abs_td_error"),
        "rows_by_phase": metrics.get("rows_by_phase"),
        # r2_* kept None so the existing lineage field degrades gracefully.
        "r2_global": None,
    }
    return candidate_cfg, refit_like


def candidate_to_champion_config(
    candidate_cfg: Dict[str, Any],
    refit_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Flatten a candidate into a registry/serving-style wrapper.

    Bridges the field-name divergence: the in-engine path uses
    ``state_eval_phase_weights`` while the registry/serving path
    (``load_candidate_config``) reads a flat ``state_eval_weights``. We emit both
    so either consumer gets calibrated weights.
    """
    params = dict(candidate_cfg.get("params", {}))
    flat: Dict[str, Any] = {
        "type": candidate_cfg.get("type", "mcts"),
        "thinking_time_ms": candidate_cfg.get("thinking_time_ms"),
    }
    flat.update(params)
    if refit_result:
        flat["state_eval_weights"] = refit_result.get("single_weights")
        flat["state_eval_phase_weights"] = refit_result.get("phase_weights")
    return flat


# ---------------------------------------------------------------------------
# Candidate evaluation battery (rotating opponents under the 4-agent rule)
# ---------------------------------------------------------------------------

def build_eval_arenas(
    state: Dict[str, Any],
    candidate_cfg: Dict[str, Any],
    rng: random.Random,
) -> List[List[Dict[str, Any]]]:
    """Build the list of 4-agent arenas for candidate evaluation.

    Each arena is ``[champion, candidate, opp_A, opp_B]`` (4 unique names). The
    opponent slots rotate so the candidate is measured against every opponent
    class while always co-present with the champion:

      1. champion, candidate, heuristic, random            (baselines)
      2. champion, candidate, prev_champion, heuristic      (regression check)
      3. champion, candidate, hist_champ_a, hist_champ_b    (anti-cycling)

    Older checkpoints fall back to distinct MCTS variants when fewer than two
    historical champions exist (cold start), keeping every arena at 4 agents.
    """
    champion_cfg = _with_name(state["champion_params"], CHAMPION_ID)
    candidate_cfg = _with_name(candidate_cfg, CANDIDATE_ID)
    checkpoints = list(state.get("checkpoints", []))

    arenas: List[List[Dict[str, Any]]] = []

    # Arena 1: baselines.
    arenas.append([champion_cfg, candidate_cfg, _baseline("heuristic"), _baseline("random")])

    # Arena 2: previous champion (latest checkpoint) vs candidate.
    if checkpoints:
        prev = _checkpoint_agent(checkpoints[-1], name="prev_champion")
    else:
        prev = _build_variant_agent_config(state["champion_params"], MCTS_VARIANTS[0])
        prev["name"] = "prev_champion"
    arenas.append([champion_cfg, candidate_cfg, prev, _baseline("heuristic")])

    # Arena 3: two historical champions (anti-cycling), or variant fallbacks.
    hist_a = _historical_opponent(state, checkpoints, slot=0, rng=rng, name="hist_champ_a")
    hist_b = _historical_opponent(state, checkpoints, slot=1, rng=rng, name="hist_champ_b")
    arenas.append([champion_cfg, candidate_cfg, hist_a, hist_b])

    return arenas


def _historical_opponent(
    state: Dict[str, Any],
    checkpoints: List[Dict[str, Any]],
    *,
    slot: int,
    rng: random.Random,
    name: str,
) -> Dict[str, Any]:
    """Pick an older checkpoint for the anti-cycling arena, else a variant fallback."""
    # Exclude the most recent checkpoint (that's "prev_champion"); use older ones.
    older = checkpoints[:-1] if len(checkpoints) > 1 else []
    if len(older) > slot:
        return _checkpoint_agent(older[-(slot + 1)], name=name)
    # Fallback: a distinct MCTS variant so the arena still has 4 agents.
    variant = MCTS_VARIANTS[(slot + 1) % len(MCTS_VARIANTS)]
    cfg = _build_variant_agent_config(state["champion_params"], variant)
    cfg["name"] = name
    return cfg


def evaluate_candidate(
    state: Dict[str, Any],
    candidate_cfg: Dict[str, Any],
    paths: TrainingPaths,
    *,
    generation: int,
    seeds: List[int],
    games_per_arena: int,
    rng: random.Random,
    thinking_time_ms: Optional[int] = None,
    min_mu_margin: float = 0.5,
    verbose: bool = False,
) -> EvaluationResult:
    """Run the rotating battery, pool all games, and apply the promotion gates.

    The pooled summary is keyed by agent name, so ``champion`` and ``candidate``
    accumulate games across all matchup contexts and seeds. Promotion is the
    repo's conservative 6-gate decision from :mod:`analytics.tournament.gauntlet`.
    """
    arenas = build_eval_arenas(state, candidate_cfg, rng)
    all_games: List[Dict[str, Any]] = []
    run_dirs: List[str] = []

    for arena_idx, agents in enumerate(arenas):
        _apply_thinking_override(agents, thinking_time_ms)
        for seed in seeds:
            result = run_arena_inproc(
                agents,
                paths=paths,
                run_label=f"eval_gen{generation:04d}_a{arena_idx}_s{seed}",
                num_games=games_per_arena,
                seed=seed,
                enable_snapshots=False,
                verbose=verbose,
            )
            run_dirs.append(result["run_dir"])
            all_games.extend(_load_games(result["run_dir"]))

    # The full agent roster across all arenas (unique names) for aggregation.
    agent_names = sorted({a["name"] for arena in arenas for a in arena})
    thinking_by_agent = {
        a["name"]: (thinking_time_ms if thinking_time_ms is not None else a.get("thinking_time_ms"))
        for arena in arenas
        for a in arena
    }

    pooled = gauntlet.aggregate_summary(
        all_games,
        agent_names=agent_names,
        thinking_time_ms_by_agent=thinking_by_agent,
        seeds=seeds,
        seat_policy="randomized",
        run_config={"phase": "candidate_eval", "generation": generation},
    )
    leaderboard = gauntlet.build_leaderboard(pooled)
    ranked = gauntlet.rank_candidates(leaderboard)
    total_games = int(pooled.get("completed_games", len(all_games)))

    thresholds = gauntlet.PromotionThresholds(
        min_seeds=2,
        min_total_games=40,
        min_mu_margin=min_mu_margin,
        num_agents=4,
    )
    decision = gauntlet.evaluate_promotion(
        ranked,
        pooled,
        n_seeds=len(seeds),
        total_games=total_games,
        thresholds=thresholds,
    )

    return EvaluationResult(
        decision=decision,
        pooled_summary=pooled,
        ranked=ranked,
        games=all_games,
        total_games=total_games,
        n_seeds=len(seeds),
        arena_run_dirs=run_dirs,
    )


def _load_games(run_dir: str) -> List[Dict[str, Any]]:
    import json
    from pathlib import Path

    games: List[Dict[str, Any]] = []
    path = Path(run_dir) / "games.jsonl"
    if not path.exists():
        return games
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                games.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return games
