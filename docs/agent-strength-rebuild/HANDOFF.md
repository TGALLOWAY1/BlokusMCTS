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

**Status: PHASE 4 PASSED** (addendum 4) for the PW + ridge-model-leaf configuration:
scaling significant at 150→500 (+14.08 pts, p=0.013, EXP-006b), monotonic 50→500
(EXP-005), knee at ~500 → **teacher budget 500 (D-008)**; model-vs-rollout at equal budget
is PARITY (EXP-006a) — the config is adopted for scaling + trainability (D-016), the
champion is untouched. Phase 5 is closed by the same evidence (model leaves selected;
rollouts deprecated as the strength path). **Phases 7–8 are unblocked.**

**UPDATE (2026-07-16, session 15):** Phase 7 is COMPLETE (teacher_dataset_v1 validated) and
gate C has run its first turn: training half PASS (v2_mixed fixes v1's severe
miscalibration on teacher play), arena half **PARTIAL** (vm2 57.5% vs vm1 42.5%
first-place, paired +2.25 p=0.60, n=20 — EXP-007). Bottleneck isolated: the
`rich_blokus_v1` ~0.68 pairwise ordering ceiling. **Exact next action: Phase 6
representation upgrade** — (a) extend the append-only versioned rich feature set
(opponent-interaction / territory-potential / endgame-parity candidates) and/or (b) the
move-level candidate-scoring evaluator (master plan §13). Acceptance BEFORE arena spend:
held-out pairwise ordering decisively above 0.68 (train/eval via
`training/experiments/value_model_v2.py` machinery); then re-run gate C
(`exp007_agents.json` pattern) on the fixed protocol. Everything below is the historical
Phase 7 handoff (done).

**UPDATE (2026-07-16, session 17):** Phase 6 path 1 in flight — the teacher recorder now
takes `--iterations` / `--value-model` (empty string → rollout leaves) and
`data/value_dataset_v2` (100 games, seed 20260716, PW-50 rollout leaves,
`teacher_record_v2` full-state format) is generating (~2.2 h). On completion: validate,
hash into `DATA_LINEAGE.md`, extend `value_model_v2.py` to consume two teacher-format
dirs, retrain with `rich_blokus_v2` features at volume, and test the pre-arena bar
(held-out pairwise decisively > 0.68) before any gate-C arena spend.

**Exact next action — Phase 7: teacher self-play data pipeline (then Phase 8 gate C):**
1. Extend the self-play recorder to the full Phase 7 record schema (master plan §14 /
   DATA_LINEAGE forward-looking section): per decision — full state (`board_state_v1`
   via `Board.to_dict()`), legal actions, ROOT VISIT COUNTS + root values (the
   `_capture_root_moves` hook already exists in MCTSAgent; policy_selfplay uses it),
   selected action (`move_v1`), final score+placement vectors, search config, model
   checkpoint hash, seed, seat map, schema versions. New manifested dataset dir
   (value_dataset generator is the template; immutability guard included).
2. Generate teacher data: 4× teacher agents (D-016 config @ 500 iters). Cost reality:
   ~20 min/game single-process on this container → size runs with deadlines; consider
   `num_workers` root-parallel for the TEACHER only after checking it composes with
   value_model_path (config extraction already propagates it).
3. Add the dataset validator (legality of selected actions, policy/legal alignment,
   player-vector ordering, terminal-score agreement, manifest consistency) BEFORE any
   training consumes it.
4. **Phase 8 gate C** (the loop's first turn): retrain the value model on teacher-search
   data (game-level held-out split), then the fixed ladder: new evaluator must beat ridge
   at equal budget AND ideally push the saturation knee past 500. Record as EXP-007+.
5. Optimization axis (not blocking): leaf-eval cost (45-feature 4-player extraction);
   cheaper subsets exist in the rich-leaf machinery.
6. Standing rules unchanged: champion changes only via the Phase 9 gate; held-out splits
   mandatory; datasets immutable + manifested; no default escapes (§20).

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
