# Learning Roadmap — Authoritative TODO

Authoritative, prioritised list of deferred learning work for the Blokus MCTS
project. Narrative version: `docs/LEARNING_ROADMAP.md`. Evidence/justification:
`docs/TD_AUDIT.md`, `docs/RICH_FEATURE_ANALYSIS.md`.

**Guiding principle (from the Phase-2 audit): validate before you complicate.**
The dominant bottleneck is the **45→8 evaluator projection**, not the learning
algorithm — measured R² of the 8 serving features is 0.57 vs 0.74 for all 45, and
the most predictive features (`score_margin_vs_leader`, `rank_so_far`) never reach
the live agent. Algorithmic upgrades are gated on first removing that ceiling.

Field key — **Priority**: Critical/High/Medium/Low · **Complexity**: Low/Medium/
High · **Risk**: Low/Medium/High · **Expected Strength Gain**: rough, evidence-
based.

---

## NEAR-TERM

### Run the candidate comparison harness on a real corpus
- **Priority:** Critical
- **Status:** **UNBLOCKED — dependencies now satisfied; powered run still owed.**
- **Expected Strength Gain:** None directly — it is the *measurement* that unblocks
  every other decision.
- **Complexity:** Low (infra already built in `training/experiments/`)
- **Risk:** Low
- **Dependencies:** a real `data/td_trajectories.csv` + trained
  `td_evaluator_weights.json` — **both now committed** (corpus: 24 games / 96
  trajectories / 1,611 rows, diagnostics ✅ healthy, ranks balanced — no rank skew
  at this size).
- **Suggested Timing:** Immediately. Nothing below should start until this runs.
- **Reason:** As of Phase 2 there was no committed trajectory corpus, so TD had
  never been validated against regression. `python -m training.experiments.compare`
  produces win/rank/TrueSkill/Elo with confidence intervals and a recommendation.
- **Done (2026-06-25):** the harness was validated end-to-end on the committed
  corpus (smoke: 5 four-agent arenas, 1 seed × 1 game each — produces valid pooled
  metrics + recommendation). A **first powered run** then followed on the
  recalibrated weights — `exp_e1261b8e0c3b`, 40 pooled games, 4 seeds, 50 ms/move:
  | Agent | Win% (95% CI) | Avg rank | TrueSkill μ | Elo |
  |---|---|---|---|---|
  | heuristic | 51.6% (35–68) | 1.62 | 48.3 | 1442 |
  | regression | 39.1% (24–56) | 1.88 | 38.4 | 1322 |
  | **td** | **25.0% (13–42)** | **2.31** | **28.3** | **1277** |
  | champion | 9.4% (3–24) | 2.59 | 22.5 | 1157 |
  | random | 0.0% (0–11) | 3.88 | −11.0 | 803 |

  **Verdict: TD does NOT beat regression.** Head-to-head TD 7 / regression 17,
  TrueSkill Δμ **−10.05**, Elo **−45**. The harness labels it "INCONCLUSIVE" only
  because the win-rate CIs technically overlap, but the direction is unambiguous —
  TD trails regression, and *both* learned candidates trail the plain heuristic.
  Recalibrating the score labels did not close the gap. **This is the evidence the
  audit said would un-gate the richer leaf evaluator** (§8): the limiter is the
  45→8 projection, not the labels or the learner. **Still owed:** a gold-standard
  run (≥100 games × ≥10 seeds) to convert the directional verdict into a
  statistically clean one — but it is not a prerequisite for starting the leaf
  evaluator, since the trend already points there.

### Larger, less-biased trajectory corpus
- **Priority:** High
- **Expected Strength Gain:** Indirect — better-conditioned, lower-variance TD fit.
- **Complexity:** Low · **Risk:** Low
- **Dependencies:** none (collection cost only)
- **Suggested Timing:** Alongside the comparison harness.
- **Reason:** Champion-vs-weak rosters skew rows to rank-1 (low label diversity;
  flagged by `trajectory_diagnostics` as `rank_skew`). Vary rosters/seats and hit
  `min_rows_per_phase` in every phase, especially `late`.

