# Handoff

_For the next agent/session. Read `MASTER_PLAN.md`, `CURRENT_STATUS.md`, `DECISIONS.md`,
`EXPERIMENT_LOG.md`, and this file before doing anything._

## Where things stand (after session 1, 2026-07-12)

- The governing plan, audit, decisions, protocol, and lineage docs all live in this directory.
- Phase 0: **complete and live** — PR #190 merged (`ea68caf`); the nightly cron is removed on
  `main` (`workflow_dispatch` kept) and no nightly run fired between baseline `cabe2dd` and
  the merge, so the `DATA_LINEAGE.md` hashes remain exact. Gate: PASS.
- Phase 1: audit complete — `AUDIT_INVENTORY.md` + `phases/PHASE_1_FORENSIC_AUDIT.md`. Gate: PASS.
- Decisions taken: stay in this repo (D-001); **standard Blokus scoring is the target ruleset**
  (D-002, explicit user decision); freeze method (D-003); branch naming (D-004).

## Exact next action

**Phase 3 — minimal trusted search** (Phase 2 is COMPLETE, gate PASS:
`phases/PHASE_2_TRUSTED_ENGINE.md`).

The candidate minimal search already exists: `MCTSAgent` with **all experimental layers off**
(plain UCT + maxⁿ per-player vector backup, no tree reuse, deterministic-only TT, single
thread, iteration budgets). Phase 3 is verification, not a rewrite:

1. Search-correctness tests on hand-authored positions: near-terminal decisions with a known
   best move (extend `tests/test_tactical_positions.py`), single-legal-move positions,
   positions requiring passes (pass-node expansion), forced outcomes on reduced positions.
   Assert node internals, not just the chosen move: root visit counts, per-player Q values
   (mover-credited), terminal values, exploration behavior under fixed seeds.
2. Node-statistics inspection CLI (build on `mcts/search_trace.py`): dump root children with
   visits / per-player Q / prior ordering / depth histogram for any `Board.from_dict` position
   (the new serialization API is the intended input format).
3. Determinism matrix: same seed → identical tree stats across runs; iteration budgets only.
4. Contingency if verification fails: a ~300-line reference MCTS for differential comparison.
5. Then `phases/PHASE_3_MINIMAL_SEARCH.md` with the gate verdict, and on PASS proceed to the
   **mandatory Phase 4 scaling gate** (`MASTER_PLAN.md` §4; builds on
   `training/diagnostics/search_quality.py`).

Notes: browser bundle (`frontend/public/blokus_core.zip`) is generated — next
`scripts/build_browser_core.sh` run picks up engine changes; never edit `browser_python/`
module copies. Zobrist/TT terminal-state edge + frontier-staleness finding documented in
`CURRENT_STATUS.md`. Differential harness scales with `BLOKUS_DIFF_GAMES` (default 3; 20 ≈ 94 s).

## Commands to reproduce current results

```bash
python -m mcts_lab.checks                      # fast sanity gate (must pass before/after any change)
python -m pytest tests/ -q -n 4                # full suite (slow)
python -m mcts_lab.eval --agents champion,baseline --games 10 --seeds 20260620,20260621
sha256sum data/*.csv training/state/champion.json   # compare against DATA_LINEAGE.md
```

## Unresolved questions / known risks

1. **Does more search produce stronger play post-fix?** (Phase 4 gate — the critical unknown;
   prior audit measured effective depth-1 search at nightly budgets.)
2. **Why are all candidates weaker than the champion?** Working hypothesis: the linear-refit
   approach family is exhausted; alternative: an evaluation/config subtlety. Phase 4/5
   experiments will discriminate.
3. **Dual champion registries** (`training/state/champion.json` gen140 vs
   `data/champion_registry.json` v2) — serving champion is not the validated training champion.
   Decision D-009 reserved for Phase 9; do not "fix" this casually, the web demo depends on it.
4. `docs/00-overview/DOCUMENTATION_INDEX.md` has dead links (hygiene debt only).

## Session protocol reminders

- Update `CURRENT_STATUS.md` at session start/end; append experiments to `EXPERIMENT_LOG.md`
  when they run; record decisions in `DECISIONS.md`; phase reports in `phases/`.
- Never advance past a phase gate without evidence; failed gate → smallest distinguishing
  experiment (no default escapes, master prompt §20).
- Champion writes only via `mcts_lab.promote` / gated nightly path.
