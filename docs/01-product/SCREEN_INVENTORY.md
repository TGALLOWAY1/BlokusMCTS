# Screen Inventory

> Frontend screens and their behavior. Last audited: 2026-05-28.
> Routes: [Route Inventory](../03-implementation/ROUTE_INVENTORY.md).
> Visual captures: [Screenshot Manifest](../08-visuals/SCREENSHOT_MANIFEST.md).

---

## Play
- **Route:** `/`, `/play` — **Status:** Implemented
- **Purpose:** Play Blokus and watch AI-vs-AI demos; primary public screen.
- **Primary actions:** start/configure game, place pieces, Run Demo Game,
  Pause/Step, Explain This Move.
- **Important components:** `Board.tsx`, `PieceTray.tsx`, `ExplainMovePanel.tsx`,
  `GameConfigModal.tsx`, mcts-viz + telemetry components.
- **Data dependencies:** in-browser Pyodide MCTS (`store/blokusWorker.ts` →
  `browser_python/worker_bridge.py`); backend gameplay API optional.
- **States:** loading shows Pyodide bootstrap; empty = new board; error if worker
  fails to init. (Detailed empty/error coverage: Unknown — verify in app.)

## RecruiterStoryPage
- **Route:** `/story` — **Status:** Implemented
- **Purpose:** "Engine → Laboratory" narrative for recruiters: findings,
  methodology, editorial images, throughput tables, references.
- **Important components:** `RecruiterStoryPage.tsx`; assets in `docs/story_images/`.

## TrainEval (Layer Progression dashboard)
- **Route:** `/train` — **Status:** Implemented
- **Purpose:** Groups arena experiments by MCTS layer with expandable result cards.
- **Data dependencies:** `/api/arena-runs` (+ `{run_id}`).
- **Note:** route/name are RL-era residue; content is MCTS layer progression.

## Benchmark (Arena Results / AI Scoreboard)
- **Route:** `/benchmark` — **Status:** Implemented
- **Purpose:** Live pairwise win-rate matrix, TrueSkill ratings, agent configs.
- **Data dependencies:** `/api/arena-runs`.

## History
- **Route:** `/history` — **Status:** Implemented
- **Purpose:** Browse past games with agent config badges and active-layer indicators.
- **Data dependencies:** `/api/history`, `/api/games`.

## Analysis
- **Route:** `/analysis/:gameId` — **Status:** Implemented
- **Purpose:** Per-game MCTS diagnostics, move-impact telemetry, replay.
- **Data dependencies:** `/api/analysis/{game_id}` (+ `/replay`, `/steps`, `/summary`).

## MctsVisualization
- **Route:** `/mcts-analysis` — **Status:** Implemented
- **Purpose:** MCTS search introspection (rollout histograms, UCT breakdown,
  depth-over-time). See [`docs/mcts-analysis-mode/`](../mcts-analysis-mode/).
- **Data dependencies:** in-browser search trace / `data/sample_search_trace.json`.

## TrainingHistory / TrainingRunDetail — Deprecated (RL-era)
- **Routes:** `/training`, `/training/:runId` — **Status:** Deprecated
- **Purpose:** Legacy RL training-run history/detail. Reads
  `/api/training-runs*` (legacy MongoDB records). Retained but not part of the
  current MCTS product story. See [Known Issues](../04-quality/KNOWN_ISSUES.md).

---

> Responsive/mobile behavior and full empty/loading/error-state coverage are
> **Unknown** from static inspection — confirm during the live-capture pass
> ([Visual Regression Plan](../08-visuals/VISUAL_REGRESSION_PLAN.md)).
