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

**Status after EXP-005 (gate 3 PARTIAL — first positive scaling):** ridge-model leaves
(`training/artifacts/value_models/v1/value_v1_ridge_baseline.joblib`, plumbed via
`value_model_path` through MCTSAgent/build_agent) produced the investigation's first
positive budget→strength curve (rank 2.12→1.83→1.75; it500−it50 +5.71 pts p=0.054) and
beat rollout leaves' anchor margins at every rung. Saturation above ~150 iters at this
evaluator quality. Phase 4 is PARTIAL — two confirmations from PASS.

**Exact next actions:**
1. **EXP-006a — direct equal-budget test (~2.5 h):** one mixed table
   [model-500 (PW + value_model_path), rollout-500 (exact EXP-002 config: PW, greedy_sample,
   cutoff 12), heuristic, random], round_robin, seeds 20260620/20260621, 12 games/seed.
   Needs a small harness extension (mixed leaf-source tables — budgets currently share one
   leaf source; e.g. `--mixed-pair model:rollout` or explicit agent-config JSONs via a new
   flag). The paired model-vs-rollout permutation test is the clean (a) criterion.
2. **EXP-006b — saturation/teacher-budget ladder (~4 h):** 150/500/1500 model-leaf rungs +
   heuristic (`--pw --value-model ... --budgets 150,500,1500`). Cost warning: model leaves
   run ~427 s/game at 50/150/500 — the 1500 rung roughly doubles that; size with the
   deadline flag. Locates saturation → teacher budget (D-008).
3. On both confirming: declare **Phase 4 PASS** (report update), formalize the PW +
   model-leaf configuration as the new minimal-search candidate (decision; PW adoption was
   deferred pending exactly this), then proceed to Phase 5 closure (rollouts formally
   deprecated as leaf source) and Phase 7 (teacher self-play data pipeline) — with the
   evaluator-improvement loop (better features/models → re-run ladder) as the ongoing
   strength axis.
4. Optimization axis (not blocking): leaf-eval cost — 45-feature 4-player extraction is the
   new hot path; the rich-leaf machinery already supports cheaper feature subsets.
5. Standing rules unchanged: no champion changes outside the gate; held-out splits
   mandatory; no default escapes (§20).

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
