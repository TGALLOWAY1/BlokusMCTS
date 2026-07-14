# Current Status

_Update at the start and end of every session (protocol in `MASTER_PLAN.md` §6 / master prompt §3)._

## Session 2026-07-13/14 (session 11 — gate 3: FIRST POSITIVE SCALING) — Phase 4 now PARTIAL

- **Current phase:** Phase 4 gate **PARTIAL — MORE EVIDENCE REQUIRED** (was FAIL-attributed).
  EXP-005: ridge-model leaves produce the first positive budget→strength signal of the
  investigation (avg rank monotonic 2.12→1.83→1.75; it500−it50 +5.71 pts p=0.054; anchor
  shut out at 0% first place) and beat rollout leaves' anchor margins at every rung
  (decisively at 500: +20.8 vs +11.0).
- **Work completed:** `mcts/value_model_evaluator.py` + `value_model_path` plumbing
  (MCTSAgent, build_agent, parallel config) + 5 unit tests; ridge artifact saved;
  `--value-model` ladder flag; EXP-005 run + full log entry; Phase 4 addendum 3.
- **Interpretation:** the evaluator-quality attribution is confirmed in reverse — changing
  ONLY the leaf value source turned scaling positive with search mechanics untouched. The
  45-feature family is NOT closed; saturation above ~150 iters at this evaluator quality is
  the next boundary.
- **Next recommended task:** EXP-006a (direct same-table model-500 vs rollout-500 test — the
  clean equal-budget criterion) and EXP-006b (150/500/1500 model-leaf ladder → saturation
  point → teacher budget D-008). Then, if both confirm: Phase 4 PASS, PW+model-leaf config
  formalized, and Phases 5→7 proceed. See `HANDOFF.md`.

## Session 2026-07-13 (session 10 — evaluator v1 models: gate 1 FAIL, feature ceiling found)

- **Current phase:** Phase 5/6 evaluator track. **EXP-004: D-015 gate 1 FAIL — informatively.**
  Non-linear models add nothing over ridge on the 45 rich features (R² 0.264/0.246/0.221;
  pairwise rank acc 0.682/0.680/0.664): **the feature representation, not model capacity, is
  the ceiling** — which also explains why historical linear refits plateaued.
