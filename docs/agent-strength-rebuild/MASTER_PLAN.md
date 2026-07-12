# Agent-Strength Rescue — Master Plan (repo-specific)

**Status:** governing plan for all agent-strength work in this repo from 2026-07-12 onward.
**Baseline commit:** `cabe2dd7738daca661798d422ee487179640e34f` (branch `claude/agent-rescue-master-plan-i9kvwf`, forked from `main`).
**Companion docs:** `CURRENT_STATUS.md` (live state), `AUDIT_INVENTORY.md` (component trust map),
`DECISIONS.md` (decision records), `EXPERIMENT_LOG.md`, `BENCHMARK_PROTOCOL.md`, `DATA_LINEAGE.md`,
`HANDOFF.md`, `phases/` (per-phase reports).

## 0. Objective

Build the strongest practical 4-player Blokus agent this repo can produce, and a system that
repeatedly yields validated, stronger generations. Success is defined by evidence, in this order:

1. Engine correctness → 2. Search correctness → 3. Search scaling (more compute ⇒ stronger play)
→ 4. Model learns correct targets → 5. Search beats raw model → 6. Trained model improves search
→ 7. Generation N+1 beats N → 8. Fixed champion gate → 9. Practical latency → 10. Beats the
target human skill level.

The prior question — "did the latest nightly run raise Elo?" — is retired as a success signal.

## 1. Where this repo actually is (July 2026)

- Champion **gen140** (promoted 2026-07-02): Elo 1388.6, TrueSkill μ 54.39 σ 5.02
  (`training/state/champion.json`). Generation 179, 6 290 games, **39-generation promotion
  drought**; every recent candidate (rich_leaf, heuristic_tune, mcts_sweep) evaluated *below*
  the champion (run `20260711T190001Z`: ΔElo −60 to −117).
- The July 2026 audit (`AUDIT_REPORT.md`) already fixed the maxⁿ backprop bug, added a two-stage
  SPRT promotion gate, and pruned the repo to one engine + one MCTS implementation.
- There is **no neural network**. All learned components are linear/log-linear weight files fit
  with sklearn/numpy (Layer-6 state evaluator, 45-feature TD value model, 4-feature move policy).
- A GitHub Actions workflow trains **every 6 hours** and commits state back
  (`.github/workflows/nightly-mcts-training.yml`) — Phase 0 freezes it.

## 2. Actual subsystems, entry points, and assets

| Subsystem | Location | Notes |
|---|---|---|
| Engine | `engine/{board,move_generator,game,pieces,bitboard}.py` | Dual grid+bitboard, incremental frontier; naive movegen + grid legality retained as reference paths |
| Search | `mcts/mcts_agent.py` (only implementation) + `mcts/{state_evaluator,rich_leaf_evaluator,move_policy,parallel,zobrist,search_profiles}.py` | maxⁿ per-player vector backprop; experimental layers default off |
| Agents | `agents/{champion,heuristic_agent,random_agent,registry}.py` | `agents/champion.py` reads `data/champion_registry.json` (serving), *not* `training/state/champion.json` |
| CLI workflow | `python -m mcts_lab.{checks,eval,self_play,train,promote}` | Canonical commands (see root `CLAUDE.md`) |
| Training pipeline | `training/nightly_run.py`, `training/selfplay_core.py`, `training/approaches/*` | Approach-comparison framework, durable resume |
| Evaluation | `analytics/tournament/*` + `training/evaluation/{benchmark_pool,head_to_head,sequential,promotion_gate}.py` | benchmark_v2 pool, TrueSkill+Elo+Wilson+SPRT |
| Data | `data/{champion_snapshots,td_trajectories,policy_targets}.csv`, weights in `training/state/*.json` | See `DATA_LINEAGE.md` for hashes and compatibility |
| State | `training/state/{champion.json,latest.json,ratings.sqlite,checkpoints/}` | Append-only ratings DB, era cutoffs |
| Serving | `webapi/` (FastAPI), `frontend/` (React+Pyodide), bundle via `scripts/build_browser_core.sh` | Browser path is numpy-only (Pyodide) — constrains Phase 6 model choices |
| Automation | `.github/workflows/nightly-mcts-training.yml`, `.claude/commands/run-overnight-mcts.md` | The skill is already promotion-guarded; the cron is the freeze target |
| Tests | `tests/` (76 files) | Differential engine tests exist; maxⁿ regression suite `tests/test_maxn_backprop.py`; no property-based framework |

Reproduce the standard checks:

