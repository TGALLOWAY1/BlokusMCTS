# User Flows

> Core flows through the product. Last audited: 2026-05-28.
> Screens: [Screen Inventory](SCREEN_INVENTORY.md). Diagrams: [Flow Diagrams](../08-visuals/FLOW_DIAGRAMS.md).

## Flow: Run Demo Game (in-browser AI vs AI)
- **Goal:** Watch the MCTS agent play without any setup.
- **Entry point:** `/` (Play page) → "Run Demo Game".
- **Steps:** load page → Pyodide worker boots and loads `blokus_core.zip` →
  click Run Demo Game → AI-vs-AI match auto-plays → use Pause/Step to freeze.
- **Expected behavior:** each AI move computed locally in the WebWorker; board
  updates per move; no backend round-trips required.
- **Failure states:** Pyodide bootstrap failure (no AI moves). Slow first load
  while WASM downloads.
- **Relevant screens:** Play. **APIs:** none (in-browser).
- **Open questions:** mobile performance of in-browser MCTS — Unknown.

## Flow: Explain This Move
- **Goal:** Understand why the agent picked a move.
- **Entry point:** Play page, during/after an AI move → ExplainMove panel.
- **Steps:** agent runs MCTS → top candidate moves, visit counts, and Q-values
  surface in `ExplainMovePanel.tsx`.
- **Expected behavior:** ranked candidates with simulation stats from the
  search trace.
- **Relevant screens:** Play (+ MctsVisualization for deeper introspection).

## Flow: Human plays the AI (backend gameplay)
- **Goal:** Play a move-by-move game against the agent via the API.
- **Entry point:** `POST /api/games` (create) → game in `webapi/game_manager.py`.
- **Steps:** create game → `POST /api/games/{id}/move` (or `/pass`) →
  `/advance_turn` triggers the AI → repeat → `/finish`. Realtime updates via
  `WS /ws/games/{id}`.
- **Expected behavior:** server validates moves, runs `MCTSAgent` via the
  gameplay adapter, returns updated state + move stats.
- **Failure states:** invalid move / not-your-turn return a **generic** error
  message (raw exception text is logged server-side, not exposed — see
  [Security & Privacy Notes](../04-quality/SECURITY_AND_PRIVACY_NOTES.md)).
- **APIs:** `/api/games*`, `/ws/games/{id}`.
- **Open questions:** structured error codes (e.g. `NOT_YOUR_TURN`) not yet
  implemented; `last_move` not tracked (TODO in `game_manager.py`).

## Flow: View AI Scoreboard / Layer Progression
- **Goal:** Compare agent strength across experiments.
- **Entry point:** `/benchmark` (matrix) and `/train` (layer cards).
- **Steps:** page fetches `/api/arena-runs` → renders pairwise win-rate matrix,
  TrueSkill ratings, and per-layer expandable result cards.
- **APIs:** `/api/arena-runs`, `/api/arena-runs/{run_id}`.

## Flow: Analyze a finished game
- **Goal:** Inspect MCTS diagnostics and move impact for one game.
- **Entry point:** `/history` → pick a game → `/analysis/:gameId`.
- **Steps:** fetch `/api/analysis/{game_id}` (+ `/replay`, `/steps`, `/summary`)
  → render diagnostics, telemetry waterfalls, replay.
- **APIs:** `/api/history`, `/api/analysis/{game_id}*`.

## Flow: Run an arena experiment (researcher, CLI)
- **Goal:** Produce reproducible tournament results.
- **Entry point:** `python scripts/arena.py --config <cfg> [--num-games N --verbose]`.
- **Steps:** load config → `build_agent` constructs agents → round-robin games
  with deterministic seeding → write `arena_runs/<ts>_<id>/` artifacts.
- **Expected behavior:** `summary.{json,md}`, `games.jsonl`,
  `snapshots.{csv,parquet}`, `run_config.json`. Frontend `/benchmark` reads these.
- **Failure states:** `fast_mcts`/`gameplay_fast_mcts` agent types raise an error.
- **Relevant docs:** [`docs/arena.md`](../arena.md),
  [`docs/config/agents/QUICK_START.md`](../config/agents/QUICK_START.md).

## Flow: Calibrate evaluation weights (ML pipeline)
- **Goal:** Refit `BlokusStateEvaluator` weights from self-play.
- **Steps:** `scripts/collect_layer6_data.py` (self-play → parquet of 7+35
  features) → `scripts/analyze_layer6_features.py` (regression/RF/SHAP) →
  `data/layer6_calibrated_weights.json`.
- **Relevant docs:** [`docs/datasets.md`](../datasets.md), [`KEY_FINDINGS.md`](../../KEY_FINDINGS.md).
