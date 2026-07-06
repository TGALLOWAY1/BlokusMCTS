"""Nightly training entry point — the durable, resumable orchestrator.

    python -m training.nightly_run --hours 5 --resume training/state/latest.json

The cardinal guarantee: **resume from disk, never start over.** On every run we
load ``latest.json`` + ``champion.json`` + ``ratings.sqlite``, run as many
self-play generations as the wall-clock budget allows (writing state atomically
after *each* generation), build and evaluate a candidate, promote it if the
conservative gates pass, append to the never-overwritten rating timeline, and
regenerate the reports. A crash leaves the last atomic state intact and is
reported by the workflow's always-run email step; the next night picks up where
this one stopped.

Promotion is **internal only** by default: it updates ``training/state/`` but does
*not* touch the deployed ``data/champion_registry.json`` unless ``--promote-registry``
is passed (preserving the existing "humans promote the live champion" safety rule).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.tournament.elo import EloTracker
from analytics.tournament.trueskill_rating import TrueSkillTracker
from scripts.champion_loop import CHAMPION_ID, build_tracker, persist_tracker
from training import REPO_ROOT, TrainingPaths
from training import human_estimate, ratings_db, state_store
from training import diagnostics, status_report
from training import selfplay_core as sc
from training import approaches as ap_pkg
from training.approaches.base import (
    ApproachContext,
    validate_candidate_artifact,
    write_candidate_artifact,
)
from training.evaluation import (
    EVAL_CONFIRM_TOTAL_GAMES,
    build_benchmark_pool,
    confirm_winner as ht_confirm_winner,
    evaluate_candidates,
    select_winner,
    summarize_trajectory,
)
from training.evaluation import report as approach_report
from training.evaluation.promotion_gate import GateThresholds, evaluate_gate
from training.evaluation.sequential import (
    DEFAULT_ELO1 as SPRT_DEFAULT_ELO1,
    DEFAULT_MAX_GAMES as SPRT_DEFAULT_MAX_GAMES,
    DEFAULT_MIN_GAMES as SPRT_DEFAULT_MIN_GAMES,
    evaluate_candidates_sequential,
)

# Fraction of the wall-clock budget spent on self-play generations; the remainder
# is reserved for candidate evaluation, reports, commit, and email.
_GENERATION_BUDGET_FRACTION = 0.7
# Safety multiplier on the rolling per-generation duration estimate.
_GEN_ESTIMATE_SAFETY = 1.25

SEED_CHAMPION_CONFIG = REPO_ROOT / "config" / "key_findings_best_params.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_run_id() -> str:
    return _utc_now().strftime("%Y%m%dT%H%M%SZ")


def _seed_champion_params_from_config() -> Dict[str, Any]:
    """Cold start: build champion_params (champion_loop shape) from the seed config.

    Splits the flat ``config/key_findings_best_params.json`` wrapper into the
    ``{type, thinking_time_ms, params}`` shape the reused helpers expect.
    """
    payload = json.loads(SEED_CHAMPION_CONFIG.read_text(encoding="utf-8"))
    metadata_keys = {"description", "champion_version", "thinking_time_ms", "type", "name"}
    params = {k: v for k, v in payload.items() if k not in metadata_keys and not k.startswith("_")}
    return {
        "type": str(payload.get("type", "mcts")),
        "thinking_time_ms": int(payload.get("thinking_time_ms", 500)),
        "params": params,
    }


def _ensure_cold_start(state: Dict[str, Any], champion: Dict[str, Any]) -> None:
    """Populate champion_params on the very first run (mutates in place)."""
    if not state.get("champion_params"):
        seeded = _seed_champion_params_from_config()
        state["champion_params"] = seeded
        if not champion.get("params"):
            champion["params"] = seeded
            champion["flat_config"] = json.loads(SEED_CHAMPION_CONFIG.read_text(encoding="utf-8"))
            champion["lineage"] = [
                {
                    "version": "gen0",
                    "promoted_at": _utc_now().isoformat(),
                    "reason": "Cold-start seed from config/key_findings_best_params.json",
                }
            ]


def _seed_elo_tracker(latest: Dict[str, Dict[str, Any]]) -> EloTracker:
    """Build an EloTracker seeded from the SQLite timeline (Elo has no serializer)."""
    elo = EloTracker()
    for agent, r in latest.items():
        elo.ratings[agent] = float(r["elo"])
        elo.games_played[agent] = int(r.get("games_played", 0))
    return elo


def _seed_trueskill_tracker(
    state: Dict[str, Any], latest: Dict[str, Dict[str, Any]]
) -> TrueSkillTracker:
    """Build the TrueSkill tracker, preferring in-state ratings, backfilling from DB.

    ``state['trueskill_ratings']`` is the in-loop authority (kept by champion_loop
    helpers); the DB row backfills any agent missing from state on a cold restart.
    """
    tracker = build_tracker(state)  # seeds from state['trueskill_ratings']
    for agent, r in latest.items():
        if agent not in tracker.agent_ids:
            tracker.load_ratings({agent: r})
    return tracker


def _replay_games_through_elo(
    elo: EloTracker,
    games: List[Dict[str, Any]],
    *,
    capture_agent: Optional[str] = None,
    start_game_number: int = 0,
) -> List[tuple]:
    """Replay an in-memory list of game records through Elo.

    When ``capture_agent`` is set, returns an ordered ``[(game_number, elo), ...]``
    list — that agent's Elo recomputed after each game — so the caller can persist
    a per-game trajectory. ``game_number`` is 1-based, continuing from
    ``start_game_number`` (the cumulative count across the whole history).
    """
    samples: List[tuple] = []
    n = start_game_number
    for record in games:
        agent_scores = record.get("agent_scores", {})
        if not agent_scores:
            continue
        elo.update_game(agent_scores)
        if capture_agent is not None:
            n += 1
            samples.append((n, float(elo.get_rating(capture_agent))))
    return samples


# ---------------------------------------------------------------------------
# Core run
# ---------------------------------------------------------------------------

def run(
    *,
    paths: TrainingPaths,
    hours: float,
    seeds: List[int],
    games_per_arena: int,
    thinking_time_ms: Optional[int],
    promote_registry: bool,
    dry_run: bool,
    verbose: bool,
    learning_mode: str = "regression",
    td_weights_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute one nightly run end-to-end. Returns the updated latest state."""
    paths.ensure_dirs()
    run_id = _new_run_id()
    started = time.monotonic()
    deadline = started + hours * 3600.0

    state = state_store.load_latest(paths)
    champion = state_store.load_champion(paths)
    _ensure_cold_start(state, champion)
    state["run_id"] = run_id

    conn = ratings_db.connect(paths.ratings_db)
    latest_db = ratings_db.latest_ratings(conn)
    elo = _seed_elo_tracker(latest_db)
    tracker = _seed_trueskill_tracker(state, latest_db)
    # Cumulative champion game index for the per-game Elo trajectory (the plot's
    # x-axis). Continues across runs so the curve is one monotonic timeline.
    champ_game_no = ratings_db.max_game_number(conn, agent=CHAMPION_ID)

    if dry_run:
        print(f"[nightly] DRY RUN run_id={run_id} hours={hours} seeds={seeds} "
              f"games_per_arena={games_per_arena} promote_registry={promote_registry}")
        print(f"[nightly] champion params: {json.dumps(state['champion_params'], indent=2)[:400]}...")
        return state

    games_this_run = 0
    gens_this_run = 0
    rolling_gen_s: Optional[float] = None
    gen_deadline = started + hours * 3600.0 * _GENERATION_BUDGET_FRACTION
    start_generation = int(state.get("generation", 0))

    # --- Self-play generation loop (time-budgeted, atomic per-generation) -----
    while True:
        now = time.monotonic()
        est = (rolling_gen_s or 0.0) * _GEN_ESTIMATE_SAFETY
        if gens_this_run >= 1 and now + est >= gen_deadline:
            break
        if gens_this_run == 0 and now >= gen_deadline:
            # Always attempt at least one generation unless already out of budget.
            if now >= deadline:
                break

        generation = start_generation + gens_this_run + 1
        rng = random.Random(generation * 997 + 42)
        seed = generation * 7919
        try:
            gen_res = sc.run_generation(
                state, paths,
                generation=generation,
                games_per_arena=games_per_arena,
                seed=seed,
                rng=rng,
                tracker=tracker,
                thinking_time_ms=thinking_time_ms,
                verbose=verbose,
            )
        except Exception as exc:  # noqa: BLE001 — preserve partial progress
            _record_error(paths, state, generation, exc)
            raise

        games_this_run += gen_res.games_run
        gens_this_run += 1
        rolling_gen_s = gen_res.elapsed_s if rolling_gen_s is None else (
            0.5 * rolling_gen_s + 0.5 * gen_res.elapsed_s
        )

        # Recompute a FRESH Elo from this generation's games and persist it +
        # a durable DB timeline row *every generation*. This is the crux of the
        # "repeated Elo" fix: previously Elo and the ratings DB were only written
        # in the post-loop finalisation block, which a time-killed CI job rarely
        # reached — so latest.json's `elo` and the committed DB froze at the first
        # run's value while generation/total_games kept advancing. Now each
        # atomically-persisted generation also carries a fresh, recomputed Elo.
        game_samples = _replay_run_dir_games(
            elo, gen_res.run_dir,
            capture_agent=CHAMPION_ID, start_game_number=champ_game_no,
        )
        if game_samples:
            champ_game_no = game_samples[-1][0]
        champ_elo_gen = float(elo.get_rating(CHAMPION_ID))

        # Persist *after every generation* (partial-state durability).
        state["generation"] = generation
        state["total_games"] = int(state.get("total_games", 0)) + gen_res.games_run
        state["games_today"] = games_this_run
        state["elo"] = champ_elo_gen
        persist_tracker(tracker, state)
        champ_rating = gen_res.champion_rating
        state["trueskill_mu"] = champ_rating["mu"]
        state["trueskill_sigma"] = champ_rating["sigma"]
        state_store.save_latest(paths, state)
        ratings_db.record_run(
            conn,
            run_id=run_id,
            timestamp=_utc_now().isoformat(),
            generation=generation,
            agent_rows=_build_agent_rows(elo, tracker),
            run_summary=ratings_db.RunSummaryRow(
                generation=generation,
                games_today=games_this_run,
                total_games=int(state["total_games"]),
                champion_elo=champ_elo_gen,
                champion_mu=champ_rating["mu"],
                champion_sigma=champ_rating["sigma"],
                promoted=False,
                days_trained=int(state.get("days_trained", 0)) + 1,
            ),
        )
        # Durable per-game Elo trajectory (one row per game) for the email plot.
        ratings_db.record_game_elos(
            conn,
            run_id=run_id,
            timestamp=_utc_now().isoformat(),
            generation=generation,
            samples=game_samples,
            agent=CHAMPION_ID,
        )
        state_store.append_jsonl(paths.history_jsonl, {
            "schema_version": state_store.HISTORY_SCHEMA_VERSION,
            "kind": state_store.HISTORY_KIND_LEGACY,
            "generation": generation,
            "run_id": run_id,
            "timestamp": _utc_now().isoformat(),
            "games": gen_res.games_run,
            "challengers": gen_res.challengers,
            "champion_elo": champ_elo_gen,
            "champion_mu": champ_rating["mu"],
            "champion_sigma": champ_rating["sigma"],
            "champion_conservative": champ_rating["conservative"],
            "champion_games_played": champ_rating["games_played"],
            "total_snapshot_rows": gen_res.snapshot_rows,
            "run_dir": gen_res.run_dir,
        })
        if verbose:
            print(f"[nightly] gen {generation}: {gen_res.games_run} games, "
                  f"elo={champ_elo_gen:.1f} mu={champ_rating['mu']:.2f} "
                  f"sigma={champ_rating['sigma']:.2f}, {gen_res.elapsed_s:.1f}s")

    # --- Candidate generation + evaluation -----------------------------------
    promoted = False
    eval_result: Optional[sc.EvaluationResult] = None
    candidate_cfg, refit = sc.build_candidate(
        state, learning_mode=learning_mode, td_weights_path=td_weights_path
    )
    # TD mode falls back to regression if no TD artifact is available yet, so a
    # cold start (no trajectories collected) still produces a candidate.
    if candidate_cfg is None and learning_mode == "td":
        print("[nightly] TD candidate unavailable; falling back to regression candidate.")
        candidate_cfg, refit = sc.build_regression_candidate(state)
    if candidate_cfg is not None and time.monotonic() < deadline:
        eval_rng = random.Random(start_generation * 31 + 7)
        eval_result = sc.evaluate_candidate(
            state, candidate_cfg, paths,
            generation=state["generation"],
            seeds=seeds,
            games_per_arena=games_per_arena,
            rng=eval_rng,
            thinking_time_ms=thinking_time_ms,
            verbose=verbose,
        )
        eval_samples = _replay_games_through_elo(
            elo, eval_result.games,
            capture_agent=CHAMPION_ID, start_game_number=champ_game_no,
        )
        if eval_samples:
            champ_game_no = eval_samples[-1][0]
            ratings_db.record_game_elos(
                conn,
                run_id=run_id,
                timestamp=_utc_now().isoformat(),
                generation=int(state["generation"]),
                samples=eval_samples,
                agent=CHAMPION_ID,
            )
        for record in eval_result.games:
            scores = record.get("agent_scores", {})
            if scores:
                tracker.update_game(scores)
        games_this_run += eval_result.total_games
        state["total_games"] = int(state.get("total_games", 0)) + eval_result.total_games

        if eval_result.decision.promote and eval_result.decision.champion == sc.CANDIDATE_ID:
            promoted = _promote(
                state, champion, candidate_cfg, refit, eval_result, paths,
                tracker=tracker, elo=elo, promote_registry=promote_registry,
            )

    # NOTE: generation Elo is now replayed and recorded incrementally inside the
    # generation loop above (durable per-generation), so we do NOT re-replay the
    # whole run's generation games here — that would double-count them.

    # --- Ratings + human estimate + state finalisation -----------------------
    champ_ts = tracker.get_rating(CHAMPION_ID)
    champ_elo = elo.get_rating(CHAMPION_ID)
    state["elo"] = float(champ_elo)
    state["trueskill_mu"] = champ_ts["mu"]
    state["trueskill_sigma"] = champ_ts["sigma"]
    state["games_today"] = games_this_run
    state["days_trained"] = int(state.get("days_trained", 0)) + 1
    state["last_error"] = None

    # Persist this run's evaluation snapshot so the (separate-process) email can
    # render the Match Breakdown without re-running anything.
    state["last_eval"] = _build_last_eval(
        eval_result, seeds, promoted, run_id,
        refit=refit, candidate_cfg=candidate_cfg, learning_mode=learning_mode,
    )

    # Durable learning history: pair this run's training loss with the candidate's
    # measured strength so the loss→strength correlation can be computed over time
    # (the headline "is optimising TD loss meaningful?" diagnostic). Best-effort.
    _record_learning_history(
        paths, run_id, eval_result, refit, candidate_cfg, learning_mode, promoted
    )

    # Append a final post-evaluation timeline row *only when evaluation actually
    # ran* (it folds the champion-vs-candidate eval games into Elo and records the
    # promotion flag). When no eval ran, the per-generation rows above are already
    # the durable record and we avoid a duplicate.
    if eval_result is not None and eval_result.total_games > 0:
        agent_rows = _build_agent_rows(elo, tracker)
        ratings_db.record_run(
            conn,
            run_id=run_id,
            timestamp=_utc_now().isoformat(),
            generation=int(state["generation"]),
            agent_rows=agent_rows,
            run_summary=ratings_db.RunSummaryRow(
                generation=int(state["generation"]),
                games_today=games_this_run,
                total_games=int(state["total_games"]),
                champion_elo=float(champ_elo),
                champion_mu=champ_ts["mu"],
                champion_sigma=champ_ts["sigma"],
                promoted=promoted,
                days_trained=int(state["days_trained"]),
            ),
        )

    # Human-strength estimate from the (now-updated) Elo timeline.
    series = ratings_db.champion_elo_series(conn)
    est = human_estimate.summarize(
        float(champ_elo), series, target=float(state.get("human_target_elo", 1700))
    )
    state["estimated_games_to_target"] = est.get("games_remaining")
    state["estimated_days_to_target"] = est.get("days_remaining")
    state["estimate_confidence"] = est.get("confidence")
    state["champion"] = {
        "name": CHAMPION_ID,
        "version": champion.get("version", state["champion"].get("version", "gen0")),
        "config_ref": "state/champion.json",
    }
    # Keep champion.json's current rating fresh and persist it every run (even when
    # no promotion happened, so a cold start always materialises the file).
    champion.setdefault("rating", {})["elo"] = float(champ_elo)
    champion["rating"]["trueskill_mu"] = champ_ts["mu"]
    champion["rating"]["trueskill_sigma"] = champ_ts["sigma"]
    champion["rating"]["conservative"] = champ_ts["conservative"]
    state_store.save_champion(paths, champion)
    state_store.save_latest(paths, state)

    # --- Reports -------------------------------------------------------------
    findings = diagnostics.write_diagnosis(paths, conn, state)
    status_report.write_status(paths, conn, state, findings=findings, eval_result=eval_result)

    conn.close()
    print(f"[nightly] DONE run_id={run_id} generations={gens_this_run} "
          f"games_this_run={games_this_run} elo={champ_elo:.1f} promoted={promoted}")
    return state


