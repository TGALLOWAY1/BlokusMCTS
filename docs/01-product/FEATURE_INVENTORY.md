# Feature Inventory

> Status/behavior view of every major feature. Last audited: 2026-05-28.
> The per-file feature *listing* lives in the root [`FEATURES.md`](../../FEATURES.md);
> this doc adds **status labels**, evidence, and known issues.
>
> Labels: `Implemented | Partial | Stubbed | Broken | Designed only | Deprecated | Unknown`.

## Game engine

| Feature | Status | Evidence | Known issues |
|---|---|---|---|
| Bitboard board, 20×20, 4 players, 21 pieces | Implemented | `engine/board.py`, `engine/bitboard.py` | — |
| Frontier-based legal move generation | Implemented | `engine/move_generator.py` | mirrored in `browser_python/engine/` — drift risk |
| Advanced metrics (mobility, territory, blocking, proximity) | Implemented | `engine/advanced_metrics.py`, `engine/mobility_metrics.py` | — |
| Per-state telemetry / move deltas | Implemented | `engine/telemetry.py` | — |
| Pydantic game schemas | Implemented | `schemas/` | — |

## MCTS search

| Feature | Status | Evidence | Known issues |
|---|---|---|---|
| UCB1 tree search (select/expand/rollout/backup) | Implemented | `mcts/mcts_agent.py` | no dedicated core unit tests (see Testing Strategy) |
| Transposition tables (Zobrist) | Implemented | `mcts/zobrist.py` | — |
| Progressive widening (L3) | Implemented | `mcts/mcts_agent.py` | recommended: `pw_c=2.0, pw_alpha=0.5` |
| Progressive history (L3) | Implemented, not recommended | `mcts/mcts_agent.py` | no benefit; hurts with RAVE |
| Rollout policies random/heuristic/two-ply (L4) | Implemented | `mcts/mcts_agent.py` | `random` best; `heuristic` worst & 10× slower |
| Rollout cutoff depth + static eval (L4) | Implemented | `mcts/mcts_agent.py`, `mcts/state_evaluator.py` | depth 5 optimal |
| Minimax backup blending (L4) | Implemented | `mcts/mcts_agent.py` | helps only with rollouts; α=0.25 |
| RAVE (L5) | Implemented | `mcts/mcts_agent.py` | recommended: `rave_k=1000` (4× convergence) |
| NST rollout bias (L5) | Implemented | `mcts/mcts_agent.py` | inconclusive |
| Calibrated eval weights (L6) | Implemented | `data/layer6_calibrated_weights.json`, `mcts/state_evaluator.py` | 76% win rate vs defaults |
| Phase-dependent eval weights (L6) | Implemented, not recommended | `mcts/state_evaluator.py` | 0% win rate |
| Opponent modeling: alliance/king-maker/asymmetric rollouts (L7) | Implemented, not recommended | `mcts/opponent_model.py`, `mcts/mcts_agent.py` | no reliable advantage; ~2.4× slower |
| Root parallelization (L8) | Implemented | `mcts/parallel.py` | recommended: `num_workers=2, parallel_strategy=root` |
| Tree parallelization / virtual loss (L8) | Implemented, not recommended | `mcts/parallel.py` | GIL-bound; slower than single-thread |
| Adaptive rollout depth (L9) | Implemented | `mcts/mcts_agent.py` | recommended; 1.64× faster |
| Adaptive exploration constant (L9) | Implemented, not recommended | `mcts/mcts_agent.py` | harmful with RAVE (8% win rate) |
| Sufficiency threshold / loss avoidance (L9) | Implemented | `mcts/mcts_agent.py` | inconclusive |
| Learned GBT evaluator (L2) | Implemented, not recommended | `mcts/learned_evaluator.py` | ~26ms inference eats budget |
| Challenge Champion profile + adaptive budget | Implemented | `mcts/champion_profile.py`, `mcts/adaptive_budget.py` | — |
| Search-trace diagnostics | Implemented | `mcts/search_trace.py` | — |
| Legacy `mcts/mcts.py` | Deprecated | `mcts/mcts.py` | superseded by `mcts_agent.py`; appears unused |
| FastMCTSAgent | Deprecated | `archive/agents/fast_mcts_agent.py` | invalid tree search; rejected by arena runner |

## Agents & arena

| Feature | Status | Evidence | Known issues |
|---|---|---|---|
| Random / Heuristic baselines | Implemented | `agents/random_agent.py`, `agents/heuristic_agent.py` | — |
| Agent registry / gameplay adapters | Implemented | `agents/registry.py`, `agents/gameplay_*.py` | — |
| Arena CLI + ~35 config presets | Implemented | `scripts/arena.py`, `scripts/arena_config*.json` | — |
| Round-robin scheduling, deterministic seeding | Implemented | `analytics/tournament/scheduler.py` | — |
| TrueSkill / ELO / statistics | Implemented | `analytics/tournament/{trueskill_rating,elo,statistics}.py` | TrueSkill often unconverged at 25 games |
| Champion loop + registry + gated promotion | Partial | `scripts/champion_loop.py`, `data/champion_registry.json` | no validated champion yet |
| Self-improvement metric tracking | Implemented | `scripts/self_improve.py` | — |
| Throughput calibration (L10) | Implemented | `scripts/calibrate_throughput.py`, `data/throughput_calibration.json` | — |

## Analytics & metrics

| Feature | Status | Evidence |
|---|---|---|
| Per-move MCTS diagnostics logging | Implemented | `analytics/logging/` |
| 7 metric feature modules | Implemented | `analytics/metrics/` |
| Baseline analysis (BF, efficiency, convergence, seat bias) | Implemented | `analytics/baseline/` |
| Visit-count heatmaps | Implemented | `analytics/heatmap/renderer.py` |
| Win-probability features (35) | Implemented | `analytics/winprob/` |
| Arena visualization (layer plots) | Implemented | `scripts/generate_arena_visuals.py`, `arena_visuals/` |

## Frontend

| Feature | Status | Evidence |
|---|---|---|
| Interactive board + piece tray | Implemented | `frontend/src/components/{Board,PieceTray}.tsx` |
| In-browser MCTS (Pyodide WebWorker) | Implemented | `frontend/src/store/blokusWorker.ts`, `browser_python/worker_bridge.py` |
| MCTS visualization suite | Implemented | `frontend/src/components/mcts-viz/` |
| Move-impact telemetry panels | Implemented | `frontend/src/components/telemetry/` |
| Advanced config UI (Layer 3–9 controls) | Implemented | `frontend/src/components/GameConfigModal.tsx` |
| Arena Results / Layer Progression / Analysis / History pages | Implemented | `frontend/src/pages/{Benchmark,TrainEval,Analysis,History}.tsx` |
| Recruiter story page | Implemented | `frontend/src/pages/RecruiterStoryPage.tsx` |

## Backend / infra

| Feature | Status | Evidence |
|---|---|---|
| FastAPI gameplay + research routes | Implemented | `webapi/routes_gameplay.py`, `webapi/routes_research.py` |
| Research / deploy profiles | Implemented | `webapi/profile.py` |
| MongoDB integration | Implemented | `webapi/db/` |
| In-memory GameManager | Implemented | `webapi/game_manager.py` (no persistence — see Known Issues) |
| League infra (ELO, Plackett-Luce, DB) | Implemented | `league/` |
| CI pipeline | Designed only | no `.github/workflows/` |
| Generative-AI / LLM prompts in product | N/A | classical MCTS only — no prompt system |
