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

**Phase 4 remediation — EXP-003: value-signal isolation.** The gate FAILED at EXP-001 and
remains OPEN after EXP-002 (PW ladder): progressive widening fixed the tree shape and raised
absolute strength (all rungs now crush the heuristic anchor, p ≤ 0.0006) but budget→strength
is STILL flat (50 ≈ 150 ≈ 500). Read `phases/PHASE_4_SEARCH_SCALING.md` incl. the EXP-002
addendum first. Phases 5–8 remain blocked.

1. **EXP-003 (one variable vs EXP-002):** same PW ladder/protocol, but budget agents get
   `rollout_cutoff_depth: 0` — pure static-eval leaves (deterministic, TT-cacheable; the
   `_rollout` depth-0 path returns `_evaluate_all_players`). Add a `--cutoff N` flag to
   `training/experiments/search_scaling.py` (keep --pw; label e.g. `pw_c0_b50_150_500`).
   Outcome A (scaling appears): rollout noise was the blocker → Phase 5 (replace rollouts
   with static/learned leaves) is the confirmed direction. Outcome B (still flat): the
   Layer-6 evaluator itself adds nothing beyond the move-ordering prior — search mechanics
   are exonerated and the rescue pivots to leaf-evaluation QUALITY (Phase 5/6), with the
   scaling gate re-run once a better evaluator exists.
   Note: cutoff-0 searches are much cheaper per iteration (no 12-ply rollouts) — recalibrate
   timing before sizing; consider adding a 1500 rung in the same run if it fits.
2. Root-statistics pre-probe with cutoff 0 (confirm Q values differentiate siblings — beware
   the old tanh clamp history, AUDIT_REPORT §8; evaluator returns ×100-scale values).
3. Then: 1500-iter PW rung; then C / visit-floor probes if needed.
4. Update the Phase 4 report addendum with each result; gate stays open until a run passes.
   PW is NOT adopted into any production/minimal config until then. No default escapes (§20).

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