def _replay_run_dir_games(
    elo: EloTracker,
    run_dir: str,
    *,
    capture_agent: Optional[str] = None,
    start_game_number: int = 0,
) -> List[tuple]:
    """Replay every game in one arena ``run_dir``'s games.jsonl through Elo.

    Called once per generation (on that generation's fresh run_dir), so each
    game is counted exactly once across the whole run. When ``capture_agent`` is
    set, returns the per-game ``[(game_number, elo), ...]`` trajectory for that
    agent (see :func:`_replay_games_through_elo`).
    """
    from pathlib import Path

    gp = Path(run_dir) / "games.jsonl"
    if not gp.exists():
        return []
    records: List[Dict[str, Any]] = []
    with gp.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return _replay_games_through_elo(
        elo, records, capture_agent=capture_agent, start_game_number=start_game_number
    )


def _build_last_eval(
    eval_result: Optional[sc.EvaluationResult],
    seeds: List[int],
    promoted: bool,
    run_id: str,
    *,
    refit: Optional[Dict[str, Any]] = None,
    candidate_cfg: Optional[Dict[str, Any]] = None,
    learning_mode: str = "regression",
) -> Optional[Dict[str, Any]]:
    """Summarise the candidate evaluation for the email's Match Breakdown.

    Returns ``None`` when no evaluation ran this cycle (e.g. the evaluator could
    not re-fit yet or the time budget was exhausted) so the email can say so
    plainly instead of implying a fresh head-to-head happened. When an evaluation
    *did* run, also carries the learning method + TD metrics so the email and
    status report can distinguish regression from temporal-difference learning.
    """
    if eval_result is None:
        return None
    pooled = getattr(eval_result, "pooled_summary", {}) or {}
    win_stats = pooled.get("win_stats", {})
    baselines: List[Dict[str, Any]] = []
    for name in ("candidate", "champion", "heuristic", "random", "prev_champion"):
        ws = win_stats.get(name)
        if ws:
            baselines.append({
                "agent": name,
                "win_rate": float(ws.get("win_rate", 0.0)),
                "games": int(ws.get("games_played", 0)),
            })

    meta = sc.candidate_metadata(candidate_cfg) if candidate_cfg else {}
    refit = refit or {}
    learning = {
        "learning_method": meta.get("learning_method")
        or refit.get("learning_method")
        or ("temporal_difference" if learning_mode == "td" else "regression"),
        "feature_set_version": meta.get("feature_set_version")
        or refit.get("feature_set_version"),
        "training_rows": meta.get("training_rows") or refit.get("rows_used"),
        "td_loss": meta.get("td_loss") if meta.get("td_loss") is not None else refit.get("td_loss"),
        "mean_abs_td_error": refit.get("mean_abs_td_error"),
        "td_loss_by_phase": refit.get("td_loss_by_phase"),
        "rows_by_phase": refit.get("rows_by_phase"),
        "r2_global": refit.get("r2_global"),
    }

    # Promotion-failure detail (runner-up, head-to-head, margin) for the report.
    decision = eval_result.decision
    cand_row = next((r for r in eval_result.ranked if r.get("name") == sc.CANDIDATE_ID), {})
    failure: Optional[Dict[str, Any]] = None
    if not (getattr(decision, "promote", False) and getattr(decision, "champion", None) == sc.CANDIDATE_ID):
        runner_up = eval_result.ranked[0].get("name") if eval_result.ranked else None
        cand_ws = win_stats.get(sc.CANDIDATE_ID, {})
        champ_ws = win_stats.get("champion", {})
        failed_criteria = [c.get("name") for c in getattr(decision, "criteria", []) or []
                           if not c.get("passed")]
        failure = {
            "failed_gate": failed_criteria[0] if failed_criteria else None,
            "failed_gates": failed_criteria,
            "summary": getattr(decision, "summary_line", None),
            "runner_up": runner_up,
            "candidate_win_rate": float(cand_ws.get("win_rate", 0.0)),
            "champion_win_rate": float(champ_ws.get("win_rate", 0.0)),
            "trueskill_mu_margin": cand_row.get("trueskill_mu_margin"),
            "candidate_mu": cand_row.get("trueskill_mu"),
            "n_games": int(eval_result.total_games),
            "seeds": list(seeds),
        }

    return {
        "run_id": run_id,
        "total_games": int(eval_result.total_games),
        "n_seeds": int(eval_result.n_seeds),
        "seeds": list(seeds),
        "promoted": bool(promoted),
        "baselines": baselines,
        "learning": learning,
        "promotion_failure": failure,
    }


