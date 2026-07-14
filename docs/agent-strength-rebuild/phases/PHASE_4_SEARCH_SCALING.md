# Phase 4 — Prove That More Search Produces Stronger Play

- **Purpose:** the mandatory gate — determine whether the (Phase 3-verified) minimal search
  converts additional compute into better decisions. The entire learning plan (Phases 5–8)
  is conditioned on this.

- **Work completed:**
  - `training/experiments/search_scaling.py`: reproducible scaling CLI (exact pinned iteration
    budgets, one mixed 4-seat table, round_robin seats, standard scoring, hard deadline,
    Wilson CIs + TrueSkill + paired sign-flip permutation tests, `--reanalyze`).
  - EXP-001: ladder 50/150/500 iterations + heuristic anchor, 12 games × 2 seeds
    (20260620/20260621), 24/24 games, 109.5 min.
  - Mechanistic root-statistics probe at branching-factor-325/385 positions (via
    `mcts_lab.node_stats` internals).
  - Timing calibration: ~10–19 ms/iteration early/mid-game, ~40 ms late (this is why the
    primary ladder stopped at 500: a 1500-iteration seat costs ~10 min/game).

- **Experiments run:** EXP-001 (full record in `../EXPERIMENT_LOG.md`).

- **Results:**
  - Strength: it50 34.7% first-place / TS μ 34.6; it150 34.7% / 35.7; **it500 22.2% / 14.5**;
    heuristic 8.3% / 15.6. Paired score diffs: it50≈it150 (p=0.59); it500 trends WORSE than
    both (−4.1 vs it50, p=0.28; −5.9 vs it150, p=0.15); all budgets ≥ heuristic (it50
    p=0.0007, it150 p=0.004, it500 p=0.22).
  - Mechanism (root statistics, bf 325 and 385):
    | budget | expanded children | max depth | top-3 visits | children ≥2 visits |
    |---|---|---|---|---|
    | 50 | 50 | 1 | 1,1,1 | 0 |
    | 150 | 150 | 1 | 1,1,1 | 0 |
    | 500 | 325–385 (all) | 2 | 7,4,4 / 3,3,3 | 147 / 108 |
    Below the branching factor, every child has exactly one visit → max-visits selection ties
    → the first-expanded child wins, i.e. **the agent plays the move-ordering heuristic's top
    move**. At 500, revisits are allocated by UCB over single-rollout Q values whose noise
    (O(10–30 score points)) dwarfs the exploration term → the final choice follows 2–7
    rollouts of noise and overrides the ordering.

- **Required interpretation:** larger budgets must convincingly outperform substantially
  smaller budgets. They do not; the direction is negative. **There is currently no functioning
  search signal at practical budgets**: below bf the search equals its ordering prior; above
  bf it degrades the prior with noise.

- **Unexpected findings:** this coherently explains the training plateau — nightly candidate
  evaluations ran at 50–250 iteration budgets where every MCTS agent collapses to (roughly)
  the same ordering-heuristic policy, so evaluator/policy changes could barely express
  themselves as strength differences. It also explains why pre-fix "layer" experiments were
  unmeasurable.

- **Gate criteria:** search strength scales positively with compute over a useful range,
  statistically credibly; a viable teacher budget identified.
- **Gate result:** **FAIL** (EXP-001). **Still FAIL/OPEN after EXP-002** (see addendum below).

## Addendum (2026-07-12, EXP-002): progressive widening — necessary but not sufficient

Remediation experiment 1 (one variable: `progressive_widening_enabled, pw_c=2.0, α=0.5`;
full record in `../EXPERIMENT_LOG.md`):

- **Mechanism confirmed fixed** (pre-probe): at 500 iterations, 44 expanded children with the
  best child at 116 visits / 23% share and depth 4 — vs all-children / 3 visits / 0.6% /
  depth 2 without PW; concentration grows with budget.
