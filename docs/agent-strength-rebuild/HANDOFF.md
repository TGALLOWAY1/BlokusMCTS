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

**Status after EXP-004 (gate 1 FAIL, feature ceiling):** dataset `data/value_dataset_v1`
(17 408 rows) exists and is manifested; `training/experiments/value_model.py` trains and
probes; non-linear ≤ linear on the 45 rich features (pairwise rank acc caps at 0.682); the
model-as-leaf Q-spread is 4.6–6.3 pts (vs Layer-6's 1.3). The 45-feature state-value family
is one gate from closure.

**Exact next action — gate 3, the acceptance ladder with the ridge model:**
1. Plumb a joblib model artifact into arena-buildable agents: extend
   `mcts/rich_leaf_evaluator.RichLeafEvaluator` (or add a sibling evaluator) to load
   `training/artifacts/value_models/v1/value_v1_*.joblib`-style artifacts
   ({model, feature_names, target}) and predict instead of dot(weights); expose via a
   `build_agent` param (e.g. `rich_leaf_model_path`). Keep `evaluate(board, player)`
   semantics (already duck-typed-proven by `ValueModelLeafEvaluator` in value_model.py —
   reuse that logic; note it caches per-board 4-player predictions). Add a unit test
   (artifact round-trip + evaluate returns finite per-player values).
   NOTE: retrain/save the RIDGE artifact (best model) — value_model.py currently saves the
   best NON-linear model; add `--save-model ridge_baseline` or similar.
2. Run the fixed ladder: `python -m training.experiments.search_scaling --pw --cutoff 0`
   variant where budget agents use the model evaluator (extend the harness with
   `--value-model PATH`). Same seeds/protocol; compare directly against the committed
   EXP-002 (rollout) and EXP-003 (Layer-6) reports. PASS = beats EXP-002 baseline at equal
   budget AND positive scaling. (~1 h.)
3. On FAIL: D-015's consequence clause closes the state-value-on-45-features family; begin
   the Phase 6 candidate-scoring (move-level) evaluator design with D-005/D-006/D-007 in
   full, using the ladder result as the calibration baseline.
4. Standing rules: PW not adopted into configs until a scaling run passes; no champion
   changes; held-out splits mandatory; no default escapes (§20).

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