def _record_learning_history(
    paths: TrainingPaths,
    run_id: str,
    eval_result: Optional[sc.EvaluationResult],
    refit: Optional[Dict[str, Any]],
    candidate_cfg: Optional[Dict[str, Any]],
    learning_mode: str,
    promoted: bool,
) -> None:
    """Append one training→strength observation to learning_history.jsonl.

    Never raises: observability must not jeopardise a training run.
    """
    if eval_result is None or candidate_cfg is None:
        return
    try:
        from training import learning_diagnostics as ld

        meta = sc.candidate_metadata(candidate_cfg)
        refit = refit or {}
        method = meta.get("learning_method") or refit.get("learning_method") or (
            "temporal_difference" if learning_mode == "td" else "regression")
        td_loss = meta.get("td_loss")
        if td_loss is None:
            td_loss = refit.get("td_loss")
        cand_row = next(
            (r for r in eval_result.ranked if r.get("name") == sc.CANDIDATE_ID), {}
        )
        ld.record_learning_event(
            paths.state_dir / "learning_history.jsonl",
            run_id=run_id,
            learning_method=method,
            td_loss=td_loss,
            candidate_trueskill_mu=cand_row.get("trueskill_mu"),
            candidate_elo=None,
            promoted=promoted,
            training_rows=meta.get("training_rows") or refit.get("rows_used"),
        )
    except Exception:  # noqa: BLE001 — observability is best-effort
        pass