```bash
python -m mcts_lab.checks
python -m pytest tests/ -q            # slow; use -n 4 while iterating
python -m mcts_lab.eval --agents champion,baseline --games 10 --seeds 20260620,20260621
```

## 3. Repository strategy (Decision D-001)

**Stay in this repository.** Rationale: exactly one engine and one search implementation survive
the July 2026 cleanup, both carry real differential/regression tests; UI coupling is
one-directional (webapi/frontend import the core, never the reverse); a new repo would duplicate
validated code without removing any risk. The `docs/agent-strength-rebuild/` tree is the
governing layer over the existing lab. Revisit condition: if Phase 6 model work makes the
Pyodide/serving coupling or repo weight a real obstacle, extract an `agent-core` package then
(see `DECISIONS.md` D-001 for the full record and scoring).

## 4. Phases (repo-specific)

Branch note (Decision D-004): all phases develop on the harness-designated branch
`claude/agent-rescue-master-plan-i9kvwf` (merged to `main` via PR per phase or phase-group),
not the `agent-rescue/phase-*` scheme from the generic master prompt.

### Phase 0 — Freeze and preserve (this session)
- Remove the `schedule:` cron from `nightly-mcts-training.yml`; keep `workflow_dispatch`.
  **Effective only once merged to `main`** (GitHub reads schedules from the default branch).
- Pin assets by sha256 + baseline commit (see `DATA_LINEAGE.md`); no copying needed — everything
  durable is git-committed. Mark legacy-data compatibility.
- Exit gate: no uncontrolled training remains scheduled; assets pinned; legacy data labeled.
- Report: `phases/PHASE_0_FREEZE.md`.

### Phase 1 — Forensic audit (this session, from completed exploration)
- Full pipeline trace and risk-ranked findings: `phases/PHASE_1_FORENSIC_AUDIT.md`;
  component trust map: `AUDIT_INVENTORY.md`.
- Exit gate: every loop component has an identified owner/data path; risks ranked; repo strategy
  decided (D-001).

### Phase 2 — Trusted engine
- Designate the existing **naive movegen + grid legality** path as the reference implementation
  (`engine/move_generator.py::_get_legal_moves_naive`, `Board.can_place_piece`); do not write a
  third engine.
- Implement **standard Blokus scoring** as the target ruleset (Decision D-002): add the missing
  +5 monomino-last bonus, make `SCORING_MODE_STANDARD` the default for all new evaluation;
  house mode remains for historical comparability only.
- Add property/invariant tests (evaluate `hypothesis`): occupancy monotonicity, piece-inventory
  conservation, turn order, clone independence, serialization round-trip, terminal-implies-no-moves.
- Extend differential tests to full-game trajectories (reference vs optimized: moves, states,
  inventories, scores, rankings) at scale (thousands of positions).
- Version the state/action formats (schema id surfaced in self-play records).
- Exit gate: reference↔optimized agreement on large randomized sets; standard scoring tested;
  formats versioned.

### Phase 3 — Minimal trusted search
- The post-fix `MCTSAgent` with **all experimental layers off** is the candidate minimal search
  (plain UCT + maxⁿ vector backup, no tree reuse, deterministic-only TT, single thread,
  iteration budgets). Task = verify, not rewrite: correctness tests on hand-authored tactical /
  near-terminal / single-move / pass positions (extend `tests/test_tactical_positions.py`,
  `tests/test_maxn_backprop.py`), plus a **node-statistics inspection CLI** (root visit counts,
  Q per player, depth histogram — build on `mcts/search_trace.py`).
- Contingency if verification fails: write a ~300-line reference MCTS for differential
  comparison against `mcts_agent.py`.
- Value semantics: per-player reward vector keyed by `Player`, mover-credited backup — already
  the implemented convention; document exact meaning/range (currently O(100) score-scale +
  win bonus; the [0,1] normalization was tried and reverted — any change needs an experiment).
- Exit gate: deterministic under fixed seeds; maxⁿ semantics verified; terminal decisions correct.

### Phase 4 — Search scaling gate (MANDATORY)
- Same agent at increasing **iteration** budgets (e.g. 50/150/500/1 500/5 000 sims; plus
  time-budget spot checks), fixed evaluator/opponents/seeds/seat protocol per
  `BENCHMARK_PROTOCOL.md`. Builds on `training/diagnostics/search_quality.py`.
- Prior audit found effective depth-1 search at nightly budgets (branching factor > iterations)
  — this gate decides whether the current search converts compute into strength at all.
- Exit gate: large budgets convincingly beat much smaller budgets; a viable slow **teacher
  budget** is identified. If it fails: stop, diagnose (backup, eval signal, branching, ordering)
  before any learning work.