- **Gate 2 probe:** even so, the model as a leaf evaluator produces root Q-spread 4.6–6.3
  points (vs Layer-6's 1.3 flatness), 23% best-child share, depth 5 — mechanically far more
  discriminating in-tree.
- **Work completed:** `training/experiments/value_model.py` (game-level held-out training,
  pairwise-rank discrimination metric, duck-typed `ValueModelLeafEvaluator` for the MCTS
  rich-leaf slot, Q-spread probe, joblib artifact + report); artifacts committed under
  `training/artifacts/value_models/v1/`.
- **Next recommended task (gate 3):** plumb a model-artifact leaf evaluator into arena agent
  configs (extend `RichLeafEvaluator` or `build_agent` to accept a joblib artifact) and run
  the fixed acceptance ladder with the RIDGE model (best on all metrics) vs the EXP-002
  rollout baseline. If it fails, D-015's consequence clause closes the
  state-value-on-45-features family and Phase 6 candidate-scoring design begins with the
  ladder result as its calibration baseline. See `HANDOFF.md`.

## Session 2026-07-12 (session 9 — evaluator track v1: dataset generation)

- **Current phase:** Phase 5/6 evaluator track (Phase 4 gate open as acceptance test).
- **Work completed:** D-015 recorded (v1 scope: data / target / features / framework / gates);
  `training/experiments/value_dataset.py` — manifested fresh-dataset generator (standard
  scoring, PW+rollout-50 teacher self-play, per-ply `rich_blokus_v1` capture, never touches
  the legacy corpus); smoke-tested (292 rows/game, ~2 min/game); **`data/value_dataset_v1/`
  generation launched** (60 games, seed 20260713, 150-min deadline, ~17k rows expected).
- **Next recommended task:** when the dataset finalizes — train v1 models (sklearn GBM/MLP,
  held-out split) vs the linear baseline; then the D-015 gates in order: held-out skill →
  root Q-spread probe (must beat the 1.3-point Layer-6 flatness) → the fixed Phase 4
  acceptance ladder. See `HANDOFF.md`.

## Session 2026-07-12 (session 8 — EXP-003) — PHASE 4 FAIL ATTRIBUTED: evaluator is the ceiling

- **Current phase:** Phase 4 gate **FAIL — ATTRIBUTED** (stays open as the acceptance test
  for evaluator work). Search mechanics exonerated. The rescue pivots to Phase 5/6 with a
  narrow mandate: build a leaf evaluator that discriminates moves.
- **EXP-003 result (24/24 games, one variable = static-eval leaves):** the entire strength
  margin over the heuristic anchor VANISHED (all rungs ≈ heuristic, p ≥ 0.46; anchor tops
  the table) — vs EXP-002's +11..+16 pts at p ≤ 0.0006 with rollout leaves. The Layer-6
  evaluator adds nothing beyond the ordering prior; rollouts carry all current signal but
  saturate (no scaling).
- **Combined attribution across EXP-001/002/003:** tree shape → fixed by PW; rollout noise →
  real but secondary; **static evaluator quality → the binding ceiling**; backup/selection →
  exonerated. Full table in `phases/PHASE_4_SEARCH_SCALING.md` addendum 2.
- **Acceptance test for any new evaluator:** this exact ladder (`--pw --cutoff 0`, same
  seeds/protocol) must beat the EXP-002 rollout baseline at equal budget AND show positive
  scaling. Phases 7–8 stay blocked until then.
- **Next recommended task:** see `HANDOFF.md` — evaluator improvement track (Phase 5/6-lite):
  candidate direction is a move/state discriminating evaluator trained from strong-rollout
  self-play labels; decisions D-005/D-006/D-007 now become active.

## Session 2026-07-12 (session 7 — Phase 4 remediation: EXP-002 PW ladder) — GATE STILL OPEN

- **Current phase:** Phase 4, remediation loop. Gate remains **FAIL/OPEN** after EXP-002.
  Phases 5–8 stay blocked.
- **EXP-002 result (24/24 games, one variable = progressive widening):** tree-shape pathology
  fixed (pre-probe: 23% best-child visit share, depth 4 at 500 iters) and absolute strength
  up — it500 22.2%→31.2%, TS μ 14.5→24.2; ALL rungs now beat the heuristic anchor decisively
  (+11..+16 pts, p ≤ 0.0006). **But budget→strength is still flat** (50 ≈ 150 ≈ 500). With
  concentration repaired, the remaining suspect is the value signal (rollout deltas /
  static-eval mix adds nothing beyond the ordering prior at these budgets).
- **Next recommended task — EXP-003 (value-signal isolation):** same PW ladder with
  `rollout_cutoff_depth: 0` (pure static-eval leaves, deterministic). Scaling appears →
  rollout noise was the blocker (Phase 5 direction confirmed). Still flat → the Layer-6
  evaluator is the ceiling; the rescue pivots to leaf-evaluation quality with search
  mechanics exonerated. Then a 1500-iter PW rung; then C / visit-floor probes.
- **Also:** PR #197 carries EXP-002 (review feedback on per-agent params addressed). PW is
  NOT adopted into any config until a scaling run passes.

## Session 2026-07-12 (session 6 — Phase 4: search-scaling gate) — PHASE 4 GATE: FAIL

- **Current phase:** Phase 4 — gate **FAIL** (`phases/PHASE_4_SEARCH_SCALING.md`).
  **Phases 5–8 (all learning work) are BLOCKED** until a scaling re-run passes.
- **Headline result (EXP-001, 24 games, round_robin, standard scoring):** no positive scaling
  over a 10× budget span; 500 iterations trends WORSE than 50/150 (TS μ 14.5 vs ~35;
  paired diffs −4.1/−5.9, p=0.28/0.15); all budgets beat the heuristic anchor (it50 p=0.0007).
- **Mechanism established (root-statistics probe):** budgets below the ~300+ branching factor
  give every child exactly 1 visit → max-visits ties → the agent plays the ordering
  heuristic's top move; at 500, revisits follow single-rollout noise and override the
  ordering. No functioning search signal at practical budgets — this coherently explains the
  training plateau (nightly evals at 50–250 iters could not express evaluator improvements).
- **Work completed:** `training/experiments/search_scaling.py` (reproducible gate CLI:
  pinned iteration budgets, round_robin, deadline, Wilson/TrueSkill/paired-permutation
  reporting, --reanalyze); timing calibration; EXP-001 run + full log entry; mechanistic
  probe; PR #196 review feedback addressed (avg-rank metrics).
- **Tests added:** none (experiment session; harness smoke-tested end-to-end).
- **Current blockers:** Phase 4 remediation — EXP-002 (progressive-widening ladder) is the
  next distinguishing experiment; see `HANDOFF.md`.
- **Next recommended task:** EXP-002, same protocol, one variable: `progressive_widening_
  enabled` (pw_c=2.0, α=0.5). Then selection-robustness probes if needed. No default escapes.

## Session 2026-07-12 (session 5 — Phase 3: minimal trusted search) — PHASE 3 GATE: PASS (after fix)

- **Current phase:** Phase 3 **complete** (gate PASS after the D-014 fix —
  `phases/PHASE_3_MINIMAL_SEARCH.md`); next is the mandatory Phase 4 scaling gate.
- **Defect found & fixed:** rollout rewards used LEAF-board score baselines, erasing the
  immediate-gain differential between sibling moves in end-of-game rollouts (pocket position:
  both children Q = 0.0, correct move chosen only by tie-break). Fix: `rollout_reward_baseline
  ="root"` default (D-014); A/B pinned in tests (leaf → 0.0/0.0 blind; root → 5.0/1.0 exact).
  Plausible plateau contributor. Era note added to `DATA_LINEAGE.md`.
- **Work completed:** `mcts_lab/node_stats.py` CLI (root-children table, tree size, depth
  histogram; takes `board_state_v1` JSON or seeded plies; `run_search_with_root` doubles as
  the test harness); `tests/test_minimal_search_semantics.py` (9 tests: layer-off defaults,
  visit conservation, pass-node sentinel, terminal reward vectors, determinism, the A/B pin).
- **Tests passing:** search group (minimal-semantics + maxn + tactical) 17/17; layer/contract
  suites re-run green; `mcts_lab.checks` 7/7; bounded sanity arena (champion 62.5% first-place
  over 4 games at 100 ms — no collapse; not a strength claim).
- **Observed for Phase 4:** the CLI makes the branching-vs-budget pathology visible — 317
  legal moves at 16 plies: 200 iterations → pure depth-1 tree; 1 500 iterations → depth 2 with
  visit concentration. This is exactly what the scaling study must quantify.
- **Next recommended task:** Phase 4 — strength-vs-iteration-budget study under
  `BENCHMARK_PROTOCOL.md` conditions (fixed pool/seeds/seat policy, iteration budgets e.g.
  50/150/500/1500/5000), building on `training/diagnostics/search_quality.py`. Mandatory gate:
  larger budgets must convincingly beat much smaller ones before ANY learning work.

## Session 2026-07-12 (session 4 — Phase 2 task 3: versioned formats + serialization) — PHASE 2 GATE: PASS

- **Current phase:** Phase 2 **complete** (gate PASS — see `phases/PHASE_2_TRUSTED_ENGINE.md`);
  next is Phase 3.
- **Work completed:** `STATE_SCHEMA_VERSION="board_state_v1"` + `Board.to_dict()/from_dict()`
  (authoritative fields persisted; bitboards/frontiers rebuilt from grid);
  `ACTION_SCHEMA_VERSION="move_v1"` + `Move.to_dict()/from_dict()`; arena game records stamp
  `state_schema_version`/`action_schema_version`/`scoring_mode` beside `audit_version`;
  decision D-013 (TD corpus columns untouched — append-only header immutability); Phase 2 gate
  report written.
- **Tests added:** `tests/test_board_serialization.py` (10: full copy()-field round-trip on
  fresh/midgame/terminal boards through real JSON, Zobrist-hash match, behavioral equivalence,
  restored-board independence, version/malformed-payload guards, Move round-trip);
  provenance-stamp assertions in `tests/test_arena_play_quality.py`.
- **Tests passing:** engine group 98/98 (incl. new suites); `mcts_lab.checks` 7/7; end-to-end
  arena run shows all three stamps in `games.jsonl`.
- **Tests failing:** none.
- **Unexpected finding:** live incremental frontiers hold stale entries for non-placing
  players by design (`update_frontier_after_move` maintains only the mover's set) — harmless
  (frontier = candidate superset, movegen re-checks legality; differential harness proves
  move-set equality), now documented in `Board.from_dict`, which restores canonical form.
- **Next recommended task:** Phase 3 — verify the minimal trusted search (`MCTSAgent` with all
  experimental layers off): correctness tests on hand-authored tactical/near-terminal/
  single-move/pass positions, deterministic seeded-search assertions on visit counts and
  per-player Q values, and a node-statistics inspection CLI (build on `mcts/search_trace.py`).
  Then the mandatory Phase 4 scaling gate.

## Session 2026-07-12 (session 3 — Phase 2 task 2: property tests + differential harness)

- **Current phase:** Phase 2 (trusted engine), tasks 1–2 of 3 complete.
- **Current phase gate:** reference↔optimized agreement at scale ✔ (this session) + property
  tests ✔ + versioned state/action formats (task 3, open).
- **Work completed:**
  - `tests/test_engine_properties.py` — seeded full-game invariant suite (every ply of 3 full
    games): occupancy monotonicity, piece-inventory conservation incl. `player_last_piece`,
    strict turn rotation, grid↔bitboard duality + pairwise-disjoint player masks, independent
    score recomputation, terminal-implies-no-moves, deep clone independence, same-seed
    reproducibility (decision D-012: hand-rolled seeded loops, no hypothesis).
  - `tests/test_engine_differential.py` — full-game reference↔optimized harness: naive
    full-scan movegen + grid legality vs frontier movegen + bitboard legality, cross-checked
    every ply (mover move-set equality; all four players on a stride; legality agreement on
    sampled legal + perturbed placements; pass-detection equality; terminal scores incl. the
    standard bonuses recomputed from the raw grid). Scales via `BLOKUS_DIFF_GAMES`.
- **Tests passing:** properties 4/4 (2 s); differential 1/1 at default 3-game scale (14 s,
  ≥240 move-set + ≥300 legality checks asserted) and at 20-game scale (94 s, ≥1 600 move-set +
  ≥2 000 legality checks) — zero disagreements. `mcts_lab.checks` 7/7.
- **Tests failing:** none.
- **Note for task 3:** a board serialization **round-trip test is not possible yet** — the
  engine has no board deserializer (only `grid.tolist()` snapshots). It lands with the
  versioned state/action formats in task 3.
- **Next recommended task:** Phase 2 task 3 — versioned state/action schema surfaced in
  self-play records + serialization round-trip; then the Phase 2 gate report.

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