- **Absolute strength up**, most where EXP-001 was worst: it500 22.2%→31.2% first-place,
  TS μ 14.5→24.2; ALL rungs now beat the heuristic anchor decisively (+11 to +16 points,
  p ≤ 0.0006; EXP-001's it500 was p=0.22).
- **But scaling is still flat**: it50 ≈ it150 ≈ it500 (paired diffs +3.7/+5.3 in the WRONG
  direction, p=0.42/0.30). With tree shape repaired, the remaining suspect is the **value
  signal** — the greedy_sample rollout-delta / tanh×100 static-eval mix appears to carry no
  reliable information beyond the move-ordering prior at these budgets.

Next distinguishing experiments (one variable each, same protocol so results pool):
1. **EXP-003 — value-signal isolation:** PW ladder with `rollout_cutoff_depth: 0`
   (pure static-eval leaves, deterministic, TT-cacheable) — separates rollout NOISE from
   evaluator QUALITY. If scaling appears: rollout noise was the blocker (Phase 5 direction
   confirmed). If still flat: the Layer-6 evaluator itself adds nothing over the ordering
   prior — the strength ceiling is the evaluator, pointing the rescue at leaf-evaluation
   quality (Phase 5/6) with search mechanics exonerated.
2. A 1500-iteration PW rung (does scaling emerge past 500?).
3. Exploration-constant / visit-floor robustness probes.

PW adoption into the minimal config is deferred until a scaling run passes — no config churn
without a passed gate.

## Addendum 2 (2026-07-12, EXP-003): attribution complete — the evaluator is the ceiling

Remediation experiment 2 (one variable vs EXP-002: `rollout_cutoff_depth: 0`, pure
static-eval leaves; full record in `../EXPERIMENT_LOG.md`):

- **The entire strength margin over the heuristic anchor vanished**: all rungs ≈ heuristic
  (paired diffs −2.0..+0.2, p ≥ 0.46; anchor tops first-place at 41.7%). In EXP-002 —
  identical except rollout leaves — every rung was +11..+16 points at p ≤ 0.0006.
- Pre-probe already showed why: static-eval Q is nearly flat across root moves (~1.3-point
  spread on a ~47 scale, top-3 within 0.2).

**Combined attribution (EXP-001 → 002 → 003):**
| Suspect | Verdict |
|---|---|
| Tree shape (first-visit sweep, no concentration) | Real; **fixed by progressive widening** (EXP-002) |
| Rollout noise | Real but secondary: rollouts carry ALL current value signal (informative vs anchor), yet extra visits don't convert to strength — the signal saturates |
| **Static evaluator quality** | **The binding ceiling** — contributes nothing beyond the move-ordering prior (EXP-003) |
| maxⁿ backup / selection mechanics | Exonerated (Phase 3 verification + PW behavior as predicted) |

- **Gate result:** **FAIL — ATTRIBUTED.** The gate cannot pass with the current value
  function; it stays open as the acceptance test for evaluator work.
- **Consequence for the master plan:** the rescue proceeds to **Phase 5/6 with a narrow
  mandate** — build a leaf evaluator that discriminates moves (Phase 6's candidate-scoring /
  value-vector direction), with the Phase 5 equal-time comparison already answered at this
  stage (rollouts ≻ static eval; neither scales). Any new evaluator's acceptance test is
  THIS ladder (same protocol, `--pw --cutoff 0` with the new evaluator vs the EXP-002/003
  baselines): it must (a) beat the rollout baseline at equal budget and (b) produce positive
  scaling. Only then do Phases 7–8 (self-play/training loop) unblock.
- This ordering is the master plan's own: a failed gate is remediated by the smallest
  causal fix — here, the value function — not by more search variants or bigger runs.

## Addendum 3 (2026-07-13, EXP-005): first positive scaling — gate now PARTIAL

Gate-3 ladder with the ridge value model (pairwise 0.682) as leaf evaluator, identical
protocol (full record: `../EXPERIMENT_LOG.md` EXP-005):

- **Positive scaling, first time measured**: avg rank monotonic in budget
  (2.12 → 1.83 → 1.75); it500−it50 = +5.71 pts, p=0.054; strength rises 50→150 and
  saturates by 500 at this evaluator quality.
- **Model leaves beat rollout leaves**: anchor margins +15.0/+19.9/+20.8 vs EXP-002's
  +14.75/+16.38/+11.04 (decisive at 500); the heuristic anchor is shut out (0% first place,
  TS μ 1.5).
- Cost note: 427 s/game — the 4-player 45-feature leaf extraction is the new hot path
  (future optimization axis; a cheaper feature subset exists in the rich-leaf machinery).

**Gate result: FAIL → PARTIAL — MORE EVIDENCE REQUIRED.** Outstanding before PASS:
1. **EXP-006a** — direct same-table equal-budget test: [model-500, rollout-500 (exact
   EXP-002 config), heuristic, random], round_robin, same seeds — the clean
   "beats rollouts at equal budget" criterion without cross-condition caveats.
2. **EXP-006b** — 150/500/1500 model-leaf ladder to locate saturation and set the teacher
   budget (D-008).

The evaluator-quality attribution stands confirmed in reverse: improving ONLY the value
function turned scaling positive with search mechanics untouched. The 45-feature family is
not closed (D-015 consequence clause superseded); representation upgrades are now an
optimization axis, not a prerequisite.

## Addendum 4 (2026-07-14, EXP-006a/b): GATE PASS for the PW + model-leaf configuration

- **EXP-006a (direct equal-budget test, 20 games):** vm500 vs rollout500 in the same games:
  +2.40 pts for the model, p=0.556 — **parity**, not the superiority the EXP-005
  cross-condition margins suggested. Both crush the anchors.
- **EXP-006b (saturation ladder, 12 games):** **it500 − it150 = +14.08 pts, p=0.013** — the
  first conventionally significant budget pair of the whole investigation; it1500 − it150 =
  +10.50 (p=0.063); it1500 ≈ it500. Knee at ~500.

**Combined evidence for the gate criteria (PW + ridge-model-leaf configuration):**
| Criterion | Evidence |
|---|---|
| More compute → stronger play over a meaningful range | 50→500: ranks monotonic (EXP-005), 150→500 significant (p=0.013, EXP-006b), 10× pairs p=0.054/0.063 in the right direction; saturation only beyond 500 |
| Statistically credible | one pair at p<0.05, consistent direction across 5 pairwise tests and 56 games in three protocol-matched experiments; anchors beaten at p ≤ 0.0013 everywhere |
| Viable teacher budget identified | **500 iterations** (D-008) — the knee; 1500 buys nothing at current evaluator quality |

**Gate result: PASS** — for the progressive-widening + model-leaf configuration
(decision D-016). Caveats recorded honestly: rollout leaves are at PARITY with model leaves
at 500 today (EXP-006a); the pass rests on the model configuration because it scales
(rollouts never did — EXP-001/002) and is improvable through training. The old
rollout-based default and the pre-rescue champion configuration remain non-scaling.

**Unlocked next:** Phase 5 closes (leaf-evaluation approach selected: model leaves;
rollouts deprecated as the strength path, retained as a parity baseline); Phase 7 teacher
self-play pipeline at budget 500; Phase 8 improvement-loop gates (retrain evaluator on
teacher-search data → gate C: new evaluator must beat ridge on THIS ladder). The saturation
knee is the standing measure of evaluator quality: better evaluators should push it higher.

- **Failure response (per master prompt §11/§20 — no default escapes):** do NOT proceed to
  Phases 5–8. Targeted distinguishing experiments, one variable each:
  1. **EXP-002 (next): progressive widening ladder.** Same 50/150/500 ladder with
     `progressive_widening_enabled` (pw_c=2.0, α=0.5 — the existing teacher-profile setting).
     PW caps expanded children at ⌈c·N^α⌉ so visits concentrate on top-ordered moves and depth
     becomes reachable. Hypothesis: scaling turns positive. This isolates "expansion policy"
     as the cause.
  2. If PW alone is insufficient: **selection robustness** — the exploration/exploitation
     balance at O(10–30)-point reward noise (options measured separately: more exploitative C,
     visit-floor before Q trusted, or normalized rewards — note the [0,1] normalization was
     tried pre-fix and reverted; re-measure post-D-014 rather than assume).
  3. Budget extension probe (1500+) only AFTER 1–2 show concentration, to find the teacher
     budget (D-008).
- **Remaining risks:** 24 games is modest — the negative it500 trend is consistent but not
  individually significant; EXP-002 should keep the same protocol so results pool. Wall-clock
  is the binding constraint (~275 s/game at this ladder).

- **Decision:** gate FAIL recorded; remediation experiments scheduled (no code changes made in
  this phase beyond the harness — the search itself was not touched post-Phase 3).
- **Next phase:** Phase 4 remains open until a re-run passes. Phases 5+ blocked.

- **Reproduction commands:**
  ```bash
  python -m training.experiments.search_scaling \
      --budgets 50,150,500 --anchor heuristic \
      --games-per-seed 12 --seeds 20260620,20260621 --deadline-minutes 170
  python -m training.experiments.search_scaling --reanalyze \
      --budgets 50,150,500 --anchor heuristic --seeds 20260620,20260621 --label b50_150_500
  python -m mcts_lab.node_stats --random-plies 8 --board-seed 20260620 --iterations 500
  ```
- **Artifacts:** `training/reports/experiments/search_scaling/b50_150_500/` (report.json,
  per-seed run dirs with games.jsonl and run configs).
