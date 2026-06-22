# Features

## Game Engine

- Bitboard board representation (20x20, 4 players, 21 pieces each) — `engine/board.py`, `engine/bitboard.py`
- Frontier-based move generation with bitboard optimization — `engine/move_generator.py`
- Advanced metrics: mobility, territory, blocking, corner proximity, center distance — `engine/advanced_metrics.py`, `engine/mobility_metrics.py`
- Per-state telemetry and diagnostics — `engine/telemetry.py`
- Pydantic game schemas (config, state, moves, updates) — `schemas/`

## MCTS Search Engine

- Full UCB1 tree search with configurable exploration constant — `mcts/mcts.py`, `mcts/mcts_agent.py`
- Transposition tables via Zobrist hashing — `mcts/zobrist.py`
- Progressive widening for action-space reduction (Layer 3) — `mcts/mcts_agent.py`
- Progressive history for move ordering (Layer 3) — `mcts/mcts_agent.py`
- Configurable rollout policies: random, heuristic, two-ply (Layer 4) — `mcts/mcts_agent.py`
- Rollout cutoff depth with static evaluation fallback (Layer 4) — `mcts/mcts_agent.py`
- Minimax backup blending (Layer 4) — `mcts/mcts_agent.py`
- RAVE (Rapid Action Value Estimation) with tunable equivalence constant (Layer 5) — `mcts/mcts_agent.py`
- N-gram Selection Technique (NST) for rollout bias (Layer 5) — `mcts/mcts_agent.py`
- Phase-dependent evaluation weights (early/mid/late) (Layer 6) — `mcts/state_evaluator.py`
- Regression-calibrated weights from 13K+ self-play states (Layer 6) — `data/layer6_calibrated_weights.json`
- Opponent modeling: alliance detection, king-maker awareness, adaptive profiles (Layer 7) — `mcts/opponent_model.py`
- Asymmetric rollout policies for opponents (Layer 7) — `mcts/mcts_agent.py`
- Root parallelization via multiprocessing (Layer 8) — `mcts/parallel.py`
- Tree parallelization with virtual loss (Layer 8) — `mcts/parallel.py`
- Adaptive exploration constant based on branching factor (Layer 9) — `mcts/mcts_agent.py`
- Adaptive rollout cutoff depth based on branching factor (Layer 9) — `mcts/mcts_agent.py`
- UCT sufficiency threshold (Layer 9) — `mcts/mcts_agent.py`
- Loss avoidance for catastrophic nodes (Layer 9) — `mcts/mcts_agent.py`
- Challenge Champion profile and adaptive human-play budget controller — `config/challenge_champion_config.json`, `mcts/champion_profile.py`, `mcts/adaptive_budget.py`
- Learned evaluator (GBT model) for state scoring (Layer 2) — `mcts/learned_evaluator.py`
- Move heuristic scoring — `mcts/move_heuristic.py`
- Search trace diagnostics (per-node Q-values, visits, depths) — `mcts/search_trace.py`

## Agents

- Random agent — `agents/random_agent.py`
- Heuristic agent — `agents/heuristic_agent.py`
- Full MCTS agent (Layers 1-9) — `mcts/mcts_agent.py`
- Agent registry for dynamic construction — `agents/registry.py`
- Gameplay protocol for human play — `agents/gameplay_protocol.py`, `agents/gameplay_human.py`
- Canonical agent interface (Phase 3): single `BlokusAgent` Protocol plus `AgentDecisionContext`/`AgentDecision` and a `decide()` front door that unifies the three historical calling conventions (`select_action`, `choose_move`, legacy RL `act`) behind thin adapters — `agents/interface.py`, `docs/02-architecture/AGENT_INTERFACE.md`
- Registry-backed champion contract (Phase 3): `load_champion()` resolves the validated champion from `data/champion_registry.json` (config path, validation date, gauntlet run path, win rate, TrueSkill, total games) and builds it through the canonical interface, failing clearly with `NoValidatedChampionError` rather than serving an unvalidated champion — `agents/champion.py`

