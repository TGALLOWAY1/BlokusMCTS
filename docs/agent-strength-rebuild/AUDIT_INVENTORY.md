# Audit Inventory — Component Trust Classification

Classification of every major subsystem, in the required audit format.
Confidence levels: Trusted / Mostly trusted / Unverified / Suspect / Known incorrect / Obsolete.
Migration actions: Reuse / Validate before reuse / Refactor / Rewrite / Remove / Archive.

Baseline commit: `cabe2dd7738daca661798d422ee487179640e34f` (2026-07-12).

---

## Engine — board & rules core

- **Subsystem:** Board state, move application, scoring
- **Location:** `engine/board.py` (674 lines), `engine/game.py` (465), `engine/pieces.py` (513), `engine/bitboard.py` (213)
- **Purpose:** Blokus rules: dual grid+bitboard state, placement, frontier tracking, turn order, terminal detection, scoring/ranking
- **Current implementations:** one; deliberately redundant internal paths (grid vs bitboard legality) kept for differential testing
- **Dependencies:** numpy only
- **Inputs/Outputs:** positions/pieces/players → mutated board, scores, `GameResult`
- **Correctness risks:** standard **+5 monomino-last bonus missing** from `Board.get_score` (board.py:562) although `AUDIT_REPORT.md` §3.8 claims scoring verified; default scoring mode is non-standard "house" (+5/corner, +2/center; game.py:25-38); incremental frontier is a correctness-sensitive cache (has a rebuild reconciler + tests); engine does not auto-skip blocked players (pass handling lives in callers — MCTS tree, rollout loop, `webapi/game_manager.py`)
- **Performance risks:** none blocking; `Board.copy()` is the MCTS hot path
- **Data risks:** none
- **Tests present:** `tests/test_engine.py`, `test_game_over_logic.py`, `test_game_result.py`, `test_frontier_basic.py` (incremental-vs-rebuild differential), `test_bitboard_basic.py`, `test_pieces_orientations.py`, `test_piece_shapes_match.py`, `test_pass_turn.py`
- **Tests missing:** property-based invariants (hypothesis), full-game reference↔optimized trajectory differential, standard-scoring tests incl. monomino bonus, serialization round-trip
- **Observed defects:** missing monomino bonus (vs standard rules)
- **Confidence:** Mostly trusted (as house-rules implementation); Suspect (as standard-rules implementation)
- **Recommendation / Migration action:** **Validate before reuse** — Phase 2: standard scoring + property tests + full-game differential harness

## Engine — legal move generation

- **Subsystem:** Move generation & legality
- **Location:** `engine/move_generator.py` (1309 lines)
- **Purpose:** legal move enumeration (frontier-based fast path; naive full-scan reference), bitboard/grid legality, `sample_legal_moves` for rollouts
- **Correctness risks:** three coexisting bitboard legality functions + grid path — equivalence currently test-enforced; env flags (`USE_FRONTIER_MOVEGEN`, `USE_BITBOARD_LEGALITY`, `USE_HEURISTIC_ANCHORS`) read at **import time** (move_generator.py:63-88) — config drift/repro risk; module-level shared generator singleton (write-once caches, read-safe)
- **Performance risks:** movegen dominates search cost (prior audit); already ~6× improved via sampled rollouts
- **Tests present:** `test_move_generation_equivalence.py` (frontier vs naive, incl. random midgame), `test_legality_bitboard_equivalence.py` (bitboard vs grid)
- **Tests missing:** equivalence under every env-flag combination; property tests
- **Confidence:** Mostly trusted
- **Recommendation:** **Validate before reuse** — designate naive+grid as the Phase 2 reference implementation; later move env flags to explicit config

## Search — canonical MCTS agent

