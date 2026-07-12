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

**Phase 4 — the mandatory search-scaling gate** (Phases 2 AND 3 are COMPLETE, gates PASS:
`phases/PHASE_2_TRUSTED_ENGINE.md`, `phases/PHASE_3_MINIMAL_SEARCH.md`; Phase 3 found and
fixed the rollout-reward-baseline defect, D-014 — read it before touching search values).

1. Strength-vs-budget study: the SAME minimal agent at increasing **iteration** budgets
   (e.g. 50 / 150 / 500 / 1 500 / 5 000) against the fixed benchmark protocol
   (`BENCHMARK_PROTOCOL.md`: round_robin seats, fixed seeds, iteration-deterministic budgets).
   Start from `training/diagnostics/search_quality.py`; use `mcts_lab/node_stats.py` to record
   root statistics (depth, visit concentration, expansion coverage) per budget.
2. Record every run in `EXPERIMENT_LOG.md` (full reproducibility block); wall-clock costs are
   real — budget the arena sizes before launching (a 4-game 100 ms-budget arena took ~3.5 min
   on this container; 5 000-iteration agents are ~10× a 500-iteration agent per move).
3. Gate: larger budgets must convincingly beat much smaller ones (e.g. 1500 > 150 > 50) with
   defensible uncertainty. On PASS: pick the teacher budget (D-008). On FAIL: stop — diagnose
   (backup, eval signal mix [score-delta vs tanh×100 static — flagged in D-014], branching,
   ordering) with targeted experiments before ANY learning work (master prompt §20 escapes
   forbidden).
4. Known structure to quantify (from the Phase 3 CLI): at ~16 plies there are ~300+ legal
   moves — 200 iterations yield a pure depth-1 tree; 1 500 reach depth 2. The +inf
   unvisited-child UCB forces a full first-visit sweep at every node; whether strength still
   scales despite this is exactly the question.

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
