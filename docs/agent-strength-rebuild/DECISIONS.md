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

---

## Open decisions (required before their phases)

| ID (reserved) | Topic | Needed by | Notes |
|---|---|---|---|
| D-005 | Multiplayer value target (normalized score vs placement vs pairwise vs mixed) | Phase 6 | Requires a Phase 5/6 experiment, not a preference |
| D-006 | Model framework & serving path (train-anywhere + numpy inference vs numpy-native; Pyodide constraint) | Phase 6 | Browser bundle currently ships numpy only |
| D-007 | State/action encoding schema (versioned) | Phase 6/7 | Candidate-scoring action representation preferred |
| D-008 | Teacher search budget | Phase 7 | Output of the Phase 4 scaling study |
| D-009 | Single champion lineage: training state vs `data/champion_registry.json` serving registry | Phase 9 | Two sources of truth currently disagree (gen140 vs v2) |
| D-010 | Production latency target & difficulty modes | Phase 10 | Measure first |
| D-011 | Rating methodology confirmation (TrueSkill-primary, matrices as evidence) | Phase 9 | Existing practice, needs a formal record |
