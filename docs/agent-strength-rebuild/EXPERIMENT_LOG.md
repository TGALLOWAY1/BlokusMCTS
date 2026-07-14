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

## EXP-006a — Phase 4 confirmation 1: direct same-table model-500 vs rollout-500

- **Experiment ID:** EXP-006a
- **Date:** 2026-07-14 (launched ~00:4x UTC)
- **Commit:** the EXP-006 PR head (harness gains `--agents-json` mixed-table mode)
- **Hypothesis:** at equal budget (500 iterations, identical PW/search config), the
  ridge-model leaf agent beats the rollout leaf agent head-to-head in the SAME games —
  the clean version of gate-3 criterion (a), no cross-condition caveats.
- **Independent variable:** leaf source per seat (vm500 = `value_model_path` ridge artifact;
  rollout500 = greedy_sample rollouts, cutoff 12 — exact EXP-002 config).
- **Controlled variables:** one mixed table [vm500, rollout500, heuristic, random];
  round_robin; seeds 20260620/20260621; 10 games/seed; standard scoring; stat seed 20260712.
- **Game count:** 20 (deadline 260 min). **Hardware:** session container (concurrent with
  EXP-006b — iteration budgets, so contention affects wall-clock only).
- **Result:** 20/20 games in 180.7 min.
  | agent | 1st% | avg rank | TS μ (σ) |
  |---|---|---|---|
  | vm500 | 47.5% | **1.45** | 42.50 (7.80) |
  | rollout500 | 42.5% | 1.60 | 39.39 (7.82) |
  | heuristic | 10.0% | 2.50 | 21.89 (7.56) |
  | random | 0.0% | 3.70 | −2.92 (7.64) |
  **vm500 − rollout500 = +2.40 pts, p=0.556** (primary test). Both crush the anchors
  (vm +23.8 vs heuristic p<0.0001; rollout +21.4 p=0.0002).
- **Uncertainty:** 20 paired games; the primary comparison is far from significant.
- **Interpretation:** **parity at equal budget, slight positive trend for model leaves** —
  NOT the "decisively better at 500" the EXP-005 cross-condition anchor margins suggested
  (that comparison overstated; the anchor faces different opposition per condition). The
  honest criterion-(a) verdict: model leaves EQUAL rollout leaves in strength at 500 iters
  today, while being deterministic, TT-cacheable, and — unlike rollouts — improvable
  through the training loop.
- **Decision:** criterion (a) as originally worded ("beats rollouts at equal budget") is
  NOT met at n=20; parity is. The architectural argument for model leaves survives on
  improvability, not present superiority. Verdict rolls into the combined Phase 4 update
  with EXP-006b.
- **Artifacts:** `training/reports/experiments/search_scaling/exp006a_vm_vs_rollout/`.

## EXP-006b — Phase 4 confirmation 2: model-leaf saturation ladder (150/500/1500)

- **Experiment ID:** EXP-006b
- **Date:** 2026-07-14 (launched ~00:4x UTC)
- **Commit:** the EXP-006 PR head
- **Hypothesis:** model-leaf scaling continues past 500 (1500 > 500), or saturates —
  locating the knee sets the teacher budget (D-008).
- **Independent variable:** iteration budget (150/500/1500), all with PW + ridge leaves.
- **Controlled variables:** heuristic anchor; round_robin; seeds 20260620/20260621;
  6 games/seed; standard scoring; stat seed 20260712. (Fewer games — the 1500 rung costs
  ~2× an entire EXP-005 game; deadline 330 min, partials analyzable via --reanalyze.)
- **Game count:** 12 requested (deadline-capped).
- **Result:** _recorded on completion below._
- **Artifacts:** `training/reports/experiments/search_scaling/pw_vm_b150_500_1500/`.

## EXP-005 — D-015 gate 3: acceptance ladder with the ridge value model as leaf evaluator

