# Data Model

> Core entities, persisted records, and data artifacts. Last audited: 2026-05-28.
> Dataset schemas (arena snapshots): [`docs/datasets.md`](../datasets.md).

## Engine entities (`engine/`)

### Board (`engine/board.py`)
- **Purpose:** authoritative game state.
- **Holds:** 20×20 occupancy (bitboard per player), per-player placed pieces,
  frontier cells, start corners (RED 0,0 · BLUE 0,19 · YELLOW 19,19 · GREEN 19,0).
- **Read by:** `LegalMoveGenerator`, `MCTSAgent`, `BlokusStateEvaluator`, metrics.
- **Mutated by:** `BlokusGame` on validated placement.
- **Constraints:** first move covers the player's start corner; same-color pieces
  touch only at corners (never edges).

### Piece / PieceGenerator (`engine/pieces.py`)
- 21 pieces per player (monomino…pentominoes), each with rotation/reflection
  orientations and placement offsets. Total 89 squares per player at full play.

### Move (`engine/move_generator.py`)
- **Fields:** piece id, orientation, anchor position (and resulting cells).
- **Created by:** `LegalMoveGenerator` (frontier + bitboard legality).

### GameResult (`engine/game.py`)
- Final scores, winner, dead/passed players. Score = squares placed − remaining
  piece penalty.

## API schemas (`schemas/`, Pydantic)

| File | Models | Purpose |
|---|---|---|
| `game_config.py` | game/agent config | Create-game payloads, agent params |
| `game_state.py` | board/player state, champion stats | API state representation |
| `move.py` | move + move response | Move requests/responses |
| `state_update.py` | incremental updates | WS/state-update messages |

These are the engine↔API boundary types; `webapi/game_manager.py` maps between
engine `Player` enum and schema players via
`ENGINE_TO_SCHEMA_PLAYER` / `SCHEMA_TO_ENGINE_PLAYER`.

## Persisted records (MongoDB `blokusdb`, research profile)

- **games / move_records** — created by `GameManager`; read by `/api/games`,
  `/api/analysis/*`, `/api/history`. Move records carry `stats`
  (`nodesEvaluated`, `timeSpentMs`, `maxDepthReached`, `topMoves`), `telemetry`,
  `isPass`/`isHuman`, ordering keys (`sequenceIndex`/`moveIndex`).
- **training-runs / evaluations** — legacy RL records served by
  `/api/training-runs*`. **Deprecated** (RL-era).

## Filesystem artifacts

### Arena run (`arena_runs/<ts>_<id>/`)
`summary.json` (+ `.md`), `games.jsonl`, `snapshots.{csv,parquet}` (per-move
state with 7 `se_` evaluator + 35 win-prob features), `run_config.json`. Read by
analytics and by `/api/arena-runs`.

### `data/layer6_calibrated_weights.json`
Three weight sets over the **8 evaluator features** (`squares_placed`,
`remaining_piece_area`, `accessible_corners`, `reachable_empty_squares`,
`largest_remaining_piece_size`, `opponent_avg_mobility`, `center_proximity`,
`territory_enclosure_area`):
- `single_weights` — recommended global calibration.
- `phase_weights` — `early`/`mid`/`late` variants (**not recommended**, 0% WR).
- `default_weights` — hand-tuned baseline.

### `data/champion_registry.json`
`current_version` + `versions{}`; each version record holds `promoted_at`,
`promoted_from`, `promotion_reason`, full MCTS `params` (incl. `state_eval_weights`),
and promotion-gate fields. Promotion rule: see
[`docs/CHAMPION_PROGRESSION.md`](../CHAMPION_PROGRESSION.md).

### Other `data/`
`throughput_calibration.json` (iter/ms by cutoff depth), `sample_search_trace.json`
(`depthOverTime` per-iteration array for the diagnostics UI).

## Open questions
- Is `piece_id` guaranteed `1..21`, or should it come from engine metadata?
  (`CODE_QUALITY_AUDIT_NOTES.md`.)
- Should live game state persist/recover beyond MongoDB logging?
