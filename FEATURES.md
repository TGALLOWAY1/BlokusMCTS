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
- Rich leaf evaluator: optional 45-feature TD-learned linear value model evaluated **only at MCTS leaves** (once per simulation, never per rollout step), unlocking the rich features the 8-feature serving evaluator discards (`score_margin_vs_leader`, `rank_so_far`, mobility, territory). Cost-tiered feature subsets (`score` ≈0.8 ms/leaf default, `no_opp_mobility` ≈7 ms, `full` ≈15–25 ms) drop the expensive opponent-mobility enumeration; loads `rich_phase_weights` from the TD artifact with graceful fallback to the 8-feature evaluator. Default OFF, enabled via `rich_leaf_eval_enabled` — `mcts/rich_leaf_evaluator.py`, `mcts/mcts_agent.py`, `training/rich_features.py` (`extract_leaf_features`, `LEAF_FEATURE_SUBSETS`), A/B harness `scripts/ab_rich_leaf.py`
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
- Append-only SQLite rating timeline (Elo + TrueSkill per agent per run; never overwritten) with cross-run rating seeding; single-file rollback journal (`journal_mode=DELETE`, **not** WAL) so the committed `ratings.sqlite` stays durable when a CI job is killed mid-run (the git-ignored `-wal` sidecar previously lost writes and froze the timeline) — `training/ratings_db.py`
- Per-generation fresh-Elo persistence: each generation recomputes the champion's Elo, writes it to `latest.json`, and appends a `ratings.sqlite` timeline row — so a job killed mid-loop still records every completed generation's Elo instead of freezing the reported Elo at the last fully-finalised run (root-cause fix for "every nightly email reports the same Elo") — `training/nightly_run.py`
- **Per-game Elo trajectory**: the champion's Elo is recomputed and recorded after **every individual game** (generation self-play *and* candidate-eval games) into an append-only `game_elo` table, numbered with a single monotonic `game_number` that continues across runs — the fine-grained series that shows whether the rating distribution is actually drifting upward rather than only one coarse point per generation — `training/ratings_db.py` (`record_game_elos`, `champion_game_elo_series`, `max_game_number`), `training/nightly_run.py`
- Champion Elo trajectory **plot** rendered to `training/reports/elo_trend.png` (matplotlib, headless `Agg`): per-game curve with a least-squares trend line, best-so-far and human-target reference lines, and the latest value annotated; falls back to the per-generation series until per-game data accumulates; non-fatal if matplotlib is unavailable (email ships text-only) — `training/elo_plot.py`
- Candidate generation via Layer-6 evaluator-weight re-fit on accumulated self-play snapshots; rotating-opponent evaluation battery (vs champion, random, heuristic, previous + historical champions) under the 4-agent arena rule; conservative 6-gate promotion (reuses `analytics/tournament/gauntlet.py`) — `training/selfplay_core.py`
- Elo-improvement-oriented per-generation challenger mix: heuristic + recent checkpoint + MCTS variant, with a `WEAK_OPPONENT_PROB`=0.2 sprinkle of `random` to anchor the bottom of the rating ladder and broaden the snapshot corpus — `scripts/champion_loop.py` (`select_challengers`)
- Internal-only champion promotion (updates `training/state/`; opt-in `--promote-registry` to also update the deployed `data/champion_registry.json`) — `training/nightly_run.py`
- Human-strength Elo estimation (1200/1500/1700 anchors) with moving-average trend, uncertainty band, and no-fabricated-confidence rule — `training/human_estimate.py`
- Nightly status report (`training/status.md`: Summary / Daily Progress / Baseline Results / Human Strength Estimate / Training Trends / Risks) — `training/status_report.py`
- Deterministic diagnostics (regression, stagnation, **stale-Elo** [byte-identical Elo across ≥3 runs], **metrics-not-updated** [current `run_id` absent from the timeline], rating instability, refit health, promotion drought) → `training/reports/latest_diagnosis.md` (always written) — `training/diagnostics.py`
- **Champion-static regression guard**: the regression detector now takes a `champion_static` flag (no promotion has changed the champion within the window). When the champion config is unchanged, an Elo "drop" is sampling variance — not a skill regression — so the finding is downgraded from a 🟠 `regression` warn to a 🔵 `elo_variance` info that names the real cause (small-sample noise vs a rotating opponent/candidate set). This stops the report from flagging a phantom regression on a fixed agent (the headline "Champion Elo dropped 101… beyond noise floor" was a false positive — the champion has never been promoted off `gen0`) — `training/diagnostics.py` (`detect_regression`, `collect_findings`)
- SMTP email digest from repo secrets reading the **live `ratings.sqlite` timeline**: subject shows current Elo + Δ-vs-previous (`ELO 1042.7 (+12.4)`); body has a Summary (Δ-vs-previous, Δ-vs-best, best historical Elo), an **ELO Trend section led by the inline per-game Elo plot** (the `elo_trend.png` is embedded inline in HTML clients via `cid:` and attached as a downloadable file, with a compact recent-generations digest as the plain-text fallback — replacing the old wall-of-numbers table), a Match Breakdown (per-baseline win rates from the run's eval), a Diagnostics section, and Links/Artifacts. Multipart `mixed`/`alternative`/`related` message so text-only clients still get the full report. Works for success+failure; graceful skip when SMTP unconfigured — `training/email_summary.py`
- **Multi-agent report branding + provenance + stale-state guardrail**: the subject is `MCTS Lab Multi-Agent Training Report — <date> — <short_sha> — ELO …` (or `FAILED`/`INCOMPLETE`), and every body opens with a `## Run Provenance` header (workflow file, run id, commit SHA, branch, state timestamp, training mode). The single source of truth for "fresh multi-agent result" is `latest.json → last_approach_comparison`; when it is absent the subject is marked `INCOMPLETE` and the body carries a prominent `LEGACY / INCOMPLETE REPORT` banner so an old-style report can never silently masquerade as a fresh multi-agent success (root-cause fix for "still getting old-style emails after the migration") — `training/email_summary.py` (`build_provenance`, `Provenance`)
- **Report-freshness guardrail** (`training/verify_report_freshness.py`, stdlib-only): exit-code contract (`0` fresh multi-agent record for the current run, `1` none, `2` stale) used by the workflow's "Verify report freshness" step and by CI tests — `training/verify_report_freshness.py`
- **Explicit verdict + loud operational alerts**: every report now opens with a one-line `## <emoji> Overall: …` verdict (`✅ GOING WELL` / `⚠️ CAUTION` / `➖ STEADY` / `❌ NOT GOING WELL` / `🚨 ALERT`) followed by a dedicated `## Alerts` section, so whether things are going well is the first thing you read. Any arena that **terminated early** (time budget exhausted before an approach was evaluated), a **training that could not be done** (no approach produced a candidate, or zero games played), a **timeout / cancellation** (no `last_approach_comparison` persisted), a **too-few-games** inconclusive gate, or a **real Elo regression beyond the noise floor** becomes a 🚨 (run did not complete) or ❌ (bad result) alert; a clean run states `✅ No alerts` explicitly. The subject line is prefixed with `🚨` whenever any alert fires (and `FAILED`/`INCOMPLETE` subjects always are). The same verdict + alerts are mirrored onto the GitHub Actions run page via `$GITHUB_STEP_SUMMARY` and `::error::`/`::warning::` annotations — `training/email_summary.py` (`collect_alerts`, `overall_verdict`, `_emit_github_outputs`)
- **Multi-agent-era trend scoping**: the report's ELO trend, run-over-run / vs-best deltas, "best historical Elo", recent-generations digest, and the `elo_trend.png` plot are all restricted to the **multi-agent approach-comparison era** (`run_id >= MULTI_AGENT_EPOCH_RUN_ID`, the 2026-06-26 cutover), so pre-multi-agent legacy self-play runs no longer inflate "best historical" or distort the trajectory. The boundary is a single constant; the per-game plot is titled "(multi-agent era)" when scoped — `training/ratings_db.py` (`MULTI_AGENT_EPOCH_RUN_ID`, `since_run_id` on `recent_window`/`champion_elo_series`/`champion_game_elo_series`), `training/elo_plot.py`, `training/email_summary.py`
- **Game-granular, fairly-partitioned eval time budget**: the evaluation deadline is now enforced at three layers — (1) before each candidate's battery, (2) as a **fair per-candidate sub-deadline** (each remaining candidate gets an equal share of the time left, recomputed each iteration so a candidate that finishes early rolls its leftover forward), and (3) **inside each arena at game granularity** via `run_experiment(..., deadline=…)`. Previously the deadline was only checked between `(arena, seed)` sub-batteries, so the first candidate (`td`) ran its full 100-game battery to completion (~199 min against a 45-min budget) and every other approach was skipped for budget on *every* run — the "approach comparison" only ever evaluated one approach. A zero-game candidate (sub-deadline too tight for one game) is recorded as skipped-for-budget rather than emitting an unusable empty eval — `analytics/tournament/arena_runner.py` (`run_experiment` deadline), `training/selfplay_core.py` (`run_arena_inproc` deadline), `training/evaluation/head_to_head.py` (`evaluate_candidates` fair split)
- GitHub Actions training workflow: cron `0 */6 * * *` (every 6 hours, ~4 runs/day) + manual dispatch, runs the **multi-agent approach-comparison** entry point (`training.nightly_run --approaches`), concurrency guard (queues rather than cancels), a report-freshness guardrail step, commit-back of durable state, always-send email, and the job fails on **any** non-success training outcome (cancellation/timeout no longer shows green) — `.github/workflows/nightly-mcts-training.yml`
- Canonical workflow + email reference docs — `docs/training_workflows.md`, `docs/email_reporting.md`
- Pipeline guide (architecture, operations, self-hosted runner fallback, storage growth) — `docs/03-implementation/NIGHTLY_TRAINING.md`

## Approach-Comparison Framework (nightly default)

- Controlled approach-comparison nightly run: generates candidates from multiple strategies, evaluates the created ones against a **fixed benchmark pool with fixed seeds**, and promotes only on a statistical gate — replacing the "run more games and hope Elo improves" loop that never promoted in 102 generations — `training/nightly_run.py` (`run_approaches`), `--approaches/--games/--time-budget-minutes/--dry-run` CLI; overview `training/README.md`
- Candidate-generation approaches, each returning a `Candidate` with an explicit `created`/`reason` (never the vague "No candidate was learned this cycle") + a validated JSON artifact written to `training/artifacts/candidates/<approach>_<run_id>.json` — `training/approaches/{base,baseline_mcts,td_learning,heuristic_tuning,mcts_param_sweep,hybrid_td_mcts}.py`
- Stable evaluation + promotion: fixed benchmark pool (heuristic, random, best historical champion) with fixed seeds, head-to-head pooled battery, and a statistical promotion gate (beats champion H2H + positive Elo/TrueSkill Δ + conservative 6-gate + min games/seeds) — `training/evaluation/{benchmark_pool,head_to_head,promotion_gate,rating_analysis}.py`
- **Short eval gate** (`head_to_head.EVAL_MIN_TOTAL_GAMES = 20`, `EVAL_MIN_SEEDS = 2`): a single source of truth for how much evidence an evaluation must collect, shared by both gate layers (the gauntlet decision and `promotion_gate.GateThresholds`). Started short (20 games/candidate over 2 seeds, ~40 min at full strength) so all four approaches fit one CI run; a backlog item tracks A/B-testing a longer eval paired with a relaxed promotion gate — `training/evaluation/head_to_head.py`, `training/evaluation/promotion_gate.py`, `docs/05-planning/BACKLOG.md`
- Noise-aware reporting: approach-comparison table (Approach · Created · Games · Win% vs Champ · Elo Δ · TrueSkill Δ · Promoted · Reason) in `training/status.md` + email, full detail in `training/reports/approach_comparison.md`, and an Elo-noise-floor "is this move real?" check — `training/evaluation/report.py`, `training/status_report.py`, `training/email_summary.py`
- Dry-run state isolation: `--dry-run` prints the plan + per-approach verdicts and writes nothing to tracked state (artifacts + TD retrain go to a temp dir) — `training/nightly_run.py`
- Pipeline audit + diagnosis of why skill stalled (champion weaker than heuristic, learning loop never closed, Elo trajectory was noise, reports frozen at gen1) — `training/reports/training_audit.md`, `training/reports/training_diagnosis.md`

## Temporal-Difference Learning (opt-in)

- Rich Blokus-specific feature extraction (`rich_blokus_v1`, 45 features): a versioned, append-only **superset** of the 8 Layer-6 evaluator features adding mobility/move-space, corner/frontier, piece-inventory, territory/blocking, score/race, and board-position features; per-extraction `FeatureCache` memoises legal-move enumeration so a 4-player snapshot enumerates each player's moves at most once. Piece-count normalisation divisors derive from the engine's **actual** (non-standard: 1/1/2/6/11, area 88) piece set so no feature exceeds its bound — `training/rich_features.py`
- Durable per-game **trajectory store** (`data/td_trajectories.csv`): ordered per-player TD transitions with current- and next-state rich features, explicit `phase`/`next_phase`, plus raw outcome labels (final_score/rank, won_game, top_2_finish, score margins, winner_id); additive append, never touches `data/champion_snapshots.csv`; `annotate_next_phase` reconstructs `next_phase` for legacy rows — `training/trajectory_store.py`
- Self-play **trajectory collector** (`python -m training.td_selfplay`): self-contained game loop over arena agents that records per-player decision-point features and terminal labels; deterministic seeded runs — `training/td_selfplay.py`
- **TD(0) trainer** (`python -m training.td_learning`): phase-aware linear value model `V(s)=w·f(s)+b` over the rich feature space with configurable terminal-value blend (rank/score/margin), **calibrated final-score normalisation** (`--score-center`/`--score-spread`, default `(82, 19)` from the observed corpus mean — replaces the old hardcoded `(40, 20)` that saturated ~75% of terminal rows to `|v|>0.9`), γ, α, L2, error clipping, and `min_rows_per_phase`; **phase-correct bootstrap** — `V(s_{t+1})` uses the *next* state's phase model (all three models held + updated in an interleaved loop), fixing the prior phase-boundary approximation; projects learned weights onto the agent's 8 features (`WEIGHT_SCALE=0.30`) for an agent-compatible `state_eval_phase_weights`; writes a durable artifact (`training/state/td_evaluator_weights.json`) with agent + rich weights, training metrics (incl. target/prediction/feature variance), and config; `--dry-run` supported — `training/td_learning.py`
- TD **candidate builder**: `selfplay_core.build_candidate(learning_mode="td")` clones the champion (never mutated in place), swaps in TD-learned phase weights, and tags candidate metadata (`learning_method`, `feature_set_version`, `training_rows`, `td_loss`); metadata stripped before any config reaches the engine or is persisted as champion; `nightly_run --learning-mode td [--td-weights-path ...]` with automatic fallback to regression when no artifact exists. **Promotion gates unchanged** — `training/selfplay_core.py`, `training/nightly_run.py`
- TD in the **approach-comparison framework**: the first-class `td` and `hybrid` approaches re-train the value model and build candidates using `TDConfig`'s defaults, so the calibrated `score_center=82`/`score_spread=19` are what the nightly run trains with (no per-approach plumbing); created candidates are scored against the fixed benchmark pool and gated statistically. Pinned by `tests/test_training_approaches_td_calibration.py` — `training/approaches/td_learning.py`, `training/approaches/hybrid_td_mcts.py`
- Reporting: status report + email show a **Learning Method** section (regression vs temporal difference) with feature-set version, training rows, TD loss, loss trend, weight drift, mean abs TD error, rows-by-phase, and — on promotion failure — the failed gate, runner-up, head-to-head win rates, TrueSkill margin, games, and seeds; plus a **Strength** section (current/best Elo + TrueSkill, promotion frequency, improvement rate) and an **Experiment** section (most recent TD-vs-regression comparison + recommendation) — `training/status_report.py`, `training/email_summary.py`
- **Feature normalisation audit** (`python -m training.feature_audit`): per-feature finite/range/dominance/variance-share checks over a trajectory CSV or randomly-sampled boards; flags NaN/inf, out-of-range, and dominant features; markdown report — `training/feature_audit.py`
- **Trajectory quality diagnostics** (`python -m training.trajectory_diagnostics`): row counts; rows per phase/player/agent/rank/outcome; terminal vs non-terminal split; trajectories missing a terminal row; `next_phase` coverage; flags under-populated phases, rank skew, seat imbalance — `training/trajectory_diagnostics.py`
- **Learning diagnostics** (`training/learning_diagnostics.py`): per-phase feature-importance ranking, weight drift/stability between artifacts, and a durable `learning_history.jsonl` pairing training loss with candidate strength + the **loss→strength Pearson correlation** ("is optimising TD loss meaningful?") — wired into `nightly_run`
- **Experiment framework** (`python -m training.experiments.compare --baseline regression --candidate td --games N --seeds K`): runs regression candidate, TD candidate, champion, heuristic, and random under identical seeded conditions; pools games; reports wins/losses/draws, average rank, rank distribution, score margin, TrueSkill, Elo, and win-rate confidence intervals with an opinionated recommendation; reproducible experiment manifests + markdown reports — `training/experiments/{manifest,compare,report}.py`
- TD learning guide — `docs/TD_LEARNING.md`; pipeline audit — `docs/TD_AUDIT.md`; rich-feature information-loss analysis — `docs/RICH_FEATURE_ANALYSIS.md`; prioritised roadmap — `docs/LEARNING_ROADMAP.md` + authoritative `tasks/TODO.md`

## Testing

- Durable nightly training pipeline tests: state store/atomicity, append-only ratings DB (incl. per-game `game_elo` timeline), human-estimate math, status rendering, diagnostics, email (incl. plot attach/embed + per-game callout), Elo-trajectory plot rendering (per-game + per-generation fallback), and resume/failure end-to-end (incl. per-game Elo accumulation across runs) — `tests/test_training_*.py`
- TD learning tests: rich-feature numeric/finite/inventory/score correctness + cache reduction (`test_td_rich_features.py`), trajectory round-trip/ordering/terminal-labeling + `next_phase` annotation (`test_td_trajectory_store.py`), TD update mechanics — terminal vs bootstrap target, **phase-correct cross-boundary bootstrap**, clipping, L2, independent per-phase updates, projection within `WEIGHT_SCALE`, artifact shape (`test_td_learning.py`), and candidate integration — TD weights load, champion cloned not mutated, metadata recorded/stripped (`test_td_candidate_integration.py`) — `tests/test_td_*.py`
- Validation-infra tests: feature-normalisation audit incl. real-feature invariant (`test_feature_audit.py`), trajectory quality diagnostics (`test_trajectory_diagnostics.py`), learning diagnostics — importance/drift/correlation (`test_learning_diagnostics.py`), and the experiment framework — per-agent stats, arena construction, manifests, report rendering (`test_experiments.py`)
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
