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

**Phase 4 remediation — EXP-002: progressive-widening ladder.** Phase 4's gate **FAILED**
(EXP-001: no positive scaling 50→500; 500 trends worse; mechanism = below-bf first-visit
sweep collapses search to the ordering heuristic, above-bf revisits follow single-rollout
noise — read `phases/PHASE_4_SEARCH_SCALING.md` first). Phases 5–8 are blocked.

1. **EXP-002 (one variable):** same protocol as EXP-001 — same seeds (20260620/20260621),
   round_robin, 12 games/seed, mixed table 50/150/500 + heuristic — but with
   `progressive_widening_enabled: true, pw_c: 2.0, pw_alpha: 0.5` added to
   `MINIMAL_SEARCH_PARAMS` budget agents (the existing teacher-profile setting;
   `MCTSNode.max_children_for_visits` already implements it). Command shape:
   add a `--pw` flag to `training/experiments/search_scaling.py` (label e.g. `pw_b50_150_500`)
   rather than editing the constant, so EXP-001 stays reproducible. ~110 min runtime.
   Record in `EXPERIMENT_LOG.md` at launch. Hypothesis: visit concentration → positive scaling.
2. Verify mechanism moved: re-run the root-statistics probe with PW (expect best-child visit
   share ≫ 1/bf and depth > 2 at 500 iters).
3. If PW scaling is positive: extend one rung (1500) to size the teacher budget (D-008) —
   ~10 min/game per 1500-iter seat; budget accordingly (deadline flag exists).
4. If PW is NOT sufficient: selection-robustness experiments, one at a time (exploration
   constant vs O(10–30)-point reward noise; visit floor; re-measure reward normalization
   post-D-014 — do not assume the pre-fix revert still holds).
5. Update the Phase 4 report with each result; the gate stays open until a run passes.
   No learning work, no champion changes, no default escapes (master prompt §20).

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
