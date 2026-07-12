# Handoff

_For the next agent/session. Read `MASTER_PLAN.md`, `CURRENT_STATUS.md`, `DECISIONS.md`,
`EXPERIMENT_LOG.md`, and this file before doing anything._

## Where things stand (after session 1, 2026-07-12)

- The governing plan, audit, decisions, protocol, and lineage docs all live in this directory.
- Phase 0: cron trigger removed from `.github/workflows/nightly-mcts-training.yml`
  (`workflow_dispatch` kept). **Not effective until the PR merges to `main`** — until then the
  6-hourly nightly job keeps running and appending to `data/*.csv` + `training/state/`.
  If the merge is delayed, expect drift from the `DATA_LINEAGE.md` hashes (baseline commit
  `cabe2dd` is the authoritative pin).
- Phase 1: audit complete — `AUDIT_INVENTORY.md` + `phases/PHASE_1_FORENSIC_AUDIT.md`.
- Decisions taken: stay in this repo (D-001); **standard Blokus scoring is the target ruleset**
  (D-002, explicit user decision); freeze method (D-003); branch naming (D-004).

## Exact next action

**Phase 2, task 1:** implement standard scoring correctly.

1. Add the +5 monomino-last bonus to scoring (standard mode). Today `Board.get_score`
   (`engine/board.py:562`) only has coverage + 15 all-pieces; `engine/game.py:25-38` defines
   `SCORING_MODE_STANDARD`/`HOUSE` with house as default. The bonus needs "last piece played
   was the monomino" state — check what `game_history` already records before adding board
   state.
2. Unit tests: all four bonus combinations (none / +15 / +5 / +20), both scoring modes,
   ranking/`GameResult` under standard mode.
3. Make standard mode the default for `mcts_lab.eval` / benchmark runs; bump
   `BENCHMARK_PROTOCOL.md` to `rescue_v2` in the same commit; house mode stays available.
4. Then: property-test suite (consider `hypothesis` — new dev dependency, record a decision)
   and the full-game reference↔optimized differential harness
   (naive movegen + grid legality vs frontier + bitboard, thousands of positions).

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
4. Nightly job may still run until merge (see above).
5. `docs/00-overview/DOCUMENTATION_INDEX.md` has dead links (hygiene debt only).

## Session protocol reminders

- Update `CURRENT_STATUS.md` at session start/end; append experiments to `EXPERIMENT_LOG.md`
  when they run; record decisions in `DECISIONS.md`; phase reports in `phases/`.
- Never advance past a phase gate without evidence; failed gate → smallest distinguishing
  experiment (no default escapes, master prompt §20).
- Champion writes only via `mcts_lab.promote` / gated nightly path.