- **Experiment ID:** EXP-005
- **Date:** 2026-07-13 (launched ~19:5x UTC)
- **Commit:** the gate-3 PR head (adds `mcts/value_model_evaluator.py`, `value_model_path`
  plumbing through MCTSAgent/build_agent/parallel config, `--value-model` ladder flag)
- **Hypothesis (the decisive one):** the ridge value model (pairwise rank acc 0.682,
  in-tree Q-spread 4.6–6.3 pts) as the leaf evaluator (a) beats the EXP-002 rollout
  baseline at equal budgets and (b) produces positive scaling. PASS reopens the Phase 4
  gate path; FAIL closes the state-value-on-45-features family (D-015 consequence clause).
- **Independent variable (vs EXP-002/003):** budget agents' leaf source =
  `value_model_path=training/artifacts/value_models/v1/value_v1_ridge_baseline.joblib`
  (replaces rollouts via the rich-leaf slot; deterministic).
- **Controlled variables:** everything else identical to EXP-002/003 (PW pw_c=2.0 α=0.5,
  budgets 50/150/500, heuristic anchor, round_robin, seeds 20260620/20260621, 12 games/seed,
  standard scoring, stat seed 20260712) — results pool across the three conditions.
- **Agents:** mcts_it50/150/500 (PW + ridge-model leaves), heuristic.
- **Game count:** 24 (deadline 170 min). **Seat-balancing:** round_robin.
- **Hardware:** session container (single process, num_workers=1).
- **Result:** 24/24 games in 171 min (427 s/game — model leaves cost more than rollouts;
  4-player 45-feature extraction dominates).
  | agent | 1st% | Wilson 95% | avg rank | TS μ (σ) | vs heuristic (paired) |
  |---|---|---|---|---|---|
  | mcts_it50 | 16.0% | [0.06, 0.35] | 2.12 | 30.41 (7.57) | +15.04 (p=0.0001) |
  | mcts_it150 | 45.1% | [0.27, 0.64] | 1.83 | 37.00 (7.66) | +19.88 (p<0.0001) |
  | mcts_it500 | 38.9% | [0.22, 0.59] | 1.75 | 31.52 (7.60) | +20.75 (p<0.0001) |
  | heuristic | 0.0% | [0.00, 0.14] | 3.38 | 1.46 (7.50) | — |
  Budget pairs: it500−it50 = **+5.71 (p=0.054)**; it150−it50 = +4.83 (p=0.29);
  it150−it500 = +0.88 (p=0.86).
- **Uncertainty:** 24 games; the 10× pair is borderline-significant; cross-condition
  anchor-margin comparison shares seeds/protocol but the anchor faces different budget
  opponents per condition (directional, not exact).
- **Interpretation:** **the first positive scaling signal of the entire investigation.**
  (b) Scaling: avg rank improves monotonically with budget (2.12 → 1.83 → 1.75); the 10×
  pair reaches p=0.054; strength rises 50→150 then saturates by 500 at this evaluator
  quality. (a) vs rollout leaves: anchor margins exceed EXP-002 at every rung
  (+15.0/+19.9/+20.8 vs +14.75/+16.38/+11.04), decisively at 500 — and the anchor is
  shut out entirely (0% first place). A 0.68-pairwise evaluator already outperforms
  rollouts as the leaf source AND converts budget into strength at the low end.
- **Decision:** **Gate 3: PARTIAL — MORE EVIDENCE REQUIRED** (per the report vocabulary):
  direction validated, two confirmations outstanding before Phase 4 can be declared
  PASSED: (1) EXP-006a — a DIRECT same-table equal-budget test: [model-500, rollout-500
  (exact EXP-002 config), heuristic, random], round_robin, same seeds — the clean (a)
  criterion; (2) EXP-006b — a 150/500/1500 model-leaf rung to locate the saturation point
  and the teacher budget (D-008). The 45-feature family is NOT closed — D-015's
  consequence clause is superseded by this result; feature/representation upgrades become
  an optimization axis rather than a prerequisite.
