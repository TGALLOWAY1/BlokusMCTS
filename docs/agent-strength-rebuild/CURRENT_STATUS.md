# Current Status

_Update at the start and end of every session (protocol in `MASTER_PLAN.md` §6 / master prompt §3)._

## Session 2026-07-12 (session 2 — Phase 2 task 1: standard scoring)

- **Current phase:** Phase 2 (trusted engine), task 1 of 3 complete.
- **Current phase gate:** reference↔optimized agreement at scale + property tests + versioned
  formats — **open** (tasks 2–3 pending). Task 1 (standard scoring) done.
- **Work completed:** +5 monomino-last bonus implemented (`Board.player_last_piece`, set in
  `place_piece`, copied in `Board.copy`, applied in `get_score` when all 21 pieces used);
  scoring defaults flipped to `SCORING_MODE_STANDARD` in `BlokusGame`, arena `RunConfig`
  (new field, validated, persisted in run configs), `training/td_selfplay.py`,
  `browser_python/worker_bridge.py`, and the `GameState` schema. House mode remains explicit
  opt-in. Benchmark protocol bumped to `rescue_v2`; scoring-era boundary recorded in
  `DATA_LINEAGE.md`.
- **Tests added:** `tests/test_standard_scoring.py` (11 tests: bonus combinations, last-piece
  tracking, copy independence, mode defaults, RunConfig round-trip/validation);
  `test_house_scoring_is_default` → `test_standard_scoring_is_default`.
- **Tests passing:** new suite 11/11; `test_engine` + `test_game_result` +
  `test_champion_serving_scoring` + `test_pass_turn` 60/60; `test_maxn_backprop` +
  `test_tactical_positions` 8/8; `test_arena_play_quality` + `test_audit_invariants` +
  `test_agent_interface_contract` 35/35; `mcts_lab.checks` 7/7. End-to-end seeded arena run
  verified (`scoring_mode: standard` persisted; identical outcomes on repeated same-seed runs).
- **Tests failing:** none.
- **Known accepted edge (verified):** the transposition table caches only feature-based
  evaluator results — no cached value depends on `get_score` — except terminal-state rewards
  under deterministic-eval configs, where the Zobrist hash (set-based piece tracking) cannot
  distinguish which piece was last. Requires all 21 pieces used + identical grid via different
  move order inside one search: negligible; revisit only if Phase 3 node-stats show anomalies.
- **Next recommended task:** Phase 2 task 2 — property-test suite + full-game
  reference↔optimized differential harness (see `HANDOFF.md`).


## Session 2026-07-12 (session 1 — plan, freeze, audit)

- **Current phase:** Phase 0 (freeze) + Phase 1 (forensic audit), executed together this session
  after the documentation-only checkpoint commit.
- **Current phase gate:**
  - Phase 0: no uncontrolled training scheduled; assets pinned; legacy data labeled.
    Status: **PASS** — PR #190 merged (`ea68caf`), the freeze is live on `main`, and no
    nightly run fired in the drift window (see `phases/PHASE_0_FREEZE.md`).
  - Phase 1: pipeline mapped, risks ranked, repo strategy decided. Status: **PASS**
    (see `phases/PHASE_1_FORENSIC_AUDIT.md`).
- **Most recent validated result:** EXP-000 baseline — champion gen140, Elo 1388.55,
  TrueSkill μ 54.39 σ 5.02; 39-generation promotion drought; all current candidates negative
  vs champion (`EXPERIMENT_LOG.md`).
- **Current blockers:** none.
- **Session objective:** documentation-only master-plan checkpoint → Phase 0 freeze →
  Phase 1 audit report. No engine/search/training code changes.
- **Files changed this session:** `docs/agent-strength-rebuild/**` (new),
  `.github/workflows/nightly-mcts-training.yml` (cron removed, dispatch kept),
  `docs/README.md` (index line).
- **Experiments planned/run:** EXP-000 (baseline snapshot, no new games).
- **Tests added:** none (docs + workflow-trigger change only). `python -m mcts_lab.checks`
  re-run as regression evidence.
- **Gate status summary:** Phase 0 PASS (post-merge); Phase 1 PASS.
- **Next recommended task:** Phase 2 — implement standard scoring (+5 monomino-last bonus,
  `SCORING_MODE_STANDARD` default for new evaluation) with unit tests, then the property-test
  suite and full-game reference↔optimized differential harness. See `HANDOFF.md`.
