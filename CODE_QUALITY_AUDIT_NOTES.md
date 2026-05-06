# Code Quality Audit Notes

## Repository Map
- `engine/`, `agents/`, `mcts/`: core Python gameplay engine and search agents.
- `webapi/`: FastAPI service and route registration split by deploy-safe/research endpoints.
- `frontend/`: React + TypeScript SPA with game setup, telemetry, and analysis views.
- `browser_python/`: Pyodide mirror of engine/MCTS for browser-side execution.
- `analytics/`: metrics, tournament aggregation, logging schemas/readers.
- `scripts/`: arena runners, benchmarking, data generation, and analysis utilities.
- `tests/`: Python test suite, including engine, web API, telemetry, and optimization layers.

## Main Execution Paths
- Backend app startup: `run_server.py` -> `webapi/app.py` route registration.
- Tournament workflows: `scripts/arena.py` with JSON configs in `scripts/`.
- Frontend app startup: `frontend/src/main.tsx` -> `frontend/src/App.tsx`.
- Browser worker gameplay path: `frontend/src/store/blokusWorker.ts` + `browser_python/worker_bridge.py`.

## Build / Test / Lint Commands
- Python: `pytest` (targeted/full), optional script-level checks from `scripts/`.
- Frontend: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` (from `frontend/`).

## Initial Risk Areas
- `webapi/game_manager.py`: repeated player mapping logic, broad exception message exposure, and ad-hoc literal constants.
- Duplication across `engine/` and `browser_python/engine/` may drift over time; correctness depends on intentional mirroring.
- Large historical/archive surface (`archive/`) increases accidental dead-code confusion; active/runtime boundaries should remain explicit.

## Dead Code Removed
| File / Symbol | Reason Removed | Verification |
|---|---|---|
| _None removed in this pass_ | No confidently unreferenced production symbol was identified without deeper feature-level deprecation confirmation. | Searched code paths and tests; uncertain candidates deferred to open questions. |

## Duplicate Logic Refactored
| Area | Before | After | Reason |
|---|---|---|---|
| `webapi/game_manager.py` player conversions | Separate dict literals for engine<->schema conversion in two methods. | Shared module-level mapping constants and reverse map. | Removes duplicated mapping logic and prevents divergence. |

## Simplicity Refactors
| File | Problem | Change Made | Why It Is Simpler |
|---|---|---|---|
| `webapi/game_manager.py` | Repeated hard-coded board size / piece count literals. | Introduced named constants (`BOARD_SIZE`, `MAX_PIECE_ID`) and reused in loops. | Improves readability and makes intent explicit. |
| `webapi/game_manager.py` | Verbose cleanup loop with temporary list. | Replaced with list comprehension for IDs to remove. | Same behavior with less ceremony and clearer intent. |

## Naming Consistency Changes
| Old Name | New Name | Reason |
|---|---|---|
| `mapping` (local, repeated) | `ENGINE_TO_SCHEMA_PLAYER`, `SCHEMA_TO_ENGINE_PLAYER` | Domain-specific names avoid generic local duplicates and clarify ownership. |

## Type Safety Improvements
| Area | Issue | Change |
|---|---|---|
| `webapi/game_manager.py` agent container | `Dict[SchemaPlayer, Any]` hides expected interface. | Added `GameplayAgent` protocol-like union type alias for explicit callable contract (`choose_move`) plus `None` for human player. |

## Error Handling Improvements
| Area | Issue | Change |
|---|---|---|
| `webapi/game_manager.py` move execution | Raw exception text returned to clients. | Added internal logging and replaced API message with stable generic error response. |

## Tests Added or Updated
| Test | Behavior Protected |
|---|---|
| _No new tests added_ | Existing `tests/test_move_error_messages.py` and API-related tests cover touched behavior paths; this pass focused on low-risk refactor. |

## Quality Gate Results
| Command | Result | Notes |
|---|---|---|
| `pytest tests/test_move_error_messages.py tests/test_analysis_steps_endpoints.py` | Pass | Validates move error surfaces and key API endpoint stability after refactor. |

# Open Questions for Project Owner

## Product Direction
1. Should the in-memory `GameManager` remain a lightweight dev/deploy component, or should persistence/recovery become a production requirement?

## Architecture
1. Is `browser_python/` expected to remain a hand-maintained mirror of `engine/`/`mcts/`, or should synchronization tooling be introduced?

## Data Model
1. Are `piece_id` ranges guaranteed to remain `1..21`, or should this come from engine metadata instead of constants?

## UX Behavior
1. For backend move failures, should clients receive structured error codes (e.g., `NOT_YOUR_TURN`, `INVALID_MOVE`) rather than only message strings?

## Cleanup Decisions
1. Can any `archive/` modules be excluded from default tooling/test discovery to reduce maintenance surface and dead-code ambiguity?

## Deployment / Production Readiness
1. Should gameplay error logging include request/game correlation IDs for easier production debugging?
