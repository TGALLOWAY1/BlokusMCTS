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

**Evaluator improvement track (Phase 5/6 with a narrow mandate).** Phase 4's gate is
**FAIL — ATTRIBUTED** after EXP-001/002/003 (read `phases/PHASE_4_SEARCH_SCALING.md`
addenda): tree shape fixed by PW; **the Layer-6 static evaluator is the binding ceiling**
(EXP-003: swapping rollouts for static-eval leaves erased the entire margin over the
heuristic anchor); rollouts carry all current signal but saturate. Search mechanics are
exonerated. Phases 7–8 stay blocked.

1. **Define the evaluator target first** (decisions D-005/D-007, record before building):
   per-player value vector from a leaf state; candidate targets = normalized final score vs
   placement vs mixed (master prompt §13). Training data source available NOW without new
   infrastructure: strong-rollout self-play labels (the EXP-002-style PW+rollout agent at
   500 iters is the strongest validated player; `data/td_trajectories.csv` machinery and
   `training/rich_features.py` 45-feature extraction already exist — but note the existing
   TD weights WERE tried as `rich_leaf` candidates and lost; a fresh approach should change
   the target/features/model, not just refit).
2. **D-006 (framework):** sklearn/numpy is available; torch is NOT in requirements and the
   browser path is numpy-only. A numpy-serving MLP or gradient-boosted trees (sklearn) on
   the 45 rich features is the low-friction first rung; a candidate-scoring move evaluator
   (master plan Phase 6) is the fuller direction if state-value alone can't discriminate.
3. **Acceptance test is fixed and cheap (~1 h):** the EXP-003 ladder with the new evaluator
   plugged into cutoff-0 leaves (`rich_leaf_eval_enabled` path or a new evaluator hook) —
   `python -m training.experiments.search_scaling --pw --cutoff 0 ...` — must (a) beat the
   EXP-002 rollout baseline at equal budgets and (b) show positive scaling. Compare against
   the committed EXP-002/003 reports (same seeds/protocol — results pool).
4. Root-statistics pre-probe for any candidate evaluator: Q spread across root moves must
   substantially exceed the ~1.3-point flatness measured for Layer-6 (EXP-003 log entry).
5. PW is NOT adopted into configs until a scaling run passes; no champion changes; no
   default escapes (§20). Every training run needs held-out evaluation (risk #6, Phase 1).

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
