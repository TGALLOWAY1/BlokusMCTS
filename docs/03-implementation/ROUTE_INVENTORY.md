# Route Inventory

> Frontend routes and backend API endpoints. Last audited: 2026-05-28.
> Canonical API reference: [`docs/webapi/README.md`](../webapi/README.md).

## Frontend routes (`frontend/src/App.tsx`)

`/` and `/story` are always available; the rest are gated behind
`!IS_DEPLOY_PROFILE` (hidden in the Vercel deploy build).

| Path | Page component | Profile | Status |
|---|---|---|---|
| `/`, `/play` | `Play` | all | Implemented |
| `/story` | `RecruiterStoryPage` | all | Implemented |
| `/train` | `TrainEval` (Layer Progression dashboard) | research | Implemented |
| `/benchmark` | `Benchmark` (Arena Results / AI Scoreboard) | research | Implemented |
| `/history` | `History` (game history browser) | research | Implemented |
| `/analysis/:gameId` | `Analysis` (MCTS diagnostics) | research | Implemented |
| `/mcts-analysis` | `MctsVisualization` | research | Implemented |
| `/training` | `TrainingHistory` | research | Deprecated (RL-era) |
| `/training/:runId` | `TrainingRunDetail` | research | Deprecated (RL-era) |

> `/training*` and the `TrainEval` naming are residue from the v1 RL phase. The
> Layer Progression dashboard reuses the `/train` route; the `/training`
> history pages read legacy RL training-run records. See
> [Known Issues](../04-quality/KNOWN_ISSUES.md).

## Backend API (registered in `webapi/routes_*.py`)

### Gameplay profile (deploy-safe — `register_gameplay_routes`)

| Method | Path | Handler | Status |
|---|---|---|---|
| GET | `/health` | health | Implemented |
| GET | `/` | root | Implemented |
| POST | `/api/games` | create_game | Implemented |
| GET | `/api/games` | list_games | Implemented |
| GET | `/api/games/{game_id}` | get_game | Implemented |
| POST | `/api/games/{game_id}/move` | make_move | Implemented |
| POST | `/api/games/{game_id}/pass` | pass_turn | Implemented |
| POST | `/api/games/{game_id}/advance_turn` | advance_turn | Implemented |
| POST | `/api/games/{game_id}/finish` | finish_game | Implemented |
| GET | `/api/agents` | get_agents | Implemented |
| GET | `/api/arena-runs` | list_arena_runs | Implemented |
| GET | `/api/arena-runs/{run_id}` | get_arena_run | Implemented |
| WS | `/ws/games/{game_id}` | realtime game stream (`webapi/app.py`) | Implemented |

### Research profile (adds — `register_research_routes`)

| Method | Path | Handler | Status |
|---|---|---|---|
| GET | `/api/health/db` | health_check_db | Implemented |
| GET | `/debug/mongo` | mongo_debug | Implemented |
| GET | `/api/analysis/{game_id}` | get_game_analysis | Implemented |
| GET | `/api/analysis/{game_id}/replay` | get_game_replay | Implemented |
| GET | `/api/analysis/{game_id}/steps` | get_analysis_steps | Implemented |
| GET | `/api/analysis/{game_id}/summary` | get_analysis_summary | Implemented |
| GET | `/api/history` | get_history | Implemented |
| GET | `/api/trends` | get_trends | Implemented |
| GET | `/api/training-runs` | list_training_runs | Deprecated (RL-era) |
| GET | `/api/training-runs/{run_id}` | get_training_run | Deprecated (RL-era) |
| GET | `/api/training-runs/agents/list` | list_agents | Deprecated (RL-era) |
| GET | `/api/training-runs/{run_id}/evaluations` | get_training_run_evaluations | Deprecated (RL-era) |

Profiles are selected in `webapi/profile.py`; auto-generated OpenAPI docs are at
`/docs` when the server runs.
