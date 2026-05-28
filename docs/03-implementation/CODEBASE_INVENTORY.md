# Codebase Inventory

> Directory-by-directory map of the active tree. Last audited: 2026-05-28.
> For the experiment/results narrative see [`docs/project-history.md`](../project-history.md).

## Top-level layout

| Path | Purpose | Status |
|---|---|---|
| `engine/` | Core Blokus engine: board, pieces, move generation, telemetry | Implemented |
| `mcts/` | MCTS agent and search infrastructure (Layers 1–10) | Implemented |
| `agents/` | Baseline agents (random, heuristic), registry, gameplay adapters | Implemented |
| `analytics/` | Metrics, tournament harness, ratings, logging, heatmaps, win-prob | Implemented |
| `scripts/` | Arena CLI, experiments, data generation, analysis, calibration | Implemented |
| `schemas/` | Pydantic models (game config/state/move/update) | Implemented |
| `webapi/` | FastAPI app (gameplay + research routes), MongoDB, profiles | Implemented |
| `browser_python/` | Pyodide mirror of engine + MCTS + agents for the browser | Implemented |
| `api-runtime/` | Vercel entry point that loads `webapi` in deploy profile | Implemented |
| `frontend/` | React 18 + TS + Vite SPA | Implemented |
| `league/` | Self-play league, ELO, Plackett-Luce, league DB | Implemented |
| `benchmarks/` | Performance benchmarks (move-gen, MCTS settings, self-play) | Implemented |
| `config/` | Agent configs and champion arena parameter sets | Implemented |
| `data/` | Calibrated weights, champion registry, calibration, sample trace | Implemented |
| `arena_runs/` | Timestamped + named tournament run artifacts | Data |
| `arena_visuals/` | Layer-progression plots embedded in the root README | Data |
| `models/` | Pickled model artifacts | Data |
| `tests/` | Python test suite (~38 `test_*.py`) | Implemented |
| `utils/` | Logging helpers | Implemented |
| `docs/` | Documentation (this tree) | Implemented |
| `archive/` | Historical artifacts: RL code, old runs, reports, logs | Archived |
| `run_server.py` | Local backend entry point (`:8000`) | Implemented |

## `engine/` — Blokus engine

| File | Key symbols | Role |
|---|---|---|
| `board.py` | `Board`, `Player`, `Position` | 20×20 board, frontier tracking, placement, scoring |
| `pieces.py` | `Piece`, `PieceOrientation`, `PieceGenerator` | 21 pieces, orientations, placements |
| `move_generator.py` | `Move`, `LegalMoveGenerator` | Frontier-based legal move generation w/ bitboard legality |
| `game.py` | `BlokusGame`, `GameResult` | Orchestration, validation, scoring, game-over |
| `bitboard.py` | bit ops (`popcount`, `shift_mask`) | Occupancy masks for fast legality |
| `advanced_metrics.py`, `mobility_metrics.py` | per-turn metrics | Territory, blocking, proximity, mobility |
| `telemetry.py` | `collect_all_player_metrics`, deltas | Per-move impact tracking |

See [`docs/engine/move-generation-optimization.md`](../engine/move-generation-optimization.md).

## `mcts/` — search

| File | Key symbols | Role / Layer |
|---|---|---|
| `mcts_agent.py` | `MCTSAgent`, `MCTSNode` | Full tree search; selection/expansion/rollout/backup; ~50 params (Layers 3–9) |
| `state_evaluator.py` | `BlokusStateEvaluator` | 8-feature static eval, phase weights (Layers 4, 6) |
| `opponent_model.py` | `BlockingTracker`, `KingMakerDetector`, `OpponentModelManager` | Opponent modeling (Layer 7) |
| `parallel.py` | worker fns | Root (multiprocessing) + tree (virtual loss) parallelization (Layer 8) |
| `zobrist.py` | `ZobristHash`, `TranspositionTable` | Transposition tables |
| `move_heuristic.py` | `compute_move_heuristic` | Move scoring for ordering + rollouts |
| `learned_evaluator.py` | `LearnedWinProbabilityEvaluator` | GBT model eval (Layer 2; not recommended) |
| `search_trace.py` | `SearchTrace`, `IterationRecord` | Per-node diagnostics for visualization |
| `champion_profile.py` | `CHALLENGE_CHAMPION_PROFILE`, `build_mcts_kwargs` | Reproducible gameplay profile |
| `adaptive_budget.py` | `AdaptiveBudgetController` | Time-budget adaptation for Challenge mode |
| `mcts.py` | (legacy) | **Deprecated** — superseded by `mcts_agent.py`; appears unused |

## `analytics/` — measurement

9 subpackages: `tournament/` (arena harness `arena_runner.py`, `scheduler.py`,
`statistics.py`, `elo.py`, `trueskill_rating.py`, `aggregate.py`, `tuning*.py`),
`metrics/` (territory, blocking, proximity, mobility, pieces, corners, center),
`baseline/` (branching factor, iteration efficiency, Q-value convergence, seat
bias, plots), `winprob/` (35-feature extraction), `heatmap/` (visit-count
renderer), `logging/` (game logger, reader, schemas), `aggregate/` (game/agent
aggregation, phase split), plus `plot_style.py`.

## `agents/` — baselines & adapters

`random_agent.py` (`RandomAgent`), `heuristic_agent.py` (`HeuristicAgent`),
`registry.py` (dynamic construction), `gameplay_protocol.py` /
`gameplay_human.py` (human play). Agent construction for the arena lives in
`analytics/tournament/arena_runner.py::build_agent`, which **rejects**
`fast_mcts` / `gameplay_fast_mcts` (archived as invalid).

## Frontend (`frontend/src/`)

Pages under `pages/` (Home, Benchmark, TrainEval, Analysis, History,
RecruiterStoryPage), components under `components/` (Board, PieceTray, mcts-viz,
telemetry, ExplainMovePanel, GameConfigModal), Zustand stores under `store/`
(incl. `blokusWorker.ts` bridging to `browser_python/worker_bridge.py`). See
[`docs/frontend/README.md`](../frontend/README.md) and the
[Screen Inventory](../01-product/SCREEN_INVENTORY.md).

## Archived (not active)

`archive/agents/` (FastMCTSAgent — invalid tree search), `archive/rl/` (RL
configs, models, training docs), `archive/arena_runs/`, `archive/reports/`
(Layer 1–10 reports), `archive/docs/`, plus `docs/_archived-2026-05/` (see its
[ARCHIVE_RATIONALE.md](../_archived-2026-05/ARCHIVE_RATIONALE.md)).
