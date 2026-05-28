# Current Behavior

> What actually runs today, stated plainly. Last audited: 2026-05-28.
> Status labels: `Implemented | Partial | Stubbed | Broken | Designed only | Deprecated | Unknown`.

## Running an arena tournament — Implemented

`python scripts/arena.py --config scripts/arena_config.json` runs a 4-player
round-robin tournament with deterministic seeding and writes a run directory
under `arena_runs/<timestamp>_<id>/` containing `summary.json`, `summary.md`,
`games.jsonl`, `snapshots.{csv,parquet}`, and `run_config.json`. Add
`--num-games 4` for a smoke test and `--verbose` for per-move progress
(reported every 4 turns). Agent construction goes through
`analytics/tournament/arena_runner.py::build_agent`, supporting `random`,
`heuristic`, `mcts`, and `challenge_champion_gameplay`. The runner **rejects**
`fast_mcts`/`gameplay_fast_mcts` with an error (archived as an invalid tree
search).

> Timing: full 50-move rollouts proved infeasible (>2h/game), so configs use
> `rollout_cutoff_depth` of 0/5/10 (~4–5 min/game; ~60–90 min for 25 games).

## Playing in the browser — Implemented

`cd frontend && npm run dev` serves the SPA on `:5173`. The MCTS agent runs
**locally in the browser** via a Pyodide WebWorker (`browser_python/`,
`frontend/public/blokus_core.zip`) — no backend scaling needed. "Run Demo Game"
starts an AI-vs-AI match with Pause/Step controls; "Explain This Move" shows top
candidates, simulation counts, and Q-values; "AI Scoreboard" shows the pairwise
win-rate / TrueSkill matrix. See [User Flows](USER_FLOWS.md).

## Backend API — Implemented

`python run_server.py` serves FastAPI on `:8000`. The **research** profile
exposes gameplay + research routes (training/analysis/history/trends/arena
results) and needs MongoDB; the **deploy** profile (Vercel) is gameplay-only.
Game orchestration uses the full `MCTSAgent` via a gameplay adapter. See
[`docs/webapi/README.md`](../webapi/README.md).

## MCTS search — Implemented (recommended config is a subset)

`MCTSAgent` implements UCB1 selection, expansion, rollout, and backup with
Layers 3–9 features. Empirically validated best settings (from
[`KEY_FINDINGS.md`](../../KEY_FINDINGS.md)): `rollout_policy: random`,
`rollout_cutoff_depth: 5`, `minimax_backup_alpha: 0.25`, calibrated
`state_eval_weights`, `rave_enabled: true` / `rave_k: 1000`, `num_workers: 2` /
`parallel_strategy: root`, `adaptive_rollout_depth_enabled: true`.

Several implemented features are **deliberately not recommended** because
experiments showed no benefit or harm:

| Feature | Status | Why not recommended |
|---|---|---|
| Phase-dependent eval weights (L6) | Implemented, not recommended | 0% win rate; inverted early-game signs, hard transitions |
| Opponent modeling (L7) | Implemented, not recommended | works after bugfix but no reliable advantage; ~2.4× slower |
| Learned GBT evaluator (L2) | Implemented, not recommended | ~26ms inference eats the time budget |
| Tree parallelization (L8) | Implemented, not recommended | GIL-bound; slower than single-threaded |
| Adaptive exploration constant (L9) | Implemented, not recommended | over-explores on top of RAVE (8% win rate) |

## ML calibration pipeline — Implemented

`scripts/collect_layer6_data.py` runs self-play and extracts 7 evaluator + 35
win-prob features per snapshot; `scripts/analyze_layer6_features.py` runs
regression / Random Forest / SHAP / residual analysis and emits calibrated
weights to `data/layer6_calibrated_weights.json`.

## Champion self-improvement loop — Partial

`scripts/champion_loop.py` / `champion_arena.py` run a persistent champion vs a
randomized challenger pool with TrueSkill tracking, snapshot-driven evaluator
recalibration, and gated promotion. **No agent is currently a *validated*
champion** — `champion_v1` is a documented failed candidate; `champion_minimal`
is the current candidate. Canonical narrative:
[`docs/CHAMPION_PROGRESSION.md`](../CHAMPION_PROGRESSION.md);
per-run status: [`docs/arena_run_registry.md`](../arena_run_registry.md).

## Verified commands

The commands above are taken from the repo's own README/CLAUDE.md and config
files. An end-to-end smoke run (`scripts/arena.py … --num-games 4`) is part of
the [Regression Checklist](../04-quality/REGRESSION_CHECKLIST.md); see
[Testing Strategy](../03-implementation/TESTING_STRATEGY.md) for results
captured during this audit.