### Phase 5 — Rollout value audit
- Equal-wall-clock comparison: static eval (cutoff 0) vs shallow vs deeper `greedy_sample`
  rollouts vs rich-leaf (TD) evaluation. Question: stronger *decisions* per unit time, not
  different numbers.
- Exit gate: strongest practical leaf evaluation selected; demonstrably valueless rollout
  depth removed from the core path.

### Phase 6 — Policy/value model
- Greenfield (no NN exists). Required decision records before building: framework (constraint:
  Pyodide browser serving is numpy-only — options: train in torch/sklearn + export numpy
  inference, or numpy-native model), value target (normalized score vs placement vs mixed),
  action representation.
- Preferred architecture: **legal-move candidate scoring** — encode state, encode each legal
  move (engine-generated), score state×move pairs, softmax over legal moves only. This replaces
  the current 4-feature log-linear policy (`training/state/policy_weights.json`, top-1 agreement
  0.53) rather than extending it.
- Gates: tiny-data overfit (few hundred positions) → held-out generalization → masking/ordering/
  round-trip tests. Do not scale training before the overfit gate passes.

### Phase 7 — Teacher self-play data pipeline
- Teacher-budget search (from Phase 4) generates records: full state, legal actions, visit
  counts, root values, final score+placement vectors, config, checkpoint hash, seed, seat map,
  schema version. Extend `training/policy_selfplay.py` record format; add a dataset **validator**
  and immutable **manifests** (see `DATA_LINEAGE.md` rules). New data never mixes with
  pre-rebuild corpora by default.
- Exit gate: validator-clean, fully traceable dataset that trains reproducibly.

### Phase 8 — Improvement-loop gates (A–D)
- A: net+search > net alone. B: new net alone > old net alone. C: same budget, new net > old net
  in search. D: generation N+1 > N under the fixed protocol. All via `BENCHMARK_PROTOCOL.md`.
- No continuous training system until all four arrows have evidence.

### Phase 9 — Candidate/champion/league
- Reuse and extend the existing machinery: two-stage gate (`training/evaluation/promotion_gate.py`
  + `gauntlet.evaluate_promotion`), checkpoints as historical anchors, matchup matrices
  (`training/reports/matchup_matrix.png` lineage). Add: explicit league manifest, promotion
  criteria fixed *before* evaluation, non-transitivity monitoring.
- Resolve the dual-registry split (training champion vs `data/champion_registry.json` serving
  champion) with a documented promotion path to serving (Decision, Phase 9).

### Phase 10 — Latency optimization
- Only after Phase 8. Strength-vs-latency frontier; difficulty modes (instant/fast/standard/
  expert); optimizations must pass semantic-equivalence regression tests. Tree reuse and
  broader TT use are allowed here only with correctness proof.

### Phase 11 — Human evaluation
- Protocol per master prompt §18; `training/human_estimate.py`'s current "beginner, target
  Elo 1700" extrapolation is replaced by real human games under recorded conditions.

## 5. Initial risk ranking (detail in PHASE_1 report)

1. **Search scaling unproven post-fix** — the whole learning plan is moot if Phase 4 fails.
2. **Candidate generation exhausted** — linear refits consistently lose to the champion; the
   ratchet needs Phases 5–7, not more nightly runs.
3. **Wrong objective** — house scoring default vs the real (standard) game; monomino bonus
   missing entirely (Phase 2, decided).
4. **Dual champion sources of truth** — training vs serving registry disagree (Phase 9).
5. **Determinism leaks** — wall-clock budgets, import-time env flags, tree-parallel mode
   (avoid; codified in `BENCHMARK_PROTOCOL.md`).
6. **Learning hygiene** — no held-out sets in current fits; `policy_targets.csv` lacks era
   tagging (Phase 7 validator).

## 6. Non-negotiables carried over from the master prompt

- Correctness → reproducibility → measurement validity → strength → performance, in that order.
- Every phase has an exit gate; failed gates stop progression and get the smallest
  distinguishing experiment.
- Experiments recorded in `EXPERIMENT_LOG.md` when run, with the full reproducibility block.
- No default escapes: no "train longer / add a variant / tweak five hyperparameters" responses
  to a failed gate (master prompt §20 list applies verbatim).
- Champion changes only via the gate (`mcts_lab.promote` / gated nightly path) — unchanged
  from root `CLAUDE.md`.
- Layer-experiment conclusions from before the maxⁿ fix stay invalid until re-measured.