- **Artifacts:** `training/reports/experiments/search_scaling/pw_vm_b50_150_500/report.json`
  (+ per-seed run dirs).

## EXP-004 — Evaluator track v1: model training + D-015 gates 1–2

- **Experiment ID:** EXP-004
- **Date:** 2026-07-13 (early UTC)
- **Commit:** the evaluator-v1 PR head (harness `training/experiments/value_model.py`)
- **Hypothesis:** a non-linear model (GBM/MLP) on the 45 `rich_blokus_v1` features beats the
  linear baseline at predicting standard final scores (D-015 gate 1), and its in-tree root
  Q-spread far exceeds Layer-6's measured 1.3-point flatness (gate 2).
- **Independent variable:** model family (ridge baseline vs HistGB vs MLP), same features,
  same data.
- **Controlled variables:** dataset `data/value_dataset_v1` (17 408 rows / 60 games,
  standard-scored PW-50 teacher self-play); GAME-level 80/20 held-out split (48/12 games,
  split seed 20260713); target = final_score/100; identical probe protocol to EXP-003's
  pre-probe (PW, 500 iterations, seeds/plies matched).
- **Result:**
  | model | held-out R² | MAE (pts) | pairwise rank accuracy |
  |---|---|---|---|
  | ridge (linear baseline) | **0.264** | **5.61** | **0.682** |
  | hist_gb | 0.246 | 5.66 | 0.680 |
  | mlp | 0.221 | 5.87 | 0.664 |
  **Gate 1: FAIL** — no non-linear lift on any metric. Gate 2 probe (hist_gb as leaf
  evaluator): root Q-spread **6.34 / 4.57** points at ply 8/24 (vs Layer-6's ~1.3), best-child
  share 23%, depth 5 — the bar "substantially exceed the flatness" is met, though top-3 Q at
  ply 24 remain within 0.06.
- **Uncertainty:** single split (12 held-out games); metric ordering consistent across all
  three metrics; gate-1 differences are small but uniformly non-positive for non-linear.
- **Interpretation:** **capacity is not the bottleneck — the 45-feature representation is.**
  The features carry genuine ordering signal (0.68 pairwise ≫ 0.5 chance) but saturate at
  R² ≈ 0.26 regardless of model family. This explains why historical `rich_leaf`/TD linear
  refits plateaued: they were already at the feature ceiling. Whether 0.68-pairwise value
  quality is enough to beat rollout leaves in actual play is exactly gate 3.
- **Decision:** run gate 3 (the fixed Phase 4 acceptance ladder) with the **ridge** model
  (best on every metric; trivially numpy-servable) before designing the Phase 6 move-level /
  richer-representation evaluator — the ladder verdict calibrates any future design either
  way. D-015 consequence clause is armed: if gate 3 fails, the state-value-on-45-features
  family is closed.
- **Artifacts:** `training/artifacts/value_models/v1/report.json`,
  `value_v1_hist_gb.joblib` (fitted artifact incl. dataset manifest + split + metrics).

## EXP-003 — Phase 4 remediation: value-signal isolation (PW + pure static-eval leaves)

- **Experiment ID:** EXP-003
- **Date:** 2026-07-12 (launched ~16:45 UTC)
- **Commit:** the EXP-003 PR head (base `859b163`; harness gains `--cutoff`)
- **Hypothesis (discriminating):** replacing noisy rollout values with deterministic
  static-eval leaves (`rollout_cutoff_depth: 0`) either (A) restores positive scaling —
  rollout NOISE was the blocker, confirming the Phase 5 direction — or (B) leaves the curve
  flat — the Layer-6 evaluator itself adds nothing beyond the ordering prior, exonerating
  search mechanics and pivoting the rescue to leaf-evaluation quality.
- **Independent variable (vs EXP-002):** `rollout_cutoff_depth: 0` on the budget agents.
  Everything else identical (PW pw_c=2.0 α=0.5, budgets 50/150/500, heuristic anchor,
  round_robin, seeds 20260620/20260621, 12 games/seed, standard scoring, stat seed).
- **Pre-probe:** cutoff-0 costs ~9–11 ms/it early/mid, ~3.4 ms/it late (2–4× cheaper than
  rollouts). **Static-eval Q is nearly flat across root moves**: top-3 children within
  ~0.2 pts, full spread ~1.3 on a ~47 scale; best-child visit share drops to 5–9% at
  bf-325/385 (vs 23% with rollout values); depth still grows with budget (3→4 midgame,
  4→8 at bf 7). Early lean toward outcome B, arena decides.
- **Agents:** mcts_it50, mcts_it150, mcts_it500 (all PW + cutoff 0), heuristic.
- **Game count:** 12 games/seed × 2 seeds = 24 (deadline 170 min; est. ~1 h).
- **Seat-balancing method:** round_robin. **Seeds:** 20260620, 20260621.
- **Hardware:** session container (single process, num_workers=1).
- **Result:** 24/24 games in 55.5 min (139 s/game). **Outcome B, decisively.**
  | agent | 1st% | Wilson 95% | avg rank | TS μ (σ) | vs heuristic (paired) |
  |---|---|---|---|---|---|
  | heuristic | 41.7% | [0.24, 0.61] | 2.12 | 30.83 (7.64) | — |
  | mcts_it50 | 37.5% | [0.21, 0.57] | 2.21 | 28.26 (7.59) | −0.58 (p=0.78) |
  | mcts_it150 | 12.5% | [0.04, 0.31] | 2.42 | 25.60 (7.52) | +0.21 (p=0.94) |
  | mcts_it500 | 8.3% | [0.02, 0.26] | 2.83 | 15.35 (7.46) | −2.00 (p=0.48) |
  Budget pairs all flat (p=0.46–0.75).
- **Uncertainty:** Wilson 95% CIs; 10k-permutation sign-flip tests; 24 games — but the
  cross-experiment contrast is the finding, and it is large: EXP-002 (identical except
  rollout leaves) had every rung +11..+16 pts over the anchor at p ≤ 0.0006; EXP-003's
  advantage is zero.
- **Interpretation:** **the Layer-6 static evaluator contributes nothing beyond the
  move-ordering prior** — replacing rollouts with static-eval leaves erased the ENTIRE
  strength margin over the heuristic anchor (consistent with the pre-probe's ~1.3-point Q
  spread on a ~47 scale). Conversely, the rollouts carry all of the current value signal:
  informative (EXP-002's anchor margins) but too noisy/saturating to convert extra visits
  into strength (flat scaling in EXP-001/002). Combined attribution across EXP-001/002/003:
  tree shape — fixed by PW; value signal — rollouts = all signal + noise-limited; static
  evaluator = uninformative. **The strength ceiling is leaf-evaluation quality.**
- **Decision:** Phase 4 gate: **FAIL — ATTRIBUTED** (stays open). Search mechanics are
  exonerated; the rescue pivots to Phase 5 (formal equal-time leaf-evaluation comparison is
  effectively done: rollouts ≻ static eval) and Phase 6 (build a leaf evaluator that actually
  discriminates — the candidate-scoring/value-vector model), then RE-RUN this scaling ladder
  as the acceptance test for any new evaluator. PW remains un-adopted until that re-run
  passes.
- **Artifacts:** `training/reports/experiments/search_scaling/pw_c0_b50_150_500/report.json`
  (+ per-seed run dirs).

## EXP-002 — Phase 4 remediation: progressive-widening ladder (one variable vs EXP-001)

- **Experiment ID:** EXP-002
- **Date:** 2026-07-12 (launched ~08:15 UTC)
- **Commit:** the EXP-002 PR head (base `d2ea3ff`; harness gains `--pw`)
- **Hypothesis:** progressive widening (pw_c=2.0, α=0.5) restores positive scaling —
  mcts_it500 > mcts_it150 > mcts_it50 — by concentrating visits on top-ordered moves
  instead of the one-visit-per-child sweep that made EXP-001 fail.
- **Independent variable (vs EXP-001):** `progressive_widening_enabled: true, pw_c: 2.0,
  pw_alpha: 0.5` on the three budget agents. EVERYTHING else identical to EXP-001
  (same budgets, seeds, seat policy, scoring, table composition, game counts, stat seed).
- **Pre-probe (mechanism check before spending arena time):** with PW at bf-325/385
  positions — 500 iters: 44 expanded children (vs all 325–385), best child 116 visits /
  23% share (vs 3 visits / 0.6%), depth 4 (vs 2); concentration grows with budget.
- **Agents:** mcts_it50, mcts_it150, mcts_it500 (all +PW), heuristic (anchor).
- **Game count:** 12 games/seed × 2 seeds = 24 (deadline 170 min).
- **Seat-balancing method:** round_robin. **Seeds:** 20260620, 20260621.
- **Hardware:** session container (single process, num_workers=1).
- **Result:** 24/24 games in 155.2 min (session container was suspended mid-run; all games
  completed).
  | agent | 1st% | Wilson 95% | avg rank | TS μ (σ) | EXP-001 comparison |
  |---|---|---|---|---|---|
  | mcts_it50 | 33.3% | [0.18, 0.53] | 2.00 | 34.83 (7.62) | ≈ unchanged |
  | mcts_it150 | 31.2% | [0.16, 0.51] | 2.04 | 33.24 (7.61) | ≈ unchanged |
  | mcts_it500 | 31.2% | [0.16, 0.51] | 2.38 | 24.22 (7.58) | **up from 22.2% / μ 14.5** |
  | heuristic | 4.2% | [0.01, 0.20] | 3.38 | 7.84 (7.48) | down from 8.3% |
  Paired permutation: it50−it150 = −1.62 (p=0.66); it50−it500 = +3.71 (p=0.42);
  it150−it500 = +5.33 (p=0.30); vs heuristic: it50 **+14.75 (p=0.0002)**, it150 **+16.38
  (p<0.0001)**, it500 **+11.04 (p=0.0006)** — every rung now beats the anchor decisively
  (EXP-001's it500 was p=0.22).
- **Uncertainty:** Wilson 95% CIs; 10k-permutation sign-flip tests; 24 games/condition —
  budget-vs-budget differences remain within noise; anchor comparisons are decisive.
- **Interpretation:** progressive widening **fixed the tree-shape pathology and raised
  absolute strength** (biggest gain exactly where EXP-001 was worst, the 500 rung; the
  pre-probe's concentration/depth predictions held), **but the scaling curve is still flat**:
  50 ≈ 150 ≈ 500, with it500 still trending slightly behind. With concentration no longer the
  bottleneck, the remaining suspect is the VALUE SIGNAL — greedy_sample rollout deltas /
  tanh×100 static-eval mix appears to add no reliable information beyond the move-ordering
  prior at these budgets, so extra visits refine noise.
- **Decision:** Phase 4 gate remains **FAIL/OPEN**. PW is necessary-but-insufficient;
  adopting PW into the minimal config is deferred until a scaling experiment passes (no
  config churn without a passed gate). Next distinguishing experiments (one variable each):
  (a) value-signal probe — same PW ladder with pure static-eval leaves (`rollout_cutoff_depth
  0`) to isolate rollout noise vs evaluator quality; (b) a 1500-iteration PW rung to test
  whether scaling appears beyond 500; (c) exploration-constant / visit-floor robustness.
- **Artifacts:** `training/reports/experiments/search_scaling/pw_b50_150_500/report.json`
  (+ per-seed run dirs), pre-probe numbers above.

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