## Arena & Tournament System

- Round-robin tournament scheduling with deterministic seeding — `analytics/tournament/scheduler.py`
- Arena CLI with configurable JSON experiments — `scripts/arena.py`
- 35+ arena configuration presets for layer experiments — `scripts/arena_config*.json`
- TrueSkill multi-player rating — `analytics/tournament/trueskill_rating.py`
- ELO rating — `analytics/tournament/elo.py`
- Bootstrap confidence intervals and permutation tests — `analytics/tournament/statistics.py`
- Seat-position bias analysis — `analytics/baseline/seat_bias.py`
- Arena statistics and aggregation — `analytics/tournament/arena_stats.py`, `analytics/tournament/aggregate.py`
- Self-improvement loop with metric tracking — `scripts/self_improve.py`
- Champion self-improvement loop: persistent champion vs 5-tier randomized challenger pool (14 agents), snapshot-driven evaluator recalibration with validation mini-tournament before weight promotion, versioned champion registry, TrueSkill tracking, and Markdown progress report — `scripts/champion_loop.py`, `data/champion_registry.json`, `data/champion_progress.md`. **Promotion rule:** an entry may only be labelled a champion when its registry record contains non-null `promotion_run_id`, `games_played`, `pairwise_vs_previous`, `pairwise_vs_pool_peer_500ms`, `pairwise_vs_pool_heuristic`, TrueSkill μ/σ, and `gate_pass=true`. See `docs/CHAMPION_PROGRESSION.md` for the canonical narrative and `docs/arena_run_registry.md` for run-level status.
- Champion arena: champion vs randomized pool with persistent TrueSkill, snapshot data collection, auto-promotion, and per-run markdown reports — `scripts/champion_arena.py`, `data/champion_state.json`, `data/champion_reports/`
- Champion gauntlet (Phase 2): one-command, multi-seed, four-way evaluation harness over the champion candidates (`champion_v1`, `champion_minimal`, `pool_peer_500ms`, `key_findings_best`). Pools games across deterministic seeds, ranks by TrueSkill conservative with Wilson-95 win-rate CIs, reports pairwise + seat-position records, and applies explicit promotion gates. Saves a timestamped run dir with `gauntlet_summary.{json,md}`; only updates `data/champion_registry.json` under `--promote` when every gate passes (otherwise prints "No validated champion promoted.") — `scripts/champion_gauntlet.py`, `analytics/tournament/gauntlet.py`, `config/pool_peer_500ms_params.json`, `config/key_findings_best_params.json`, `docs/CHAMPION_GAUNTLET.md`
- Wilson score confidence interval helper (shared by the gauntlet and parameter-tuning stats) — `analytics/tournament/statistics.py`
- Overnight training orchestrator (Phase 4): thin wrapper that chains self-play data generation → learned-evaluator fit → champion gauntlet validation into one resumable run with per-stage logs and a `manifest.json`. Supports `--dry-run`, `--resume`, and is **no-promote-by-default** (only forwards `--promote` to the gauntlet when explicitly set). Defaults data generation to the valid `mcts` agent (not archived `fast_mcts`) — `scripts/run_overnight_training.py`, `tests/test_run_overnight_training.py`
- Training & overnight runbook (Phase 4): documents the offline (non-RL) training pipeline, one-command path, artifact versioning, overnight strategy, and agent-assisted automation (Claude Code command + Codex `codex exec` prompt) — `docs/03-implementation/TRAINING_AND_OVERNIGHT_RUNS.md`, `.claude/commands/run-overnight-mcts.md`, `prompts/codex/overnight_mcts.md`
- Champion gauntlet reference run (v1): documented 40-game specification for champion vs Tier 3/4/5 challengers with snapshot collection and expected-outcome analysis — `arena_runs/champion_gauntlet_v1/`, `scripts/arena_config_champion_gauntlet.json`, `config/champion_arena_params.json`
- Champion gauntlet v2: extended 60-game run spec building on v1 baseline, adds heuristic Tier 0 anchor and se_ state-evaluator feature collection for evaluator regression — `scripts/arena_config_champion_gauntlet_v2.json`, `arena_runs/champion_gauntlet_v2/`
- Champion minimal candidate (v2 candidate): drops empirically-debunked features (phase weights, adaptive exploration, opponent modeling, sufficiency / loss-avoidance) and adds Layer 8 root parallelization (`num_workers=2, parallel_strategy="root"`) — designed from `KEY_FINDINGS.md` to be the minimum-viable validated stack for head-to-head against the bloated v1 champion — `config/champion_minimal_params.json`, `scripts/arena_config_night1_champion_reset.json`
- Overnight training roadmap 2026-05-14: 7-night plan that resets the champion before continuing the original program (Night 1 = champion_v1 vs champion_minimal vs pool_peer_500ms vs pool_heuristic; gated promotion; Nights 2–7 unchanged from prior roadmap with refit and headline statistical run) — `docs/overnight_training_roadmap_2026-05-14.md`
- Champion progression doc: single source of truth for the agent storyline — `champion_v1` is documented as a failed full-stack candidate (lost head-to-head to a same-budget peer at the 500 ms budget), `champion_minimal` is the current candidate, no agent is currently a validated champion, and `champion_v2`/`v3` are placeholders gated behind promotion criteria — `docs/CHAMPION_PROGRESSION.md`
- Arena run registry: per-run catalogue of recent arena runs (PRs #146–#148 + the planned champion-reset run) with status labels (`diagnostic_failure`, `candidate_validation`, `validated_baseline`, `superseded`, `invalid`, `planned`) and explicit "reusable for / not reusable for" columns — `docs/arena_run_registry.md`
- Persistent cross-session TrueSkill seeding via `load_ratings()` — `analytics/tournament/trueskill_rating.py`
- Arena snapshot rows enriched with state-evaluator (se_) features for direct evaluator regression without a separate data-collection pass — `analytics/tournament/arena_runner.py`
- Throughput calibration — `scripts/calibrate_throughput.py`, `data/throughput_calibration.json`

## Analytics & Metrics

- Per-move MCTS diagnostics logging (iterations, tree depth, visit entropy, Q-values) — `analytics/logging/`
- 7 feature extraction modules: territory, blocking, proximity, mobility, pieces, corners, center — `analytics/metrics/`
- Baseline analysis: branching factor, iteration efficiency, Q-value convergence, simulation quality — `analytics/baseline/`
- Heatmap visualization and spatial analysis — `analytics/heatmap/`
- Frontier-overlay board rendering from captured turn snapshots — `analytics/heatmap/renderer.py`
- Win probability modeling — `analytics/winprob/`
- Game aggregation and phase splitting — `analytics/aggregate/`
- Arena visualization generation (layer progression charts) — `scripts/generate_arena_visuals.py`, `arena_visuals/`

## Frontend

- React 18 + TypeScript SPA with Zustand state management — `frontend/`
- Interactive Blokus board with piece selection and placement (cursor-centered piece preview, optimistic-UI placement, cross-turn pre-selection) — `frontend/src/components/Board.tsx`, `frontend/src/components/PieceTray.tsx`, `frontend/src/utils/pieceUtils.ts`
- MCTS visualization suite: rollout histograms, UCT breakdown, exploration/exploitation charts — `frontend/src/components/mcts-viz/`
- Move impact panels: waterfall charts, strategy-mix radar, move-delta diverging bars — `frontend/src/components/telemetry/`
- Advanced MCTS configuration UI with Layer 3-9 parameter controls and layer presets — `frontend/src/components/GameConfigModal.tsx`
- Arena Results page with live pairwise win rate matrix, TrueSkill ratings, and agent config display — `frontend/src/pages/Benchmark.tsx`
- Layer Progression dashboard grouping arena experiments by MCTS layer with expandable result cards — `frontend/src/pages/TrainEval.tsx`
- Analysis page with MCTS diagnostics — `frontend/src/pages/Analysis.tsx`
- ExplainMove panel — `frontend/src/components/ExplainMovePanel.tsx`
- Game history browser with agent config badges and active layer indicators — `frontend/src/pages/History.tsx`
- Recruiter-facing story page reframed as "Engine → Laboratory" narrative: 12-section structure covering engine foundation, experimentation framework, controlled findings, evaluator calibration, systems insights, and explainability. Integrates 9 Gemini-generated editorial images, throughput data table, TrueSkill vs ELO explanation, regression methodology, and research references — `frontend/src/pages/RecruiterStoryPage.tsx`
- "Take the Tour" interactive guided experience at `/tour` (alias `/about`): a standalone, mobile-friendly, ~3-minute step tour with guided/overview modes, horizontal stage chips, progress dots + step counter, animated screen host (reduced-motion aware), keyboard + touch-swipe navigation, skip/restart, and a localStorage completion flag (`mcts-laboratory-tour-completed`). Eight screens — Rules, Complexity, Agents, Techniques, Evaluation, TrueSkill, Champion progression, and Play the Champion — built on a pure reducer (`useTourState`) with a metric adapter (`tourMetrics`) that uses live arena/champion data when available and clearly-labeled demo fallbacks otherwise. Runs without any MCTS search. Discoverable from the homepage via a "Take the Tour" link surfaced on the initial game-config modal (both deploy and research profiles) — `frontend/src/pages/TourPage.tsx`, `frontend/src/components/tour/`, `frontend/src/components/GameConfigModal.tsx`, `docs/TOUR_IMPLEMENTATION.md`
- Play the Champion demo (Phase 6): public, portfolio-facing flow to play a full game against the registry-backed validated champion. A start-modal card (`ChampionCard`) shows champion name/version, win rate, TrueSkill, total validation games, and validation date from `GET /api/champion`; an in-game banner (`ChampionBanner`) pins that metadata plus the scoring-mode badge, a live "Champion thinking…" indicator, and lightweight per-move diagnostics (time, simulations, depth, budget tier). Gracefully handles no-validated-champion (404), backend-unavailable, illegal moves, and game-over. The frontend never hardcodes a champion config path — it forwards the registry-resolved `agentConfig` from the API into the Pyodide worker — `frontend/src/components/ChampionCard.tsx`, `frontend/src/components/ChampionBanner.tsx`, `frontend/src/hooks/useChampion.ts`, `frontend/src/utils/championConfig.ts`, `frontend/src/components/GameConfigModal.tsx`, `frontend/src/pages/Play.tsx`, `docs/05-frontend/PLAY_THE_CHAMPION_DEMO.md`
- Persistent critical controls: hint/pass/save stay visible across AI turns (disabled when it isn't your turn) so the layout never shifts and no critical action is hidden — `frontend/src/pages/Play.tsx`, `frontend/src/__tests__/HeaderPersistence.test.tsx`

## Web API

- FastAPI REST backend — `webapi/app.py`
- Gameplay routes: game creation, moves, state management — `webapi/routes_gameplay.py`
- Research routes: training runs, analysis, history, trends, arena results — `webapi/routes_research.py`
- Arena results API: list and detail endpoints for tournament data (`/api/arena-runs`) — `webapi/app.py`, `webapi/routes_research.py`
- Champion metadata API (Phase 5): `GET /api/champion` returns the validated champion's name, version, config path, validation date, total games, win rate, TrueSkill, gauntlet run path, and notes by resolving the registry-backed loader (`agents.champion.load_champion_metadata`). Returns HTTP 404 with a clear reason when no validated champion exists — never silently serving an unvalidated config. Deploy-safe (read-only) — `webapi/app.py`, `webapi/routes_gameplay.py`
- Provisional champion promotion (Phase 6): `scripts/promote_layered_best.py` promotes `key_findings_best` — the "Best Configuration" from the Layer 1-9 assessment (`KEY_FINDINGS.md`) — as the registry's current champion (`v2`), **clearly labelled provisional / not gauntlet-validated**. Uses the documented layered-assessment metrics (win rate 0.54, TrueSkill prior μ=25.0; null total games / gauntlet path) so the public demo has a concrete opponent until a full gauntlet supersedes it. Preserves `v1`, writes a `.bak` — `scripts/promote_layered_best.py`, `data/champion_registry.json`, `docs/CHAMPION_PROGRESSION.md`
- Champion browser config (Phase 6): `GET /api/champion` also returns a browser-ready `agentConfig` (`{type, thinkingTimeMs, mcts:{...}}`) so the in-browser (Pyodide) "Play the Champion" demo can instantiate the **exact** validated agent without hardcoding a config path. `agents.champion.champion_browser_config()` loads the champion's validated config through the canonical loader and applies the same deterministic-budget → iteration-count translation as the arena's `build_agent`, stripping wrapper-only keys and forcing `num_workers=1` (Pyodide has no working multiprocessing, so root parallelization cannot run in-browser) — `agents/champion.py`, `webapi/app.py`
- Champion move serving (Phase 5): the gameplay factory resolves `agent_config.profile == "champion"` through the registry loader (`agents.champion.build_champion_gameplay_agent`), so a future "human vs champion" demo plays the validated champion with no hardcoded config path. Deploy validation accepts an all-champion MCTS lineup (cannot be mixed with difficulty presets or the challenge-champion profile) — `webapi/gameplay_agent_factory.py`, `webapi/deploy_validation.py`, `agents/champion.py`
- Scoring mode flag (Phase 5): games support `scoring_mode` of `standard` (standard Blokus: covered squares + all-pieces bonus) or `house` (standard plus non-standard corner/center positional bonuses used in prior experiments). `BlokusGame` defaults to `house` to preserve all historical arena/experiment behavior; the web API defaults public deploy play to `standard` and the research profile to `house`. The active mode is surfaced in `GameState.scoring_mode` — `engine/game.py`, `schemas/game_state.py`, `webapi/app.py`
- Game orchestration with full MCTSAgent (Layers 3-9) — `webapi/app.py`
- Agent factory using MCTSAgent with gameplay adapter — `webapi/gameplay_agent_factory.py`
- Challenge Champion gameplay profile with tier/cap/reason move stats — `webapi/gameplay_agent_factory.py`, `schemas/game_state.py`
- MongoDB integration — `webapi/db/`
- Research and deploy profiles — `webapi/profile.py`

## Browser-Side Execution

- Pyodide mirror of engine, MCTS, and agents — `browser_python/`
- WebWorker bridge for background computation — `browser_python/worker_bridge.py`
- Browser Challenge Champion gameplay using the full MCTS profile bundle — `browser_python/worker_bridge.py`, `frontend/public/blokus_core.zip`
- Browser "Play the Champion" gameplay (Phase 6): the worker builds the registry-backed validated champion from the `agentConfig` spec forwarded by the frontend (`profile == "champion"`), filtering it to the `MCTSAgent` signature so the exact validated agent is rebuilt client-side. Also plumbs `scoring_mode` from the game config into the in-browser `BlokusGame` (default standard for public play) and reports it in game state — `browser_python/worker_bridge.py`, `frontend/public/blokus_core.zip`
- Zero-backend Blokus gameplay in the browser

## League Infrastructure

- Self-play league management — `league/league.py`
- ELO tracking — `league/elo.py`
- Plackett-Luce ranking model — `league/pdl.py`
- League database — `league/db.py`

## Scripts & Tools

- Self-play data collection for evaluation refinement — `scripts/collect_layer6_data.py`
- Feature importance analysis (regression, SHAP) — `scripts/analyze_layer6_features.py`
- Eval model training and validation — `scripts/train_eval_model.py`, `scripts/validate_eval_model.py`
- MCTS profiler (time breakdown by phase) — `scripts/profile_mcts.py`
- TrueSkill computation from JSONL logs — `scripts/compute_trueskill_from_jsonl.py`
- Training data generation — `scripts/generate_training_data.py`
- Tournament runner (single-command) — `scripts/run_tournament.py`
- Frontier video generation for per-turn board snapshots — `scripts/generate_frontier_video.py`
- Legal-move-count plot generation from per-turn board snapshots — `scripts/plot_legal_move_counts.py`

## Nightly Training Pipeline

- Durable, resumable nightly self-play training orchestrator (time-budgeted; resumes from on-disk state every run, never starts over) — `training/nightly_run.py`
- Durable state layout under `training/state/` (`latest.json`, `champion.json`, `ratings.sqlite`, `history.jsonl`, `checkpoints/`, `selfplay_runs/`, `reports/`) reconstructable in full from disk — `training/__init__.py`, `training/state_store.py`
- Atomic state persistence (tmp + `os.replace`) + append-only JSONL history for partial-progress durability — `training/state_store.py`
- Append-only SQLite rating timeline (Elo + TrueSkill per agent per run; never overwritten) with cross-run rating seeding — `training/ratings_db.py`
- Candidate generation via Layer-6 evaluator-weight re-fit on accumulated self-play snapshots; rotating-opponent evaluation battery (vs champion, random, heuristic, previous + historical champions) under the 4-agent arena rule; conservative 6-gate promotion (reuses `analytics/tournament/gauntlet.py`) — `training/selfplay_core.py`
- Elo-improvement-oriented per-generation challenger mix: heuristic + recent checkpoint + MCTS variant, with a `WEAK_OPPONENT_PROB`=0.2 sprinkle of `random` to anchor the bottom of the rating ladder and broaden the snapshot corpus — `scripts/champion_loop.py` (`select_challengers`)
- Internal-only champion promotion (updates `training/state/`; opt-in `--promote-registry` to also update the deployed `data/champion_registry.json`) — `training/nightly_run.py`
- Human-strength Elo estimation (1200/1500/1700 anchors) with moving-average trend, uncertainty band, and no-fabricated-confidence rule — `training/human_estimate.py`
- Nightly status report (`training/status.md`: Summary / Daily Progress / Baseline Results / Human Strength Estimate / Training Trends / Risks) — `training/status_report.py`
- Deterministic diagnostics (regression, stagnation, rating instability, refit health, promotion drought) → `training/reports/latest_diagnosis.md` (always written) — `training/diagnostics.py`
- SMTP email digest from repo secrets, for both success and failure (graceful skip when unconfigured) — `training/email_summary.py`
- GitHub Actions training workflow: cron `0 */6 * * *` (every 6 hours, ~4 runs/day) + manual dispatch, concurrency guard (queues rather than cancels), commit-back of durable state, always-send email — `.github/workflows/nightly-mcts-training.yml`
- Pipeline guide (architecture, operations, self-hosted runner fallback, storage growth) — `docs/03-implementation/NIGHTLY_TRAINING.md`

## Testing

- Durable nightly training pipeline tests: state store/atomicity, append-only ratings DB, human-estimate math, status rendering, diagnostics, email, and resume/failure end-to-end — `tests/test_training_*.py`
- Layer-specific test suites (Layers 3, 5, 6, 7, 8, 9) — `tests/test_layer*.py`
- Core engine tests: legality, game over, pass, piece shapes, bitboard — `tests/`
- Integration tests: audit invariants, agent timeout, telemetry — `tests/`
- TrueSkill convergence testing — `tests/test_trueskill_rating.py`
- Analytics metrics tests — `analytics/metrics/tests/`
- Performance benchmarks — `tests/performance_test.py`

## Benchmarking

- Move generation benchmarks — `benchmarks/benchmark_move_generation.py`
- MCTS settings sweep benchmarks — `benchmarks/benchmark_mcts_settings.py`
- Self-play league benchmarks — `benchmarks/bench_selfplay_league.py`

## Data & Calibration

- Regression-calibrated evaluation weights — `data/layer6_calibrated_weights.json`
- Throughput calibration (iterations/ms by phase and depth) — `data/throughput_calibration.json`
- Sample search trace for diagnostics — `data/sample_search_trace.json`
