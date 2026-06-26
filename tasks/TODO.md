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
- **Expected Strength Gain:** None directly — it is the *measurement* that unblocks
  every other decision.
- **Complexity:** Low (infra already built in `training/experiments/`)
- **Risk:** Low
- **Dependencies:** a real `data/td_trajectories.csv` + trained
  `td_evaluator_weights.json`
- **Suggested Timing:** Immediately. Nothing below should start until this runs.
- **Reason:** As of Phase 2 there was no committed trajectory corpus, so TD had
  never been validated against regression. `python -m training.experiments.compare`
  produces win/rank/TrueSkill/Elo with confidence intervals and a recommendation.

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
- **Expected Strength Gain:** Small.
- **Complexity:** Low · **Risk:** Low
- **Dependencies:** trajectory diagnostics (score/rank distributions) — done
- **Suggested Timing:** After the first comparison run.
- **Reason:** `normalized_final_score = tanh((score−40)/20)` hardcodes a neutral
  score of 40 and the rank map `{1:1.0,2:0.5,3:-0.25,4:-1.0}` is arbitrary. Derive
  the centre/spread and rank values from observed distributions.

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

### Richer leaf evaluator  ← TOP medium-term item
- **Priority:** High
- **Expected Strength Gain:** **High** — the change most likely to convert TD's
  richer model into stronger play.
- **Complexity:** High · **Risk:** Medium (new eval path; must stay within MCTS
  leaf budget, not per-rollout-step)
- **Dependencies:** comparison harness confirming the 8-feature ceiling
- **Suggested Timing:** Immediately after validation shows TD ≈ regression.
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

## Approach-comparison framework — DONE (this cycle)

- ✅ Audit + diagnosis of why skill was not improving
  (`training/reports/training_audit.md`, `training_diagnosis.md`).
- ✅ `training/approaches/` — first-class candidate generators (baseline_mcts, td,
  heuristic_tune, mcts_param_sweep, hybrid) each returning a `Candidate` with an
  explicit `created`/`reason` and a validated JSON artifact.
- ✅ `training/evaluation/` — fixed benchmark pool + fixed seeds, head-to-head
  battery, statistical promotion gate, noise-aware rating analysis.
- ✅ `nightly_run.run_approaches` orchestrator + CLI (`--approaches/--games/
  --time-budget-minutes/--dry-run`); ratings/history updated only after a valid
  eval; dry-run touches no tracked state.
- ✅ Approach-comparison table in status.md + email; `approach_comparison.md`;
  elo_plot rolling average + promotion markers.

## DEFERRED (next cycles)

Tracked here so the next agent can pick them up. Most are gated on the framework
above now existing.

- **Larger training budgets / self-hosted runner.** Hosted runners cap a job at
  360 min; full heuristic-rollout baselines are slow. A self-hosted runner would
  allow more games/seeds per candidate (tighter CIs) and the full 5-approach roster
  incl. hybrid every night. *(Priority: High · gates statistical power.)*
- **Remote-runner support** for the nightly workflow (matrix/parallel approach
  evaluation across machines).
- **More robust learned evaluators.** Remove the 45→8 projection ceiling (the
  measured bottleneck) before TD(λ)/eligibility traces; let the live agent see the
  top non-SE signals (`score_margin_vs_leader`, `rank_so_far`).
- **Opening-book generation** for the first N plies (cheap, high-leverage).
- **Neural-network evaluator** (AlphaZero-style expert iteration) — gated on the
  richer evaluator + larger corpus.
- **Better human-strength calibration.** The 1700-Elo anchor is unvalidated;
  calibrate against known human benchmarks / external bots in the pool.
- **Web dashboard for training progress** (live Elo trajectory, approach win rates,
  promotion history) instead of committed PNG + markdown.
- **Better rating-uncertainty modelling.** Surface win-rate confidence bands and a
  Bayesian skill estimate; gate promotion on posterior P(candidate > champion).
- **Per-candidate time budgeting inside `evaluate_candidates`.** Today the deadline
  gates only the *start* of evaluation; a slow candidate battery can overrun. Add a
  mid-battery time check and/or move-time caps for the strong baseline.
- **Wire `mcts_param_sweep` to a real internal sweep** (currently emits the best
  a-priori grid point validated by the benchmark battery).

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
