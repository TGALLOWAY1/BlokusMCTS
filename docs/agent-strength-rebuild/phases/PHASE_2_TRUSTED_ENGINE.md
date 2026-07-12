# Phase 2 — Establish a Trusted Game Engine

- **Purpose:** make the game rules an unquestionable source of truth — validated reference vs
  optimized implementations, the correct (standard) scoring objective, invariant coverage, and
  versioned state/action formats — before any search or learning work relies on them.

- **Work completed** (three tasks, PRs #192, #193, and this one):
  1. **Standard scoring (D-002):** `Board.player_last_piece` tracking + the missing standard
     +5 monomino-last bonus in `Board.get_score`; `SCORING_MODE_STANDARD` made the default for
     `BlokusGame`, arena `RunConfig` (new validated field), TD self-play, browser worker, and
     API schema; benchmark protocol bumped to `rescue_v2`.
  2. **Property + differential coverage:** `tests/test_engine_properties.py` (every-ply
     invariants over seeded full games) and `tests/test_engine_differential.py` (full-game
     reference↔optimized harness: naive full-scan movegen + grid legality vs frontier +
     bitboard). Decision D-012: hand-rolled seeded loops, no hypothesis dependency.
  3. **Versioned formats + serialization:** `STATE_SCHEMA_VERSION = "board_state_v1"` with
     `Board.to_dict()/from_dict()` (authoritative fields persisted; frontiers/bitboards
     rebuilt from the grid on load); `ACTION_SCHEMA_VERSION = "move_v1"` with
     `Move.to_dict()/from_dict()`; arena game records now stamp
     `state_schema_version`/`action_schema_version`/`scoring_mode` beside the existing
     `audit_version`. Decision D-013 scopes the TD corpus out (append-only header immutability).

- **Components changed:** `engine/board.py`, `engine/game.py`, `engine/move_generator.py`,
  `analytics/tournament/arena_runner.py`, `training/td_selfplay.py`,
  `browser_python/worker_bridge.py`, `schemas/game_state.py`, `webapi/app.py` (one default).

- **Tests added:** `tests/test_standard_scoring.py` (11), `tests/test_engine_properties.py`
  (4), `tests/test_engine_differential.py` (1 harness, ~900–6 000 cross-checks by scale),
  `tests/test_board_serialization.py` (10), provenance assertions in
  `tests/test_arena_play_quality.py`; guardrail repurposed to protect the Phase 0 freeze.

- **Experiments run:** none (engineering phase; scaled differential validation at
  `BLOKUS_DIFF_GAMES=20` ≈ 6 000 cross-checks, zero disagreements, 94 s).

- **Results / gate criteria → evidence:**
  | Criterion | Evidence |
  |---|---|
  | Reference and optimized engines agree across large randomized sets | Differential harness: move-set equality every ply, legality agreement on legal + perturbed placements, pass-detection + terminal-score equality; zero disagreements at 20-game scale (plus pre-existing equivalence suites) |
  | No unresolved mutation/cloning defects | Every-ply invariants + deep clone-independence tests; serialization round-trip preserves all `copy()`-captured fields |
  | Scoring is the correct (standard) target | D-002 implemented; all bonus combinations unit-tested; arena/ratings path mode-explicit |
  | State and action formats versioned | `board_state_v1` / `move_v1` + round-trip tests + stamps in every new arena game record |
  | Engine trusted enough to generate training data | All of the above; `mcts_lab.checks` 7/7; full engine group 98/98 |

- **Unexpected findings:**
  1. Live incremental frontiers accumulate stale entries for **non-placing** players
     (`update_frontier_after_move` maintains only the mover's set). Harmless — frontier is a
     candidate superset and movegen re-checks legality (differential harness proves move-set
     equality) — but documented now in `Board.from_dict`, which restores the canonical
     recomputed form.
  2. (Task 1) The Zobrist hash omits `player_last_piece`; only terminal-state rewards under
     deterministic-eval configs could ever collide. Accepted, documented in CURRENT_STATUS.
  3. (Task 1) `AUDIT_REPORT.md` §3.8's claim that scoring was fully verified was wrong — the
     monomino bonus was absent.

- **Gate criteria:** see table above.
- **Gate result:** **PASS.**

- **Remaining risks:** frontier staleness is tolerated, not eliminated (revisit only if a
  future consumer treats `get_frontier` as exact); house-scored historical data remains
  quarantined per `DATA_LINEAGE.md`; browser bundle picks up engine changes only on next
  `scripts/build_browser_core.sh` run.

- **Decision:** D-002 (implemented), D-012, D-013 in `../DECISIONS.md`.
- **Next phase:** Phase 3 — minimal trusted search verification (all-layers-off `MCTSAgent`
  correctness tests + node-statistics inspection utility), then the mandatory Phase 4
  search-scaling gate.

- **Reproduction commands:**
  ```bash
  python -m pytest tests/test_engine.py tests/test_engine_properties.py \
    tests/test_engine_differential.py tests/test_standard_scoring.py \
    tests/test_board_serialization.py tests/test_move_generation_equivalence.py \
    tests/test_legality_bitboard_equivalence.py tests/test_frontier_basic.py \
    tests/test_bitboard_basic.py -q          # engine group
  BLOKUS_DIFF_GAMES=20 python -m pytest tests/test_engine_differential.py -q  # scaled
  python -m mcts_lab.checks
  python -m mcts_lab.eval --agents heuristic,random --games 2 --seeds 20260620
  # then: head -1 <run_dir>/games.jsonl | python -m json.tool | grep -E "schema|scoring"
  ```

- **Artifacts:** PRs #192/#193/this PR; test suites listed above; provenance-stamped
  `games.jsonl` records under `training/state/selfplay_runs/`.
