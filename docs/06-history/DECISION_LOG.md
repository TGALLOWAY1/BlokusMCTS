# Decision Log

> Evidence-backed decisions that shaped the project. Newest first.
> Last audited: 2026-05-28. Full layer reports: `archive/reports/`.

---

# Decision: Fair-split eval budget + short eval gate for nightly approach comparison
Date: 2026-06-29
Status: Accepted
Context: The nightly approach-comparison run was silently degenerate — the eval
deadline was only checked between `(arena, seed)` sub-batteries, so the first
candidate's uninterruptible 100-game battery (~199 min) consumed the entire
45-min budget and the other three approaches got 0 games on *every* run. The
"comparison" only ever evaluated one approach.
Decision: Enforce the deadline at game granularity (`run_experiment(deadline=…)`),
split the budget fairly across candidates (equal share of remaining time,
recomputed each iteration), and start with a **short eval gate**
(`EVAL_MIN_TOTAL_GAMES = 20`, two seeds) so all four approaches fit one CI run at
full 500 ms strength.
Why: A comparison that only ever scores one approach is useless; fairness must be
structural, not dependent on roster order. Short-but-complete beats
long-but-truncated for a first healthy baseline.
Alternatives considered: (a) lower the per-move thinking time to fit more games
at full roster — deferred to a backlog A/B (longer eval + relaxed promotion gate);
(b) keep the 40-game gate and raise the budget past the 350-min CI cap — rejected
(doesn't fit one run).
Consequences: Promotion is conservative on thin runs (fails safe). A backlog item
tracks testing the opposite regime.
Verification: smoke run evaluated 4/4 approaches within a tight budget (vs 1/4
before); 44 training tests pass.
Related files: `training/evaluation/head_to_head.py`,
`training/evaluation/promotion_gate.py`, `analytics/tournament/arena_runner.py`,
`.github/workflows/nightly-mcts-training.yml`,
`docs/05-planning/BACKLOG.md`.

# Decision: Pivot from RL environment to MCTS platform
Date: 2026-03-06
Status: Accepted
Context: The project started as a Blokus RL environment (PPO/MaskablePPO,
PettingZoo/Gymnasium). Engine throughput, not policy learning, turned out to be
the real bottleneck, and tournament/evaluation infrastructure shifted the focus
to comparing agents.
Decision: Archive the RL training code to `archive/rl/` and reframe the repo
around MCTS.
Why: Clarifies identity; the search agent is where the interesting results are.
Alternatives considered: Keep RL and MCTS side by side (rejected — split focus).
Consequences: RL-era residue remains (package name, `/training*` routes/pages) —
tracked in [Known Issues](../04-quality/KNOWN_ISSUES.md).
Related files: `archive/rl/`, `docs/project-history.md`.

# Decision: Archive FastMCTSAgent as an invalid tree search
Date: 2026-03-28
Status: Accepted
Context: An audit found `FastMCTSAgent` nodes did not represent successor states
and rollouts scored heuristically from the root — not a valid MCTS.
Decision: Move it to `archive/agents/` and make the arena runner **reject**
`fast_mcts`/`gameplay_fast_mcts`.
Why: Results from an invalid search are misleading.
Consequences: All arena/eval must use `"type": "mcts"` (`MCTSAgent`).
Related files: `archive/agents/fast_mcts_agent.py`,
`analytics/tournament/arena_runner.py`, `docs/audits/mcts_audit_remediation_summary.md`.

# Decision: Use calibrated global eval weights, not phase-dependent weights
Date: 2026-03-25
Status: Accepted
Context: Regression on 13K+ self-play states produced both a single global weight
set and early/mid/late phase weights. Phase weights had inverted early-game signs
and hard transition discontinuities.
Decision: Ship `single_weights`; do not use `phase_weights`.
Why: Calibrated global = 76% win rate; phase weights = 0% win rate.
Alternatives: Phase weights (rejected); hand-tuned defaults (rejected — had a
wrong-sign weight).
Consequences: `phase_weights` retained in `data/layer6_calibrated_weights.json`
for the record but flagged not-recommended.
Related files: `mcts/state_evaluator.py`, `KEY_FINDINGS.md`.

# Decision: Random rollout + cutoff depth 5 + minimax α=0.25
Date: 2026-03-25
Status: Accepted
Context: Layer 4 compared rollout policies and depths.
Decision: Default to random rollouts, `rollout_cutoff_depth=5`,
`minimax_backup_alpha=0.25`.
Why: Random is ~10× faster than two-ply and beats heuristic (the worst policy);
cutoff 5 at 25 iters beats cutoff 0 at 1000 iters. Rollout quality > iteration
quantity.
Related files: `mcts/mcts_agent.py`, `archive/reports/layer4_arena_results.md`.

# Decision: Enable RAVE (k=1000), not progressive history
Date: 2026-03-25
Status: Accepted
Context: Layer 5 history heuristics.
Decision: `rave_enabled=true`, `rave_k=1000`; keep progressive history off.
Why: RAVE gives ~4× convergence speedup (50ms RAVE > 200ms baseline); PH hurts
when combined with RAVE.
Related files: `mcts/mcts_agent.py`, `archive/reports/layer5_arena_results.md`.

# Decision: Root parallelization (2 workers), not tree parallelization
Date: 2026-03-26
Status: Accepted
Context: Layer 8 compared root (multiprocessing) vs tree (threading + virtual loss).
Decision: `num_workers=2`, `parallel_strategy="root"`.
Why: Root wins 86% of games and scales near-linearly; tree parallelization is
slower than single-threaded due to the GIL.
Related files: `mcts/parallel.py`, `KEY_FINDINGS.md`.

# Decision: Adaptive rollout depth yes, adaptive exploration constant no
Date: 2026-03-26
Status: Accepted
Context: Layer 9 meta-optimization.
Decision: Enable `adaptive_rollout_depth`; do not enable
`adaptive_exploration`.
Why: Adaptive depth wins 36% and is 1.64× faster; adaptive-C is harmful (8%)
because it over-explores on top of RAVE. The combined "full" agent loses to
baseline — less is more.
Related files: `mcts/mcts_agent.py`, `archive/reports/layer9_arena_results.md`.

# Decision: Replace full rollouts with cutoff-depth configs (compute ceiling)
Date: 2026-03-24
Status: Accepted
Context: Layer 10 throughput calibration measured iter/ms by depth; full 50-move
rollouts exceed 2h/game.
Decision: All arena configs use `rollout_cutoff_depth` of 0/5/10; add per-move
verbose progress reporting.
Why: Make 25-game tournaments finish in ~60–90 min.
Consequences: Strength conclusions are conditional on this compute regime
([Risk Register](../04-quality/RISK_REGISTER.md)).
Related files: `scripts/calibrate_throughput.py`, `data/throughput_calibration.json`.

# Decision: Documentation reorganization (this pass)
Date: 2026-05-28
Status: Accepted
Context: A heavily-documented repo (47 docs) lacked a single navigable,
status-labeled system; some docs were stale RL-era or superseded.
Decision: Add a numbered `docs/00-08` system; archive stale/superseded docs to
`docs/_archived-2026-05/`; keep active topic docs in place and link them.
Why: Make current behavior, architecture, risks, and next actions easy for humans
and agents to find. Owner chose a high-value subset over a literal full rebuild.
Related files: `docs/`, `docs/_archived-2026-05/ARCHIVE_RATIONALE.md`,
[`AUDIT_LOG.md`](AUDIT_LOG.md).
