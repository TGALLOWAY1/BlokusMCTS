# Decision Records

Format per governing master prompt §21. Statuses: Proposed / Accepted / Superseded.

---

## D-001 — Repository strategy: stay in the current repo

- **Date:** 2026-07-12
- **Status:** Accepted
- **Context:** The master prompt allows a rewrite or a new agent-focused repo. The July 2026
  cleanup already reduced the lab to one engine and one MCTS implementation.
- **Options considered:** (a) new `agent-core` repo inheriting validated pieces; (b) stay here
  with `docs/agent-strength-rebuild/` as the governing layer.
- **Evidence:** single engine/search implementations with real differential + regression tests
  (`tests/test_move_generation_equivalence.py`, `test_legality_bitboard_equivalence.py`,
  `test_maxn_backprop.py`); UI coupling is one-directional (webapi/frontend import core, never
  the reverse); evaluation infra (TrueSkill/SPRT/gate) is the strongest subsystem and would have
  to be ported wholesale; no neural training stack exists yet to isolate.
- **Decision:** stay in `MCTS_Laboratory`. Legacy experiment surfaces are archived-in-place via
  `AUDIT_INVENTORY.md` classifications rather than physically moved.
- **Consequences:** less migration risk and immediate reuse of eval infra; discipline required
  to keep new datasets/models from silently mixing with legacy ones (see `DATA_LINEAGE.md`).
- **Revisit conditions:** Phase 6 model work makes the Pyodide/serving coupling or repo weight a
  concrete obstacle; or the archive surfaces materially slow CI/test cycles.
- **Related:** `MASTER_PLAN.md` §3, `AUDIT_INVENTORY.md`.

## D-002 — Target ruleset: standard Blokus scoring

- **Date:** 2026-07-12
- **Status:** Accepted (explicit user decision, session 1)
- **Context:** Engine default is the non-standard "house" mode (+5/controlled corner,
  +2/center square; `engine/game.py:25-38`). Standard Blokus is coverage + 15 all-pieces bonus
  + 5 monomino-last. The monomino bonus is **not implemented** in `Board.get_score`
  (`engine/board.py:562`), although `AUDIT_REPORT.md` §3.8 claims scoring was verified.
  The project goal is beating a skilled human, who plays standard rules.
- **Options considered:** standard (implement bonus, retarget); keep house; defer to Phase 2
  experiments.
- **Decision:** **Standard Blokus scoring** is the training/evaluation objective. Phase 2
  implements the monomino-last bonus and makes `SCORING_MODE_STANDARD` the default for all new
  evaluation. House mode remains available for historical comparability only.
- **Implemented:** 2026-07-12 (Phase 2 task 1) — `Board.player_last_piece` + the +5 bonus in
  `Board.get_score`; `BlokusGame`, arena `RunConfig`, TD self-play, browser worker, and API
  schema defaults flipped to standard; protocol bumped to `rescue_v2`. Tests:
  `tests/test_standard_scoring.py`.
- **Consequences:** historical arena results (house-scored) are not directly comparable to
  post-Phase-2 results; benchmark baselines must be re-anchored under standard scoring
  (recorded in `BENCHMARK_PROTOCOL.md` as a protocol version bump when it happens).
- **Revisit conditions:** none anticipated; a product decision to ship house-rules play would
  add a secondary objective, not replace this one.
- **Related:** Phase 2 in `MASTER_PLAN.md`; risk #3 in the Phase 1 report.

## D-003 — Phase 0 freeze method: drop the cron, keep workflow_dispatch

- **Date:** 2026-07-12
- **Status:** Accepted
- **Context:** `.github/workflows/nightly-mcts-training.yml` runs every 6 h with
  `contents: write`, appending corpora and refreshing ratings — exactly the uncontrolled data
  generation Phase 0 must stop.
- **Options considered:** delete the workflow; disable via repo UI (not reproducible in-code);
  remove `schedule:` and keep `workflow_dispatch`.
- **Decision:** remove the `schedule:` trigger, keep `workflow_dispatch` so deliberate,
  attended runs remain possible with the full input surface.
- **Consequences:** **GitHub reads cron schedules from the default branch — the freeze takes
  effect only when this branch merges to `main`.** Until then, 6-hourly runs continue and may
  append to corpora/ratings; the asset hashes in `DATA_LINEAGE.md` are pinned to the baseline
  commit, so later drift is detectable.
- **Revisit conditions:** the Phase 7+ pipeline earns back a scheduled run under the new gates.
- **Related:** `phases/PHASE_0_FREEZE.md`.