### Calibrate label normalisation
- **Priority:** Medium
- **Status:** **Score centre/spread DONE (2026-06-25); rank map still open.**
- **Expected Strength Gain:** Small.
- **Complexity:** Low · **Risk:** Low
- **Dependencies:** trajectory diagnostics (score/rank distributions) — done
- **Suggested Timing:** After the first comparison run.
- **Reason:** `normalized_final_score = tanh((score−40)/20)` hardcoded a neutral
  score of 40 and the rank map `{1:1.0,2:0.5,3:-0.25,4:-1.0}` is arbitrary. Derive
  the centre/spread and rank values from observed distributions.
- **Done:** the committed corpus has terminal-score mean ≈ 82 (median 83, std 19),
  so the old centre of 40 saturated the score component — 75% of terminal rows
  mapped to |v| > 0.9 (mean 0.89). `score_center`/`score_spread` are now
  `TDConfig` fields (CLI `--score-center`/`--score-spread`), defaulting to the
  calibrated `(82, 19)`. The score component now spans [−0.98, +0.97] (mean ≈ 0,
  18% saturated) and blended terminal value separates ranks cleanly
  (1→0.82, 2→0.22, 3→−0.26, 4→−0.89). Weights retrained. **Still open:** derive
  the rank-value map from observed win-equity rather than the hand-picked values.

### Prune dead / duplicate rich features
- **Priority:** Medium
- **Expected Strength Gain:** None (cost/clarity win).
- **Complexity:** Low · **Risk:** Low (feature set is append-only — deprecate, do
  not reorder, to keep artifacts readable)
- **Dependencies:** none
- **Suggested Timing:** Opportunistic.
- **Reason:** `corner_count` is identical to `frontier_size`;
  `reachable_empty_squares` (corr −0.004) and `territory_enclosure_area` (0.000)
  carry ~no signal. Pruning cuts collection cost and sharpens importance reads.

### Trajectory filtering / confidence weighting
- **Priority:** Medium
- **Expected Strength Gain:** Small–Medium (less noise in targets).
- **Complexity:** Medium · **Risk:** Low
- **Dependencies:** larger corpus
- **Suggested Timing:** After corpus growth.
- **Reason:** Down-weight random-seat rows and ultra-early plies; weight terminal
  targets by score-margin confidence.

### Trajectory dedup + provenance
- **Priority:** Medium
- **Expected Strength Gain:** Small (guards against overfitting the roster).
- **Complexity:** Medium · **Risk:** Low
- **Dependencies:** none
- **Suggested Timing:** Before the corpus grows large enough to retrain on stale
  self-play.
- **Reason:** Track collection roster + champion version per row and drop stale
  trajectories so the value model fits the game, not the current champion.

---

## MEDIUM-TERM (remove the bottleneck)

### Richer leaf evaluator  ← TOP medium-term item — **NOW UN-GATED**
- **Priority:** High
- **Expected Strength Gain:** **High** — the change most likely to convert TD's
  richer model into stronger play.
- **Complexity:** High · **Risk:** Medium (new eval path; must stay within MCTS
  leaf budget, not per-rollout-step)
- **Dependencies:** comparison harness confirming the 8-feature ceiling —
  **SATISFIED 2026-06-25** by `exp_e1261b8e0c3b` (TD 25% vs regression 39%, Δμ
  −10; recalibrated labels did not help). The gate condition is met.
- **Suggested Timing:** **Next.** Validation shows TD does not beat regression even
  after label calibration, which points squarely at the 45→8 projection.
- **Reason:** Only 8 of 45 features reach the agent; the most predictive ones do
  not. Evaluating the full rich vector at MCTS *leaves* (called far less often than
  rollout steps) lets `rank_so_far`/mobility/territory influence search. See
  `docs/RICH_FEATURE_ANALYSIS.md`.

### Add top non-SE signals to the live evaluator (interim)
- **Priority:** Medium
- **Expected Strength Gain:** Medium.
- **Complexity:** Medium · **Risk:** Medium (per-step eval cost)
- **Dependencies:** none
- **Suggested Timing:** If the full leaf evaluator is too large a step.
- **Reason:** Extend `BlokusStateEvaluator` to ~9–10 features (`rank_so_far` + a
  score-margin feature) to recover much of the lost signal cheaply.

