# Rich Features vs the Live Evaluator — Information-Loss Analysis

_Audited 2026-06-24 · Phase 2 · companion to `docs/TD_AUDIT.md`_

This is the most important architectural question in the TD pipeline:

> TD learning trains a **45-feature** value model, but only **8 projected
> weights** reach the live agent's `BlokusStateEvaluator`. **How much is lost,
> and is TD learning bottlenecked by the evaluator architecture rather than the
> algorithm?**

Short answer: **yes, the evaluator is the bottleneck.** The 8 features the agent
can actually use explain materially less of the learning target than the full 45,
and — critically — the **single most predictive features are ones that cannot
reach the agent at all**.

---

## 1. The projection, precisely

`training/td_learning.py::project_to_agent_weights` takes the trained 45-feature
per-phase weight vector and:

1. slices out the 8 leading entries (the SE features, by construction the first 8
   of `RICH_FEATURE_NAMES`),
2. rescales them so `max(|w|) == WEIGHT_SCALE (0.30)`,
3. discards the other 37 weights for serving (they are persisted only as
   `rich_phase_weights` for transparency).

So at play time the agent computes `Σ w_i · f_i` over **8** features. The 37 extra
features influence the 8 only indirectly: because TD fits all 45 jointly, the 8
projected coefficients are *partial* coefficients (controlling for the other 37),
which is better-conditioned than a plain 8-feature regression — but the marginal
value those 37 features carry is gone.

---

## 2. Quantifying the loss (measured, not asserted)

Method: on a real self-play trajectory corpus (667 rows, champion + heuristic +
random roster), fit a linear model predicting the **blended terminal value**
(`td_learning.terminal_value`, the actual learning target) from (a) the 8 SE
features and (b) all 45 rich features. Compare in-sample R².

| Feature set | R² explaining the terminal value |
|---|---|
| 8 SE features (what the agent uses) | **0.572** |
| 45 rich features (what TD trains on) | **0.739** |
| **Explained-variance discarded by the projection** | **0.167** (≈ 23% of the explained signal) |

The 8-feature evaluator captures roughly three-quarters of the *explainable*
value signal; the projection throws away the remaining ~quarter.

### The lost signal is the *most* predictive signal

Top non-SE features by absolute correlation with the terminal value — **none of
these reach the live agent**:

| Rank | Feature (non-SE) | corr with value |
|---|---|---|
| 1 | `score_margin_vs_leader` | **+0.725** |
| 2 | `rank_so_far` | **+0.675** |
| 3 | `score_margin_vs_next_player` | **+0.526** |
| 4 | `corner_count` (= `frontier_size`) | +0.481 |
| 5 | `quadrant_balance` | +0.413 |
| 6 | `legal_move_count_small_pieces` | +0.410 |
| 7 | `edge_pressure` | −0.397 |

For comparison, the best **SE** feature (`accessible_corners`) correlates +0.481,
and several SE features carry almost no signal: `reachable_empty_squares` (−0.004)
and `territory_enclosure_area` (0.000, a hardcoded placeholder).

### Honest caveat

The three top features are score/rank/margin features. At **late** plies these are
partly tautological with the final outcome (knowing your score margin near the end
trivially predicts your rank), so part of the 0.167 R² gap is "easy" late-game
signal rather than deep positional understanding. Even discounting them, the
projection still drops genuine positional features (`quadrant_balance`,
`legal_move_count_small_pieces`, `edge_pressure`, mobility/territory metrics) that
the 8-feature evaluator has no slot for. The qualitative conclusion is robust; the
exact 23% figure will shift with corpus and phase.

---

## 3. Are the projected weights sufficient?

**Partially.** The projection is a *reasonable* way to get calibrated 8-feature
weights — and may beat the regression refit because it controls for confounders.
But it is **structurally incapable** of expressing the value contributions of the
37 dropped features. Two concrete failure modes:

- **Information the agent can't see.** `rank_so_far` and `score_margin_*` are
  strong value signals with **no SE-feature proxy**. The agent simply cannot
  condition its evaluation on "am I ahead?".
- **Wasted training.** Compute spent learning weights for 37 features is, at
  serving time, only useful insofar as it nudges the 8 survivors. That is a small
  fraction of the learned model.

## 4. Is TD bottlenecked by the evaluator architecture?

**Yes.** The likely outcome of the comparison harness (`training/experiments/`) is
that TD and regression land within noise — because both converge to the *same
8-dimensional output*. TD's advantage (richer features, temporal credit
assignment) is mostly squeezed out by the projection before it can affect play.
If the experiment shows TD ≈ regression, the conclusion is **not** "TD doesn't
work" — it is "the 8-feature serving evaluator is the ceiling".

## 5. Are the rich features helping at all?

**Modestly, and indirectly.** They improve the conditioning of the 8 projected
weights (partial vs marginal coefficients) and they are invaluable for *analysis*
(this document, feature-importance tracking). They are **not** helping the agent
evaluate positions with more than 8 features, because they never reach it.

---

## 6. Recommendations

1. **Measure first.** Run `python -m training.experiments.compare` on a real
   corpus. If TD ≈ regression, that confirms the bottleneck empirically.
2. **Attack the bottleneck, not the algorithm.** The highest-leverage next step is
   a **richer leaf evaluator**: consume more of the 45 features at MCTS *leaf*
   nodes (called far less often than per-rollout-step eval), where the extra cost
   is affordable. This lets `rank_so_far` / mobility / territory actually
   influence search. _Substantial work — deferred; see `tasks/TODO.md`._
3. **Prune dead/duplicate features.** `corner_count` duplicates `frontier_size`;
   `reachable_empty_squares` and `territory_enclosure_area` carry ~no signal.
   Pruning lowers collection cost and sharpens feature-importance reads. _Small._
4. **Add the strongest non-SE signals to the live evaluator** if a full leaf
   evaluator is too big a step: even adding `rank_so_far` and one score-margin
   feature to `BlokusStateEvaluator` (making it a 9–10-feature evaluator) would
   recover much of the lost signal cheaply. _Medium; weigh against per-step cost._
5. **Do not** build TD(λ)/boosting/a value network to fix this — they would all
   still be projected to 8 features. The architecture, not the learner, is the
   limit.

> **Decision:** do **not** implement a rich-feature evaluator yet (per Phase-2
> constraints). It is documented and prioritised in `tasks/TODO.md` and
> `docs/LEARNING_ROADMAP.md` as the top medium-term item, gated on the comparison
> harness confirming the bottleneck.

---

_Reproduce: `training/experiments/` for the comparison; the R²/correlation figures
above come from a linear fit on a 667-row champion/heuristic/random corpus and
will vary with the corpus._