## D-004 — Branch naming: harness-designated branch

- **Date:** 2026-07-12
- **Status:** Accepted
- **Context:** The generic master prompt suggests `agent-rescue/phase-*` branches; the execution
  environment designates `claude/agent-rescue-master-plan-i9kvwf` and forbids pushing elsewhere.
- **Decision:** all rescue work develops on the designated branch (per session), merged to
  `main` via PR; phase identity is carried by commit messages and `phases/` reports instead of
  branch names.
- **Related:** session protocol in `CURRENT_STATUS.md`.

## D-012 — Property tests: hand-rolled seeded invariant loops, no hypothesis (for now)

- **Date:** 2026-07-12
- **Status:** Accepted
- **Context:** Phase 2 task 2 requires property/invariant tests. The master plan flagged
  `hypothesis` as a candidate tool; the repo has no property-testing framework and its existing
  invariant suites (`tests/test_frontier_basic.py`, `tests/test_bitboard_basic.py`) are
  hand-rolled loops over seeded random self-play.
- **Options considered:** adopt `hypothesis` (shrinking, broader input distribution, new dev
  dependency + CI cost); extend the existing hand-rolled seeded-trajectory pattern.
- **Decision:** hand-rolled seeded full-game invariant loops
  (`tests/test_engine_properties.py`), consistent with the repo's existing pattern; every ply
  of real games is checked, seeds are fixed, failures reproduce exactly.
- **Consequences:** no automatic input shrinking; coverage is bounded by the seeded
  trajectories rather than adversarial generation.
- **Revisit conditions:** an engine bug slips past these suites, or Phase 2 differential
  testing needs adversarial position generation the trajectories don't reach.
- **Related:** Phase 2 in `MASTER_PLAN.md`; `tests/test_engine_differential.py`.

## D-013 — Engine state/action schema v1; TD corpus keeps its existing columns

- **Date:** 2026-07-12
- **Status:** Accepted
- **Context:** Phase 2 task 3 versions the state/action formats and surfaces them in self-play
  records. `data/td_trajectories.csv` is an append-only corpus with a fixed header — adding a
  column would misalign every existing row against the header, violating the DATA_LINEAGE
  immutability rule.
- **Decision:** `STATE_SCHEMA_VERSION = "board_state_v1"` (`engine/board.py`,
  `Board.to_dict/from_dict`; frontiers/bitboards rebuilt from the grid on load) and
  `ACTION_SCHEMA_VERSION = "move_v1"` (`engine/move_generator.py`, `Move.to_dict/from_dict`,
  matching the shape already persisted by game_history/webapi/schemas). Arena game records
  stamp both plus `scoring_mode`. The TD corpus is NOT modified — its rows already carry
  `feature_set_version` + `agent_version` provenance; raw-state schema ids belong to the
  Phase 7 fresh-manifest datasets.
- **Consequences:** every new arena game is provenance-complete; the browser worker's
  frontend-orientation remap is explicitly outside `move_v1` (documented at the constant).
- **Revisit conditions:** Phase 7 dataset design (D-007) supersedes this for training data.
- **Related:** `phases/PHASE_2_TRUSTED_ENGINE.md`, D-007.

## D-014 — Rollout reward baseline: root-board deltas (fixing sibling-blind endgame values)

- **Date:** 2026-07-12
- **Status:** Accepted
- **Context:** Phase 3 node-level verification found both children of the endgame-pocket
  position at exactly Q = 0.0: `MCTSAgent._rollout` measured per-player rewards as score
  deltas from the expanded leaf's own board, subtracting the points banked by the move that
  created the leaf out of its own value. End-of-game rollouts (the only ones returning
  deltas — cutoff-hit rollouts return static evals) could not distinguish sibling moves whose
  difference was immediate banked points. The tactical regression test passed only via
  move-ordering tie-break.
- **Options considered:** root-board baseline (constant per search → child values reflect true
  final-score differences, magnitudes unchanged in scale); absolute final scores (equivalent
  argmax, larger magnitudes vs C=1.414 calibration); leave as-is and rely on static-eval
  cutoff (leaves endgames blind).
- **Evidence:** deterministic probe — legacy baseline Q 0.0/0.0 and 40/40 visits; root
  baseline Q 5.0/1.0 (exact final-score difference) with correct visit dominance. Pinned as
  an A/B regression test in `tests/test_minimal_search_semantics.py`. Bounded post-fix sanity
  arena showed no collapse.
