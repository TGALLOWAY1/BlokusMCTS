"""Wall-clock-capped fresh-experience generation for the nightly loop.

This is the P1 fix from ``docs/05-planning/CONTINUOUS_TRAINING_PLAN.md``: the
approach-comparison orchestrator (``training.nightly_run.run_approaches``)
compared candidates all night but never generated new game experience, so the
learning approaches (``heuristic_tune`` / ``td`` / ``rich_leaf``) kept fitting
frozen, pre-search-fix corpora and the champion could not ratchet.

One call to :func:`refresh_training_data` runs two capped collection phases
from the *current* registry champion:

1. **TD trajectories** (expert iteration's teacher step) — full games with the
   champion seats searched at a named profile (default ``teacher``: 1200
   iterations + progressive widening, i.e. strictly deeper search than the
   champion's own play budget), appended to ``data/td_trajectories.csv`` with
   provenance (``gen140@teacher:1200``) stamped per row. ``td`` and
   ``rich_leaf`` train on this corpus.
2. **Evaluator snapshots** — one snapshot-enabled arena at the champion's own
   (fixed-search) budget, accumulated into ``data/champion_snapshots.csv`` with
   a recency cap (see ``scripts.champion_loop.accumulate_snapshots``).
   ``heuristic_tune`` re-fits on this corpus.

Both phases stop between games once their share of ``budget_s`` is spent, so a
refresh can never starve the candidate evaluation that follows it.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from training import TrainingPaths

# Fraction of the refresh budget spent on teacher-budget TD trajectories; the
# remainder goes to the snapshot arena. Trajectories get the larger share: they
# are the expert-iteration signal and the teacher budget makes them expensive.
_TD_BUDGET_FRACTION = 0.7
# Upper bounds so a tiny/fast configuration can't loop forever; the deadline is
# the real limiter on the nightly runner.
_MAX_TD_GAMES = 200
_MAX_SNAPSHOT_GAMES = 24


def refresh_training_data(
    state: Dict[str, Any],
    paths: TrainingPaths,
    *,
    run_id: str,
    budget_s: float,
    seed: int,
    teacher_profile: Optional[str] = "teacher",
    td_output_path: Optional[Any] = None,
    collect_snapshots: bool = True,
    thinking_time_ms: Optional[int] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Generate fresh training data from the current champion, capped on wall-clock.

    ``thinking_time_ms`` overrides every MCTS seat's budget (smoke tests / local
    runs only — the nightly job must NOT pass its low evaluation override here,
    that would recreate the weak-teacher data this step exists to replace).
    Returns a summary dict recorded in the run's approach-comparison record.

    Both corpora are resolved under ``paths.root`` (``<root>/data/…``) so an
    isolated ``TrainingPaths`` (tests, tmp roots) never reads or contaminates
    the real repo corpora; under the default paths these are exactly
    ``data/td_trajectories.csv`` / ``data/champion_snapshots.csv``.
    """
    from scripts.champion_loop import accumulate_snapshots
    from training import selfplay_core as sc
    from training.td_selfplay import collect_trajectories
    from training.teacher_roster import champion_version, teacher_roster

    if td_output_path is None:
        td_output_path = paths.root / "data" / "td_trajectories.csv"
    snapshot_csv = paths.root / "data" / "champion_snapshots.csv"

    t0 = time.monotonic()
    deadline = t0 + budget_s
    td_deadline = t0 + budget_s * (_TD_BUDGET_FRACTION if collect_snapshots else 1.0)

    # --- Phase 1: teacher-budget TD trajectories ------------------------------
    roster = teacher_roster(teacher_profile)
    _override_thinking(roster, thinking_time_ms)
    budget = roster[0].get("thinking_time_ms")
    agent_version = f"{champion_version()}@{teacher_profile or 'stored'}:{budget}"

    td_rows = collect_trajectories(
        roster,
        run_id=f"refresh_{run_id}",
        num_games=_MAX_TD_GAMES,
        seed=seed,
        agent_version=agent_version,
        output_path=td_output_path,
        capture_agents=("champion", "champion2"),
        deadline=td_deadline,
        min_games=1,
        verbose=verbose,
    )
    td_elapsed = time.monotonic() - t0

    summary: Dict[str, Any] = {
        "run_id": run_id,
        "profile": teacher_profile or "stored",
        "agent_version": agent_version,
        "td_rows": int(td_rows),
        "td_elapsed_s": round(td_elapsed, 1),
        "snapshot_new_rows": 0,
        "snapshot_corpus_rows": None,
        "budget_s": round(budget_s, 1),
    }

    # --- Phase 2: snapshot arena at the champion's own budget -----------------
    if collect_snapshots and time.monotonic() < deadline:
        snap_roster = teacher_roster(None)  # champion at its stored (play) budget
        _override_thinking(snap_roster, thinking_time_ms)
        result = sc.run_arena_inproc(
            snap_roster,
            paths=paths,
            run_label=f"refresh_{run_id}",
            num_games=_MAX_SNAPSHOT_GAMES,
            seed=seed + 777,
            enable_snapshots=True,
            verbose=verbose,
            deadline=deadline,
        )
        corpus_rows = accumulate_snapshots(result["run_dir"], snapshot_csv=snapshot_csv)
        state["total_snapshot_rows"] = corpus_rows
        summary["snapshot_new_rows"] = int(result.get("snapshot_rows", 0) or 0)
        summary["snapshot_corpus_rows"] = int(corpus_rows)
        summary["snapshot_games"] = int(
            (result.get("summary", {}) or {}).get("completed_games", 0))

    summary["elapsed_s"] = round(time.monotonic() - t0, 1)
    if verbose:
        print(f"[data_refresh] {summary}")
    return summary