def _build_agent_rows(elo: EloTracker, tracker: TrueSkillTracker) -> List[ratings_db.AgentRatingRow]:
    rows: List[ratings_db.AgentRatingRow] = []
    agents = set(tracker.agent_ids) | set(elo.ratings.keys())
    for agent in sorted(agents):
        ts = tracker.get_rating(agent)
        rows.append(ratings_db.AgentRatingRow(
            agent=agent,
            elo=float(elo.get_rating(agent)),
            trueskill_mu=ts["mu"],
            trueskill_sigma=ts["sigma"],
            conservative=ts["conservative"],
            games_played=ts["games_played"],
        ))
    return rows


def _promote(
    state: Dict[str, Any],
    champion: Dict[str, Any],
    candidate_cfg: Dict[str, Any],
    refit: Optional[Dict[str, Any]],
    eval_result: sc.EvaluationResult,
    paths: TrainingPaths,
    *,
    tracker: TrueSkillTracker,
    elo: EloTracker,
    promote_registry: bool,
) -> bool:
    """Promote the candidate to champion: update state, checkpoint, lineage.

    Registry (the live web demo) is touched only when ``promote_registry`` is set.
    """
    generation = int(state["generation"])
    now = _utc_now().isoformat()
    new_version = f"gen{generation}"

    # Snapshot the *outgoing* champion as a historical checkpoint (anti-cycling).
    prev_rating = tracker.get_rating(CHAMPION_ID)
    checkpoint = {
        "generation": generation,
        "id": f"ckpt_{new_version}",
        "promoted_at": now,
        "rating": {
            "elo": float(elo.get_rating(CHAMPION_ID)),
            "mu": prev_rating["mu"],
            "sigma": prev_rating["sigma"],
        },
        # champion_loop format: 'params' is the full agent config dict.
        "params": copy.deepcopy(state["champion_params"]),
    }
    state.setdefault("checkpoints", []).append(checkpoint)
    state_store.write_checkpoint(paths, generation, checkpoint)

    # Candidate becomes the new champion. Strip candidate-metadata keys so the
    # persisted champion params stay a clean engine config; keep the metadata for
    # lineage below.
    cand_meta = sc.candidate_metadata(candidate_cfg)
    new_params = sc.strip_candidate_meta(candidate_cfg)
    new_params.pop("name", None)
    state["champion_params"] = new_params
    state["last_promoted_generation"] = generation

    # Reset champion uncertainty: the agent changed, so its old rating is less sure.
    tracker.reset_agent(CHAMPION_ID, increase_sigma=True)

    cand_row = next((r for r in eval_result.ranked if r["name"] == sc.CANDIDATE_ID), {})
    reason = eval_result.decision.summary_line
    champion["version"] = new_version
    champion["promoted_at"] = now
    champion["rating"] = {
        "elo": float(elo.get_rating(CHAMPION_ID)),
        "trueskill_mu": cand_row.get("trueskill_mu"),
        "trueskill_sigma": cand_row.get("trueskill_sigma"),
        "conservative": cand_row.get("trueskill_conservative"),
    }
    champion["params"] = new_params
    champion["flat_config"] = sc.candidate_to_champion_config(candidate_cfg, refit)
    champion.setdefault("lineage", []).append({
        "version": new_version,
        "promoted_at": now,
        "reason": reason,
        "refit_r2_global": (refit or {}).get("r2_global"),
        "learning_method": cand_meta.get("learning_method")
        or (refit or {}).get("learning_method") or "regression",
        "feature_set_version": cand_meta.get("feature_set_version")
        or (refit or {}).get("feature_set_version"),
        "training_rows": cand_meta.get("training_rows") or (refit or {}).get("rows_used"),
        "td_loss": cand_meta.get("td_loss") if cand_meta.get("td_loss") is not None
        else (refit or {}).get("td_loss"),
    })
    state_store.save_champion(paths, champion)

    if promote_registry:
        _update_registry(champion, eval_result, generation)

    print(f"[nightly] PROMOTED candidate -> champion {new_version}: {reason}")
    return True