### TD(λ) with eligibility traces
- **Priority:** High (value) — but **gated**
- **Expected Strength Gain:** Medium, *only once >8 features reach the agent*.
- **Complexity:** Medium · **Risk:** Low
- **Dependencies:** richer leaf evaluator (else still projected to 8)
- **Suggested Timing:** After TD validation demonstrates measurable gains.
- **Reason:** Improves temporal credit assignment; the natural extension of TD(0).
  Removes the single-step bootstrap approximation.

### Opponent-aware / multiplayer value targets
- **Priority:** Medium
- **Expected Strength Gain:** Medium.
- **Complexity:** Medium · **Risk:** Medium
- **Dependencies:** Layer-7 opponent modelling
- **Suggested Timing:** Medium-term.
- **Reason:** Condition terminal value on the opponent roster; anti-kingmaking
  shaping; per-seat (first-move advantage) calibration.

### Online TD updates during self-play
- **Priority:** Medium
- **Expected Strength Gain:** Small (operational robustness).
- **Complexity:** Medium · **Risk:** Medium
- **Dependencies:** none
- **Suggested Timing:** Medium-term.
- **Reason:** Update the value model incrementally in the nightly loop instead of a
  separate batch step; also removes the stale-artifact risk noted in the audit.

### SQLite trajectory backend
- **Priority:** Low
- **Expected Strength Gain:** None (scaling).
- **Complexity:** Medium · **Risk:** Low
- **Dependencies:** corpus outgrowing CSV
- **Suggested Timing:** When `data/td_trajectories.csv` becomes unwieldy.
- **Reason:** Migrate to a table for indexed queries / dedup at scale.

---

## LONG-TERM (high-capacity models — only after the bottleneck is gone)

### Gradient-boosted value model (LightGBM/XGBoost)
- **Priority:** Low (until bottleneck removed)
- **Expected Strength Gain:** High capacity, unproven for this game.
- **Complexity:** High · **Risk:** Medium–High
- **Dependencies:** richer leaf evaluator + fast leaf-only inference path
- **Suggested Timing:** Long-term.
- **Reason:** Captures non-linear feature interactions the linear model cannot.
  Out of scope for Phase 2 (no gradient boosting).

### Policy learning from MCTS visit counts
- **Priority:** Low
- **Expected Strength Gain:** High (search guidance).
- **Complexity:** High · **Risk:** Medium
- **Dependencies:** none structural, but pairs with a value model
- **Suggested Timing:** Long-term.
- **Reason:** Distil normalised root visit counts into a move-ranking model to bias
  rollouts / progressive widening. Out of scope for Phase 2 (no policy learning).

### Neural value network
- **Priority:** Low
- **Expected Strength Gain:** High capacity.
- **Complexity:** High · **Risk:** High
- **Dependencies:** richer evaluator path; inference budget the engine lacks today
- **Suggested Timing:** Long-term.
- **Reason:** Replaces the linear evaluator. Out of scope for Phase 2 (no neural
  networks).

### AlphaZero-style expert iteration
- **Priority:** Low
- **Expected Strength Gain:** Highest, eventually.
- **Complexity:** Highest · **Risk:** High
- **Dependencies:** value network + policy head + search/serving budget
- **Suggested Timing:** Long-term end-state.
- **Reason:** Joint policy+value trained from self-play. Out of scope for Phase 2
  (no AlphaZero-style training).

---

## DONE in Phase 2 (for reference)

- ✅ Phase-boundary bootstrap fix (`next_phase` stored; `V(s_{t+1})` uses next
  state's phase model).
- ✅ Feature normalisation fix (piece-count divisors derive from the engine's
  actual non-standard set) + `training/feature_audit.py` guard.
- ✅ Trajectory quality diagnostics (`training/trajectory_diagnostics.py`).
- ✅ Learning diagnostics (`training/learning_diagnostics.py`): feature importance,
  weight drift, loss→strength correlation, training metrics (target/prediction
  variance, feature variance).
- ✅ Reproducible experiment framework (`training/experiments/`): comparison
  harness, manifests, markdown reports.
- ✅ Status report Learning / Strength / Experiment sections.