- **Decision:** `rollout_reward_baseline="root"` is the default; "leaf" retained strictly for
  A/B experiments; value validated in the constructor; propagated to root-parallel workers.
- **Consequences:** rollout rewards change for every MCTS agent including the champion —
  absolute ratings drift across this boundary (era note in `DATA_LINEAGE.md`). Reward-scale
  mix (score-delta+bonus vs tanh×100 static eval) unchanged and flagged for Phase 4/5.
- **Revisit conditions:** Phase 4 scaling results; Phase 5 leaf-evaluation selection may
  replace rollout deltas entirely.
- **Related:** `phases/PHASE_3_MINIMAL_SEARCH.md`; AUDIT_REPORT §3.1 (the sibling maxⁿ fix).

## D-015 — Evaluator track v1 scope (data source, target, features, framework)

- **Date:** 2026-07-12
- **Status:** Accepted (v1 scope; D-005/D-006/D-007 remain open for the full Phase 6 design)
- **Context:** Phase 4 FAIL is attributed to the static evaluator (EXP-003: swapping rollout
  leaves for Layer-6 static-eval leaves erased the entire margin over the heuristic anchor;
  Q spread across root moves ~1.3 points on a ~47 scale). The rescue needs a leaf evaluator
  that discriminates. Constraints: no torch in deps; browser serving is numpy-only; the
  existing 45-feature TD refits (`rich_leaf` etc.) already failed as candidates — a v1 must
  change more than the fitting pass, and everything must run on fresh standard-scored data
  (legacy corpora are house-scored, DATA_LINEAGE).
- **Decision (v1):**
  - **Data:** fresh manifested dataset `data/value_dataset_v1/` (never the legacy CSV),
    generated by `training/experiments/value_dataset.py`: self-play among four identical
    PW+rollout-50 agents (EXP-002-validated config family; 50 ≈ 500 in strength there),
    standard scoring, per-ply capture, `rich_blokus_v1` features, full manifest (commit,
    agent configs, seeds, schema ids).
  - **Target:** per-player normalized standard final score (primary), final rank
    (secondary) — matches the existing TD-row label machinery so v1 needs no new plumbing.
  - **Model family:** sklearn (gradient boosting and/or small MLP) with numpy-exportable
    inference; MUST use a held-out split (Phase 1 risk #6).
  - **Gates for v1, in order:** (1) held-out predictive skill vs the linear baseline;
    (2) root Q-spread probe ≫ the measured 1.3-point Layer-6 flatness; (3) the fixed
    Phase 4 acceptance ladder (`--pw --cutoff 0` with the new evaluator) must beat the
    EXP-002 rollout baseline at equal budget AND show positive scaling.
- **Consequences:** if v1 fails gate (2) or (3), the state-value-on-45-features family is
  falsified and Phase 6's candidate-scoring (move-level) architecture becomes the next
  design, with D-005/D-006/D-007 decided in full then.
- **Revisit conditions:** any v1 gate result; torch/other framework only via a new decision.
- **Related:** `phases/PHASE_4_SEARCH_SCALING.md` addendum 2, EXP-003, `HANDOFF.md`.

---

## Open decisions (required before their phases)

| ID (reserved) | Topic | Needed by | Notes |
|---|---|---|---|
| D-005 | Multiplayer value target — **v1 scoped 2026-07-12**: per-player standard final score (normalized) primary, final rank secondary; picked to match the TD-row label machinery; full target study deferred until a discriminating model exists | Phase 6 | v1 record below (D-015 context); revisit with the first model's calibration results |
| D-006 | Model framework — **v1 scoped 2026-07-12**: sklearn (GBM/MLP) with numpy-exportable inference; torch not in deps, browser path numpy-only | Phase 6 | v1 record below (D-015 context) |
| D-007 | State/action encoding schema (versioned) — v1 uses existing `rich_blokus_v1` 45 features (already versioned); candidate-scoring action representation remains the Phase 6 direction | Phase 6/7 | v1 record below (D-015 context) |
| D-008 | Teacher search budget | Phase 7 | Output of the Phase 4 scaling study |
| D-009 | Single champion lineage: training state vs `data/champion_registry.json` serving registry | Phase 9 | Two sources of truth currently disagree (gen140 vs v2) |
| D-010 | Production latency target & difficulty modes | Phase 10 | Measure first |
| D-011 | Rating methodology confirmation (TrueSkill-primary, matrices as evidence) | Phase 9 | Existing practice, needs a formal record |
