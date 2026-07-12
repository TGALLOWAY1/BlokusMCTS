# Experiment Log

Record experiments **when they run**, not afterward. Never overwrite an entry; corrections are
appended. Every entry uses the template below (from the governing master prompt §3).

```
Experiment ID:
Date:
Commit:
Hypothesis:
Independent variable:
Controlled variables:
Agents:
Game count:
Seat-balancing method:
Seeds:
Hardware:
Result:
Uncertainty:
Interpretation:
Decision:
Artifacts:
```

---

## EXP-001 — Phase 4 search-scaling gate, primary ladder (50/150/500 + heuristic anchor)

- **Experiment ID:** EXP-001
- **Date:** 2026-07-12 (launched ~06:05 UTC)
- **Commit:** the Phase 4 PR head (contains `training/experiments/search_scaling.py`; base `b6b8c1f`)
- **Hypothesis:** with the Phase 3 reward-baseline fix in place, more search iterations
  produce stronger play: mcts_it500 > mcts_it150 > mcts_it50 (> heuristic) in first-place
  rate / avg rank / paired score difference.
- **Independent variable:** exact iteration budget (50, 150, 500), pinned via `iterations`
  param (thinking_time_ms None — build_agent cannot rewrite it).
- **Controlled variables:** identical minimal search config for all budget agents
  (greedy_sample K=12, cutoff 12, heuristic ordering, C=1.414, TT on, 1 worker, maxⁿ,
  root reward baseline); engine @ standard scoring; mixed 4-seat table; round_robin seats;
  max_turns 2500; scoring_mode standard.
- **Agents:** mcts_it50, mcts_it150, mcts_it500, heuristic (anchor).
- **Game count:** 12 games/seed × 2 seeds = 24 (deadline-capped at 170 min).
- **Seat-balancing method:** round_robin (rotates each game).
- **Seeds:** 20260620, 20260621 (game seeds derived via SHA256 per arena_runner).
- **Hardware:** session container (Linux, single process, num_workers=1).
- **Result:** 24/24 games completed in 109.5 min (274 s/game).
  | agent | 1st% | Wilson 95% | avg rank | TS μ (σ) |
  |---|---|---|---|---|
  | mcts_it50 | 34.7% | [0.19, 0.55] | 1.96 | 34.62 (7.61) |
  | mcts_it150 | 34.7% | [0.19, 0.55] | 2.00 | 35.69 (7.68) |
  | mcts_it500 | 22.2% | [0.10, 0.42] | 2.75 | 14.49 (7.51) |
  | heuristic | 8.3% | [0.02, 0.26] | 2.96 | 15.59 (7.44) |
  Paired permutation (score diff): it50−it150 = −1.79 (p=0.585); it50−it500 = **+4.08**
  (p=0.276); it150−it500 = **+5.88** (p=0.149); it50−heuristic = +7.58 (**p=0.0007**);
  it150−heuristic = +9.38 (**p=0.004**); it500−heuristic = +3.50 (p=0.220).
- **Uncertainty:** Wilson 95% CIs; 10k-permutation sign-flip tests; TrueSkill μ/σ; 24 paired
  games — the 500-worse-than-50/150 direction is a consistent point estimate, not
  individually significant.
- **Interpretation:** **no positive scaling over a 10× budget span; 500 iterations trends
  WORSE than 50/150.** Mechanistic probe (root statistics at bf 325/385 positions): at 50/150
  iterations every expanded child has exactly 1 visit → max-visits selection ties → the agent
  plays the move-ordering heuristic's first-expanded (top) move; at 500 iterations all ~325–385
  children expand and revisits (best child 3–7 visits) follow single-rollout noise, overriding
  the ordering. Below the branching factor the "search" is the ordering heuristic; above it,
  it follows noise. Search does beat the raw HeuristicAgent anchor at low budgets (the
  ordering heuristic + occasional rollout signal is stronger than HeuristicAgent's own move
  scoring), but compute does not convert to strength. Fully consistent with the training
  plateau: nightly evaluation budgets (50–250 iters) cannot express evaluator improvements.
- **Decision:** **Phase 4 gate FAIL** (`phases/PHASE_4_SEARCH_SCALING.md`). No learning-phase
  work (Phases 5–8) until scaling is repaired. Next distinguishing experiment: EXP-002 — the
  same ladder with progressive widening enabled (already implemented, off by default; the
  teacher profile uses pw_c=2.0, α=0.5), which restricts expansion so visits concentrate.
- **Artifacts:** `training/reports/experiments/search_scaling/b50_150_500/report.json`
  (+ per-seed run dirs with games.jsonl); mechanistic probe numbers in the phase report.

## EXP-000 — Rescue baseline snapshot (no new games played)

- **Experiment ID:** EXP-000
- **Date:** 2026-07-12
- **Commit:** `cabe2dd7738daca661798d422ee487179640e34f`
- **Hypothesis:** n/a — reference snapshot of the frozen system's last recorded performance.
- **Independent variable:** none.
- **Controlled variables:** all values read from committed durable state
  (`training/state/latest.json`, `training/status.md`, run `20260711T190001Z`).
- **Agents:** champion gen140 vs benchmark_v2 pool + candidates rich_leaf / heuristic_tune /
  mcts_sweep.
- **Game count:** cumulative 6 290 (generation 179); last run: 48–56 paired games/candidate.
- **Seat-balancing method:** round_robin (SPRT sequential screen).
- **Seeds:** 20260620, 20260621.
- **Hardware:** GitHub-hosted 2-core runner (nightly workflow).
- **Result:** champion gen140 Elo 1388.55, TrueSkill μ 54.39 σ 5.02 (conservative 39.33). Last
  run candidates all HELD, SPRT inconclusive, all negative vs champion: rich_leaf 56 games,
  39% win vs champ, ΔElo −60.1, Δμ −9.62; heuristic_tune 48 games, ΔElo −117.3, Δμ −9.71;
  mcts_sweep 48 games, ΔElo −108.4, Δμ −10.54. Best historical Elo 1418.1 (gap −29.5, within
  documented rating noise σ≈±42.5). 39 generations without promotion.
- **Uncertainty:** rating noise at nightly game counts documented at ±42–72 Elo; SPRT verdicts
  inconclusive (neither H0 nor H1).
- **Interpretation:** the plateau is real at the current approach family's effect size:
  candidates are consistently *weaker* than the champion, not undetectably better. Supports
  risk ranking #2 (candidate generation exhausted) and motivates Phases 4–8 rather than more
  nightly iterations.
- **Decision:** freeze (Phase 0); proceed per `MASTER_PLAN.md`.
- **Artifacts:** `training/state/latest.json` (`last_approach_comparison`),
  `training/status.md`, `training/reports/approach_comparison.md`, hashes in `DATA_LINEAGE.md`.