def _override_thinking(agents: List[Dict[str, Any]], thinking_time_ms: Optional[int]) -> None:
    if thinking_time_ms is None:
        return
    for a in agents:
        if a.get("type", "mcts") == "mcts":
            a["thinking_time_ms"] = int(thinking_time_ms)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    from mcts.search_profiles import SEARCH_PROFILES
    from training import state_store

    p = argparse.ArgumentParser(
        description="Refresh the training corpora (TD trajectories + evaluator "
                    "snapshots) from the current champion, capped on wall-clock.")
    p.add_argument("--minutes", type=float, default=30.0,
                   help="Wall-clock budget for the whole refresh (default 30).")
    p.add_argument("--profile", default="teacher",
                   choices=sorted(SEARCH_PROFILES) + ["none"],
                   help="Search profile for the trajectory champion seats "
                        "(default: teacher). 'none' keeps the stored budget.")
    p.add_argument("--seed", type=int, default=None, help="Base seed (default: time-derived).")
    p.add_argument("--no-snapshots", action="store_true",
                   help="Skip the snapshot arena; collect TD trajectories only.")
    p.add_argument("--thinking-time-ms", type=int, default=None,
                   help="Override every MCTS seat's budget (smoke tests only).")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    paths = TrainingPaths.default()
    paths.ensure_dirs()
    state = state_store.load_latest(paths)
    seed = args.seed if args.seed is not None else int(time.time()) % (2**31)
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    summary = refresh_training_data(
        state, paths,
        run_id=run_id,
        budget_s=args.minutes * 60.0,
        seed=seed,
        teacher_profile=None if args.profile == "none" else args.profile,
        collect_snapshots=not args.no_snapshots,
        thinking_time_ms=args.thinking_time_ms,
        verbose=args.verbose,
    )
    state_store.save_latest(paths, state)
    print(f"[data_refresh] +{summary['td_rows']} TD rows "
          f"(labels from {summary['agent_version']}), "
          f"+{summary['snapshot_new_rows']} snapshot rows "
          f"in {summary['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
