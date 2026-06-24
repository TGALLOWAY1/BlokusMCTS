# Learning Roadmap

_Created 2026-06-24 · Phase 2 · companion to `docs/TD_AUDIT.md`,
`docs/RICH_FEATURE_ANALYSIS.md`, and the authoritative `tasks/TODO.md`._

Prioritised future work for the Blokus learning system. **Sequencing principle
(from the audit): validate before you complicate.** The single most likely reason
TD does not beat regression is the **45→8 evaluator bottleneck**, not the
learning algorithm. Therefore most algorithmic upgrades (TD(λ), boosting,
networks) are *low priority until the bottleneck is removed*, because each would
still be projected down to 8 serving features.

Every item below is also captured in `tasks/TODO.md` with full
Priority/Complexity/Risk/Dependencies/Timing fields.

---

## Near-term (validation & cheap wins)

These directly support the Phase-2 goal of *knowing whether TD helps*.

1. **Run the comparison harness on a real corpus.** _(Priority: Critical ·
   Complexity: Low · Risk: Low.)_ Generate `data/td_trajectories.csv`, train TD,
   run `python -m training.experiments.compare`. This is the gate for everything.
2. **Larger, less-biased trajectory corpus.** _(High · Low · Low.)_ More games,
   varied rosters and seats to fix rank-skew; target ≥ `min_rows_per_phase` in
   every phase (the trajectory diagnostics flag shortfalls).
3. **Calibrate label normalisation.** _(Medium · Low · Low.)_ The `tanh((score −
   40)/20)` centre and the rank-value map are unvalidated; derive them from the
   observed score/rank distributions the trajectory diagnostics now expose.
4. **Prune dead/duplicate features.** _(Medium · Low · Low.)_ `corner_count`
   duplicates `frontier_size`; `reachable_empty_squares` /
   `territory_enclosure_area` carry ~no signal. Lowers collection cost.
5. **Trajectory filtering / confidence weighting.** _(Medium · Medium · Low.)_
   Down-weight random-seat and very-early rows; weight terminal targets by margin
   confidence.

## Medium-term (attack the real bottleneck)

6. **Richer leaf evaluator — TOP medium-term item.** _(High · High · Medium.)_
   Consume more of the 45 rich features at MCTS *leaf* nodes (not per rollout
   step), so `rank_so_far`, mobility, and territory can influence search. This is
   the change most likely to convert TD's richer model into stronger play. Gated
   on the comparison harness confirming the 8-feature ceiling.
7. **Add top non-SE signals to the live evaluator.** _(Medium · Medium · Medium.)_
   Cheaper interim step: extend `BlokusStateEvaluator` to ~9–10 features
   (`rank_so_far` + a score-margin feature) to recover much of the lost signal
   without a full leaf evaluator.
8. **TD(λ) / eligibility traces.** _(High value *after* the bottleneck · Medium ·
   Low.)_ Better temporal credit assignment; the natural extension of TD(0). Only
   worthwhile once more than 8 features reach the agent.
9. **Opponent-aware / multiplayer value targets.** _(Medium · Medium · Medium.)_
   Condition terminal value on roster; anti-kingmaking shaping; per-seat
   calibration. Ties into Layer-7 opponent modelling.
10. **Online TD updates during self-play.** _(Medium · Medium · Medium.)_ Update
    the value model incrementally in the nightly loop rather than as a separate
    batch step (also removes the stale-artifact risk).

## Long-term (high-capacity models — only after the above)

11. **Gradient-boosted value model** (LightGBM/XGBoost) over the rich features.
    _(High capacity · High complexity · Medium–High risk.)_ Captures non-linear
    interactions; needs a fast leaf-only inference path to be usable in play.
12. **Policy learning from MCTS visit counts.** _(High · High · Medium.)_ Distil
    root visit distributions into a move-ranking model to bias rollouts /
    progressive widening.
13. **Neural value network.** _(High · High · High.)_ Replaces the linear
    evaluator; requires an inference budget the current engine does not have.
14. **AlphaZero-style expert iteration** (joint policy+value, self-play loop).
    _(Highest · Highest · High.)_ The end-state; only sensible once a value
    network and policy head exist and the search/serving budget supports them.

---

## Why this ordering

The audit's measured finding (`docs/RICH_FEATURE_ANALYSIS.md`): the 8 serving
features explain R²≈0.57 of the value vs R²≈0.74 for all 45, and the **top
predictors are non-SE features the agent cannot see**. Every long-term model
(11–14) would still be funnelled through the 8-feature projection unless the
serving evaluator is widened first. So **item 6 (richer leaf evaluator) gates the
entire long-term track** — building a value network before it would waste the
network's capacity at serving time.

Constraints honoured: no neural networks, gradient boosting, policy learning,
AlphaZero training, or TD(λ) are *implemented* in Phase 2 — they are documented
and prioritised here and in `tasks/TODO.md` only.