- **Subsystem:** `MCTSAgent` + `MCTSNode`
- **Location:** `mcts/mcts_agent.py` (2452 lines)
- **Purpose:** the one production/search implementation: UCT selection, maxⁿ per-player vector backprop, configurable rollouts/leaf evals
- **Correctness risks:** post-fix maxⁿ semantics look right (`_backpropagation:2231` credits each node with the mover's reward; regression suite exists) but strength-vs-compute is **unproven** (Phase 4 gate); reward scale O(100) with C=1.414 is a deliberate but fragile near-greedy calibration; wall-clock budget mode is nondeterministic (repo convention avoids it); `_history_table`/`_nst_table` persist across moves within a game
- **Performance risks:** no tree reuse (rebuilds root each move — acceptable per plan until Phase 10); Zobrist hash recomputed O(400)/call
- **Tests present:** `test_maxn_backprop.py`, `test_tactical_positions.py`, `test_move_policy.py`, layer suites (3/5/6/7/8/9), `test_agent_interface_contract.py`, `test_agent_timeout_behavior.py`
- **Tests missing:** node-statistics assertions on hand-authored near-terminal positions at scale; scaling benchmark; determinism test matrix
- **Confidence:** core loop Mostly trusted; **experimental layers Unverified** (all pre-fix conclusions invalid)
- **Recommendation:** **Validate before reuse** (core, Phase 3–4). Experimental layers (RAVE, NST, minimax-backup, PW, opponent modeling, adaptive meta, tree-parallel): **Archive-in-place** — keep off, re-admit only via post-fix experiments; candidates for code removal in a later cleanup if Phase 10 doesn't resurrect them

## Search — supporting evaluators & policy

- **Location:** `mcts/state_evaluator.py` (Layer-6, 8 features, tanh squash), `mcts/rich_leaf_evaluator.py` (45-feature TD), `mcts/learned_evaluator.py`, `mcts/move_heuristic.py`, `mcts/move_policy.py` (log-linear, 4 features + per-piece bias), `mcts/search_profiles.py`
- **Correctness risks:** evaluator scale interacts with exploration constant; move policy top-1 agreement only 0.53 and self-distils toward the fixed heuristic (AUDIT_REPORT §7)
- **Confidence:** Mostly trusted mechanically; Unverified for strength contribution
- **Recommendation:** **Validate before reuse** (Phase 5 decides the leaf-eval path); `move_policy` expected to be **superseded** by the Phase 6 model

## Search — parallelism & transposition

- **Location:** `mcts/parallel.py` (root-parallel, derived seeds), tree-parallel path in `mcts_agent.py`, `mcts/zobrist.py` (TT, deterministic-only caching)
- **Correctness risks:** tree-parallel has documented races (GIL-tolerated) — excluded from trusted path; root-parallel is deterministic by construction but adds variance to merged stats
- **Recommendation:** root-parallel **Reuse** (teacher self-play throughput); tree-parallel **Archive** (do not use); TT **Reuse** as-is (deterministic-only)

## Agents & registry

- **Location:** `agents/{champion,heuristic_agent,random_agent,registry,base_agent,gameplay_protocol,interface}.py`
- **Correctness risks:** `agents/champion.py` reads `data/champion_registry.json` (v2 "key_findings_best") while training's champion is `training/state/champion.json` (gen140) — **two disagreeing sources of truth**; serving champion is NOT the validated training champion
- **Confidence:** Mostly trusted mechanically; Suspect as lineage
- **Recommendation:** **Reuse** code; **Decision required (Phase 9)** on a single promotion path training→serving

## Evaluation & arena

- **Location:** `analytics/tournament/{arena_runner,gauntlet,elo,trueskill_rating,...}.py`, `training/evaluation/{benchmark_pool,head_to_head,sequential,promotion_gate}.py`, `mcts_lab/eval.py`
- **Purpose:** seeded 4-seat arenas, benchmark_v2 pool, TrueSkill(PlackettLuce)+Elo+Wilson CI, Wald SPRT sequential screen, two-stage promotion gate
- **Correctness risks:** Elo-from-pairwise decomposition in a 4-player game is a known approximation (TrueSkill is primary — keep it that way); default seat policy `randomized` (round_robin exists and is used by SPRT — protocol should require it); screen noise ±72 Elo documented at small game counts
- **Tests present:** promotion gate, sequential eval, ratings, TrueSkill suites in `tests/`
- **Confidence:** Mostly trusted — the strongest part of the lab
- **Recommendation:** **Reuse**; codify as `BENCHMARK_PROTOCOL.md`; add matchup-matrix retention + non-transitivity checks (Phase 9)

## Training pipeline & approaches

- **Location:** `training/nightly_run.py`, `training/selfplay_core.py`, `training/approaches/*` (baseline, heuristic_tuning, mcts_param_sweep, td_learning, hybrid, policy_prior, progressive_widening, rich_leaf), `training/{td_learning,policy_learning,policy_selfplay,data_refresh}.py`
- **Correctness risks:** the approaches are linear refits over small corpora with **no held-out evaluation**; empirically they have produced 0 promotions in 39 generations and uniformly negative deltas — the approach family, not the plumbing, is the suspect
- **Data risks:** corpora are append-only CSVs; `--refresh-data` recency-caps but era-mixing is possible (see `DATA_LINEAGE.md`)
- **Confidence:** pipeline plumbing Mostly trusted (durable resume, atomic writes); approach *effectiveness* Suspect
- **Recommendation:** plumbing **Reuse**; approaches **Archive** as experiments — the Phase 6–8 policy/value loop replaces them as the candidate source

## State & ratings persistence

- **Location:** `training/state/{champion.json,latest.json,ratings.sqlite,checkpoints/,policy_weights.json,td_evaluator_weights.json,rich_leaf_weights.json}`, `training/{state_store,ratings_db,reporting_era}.py`
- **Confidence:** Mostly trusted (append-only DB, atomic saves, era cutoffs already implemented)
- **Recommendation:** **Reuse**; assets pinned by hash in `DATA_LINEAGE.md`

## Data corpora

- **Location:** `data/{champion_snapshots,td_trajectories,policy_targets}.csv`, `data/archive/`
- **Confidence / status:** per-file compatibility table in `DATA_LINEAGE.md` (pre-fix archive Incompatible; snapshots Suspect; td_trajectories Verified-tagged; policy_targets Suspect)
- **Recommendation:** **Archive** for the new loop — Phase 7 datasets start fresh with manifests; legacy corpora stay for the existing approaches only

## Automation

- **Location:** `.github/workflows/nightly-mcts-training.yml` (cron every 6 h — ACTIVE at baseline), `.claude/commands/run-overnight-mcts.md` (already promotion-guarded, manual)
- **Recommendation:** cron **Remove** (Phase 0; keep `workflow_dispatch`); skill **Reuse**

## Serving (webapi / frontend / browser bundle)

- **Location:** `webapi/`, `api-runtime/`, `frontend/`, `browser_python/worker_bridge.py`, `scripts/build_browser_core.sh`
- **Notes:** one-directional dependency UI→core; Pyodide bundle is a verbatim copy of `engine/ mcts/ agents/` (numpy-only constraint for Phase 6)
- **Confidence:** out of scope for strength work
- **Recommendation:** **Defer** — untouched until Phase 10/production integration

## Analytics / metrics / telemetry

- **Location:** `analytics/{logging,metrics,aggregate,winprob}`, `engine/{telemetry,advanced_metrics,mobility_metrics}.py`
- **Recommendation:** **Reuse** passively; not on the critical path

## Docs

- **Location:** `docs/` numbered buckets
- **Observed defects:** `docs/00-overview/DOCUMENTATION_INDEX.md` links many deleted files (hygiene debt, non-blocking)
- **Recommendation:** `docs/agent-strength-rebuild/` is now the governing planning layer; `docs/05-planning/CONTINUOUS_TRAINING_PLAN.md` is superseded for strategy (kept as history)
