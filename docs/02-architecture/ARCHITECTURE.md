# Architecture

> How the system works internally. Last audited: 2026-05-28.
> Module map + diagram: [System Map](SYSTEM_MAP.md). Data shapes: [Data Model](DATA_MODEL.md).

## System overview

Three cooperating subsystems share one Blokus engine:

1. **Core (Python)** — `engine/` (rules, board, move generation) + `mcts/`
   (search) + `agents/` (baselines). Pure compute, no I/O.
2. **Research/offline (Python)** — `scripts/` (arena CLI, calibration) +
   `analytics/` (metrics, tournament harness, ratings) write artifacts to
   `arena_runs/` and `data/`.
3. **Application (web)** — `webapi/` (FastAPI + MongoDB) serves gameplay and
   research data; `frontend/` (React) renders it and also runs the **same**
   engine + MCTS in the browser via Pyodide (`browser_python/`).

## Major modules

- **`engine/`** — `Board`, `Piece`/`PieceGenerator`, `LegalMoveGenerator`,
  `BlokusGame`/`GameResult`, bitboard ops, telemetry. The performance-critical
  core (frontier + bitboard legality).
- **`mcts/`** — `MCTSAgent` (UCB1 + Layers 3–9), `BlokusStateEvaluator`,
  `OpponentModelManager`, root/tree `parallel`, `ZobristHash`/`TranspositionTable`,
  `SearchTrace`, `LearnedWinProbabilityEvaluator`, `champion_profile`.
- **`analytics/`** — tournament harness (`arena_runner.py`), schedulers,
  ratings (TrueSkill/ELO), statistics, metrics, win-prob features, heatmaps,
  logging.
- **`webapi/`** — app assembly (`app.py`), route registration
  (`routes_gameplay.py`, `routes_research.py`), `GameManager` (in-memory game
  state), `gameplay_agent_factory`, profile switch, MongoDB (`db/`).
- **`frontend/` + `browser_python/`** — SPA + Pyodide WebWorker mirror.

## Runtime flows

- **Arena (offline):** `scripts/arena.py` → `arena_runner.run_arena` →
  `build_agent` per player → round-robin games over `engine/` + `mcts/` →
  snapshots + ratings → `arena_runs/<ts>_<id>/`.
- **Browser gameplay:** React store posts board state to the Pyodide WebWorker
  (`store/blokusWorker.ts` → `browser_python/worker_bridge.py`), which runs the
  engine + `MCTSAgent` and returns the move + search trace. **No backend
  involved.**
- **Backend gameplay:** `POST /api/games` → `GameManager` holds state →
  `advance_turn` invokes `MCTSAgent` via `gameplay_agent_factory` → move + stats;
  realtime over `WS /ws/games/{id}`; persisted to MongoDB (research profile).

## Data flow

`engine` produces game states → `analytics/winprob` + `BlokusStateEvaluator`
extract features → arena snapshots (`snapshots.parquet`) →
`analyze_layer6_features.py` regression → `data/layer6_calibrated_weights.json`
→ loaded back into `BlokusStateEvaluator`. This is the calibration feedback loop
behind the headline result.

## Auth / authorization

**None.** There is no authentication or route guard on the API (single-user
research tool). Noted as a risk in the [Risk Register](../04-quality/RISK_REGISTER.md).

## Storage model

- **MongoDB** (research profile): games, move records, analysis, legacy training
  runs. Database `blokusdb`. Deploy/gameplay profile and the arena CLI need no DB.
- **Filesystem:** arena run artifacts (`arena_runs/`), calibrated weights and
  registries (`data/`), pickled models (`models/`), plots (`arena_visuals/`).
- **In-memory:** `webapi/game_manager.py` `GameManager` (no persistence/recovery
  for live games beyond MongoDB logging).

## Important boundaries

- **Engine ↔ search:** `mcts/` depends on `engine/` but not vice versa.
- **Core ↔ web:** `webapi/` and `frontend/` depend on core; core has no web deps.
- **Python ↔ browser:** `browser_python/` is a **hand-maintained mirror** of
  `engine/` + `mcts/` + `agents/` compiled for Pyodide.

## Areas of architectural risk

- **Engine/browser mirror drift** — two copies of engine+MCTS must stay in sync;
  no automated sync tooling. (`CODE_QUALITY_AUDIT_NOTES.md`, Risk Register.)
- **In-memory game state** — `GameManager` has no recovery; a restart drops
  live games.
- **RL-era residue** — package metadata, `/training*` routes/pages, and
  `TrainEval` naming reflect the archived v1 identity.
- **MCTS-core test gap** — selection/expansion/backup lack dedicated unit tests.
- **Compute ceiling** — full rollouts are infeasible; all results are
  conditional on `rollout_cutoff_depth` 0/5/10.
