# State Management

> Short reference. Last audited: 2026-05-28.

## Frontend (React)

- **Library:** Zustand (`frontend/src/store/`).
- **Game state:** held in a Zustand store; the in-browser MCTS runs off-thread in
  a WebWorker (`store/blokusWorker.ts`) bridging to
  `browser_python/worker_bridge.py`, so search does not block the UI.
- **Deploy profile flag:** `frontend/src/constants/gameConstants.ts`
  (`IS_DEPLOY_PROFILE`) gates research-only routes.
- **Data fetching:** REST calls to the FastAPI backend for arena/analysis/history
  (research profile); realtime games over `WS /ws/games/{id}`.

## Backend

- **Live games:** `webapi/game_manager.py` `GameManager` holds games **in
  memory** keyed by id — no persistence/recovery for in-flight games (MongoDB
  receives move/analysis records in the research profile).
- **Profiles:** `webapi/profile.py` selects research vs deploy at startup.

## Core (Python)

- Stateless services operate on an explicit `Board`; `MCTSAgent` builds a
  per-decision search tree and an optional `TranspositionTable` (`mcts/zobrist.py`).

See [Architecture](ARCHITECTURE.md) for the storage model and
[State leftover risks](../04-quality/KNOWN_ISSUES.md).
