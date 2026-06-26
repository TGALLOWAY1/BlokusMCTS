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
   influence search. **IMPLEMENTED 2026-06-26 — see §7.**
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

> **Decision (superseded 2026-06-26):** the gate condition was met by
> `exp_e1261b8e0c3b` (TD 25% vs regression 39%; the limiter is the 45→8
> projection, not the learner), so the rich leaf evaluator is now **implemented**.
> See §7.

---

## 7. The rich leaf evaluator (implemented 2026-06-26)

The fix recommended above is now an **optional, default-OFF** feature.
`mcts/rich_leaf_evaluator.py::RichLeafEvaluator` evaluates a node with the full
45-feature TD value `Σ wᵢ·fᵢ + bias` using the per-phase `rich_phase_weights`
already persisted in `training/state/td_evaluator_weights.json`. It is wired into
`MCTSAgent._simulation` as a **leaf-only** call (flag `rich_leaf_eval_enabled`):
invoked exactly once per simulation, replacing the rollout — **never** per
rollout step. It loads the rich weights with graceful fallback to the 8-feature
`BlokusStateEvaluator` when the artifact is missing/untrained.

### The leaf-budget problem and the subset solution

Full 45-feature extraction enumerates legal moves for **all four** players (the
opponent-mobility features), measured at **~15–27 ms/leaf** — calling that even
once per simulation would gut the iteration budget. So the evaluator selects a
**cost tier** (`training.rich_features.LEAF_FEATURE_SUBSETS`); excluded features
are zeroed, so their TD weights simply drop out of the dot product:

| Subset | Features | Per-leaf cost | Drops |
|---|---|---|---|
| `full` | 45 | ~15–25 ms | nothing |
| `no_opp_mobility` | 41 | ~7 ms | `opponent_mobility_{avg,max,min}`, `leader_mobility_pressure` (the all-player enumeration) |
| **`score`** (default) | 27 | **~0.8 ms** | all legal-move enumeration + territory BFS |

(measured with the engine's shared move generator at ~0.35 board occupancy;
per-leaf cost rises with board density.)

The `score` default is deliberate: the three **highest-signal** non-SE features
(`score_margin_vs_leader` +0.725, `rank_so_far` +0.675,
`score_margin_vs_next_player` +0.526; §2) are *cheap* — they need only square
counts — while the expensive opponent-mobility features carry less signal. So the
default tier recovers most of the lost signal at ~1/30th the cost of full
extraction, and is the only tier cheaper than a rollout. The included features
carry **identical values** to `extract_rich_features` (shared gated
implementation, pinned by tests), so the TD-trained weights apply directly.

### Validation

A/B harness: `scripts/ab_rich_leaf.py` (baseline MCTS vs MCTS+rich-leaf, two of
each per game, rotating seats, fixed iteration budget). It reports win rate, mean
score, iterations/move, and per-leaf cost.

**Measured so far.** Per-iteration cost (the decisive number): leaf eval
*replaces* the rollout, so at a 334-legal-move position the baseline's full
heuristic rollout costs **~273 ms/iter** vs rich-`score` **~4.5 ms/iter (~60×
faster)**. Under a wall-clock / deterministic-arena budget that buys ~60× more
iterations. A clean *fixed-iteration* strength A/B needs a high iteration count
(the regime where the tree search, not a single leaf eval, carries strength), but
the slow baseline rollout makes powered fixed-iteration runs impractical here; at
a low budget (30 iters) the baseline leads, as expected. A powered
deterministic-arena run is the recommended next validation (see `tasks/TODO.md`).
The feature is **default OFF**, so there is no regression risk to the existing
agent.

---

_Reproduce: `training/experiments/` for the comparison; the R²/correlation figures
above come from a linear fit on a 667-row champion/heuristic/random corpus and
will vary with the corpus._
