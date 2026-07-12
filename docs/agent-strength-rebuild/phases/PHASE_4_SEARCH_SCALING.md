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
- **Gate result:** **FAIL.**

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