def _update_registry(champion: Dict[str, Any], eval_result: sc.EvaluationResult, generation: int) -> None:
    """Opt-in: push the promoted champion into data/champion_registry.json."""
    from analytics.tournament import gauntlet

    registry_path = REPO_ROOT / "data" / "champion_registry.json"
    cand_row = next((r for r in eval_result.ranked if r["name"] == sc.CANDIDATE_ID), {})
    cand_row = dict(cand_row)
    cand_row["name"] = f"nightly_gen{generation}"
    entry = gauntlet.build_registry_entry(
        champion_row=cand_row,
        config_path="(nightly training — params inline)",
        params=champion.get("flat_config", {}),
        seeds=[],
        total_games=eval_result.total_games,
        gauntlet_run_path="training/state/selfplay_runs",
        comparison_opponents=["champion", "heuristic", "random", "prev_champion"],
        promoted_from=None,
        promotion_reason=f"Nightly training promotion gen{generation}: "
                         + eval_result.decision.summary_line,
        notes="Promoted automatically by training.nightly_run --promote-registry.",
    )
    gauntlet.update_registry(registry_path, entry, make_backup=True)
    print(f"[nightly] registry updated (gen{generation})")


def _record_error(paths: TrainingPaths, state: Dict[str, Any], generation: int, exc: Exception) -> None:
    """Persist a truncated crash summary into latest.json for the failure email."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    state["last_error"] = {
        "generation": generation,
        "message": f"{type(exc).__name__}: {exc}"[:500],
        "traceback": tb[-2000:],
        "timestamp": _utc_now().isoformat(),
    }
    try:
        state_store.save_latest(paths, state)
    except Exception:  # noqa: BLE001 — never mask the original error
        pass


# ---------------------------------------------------------------------------
# Approach-comparison orchestrator (the new default nightly path)
# ---------------------------------------------------------------------------

def _promote_winner(
    state: Dict[str, Any],
    champion: Dict[str, Any],
    winner_eval: Any,  # evaluation.head_to_head.CandidateEval
    winner_agent_config: Dict[str, Any],
    winner_metrics: Dict[str, Any],
    gate_reason: str,
    paths: TrainingPaths,
    *,
    tracker: TrueSkillTracker,
    elo: EloTracker,
    promote_registry: bool,
) -> bool:
    """Promote a benchmark-pool winner to champion (multi-candidate naming aware).

    Mirrors :func:`_promote` but keys ranked-row lookups on the winner's own name
    (approaches use distinct names, not the single ``candidate`` id).
    """
    generation = int(state["generation"])
    now = _utc_now().isoformat()
    new_version = f"gen{generation}"

    prev_rating = tracker.get_rating(CHAMPION_ID)
    checkpoint = {
        "generation": generation,
        "id": f"ckpt_{new_version}",
        "promoted_at": now,
        "rating": {"elo": float(elo.get_rating(CHAMPION_ID)),
                   "mu": prev_rating["mu"], "sigma": prev_rating["sigma"]},
        "params": copy.deepcopy(state["champion_params"]),
    }
    state.setdefault("checkpoints", []).append(checkpoint)
    state_store.write_checkpoint(paths, generation, checkpoint)

    new_params = sc.strip_candidate_meta(winner_agent_config)
    new_params.pop("name", None)
    state["champion_params"] = new_params
    state["last_promoted_generation"] = generation

    tracker.reset_agent(CHAMPION_ID, increase_sigma=True)

    champion["version"] = new_version
    champion["promoted_at"] = now
    champion["rating"] = {
        "elo": float(elo.get_rating(CHAMPION_ID)),
        "trueskill_mu": winner_eval.trueskill_mu,
        "trueskill_sigma": winner_eval.trueskill_sigma,
        "conservative": (winner_eval.trueskill_mu - 3.0 * winner_eval.trueskill_sigma
                         if winner_eval.trueskill_mu is not None
                         and winner_eval.trueskill_sigma is not None else None),
    }
    champion["params"] = new_params
    champion["flat_config"] = sc.candidate_to_champion_config(new_params, None)
    champion.setdefault("lineage", []).append({
        "version": new_version,
        "promoted_at": now,
        "reason": gate_reason,
        "approach": winner_eval.approach,
        "learning_method": winner_metrics.get("learning_method"),
        "training_rows": winner_metrics.get("training_rows") or winner_metrics.get("source_rows"),
        "td_loss": winner_metrics.get("td_loss"),
    })
    state_store.save_champion(paths, champion)
    print(f"[nightly] PROMOTED {winner_eval.approach} -> champion {new_version}: {gate_reason}")
    return True


def run_approaches(
    *,
    paths: TrainingPaths,
    approaches: List[str],
    games_per_arena: int,
    seeds: List[int],
    time_budget_minutes: float,
    thinking_time_ms: Optional[int],
    promote_registry: bool,
    dry_run: bool,
    verbose: bool,
    td_weights_path: Optional[str] = None,
    two_stage_promotion: bool = False,
    sequential_eval: bool = False,
    sprt_elo1: float = SPRT_DEFAULT_ELO1,
    sprt_min_games: int = SPRT_DEFAULT_MIN_GAMES,
    sprt_max_games: int = SPRT_DEFAULT_MAX_GAMES,
) -> Dict[str, Any]:
    """One nightly run as an approach-comparison: generate candidates from each
    approach, evaluate the created ones against a fixed benchmark pool with fixed
    seeds, promote only a gate-passing winner, and write reports.

    Dry-run writes nothing to tracked state (artifacts go to a temp dir); it prints
    the plan and the per-approach created/reason verdicts and returns.
    """
    paths.ensure_dirs()
    run_id = _new_run_id()
    now_iso = _utc_now().isoformat()
    started = time.monotonic()
    deadline = started + time_budget_minutes * 60.0

    state = state_store.load_latest(paths)
    champion = state_store.load_champion(paths)
    _ensure_cold_start(state, champion)
    state["run_id"] = run_id

    # 1. Candidate generation (budget a quarter of wall-clock to learning).
    # In dry-run, redirect *all* writes (candidate artifacts + freshly-trained TD
    # weights) into a throwaway temp dir so no tracked state is touched.
    artifact_root = paths.root
    ctx_td_weights = td_weights_path
    if dry_run:
        import tempfile
        artifact_root = Path(tempfile.mkdtemp(prefix="nightly_dryrun_"))
        if ctx_td_weights is None:
            ctx_td_weights = str(artifact_root / "td_evaluator_weights.json")

    gen_budget = max(60.0, time_budget_minutes * 60.0 * 0.25)
    ctx = ApproachContext(
        state=state, repo_root=paths.root, run_id=run_id, now_iso=now_iso,
        time_budget_s=gen_budget / max(len(approaches), 1), verbose=verbose,
        td_weights_path=ctx_td_weights,
    )
    candidates = [a.generate(ctx) for a in ap_pkg.build_approaches(approaches)]

    # Validate; demote any "created" candidate whose artifact is malformed.
    for c in candidates:
        ok, why = validate_candidate_artifact(c.to_artifact(run_id, now_iso))
        if c.created and not ok:
            c.created = False
            c.agent_config = None
            c.reason = f"{c.approach}: invalid candidate artifact ({why})"

    for c in candidates:
        write_candidate_artifact(c, repo_root=artifact_root, run_id=run_id, now_iso=now_iso)

    created = [c for c in candidates if c.created]

    if dry_run:
        print(f"[nightly] DRY RUN run_id={run_id} approaches={approaches} "
              f"games={games_per_arena} seeds={seeds} budget_min={time_budget_minutes}")
        for c in candidates:
            print(f"[nightly]   {c.approach:18s} created={c.created!s:5s} :: {c.reason}")
        print(f"[nightly] {len(created)}/{len(candidates)} candidates created. "
              f"No tracked state written (dry run). Artifacts -> {artifact_root}")
        return state

    # 2. Evaluation against the fixed benchmark pool.
    conn = ratings_db.connect(paths.ratings_db)
    latest_db = ratings_db.latest_ratings(conn)
    elo = _seed_elo_tracker(latest_db)
    tracker = _seed_trueskill_tracker(state, latest_db)
    champ_game_no = ratings_db.max_game_number(conn, agent=CHAMPION_ID)

    prev_generation = int(state.get("generation", 0))
    generation = prev_generation  # advanced to +1 only once an evaluation runs

    evals_by_name: Dict[str, Any] = {}
    gates_by_name: Dict[str, Any] = {}
    winner = None
    promoted = False
    total_eval_games = 0
    eval_samples: List[tuple] = []
    confirmation_record = None
    sprt_results: Dict[str, Any] = {}

    if created and time.monotonic() < deadline and sequential_eval:
        # Variance-reduced sequential screen (SPRT on the paired champion-vs-candidate
        # outcome, seat-balanced). Decisive candidates — clearly better OR clearly not —
        # resolve in few games; only genuinely borderline ones cost many. A candidate is
        # promotable only if the SPRT accepts H1 *and* it clears the conservative gate on
        # those same games, so the SPRT evidence doubles as the confirmation battery.
        pool = build_benchmark_pool(state, seeds=seeds)
        ht, sprt_results = evaluate_candidates_sequential(
            state, created, pool, paths, seeds=seeds, thinking_time_ms=thinking_time_ms,
            elo1=sprt_elo1, min_games=sprt_min_games, max_games=sprt_max_games,
            deadline=deadline, verbose=verbose,
        )
        evals_by_name = {e.name: e for e in ht.candidate_evals}
        gates_by_name = {ce.name: evaluate_gate(ce, GateThresholds())
                         for ce in ht.candidate_evals}
        improved = [ce for ce in ht.candidate_evals
                    if sprt_results.get(ce.name) is not None
                    and sprt_results[ce.name].is_improvement]
        sel = select_winner(improved, GateThresholds())
        gates_by_name.update(sel["gates"])  # authoritative gate for the winner subset
        winner = sel["winner"]
        total_eval_games = len(ht.all_games)
        # Fold the SPRT verdict into each candidate's report reason for visibility.
        for c in created:
            sr = sprt_results.get(c.name)
            if sr is not None:
                c.reason = f"{c.reason} — {sr.summary_line()}"
        if winner is not None:
            sr = sprt_results.get(winner.name)
            confirmation_record = {
                "candidate": winner.name, "approach": winner.approach,
                "method": "sprt_sequential",
                "screen_games": int(sr.n_games) if sr else 0,
                "confirm_games": int(sr.n_games) if sr else 0,
                "confirm_min_games": sprt_min_games,
                "passed": True,
                "reason": (sr.summary_line() if sr else ""),
            }
    elif created and time.monotonic() < deadline:
        pool = build_benchmark_pool(state, seeds=seeds)
        ht = evaluate_candidates(
            state, created, pool, paths,
            games_per_arena=games_per_arena, seeds=seeds,
            thinking_time_ms=thinking_time_ms, deadline=deadline, verbose=verbose,
        )
        evals_by_name = {e.name: e for e in ht.candidate_evals}
        sel = select_winner(ht.candidate_evals, GateThresholds())
        gates_by_name = sel["gates"]
        winner = sel["winner"]
        total_eval_games = len(ht.all_games)

        # Two-stage promotion (audit #4): the screen above identified a leading
        # candidate over the cheap 20-game gate. Before promoting, re-evaluate ONLY
        # that candidate over a larger confirmation sample and require it to clear
        # the gate again at the higher game floor. A lucky short run can no longer
        # promote on its own; the extra cost is bounded to one candidate and the
        # remaining wall-clock budget.
        if two_stage_promotion and winner is not None and time.monotonic() < deadline:
            wcand0 = next((c for c in created if c.name == winner.name), None)
            if wcand0 is not None and getattr(wcand0, "agent_config", None):
                conf_eval, conf_games, _conf_dirs = ht_confirm_winner(
                    state, winner.name, winner.approach, wcand0.agent_config, pool, paths,
                    seeds=seeds, thinking_time_ms=thinking_time_ms,
                    deadline=deadline, verbose=verbose,
                )
                conf_gate = evaluate_gate(
                    conf_eval, GateThresholds(min_total_games=EVAL_CONFIRM_TOTAL_GAMES))
                # The champion plays every confirmation game too — fold them into the
                # pooled game set so ratings and counts reflect the full evidence.
                ht.all_games.extend(conf_games)
                total_eval_games = len(ht.all_games)
                confirmation_record = {
                    "candidate": winner.name,
                    "approach": winner.approach,
                    "screen_games": int(evals_by_name[winner.name].games),
                    "confirm_games": int(conf_eval.games),
                    "confirm_min_games": EVAL_CONFIRM_TOTAL_GAMES,
                    "passed": bool(conf_gate.passed),
                    "reason": conf_gate.reason,
                }
                if conf_gate.passed:
                    # Promote on the stronger confirmation evidence.
                    evals_by_name[winner.name] = conf_eval
                    gates_by_name[winner.name] = conf_gate
                    winner = conf_eval
                else:
                    # The screen result did not hold up over more games — hold.
                    winner = None

        # A real evaluation ran -> advance the durable generation counter now. A
        # skipped/empty cycle must NOT look like a completed generation.
        if total_eval_games > 0:
            generation = prev_generation + 1
            state["generation"] = generation

        # Surface any candidates skipped for budget in their report reason.
        for nm in ht.skipped_for_budget:
            c = next((cc for cc in created if cc.name == nm), None)
            if c is not None:
                c.reason = f"{c.reason} — not evaluated this run (time budget exhausted)"

        # Fold every eval game into the champion's Elo + TrueSkill timeline (the
        # champion plays in every candidate's battery against a STABLE pool).
        eval_samples = _replay_games_through_elo(
            elo, ht.all_games, capture_agent=CHAMPION_ID, start_game_number=champ_game_no)
        if eval_samples:
            champ_game_no = eval_samples[-1][0]
        for record in ht.all_games:
            scores = record.get("agent_scores", {})
            if scores:
                tracker.update_game(scores)

        if winner is not None:
            wcand = next((c for c in created if c.name == winner.name), None)
            wmetrics = wcand.metrics if wcand else {}
            wcfg = wcand.agent_config if wcand else copy.deepcopy(state["champion_params"])
            promoted = _promote_winner(
                state, champion, winner, wcfg, wmetrics,
                gates_by_name[winner.name].reason, paths,
                tracker=tracker, elo=elo, promote_registry=promote_registry,
            )
            if promote_registry:
                try:
                    _update_registry_for_winner(champion, winner, generation)
                except Exception as exc:  # noqa: BLE001
                    print(f"[nightly] registry update skipped: {exc}")

    # 3. Finalise ratings + state.
    eval_ran = total_eval_games > 0
    champ_ts = tracker.get_rating(CHAMPION_ID)
    champ_elo = elo.get_rating(CHAMPION_ID)
    state["elo"] = float(champ_elo)
    state["trueskill_mu"] = champ_ts["mu"]
    state["trueskill_sigma"] = champ_ts["sigma"]
    state["games_today"] = total_eval_games
    state["total_games"] = int(state.get("total_games", 0)) + total_eval_games
    # Counters that represent *training progress* advance only when an evaluation
    # actually ran — a cycle where every approach failed to produce a candidate (or
    # the budget was spent before evaluation) is not a completed generation.
    if eval_ran:
        state["days_trained"] = int(state.get("days_trained", 0)) + 1
    state["last_error"] = None

    # Build + persist the comparison record (status/email/markdown all read this).
    series = ratings_db.champion_elo_series(conn)
    series_vals = [float(r.get("elo", 0.0)) for r in series] + [float(champ_elo)]
    traj = summarize_trajectory(series_vals)
    record = approach_report.build_comparison_record(
        run_id=run_id, now_iso=now_iso, candidates=candidates,
        evals_by_name=evals_by_name, gates_by_name=gates_by_name,
        winner_name=(winner.name if winner else None),
        pool=(build_benchmark_pool(state, seeds=seeds).describe()),
        trajectory=traj.to_dict(), seeds=seeds,
        generation=generation,
        last_promoted_generation=state.get("last_promoted_generation"),
        confirmation=confirmation_record,
    )
    if sprt_results:
        # Persist the sequential (SPRT) screen evidence alongside the comparison so the
        # status report / email can show each candidate's paired verdict and game count.
        record["sprt_screen"] = {n: r.to_dict() for n, r in sprt_results.items()}
    state["last_approach_comparison"] = record
    state["last_eval"] = None  # superseded by last_approach_comparison

    # Persist DB timeline row (only after a real evaluation).
    if total_eval_games > 0:
        ratings_db.record_run(
            conn, run_id=run_id, timestamp=_utc_now().isoformat(), generation=generation,
            agent_rows=_build_agent_rows(elo, tracker),
            run_summary=ratings_db.RunSummaryRow(
                generation=generation, games_today=total_eval_games,
                total_games=int(state["total_games"]), champion_elo=float(champ_elo),
                champion_mu=champ_ts["mu"], champion_sigma=champ_ts["sigma"],
                promoted=promoted, days_trained=int(state["days_trained"]),
            ),
        )
        ratings_db.record_game_elos(
            conn, run_id=run_id, timestamp=_utc_now().isoformat(), generation=generation,
            samples=eval_samples, agent=CHAMPION_ID,
        )

    est = human_estimate.summarize(
        float(champ_elo), ratings_db.champion_elo_series(conn),
        target=float(state.get("human_target_elo", 1700)))
    state["estimated_games_to_target"] = est.get("games_remaining")
    state["estimated_days_to_target"] = est.get("days_remaining")
    state["estimate_confidence"] = est.get("confidence")
    state["champion"] = {
        "name": CHAMPION_ID,
        "version": champion.get("version", state["champion"].get("version", "gen0")),
        "config_ref": "state/champion.json",
    }
    champion.setdefault("rating", {})["elo"] = float(champ_elo)
    champion["rating"]["trueskill_mu"] = champ_ts["mu"]
    champion["rating"]["trueskill_sigma"] = champ_ts["sigma"]
    champion["rating"]["conservative"] = champ_ts["conservative"]
    state_store.save_champion(paths, champion)

    # Append to the per-generation history only when a generation actually
    # completed (an evaluation ran), so a skipped cycle does not fabricate a row.
    if eval_ran:
        state_store.append_jsonl(paths.history_jsonl, {
            "schema_version": state_store.HISTORY_SCHEMA_VERSION,
            "kind": state_store.HISTORY_KIND_APPROACH,
            "generation": generation, "run_id": run_id, "timestamp": _utc_now().isoformat(),
            "games": total_eval_games, "approaches": approaches,
            "candidates_created": [c.name for c in created],
            "winner": winner.name if winner else None, "promoted": promoted,
            "champion_elo": float(champ_elo), "champion_mu": champ_ts["mu"],
            "champion_sigma": champ_ts["sigma"], "champion_conservative": champ_ts["conservative"],
        })

    # Persist the FULL TrueSkill tracker (all agents) back into state so the next
    # run resumes from the freshly-measured priors. Without this, _seed_trueskill_tracker
    # prefers stale state['trueskill_ratings'] and the new ratings are lost.
    persist_tracker(tracker, state)
    state_store.save_latest(paths, state)

    # 4. Reports.
    approach_report.write_approach_comparison(
        paths.reports_dir / "approach_comparison.md", record)
    findings = diagnostics.write_diagnosis(paths, conn, state)
    status_report.write_status(paths, conn, state, findings=findings, eval_result=None)
    conn.close()

    print(f"[nightly] DONE run_id={run_id} approaches={len(approaches)} "
          f"created={len(created)} eval_games={total_eval_games} "
          f"elo={champ_elo:.1f} promoted={promoted} winner={winner.name if winner else None}")
    return state


def _update_registry_for_winner(champion: Dict[str, Any], winner_eval: Any, generation: int) -> None:
    """Opt-in: push a promoted approach winner into data/champion_registry.json."""
    from analytics.tournament import gauntlet

    registry_path = REPO_ROOT / "data" / "champion_registry.json"
    row = {"name": f"nightly_gen{generation}",
           "trueskill_mu": winner_eval.trueskill_mu,
           "trueskill_sigma": winner_eval.trueskill_sigma,
           "win_rate": winner_eval.win_rate}
    entry = gauntlet.build_registry_entry(
        champion_row=row, config_path="(nightly approach winner — params inline)",
        params=champion.get("flat_config", {}), seeds=[],
        total_games=winner_eval.games, gauntlet_run_path="training/state/selfplay_runs",
        comparison_opponents=["champion", "heuristic", "random", "best_historical"],
        promoted_from=None,
        promotion_reason=f"Nightly approach '{winner_eval.approach}' gen{generation}",
        notes="Promoted by training.nightly_run --promote-registry.",
    )
    gauntlet.update_registry(registry_path, entry, make_backup=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Durable nightly Blokus MCTS training run.")
    p.add_argument("--hours", type=float, default=5.0, help="Wall-clock budget (hours).")
    p.add_argument("--resume", default="training/state/latest.json",
                   help="Path to latest.json (informational; state always resumes from training/state/).")
    p.add_argument("--seeds", type=int, nargs="+", default=[20260620, 20260621],
                   help="Evaluation seeds (>=2 to satisfy the multi-seed gate).")
    p.add_argument("--games-per-arena", type=int, default=12,
                   help="Games per arena (per seed) for generations and evaluation.")
    p.add_argument("--thinking-time-ms", type=int, default=None,
                   help="Override every MCTS agent's thinking budget (small for smoke tests).")
    p.add_argument("--promote-registry", action="store_true",
                   help="Also update data/champion_registry.json on promotion (off by default).")
    p.add_argument("--learning-mode", choices=["regression", "td"], default="regression",
                   help="Candidate evaluator learning mode: 'regression' (default) or "
                        "'td' (temporal-difference). TD falls back to regression if no "
                        "TD weights artifact exists yet.")
    p.add_argument("--td-weights-path", default=None,
                   help="Path to the TD weights JSON (default: training/state/td_evaluator_weights.json).")
    # --- Approach-comparison mode (the new default nightly path) ---
    p.add_argument("--approaches", default=None,
                   help="Comma-separated candidate-generation approaches to compare "
                        f"(e.g. 'td,mcts_sweep,heuristic_tune,baseline,hybrid'; "
                        f"'all' = {','.join(ap_pkg.DEFAULT_APPROACHES)}). When set, runs "
                        "the approach-comparison framework instead of the legacy "
                        "self-play generation loop.")
    p.add_argument("--games", type=int, default=None,
                   help="Games per arena per seed for approach evaluation (approach mode).")
    p.add_argument("--time-budget-minutes", type=float, default=None,
                   help="Wall-clock budget in minutes for an approach-comparison run.")
    p.add_argument("--two-stage-promotion", action="store_true",
                   help="Two-stage promotion: after the cheap 20-game screen picks a "
                        "leading candidate, re-evaluate ONLY that candidate over a larger "
                        f"confirmation sample ({EVAL_CONFIRM_TOTAL_GAMES} games) and promote "
                        "only if it clears the gate again (off by default).")
    # --- Sequential (SPRT) evaluation: variance-reduced, stops early ---
    p.add_argument("--sequential-eval", action="store_true",
                   help="Use the variance-reduced sequential screen instead of the fixed "
                        "N-game screen: a seat-balanced SPRT on the paired champion-vs-"
                        "candidate outcome that stops as soon as the result is conclusive. "
                        "A candidate promotes only if the SPRT accepts H1 AND it clears the "
                        "conservative gate on those games (supersedes --two-stage-promotion).")
    p.add_argument("--sprt-elo1", type=float, default=SPRT_DEFAULT_ELO1,
                   help=f"SPRT H1: smallest candidate-over-champion Elo edge worth promoting "
                        f"(default {SPRT_DEFAULT_ELO1:.0f}). Smaller ⇒ more games to decide.")
    p.add_argument("--sprt-min-games", type=int, default=SPRT_DEFAULT_MIN_GAMES,
                   help=f"SPRT: never decide before this many paired games "
                        f"(default {SPRT_DEFAULT_MIN_GAMES}).")
    p.add_argument("--sprt-max-games", type=int, default=SPRT_DEFAULT_MAX_GAMES,
                   help=f"SPRT: give up (inconclusive → hold) beyond this many paired games "
                        f"per candidate (default {SPRT_DEFAULT_MAX_GAMES}).")
    p.add_argument("--dry-run", action="store_true", help="Print the plan and exit.")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def _resolve_approaches(arg: Optional[str]) -> List[str]:
    if not arg:
        return []
    if arg.strip().lower() == "all":
        return list(ap_pkg.DEFAULT_APPROACHES)
    return [a.strip() for a in arg.split(",") if a.strip()]


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    paths = TrainingPaths.default()
    approaches = _resolve_approaches(args.approaches)
    try:
        if approaches:
            # New default: approach-comparison framework.
            run_approaches(
                paths=paths,
                approaches=approaches,
                games_per_arena=args.games if args.games is not None else args.games_per_arena,
                seeds=args.seeds,
                time_budget_minutes=(args.time_budget_minutes
                                     if args.time_budget_minutes is not None
                                     else args.hours * 60.0),
                thinking_time_ms=args.thinking_time_ms,
                promote_registry=args.promote_registry,
                dry_run=args.dry_run,
                verbose=args.verbose,
                td_weights_path=args.td_weights_path,
                two_stage_promotion=args.two_stage_promotion,
                sequential_eval=args.sequential_eval,
                sprt_elo1=args.sprt_elo1,
                sprt_min_games=args.sprt_min_games,
                sprt_max_games=args.sprt_max_games,
            )
            return 0
        run(
            paths=paths,
            hours=args.hours,
            seeds=args.seeds,
            games_per_arena=args.games_per_arena,
            thinking_time_ms=args.thinking_time_ms,
            promote_registry=args.promote_registry,
            dry_run=args.dry_run,
            verbose=args.verbose,
            learning_mode=args.learning_mode,
            td_weights_path=args.td_weights_path,
        )
        return 0
    except Exception:  # noqa: BLE001 — surface failure but leave atomic state intact
        traceback.print_exc()
        # Best-effort: still write reports so status.md/diagnosis reflect the crash.
        try:
            conn = ratings_db.connect(paths.ratings_db)
            state = state_store.load_latest(paths)
            findings = diagnostics.write_diagnosis(paths, conn, state)
            status_report.write_status(paths, conn, state, findings=findings, eval_result=None)
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
