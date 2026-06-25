# TD Learning — Pipeline Audit

_Status: **Implemented** · Audited 2026-06-24 · Phase 2 (validation & measurement)_

This is a full audit of the temporal-difference (TD) learning pipeline introduced
in Phase 1, written to answer one question before any more algorithms are added:
**is TD learning actually producing stronger Blokus agents than the regression
baseline, and if not, where is the bottleneck?**

Companion docs: `docs/TD_LEARNING.md` (design), `docs/RICH_FEATURE_ANALYSIS.md`
(the 45→8 feature bottleneck), `docs/LEARNING_ROADMAP.md` (prioritised future
work), `tasks/TODO.md` (authoritative deferred-work list).

---

## 0. Executive summary (read this first)

- **TD learning is plausible but unproven.** As of this audit there was **no
  `data/td_trajectories.csv` in the repo** — the TD path had never been run
  end-to-end on committed data, so there was *zero evidence* it improves play.
  The infrastructure to generate that evidence is what Phase 2 adds.
- **The biggest structural bottleneck is not the learner — it is the
  evaluator.** TD trains a 45-feature value model, but only **8 projected
  weights** reach the live agent. Whatever TD learns about the other 37 features
  is discarded at serving time except as a conditioning effect on the 8. See
  §6 and `docs/RICH_FEATURE_ANALYSIS.md`.
- **Two real correctness bugs were found and fixed during this audit:**
  1. **Phase-boundary bootstrap** — `V(s_{t+1})` used the *current* phase's
     weights even when the next state was in a different phase. Fixed: the next
     state's phase model is now used (`next_phase` stored per row).
  2. **Feature normalisation** — `remaining_tetrominoes` / `remaining_pentominoes`
     used hardcoded divisors (5, 12) that assume the *standard* Blokus piece set.
     This engine ships a **non-standard set (1/1/2/6/11 pieces of sizes 1–5, area
     88)**, so `remaining_tetrominoes` could reach **1.2** — an unbounded feature
     in a linear model. Fixed: divisors now derive from the engine's actual piece
     counts. Caught by the new `training.feature_audit`.
- **The champion is not currently getting stronger.** The committed rating
  timeline (`training/state/ratings.sqlite`) shows **19 runs, 0 promotions**, with
  champion Elo drifting **1174 → 1140 (net −35, range 1093–1339)**. Whatever the
  *regression* loop has been doing for 19 runs, it has not cleared the promotion
  gates once. This is the strongest single piece of evidence that the current
  approach has plateaued — and the reason Phase 2 prioritises measurement over
  more algorithms. (See Part 6 / `## 9` below.)
- **Recommended order of work:** (1) generate a real trajectory corpus and run
  the new comparison harness; (2) if TD ≈ regression, the limiting factor is the
  8-feature projection, not the algorithm — build a richer leaf evaluator before
  adding TD(λ)/boosting/networks. Do **not** add learning algorithms until the
  comparison harness shows TD is at least competitive.

---

## 1. Architecture

```
                          ┌─────────────────────────────────────────┐
                          │          NIGHTLY TRAINING RUN            │
                          │           training/nightly_run           │
                          └───────────────┬─────────────────────────┘
                                          │
              ┌───────────────────────────┼────────────────────────────┐
              │                           │                            │
              ▼                           ▼                            ▼
   ┌──────────────────┐        ┌────────────────────┐      ┌────────────────────┐
   │  self-play gens  │        │ candidate builder  │      │  evaluation +       │
   │  selfplay_core   │        │ selfplay_core      │      │  promotion gates    │
   │  .run_generation │        │ .build_candidate   │      │  gauntlet (6 gates) │
   └────────┬─────────┘        └─────────┬──────────┘      └─────────┬──────────┘
            │ snapshots                  │                           │
            ▼  (fixed ply)               │ learning_mode             ▼
   data/champion_snapshots.csv           │                  promote? (internal)
            │                  ┌──────────┴───────────┐
            │                  ▼                      ▼
            │        ┌──────────────────┐   ┌────────────────────┐
            │        │  REGRESSION       │   │   TD (opt-in)       │
            │        │  champion_loop    │   │   td_learning       │
            │        │  .refit_evaluator │   │   (this audit)      │
            │        └─────────┬─────────┘   └─────────┬──────────┘
            │                  │                       │
            │                  │            ┌──────────┴───────────┐
            │                  │            │  td_selfplay (sep.   │
            │                  │            │  game loop)          │
            │                  │            │   → trajectory_store │
            │                  │            │   data/td_trajectories.csv
            │                  │            │  rich_features (45)  │
            │                  │            └──────────┬───────────┘
            ▼                  ▼                       ▼
        8-feature        state_eval_phase_weights  rich weights (45) → PROJECT → 8
        snapshots          (early/mid/late)         training/state/td_evaluator_weights.json
                                  │                       │
                                  └───────────┬───────────┘
                                              ▼
                                   BlokusStateEvaluator (LIVE AGENT)
                                   consumes only the 8 SE features
```

Key observation: both learners converge to the **same 8-dimensional output**
(`state_eval_phase_weights`). TD's 45-feature richness exists only during
training; it is projected down to 8 before it can affect play.

### Module map

| Concern | Module |
|---|---|
| Rich feature extraction (45) | `training/rich_features.py` |
| Trajectory schema / persistence | `training/trajectory_store.py` |
| Self-play trajectory collection | `training/td_selfplay.py` |
| TD(0) learner + projection | `training/td_learning.py` |
| Candidate build / eval / promote | `training/selfplay_core.py`, `training/nightly_run.py` |
| Live evaluator (8 features) | `mcts/state_evaluator.py` |
| **Feature normalisation audit (new)** | `training/feature_audit.py` |
| **Trajectory quality diagnostics (new)** | `training/trajectory_diagnostics.py` |
| **Learning diagnostics (new)** | `training/learning_diagnostics.py` |
| **Experiment framework (new)** | `training/experiments/` |

---

## 2. Data flow (TD path)

```
 self-play game (td_selfplay.play_game)
   └─ per player, per decision point:  extract_rich_features(board, player)  [45 floats]
        │                                  (FeatureCache memoises legal moves)
        ▼
   GameTrajectory: decisions[pid] = [dp0, dp1, ...]  +  terminal_features[pid]
        │
   trajectory_to_rows():  for each dp_i →
        TrajectoryRow(state=dp_i.features,
                      next_state = dp_{i+1}.features (or terminal),
                      phase = dp_i.phase,
                      next_phase = dp_{i+1}.phase,        ← NEW (phase-boundary fix)
                      terminal = (i == last),
                      labels: final_rank/score/margins)
        ▼
   data/td_trajectories.csv   (append-only; f_<name>, nf_<name> columns)
        │
   td_learning.train_from_file():
        load → sort(game,player,ply) → annotate_next_phase() → train_td()
        ▼
   train_td():  bucket by phase → interleaved TD(0) update
        target = γ · V_{next_phase}(s')        (non-terminal, phase-correct)
        target = terminal_value(labels)        (terminal)
        ▼
   PhaseModel per phase (45 weights + bias)
        ▼
   project_to_agent_weights():  slice 8 SE features → rescale to WEIGHT_SCALE
        ▼
   td_evaluator_weights.json  { phase_weights(8), rich_phase_weights(45), metrics }
```

---

## 3. Component-by-component audit

### Trajectory collection (`td_selfplay.py`)
- **Working:** clean, deterministic (seeded), separate from the snapshot path
  (zero risk to regression). Records ordered per-player transitions with a true
  terminal state. `next_phase` now captured.
- **Concern (noise):** the default roster is `champion + heuristic + random +
  heuristic2`. A `random` seat injects low-quality states; that is *fine for
  coverage* but means ~25% of trajectories are near-random play. Value targets
  from those games are noisy.
- **Concern (cost):** `extract_rich_features` enumerates legal moves for **all 4
  players** at every captured decision point (for the opponent-mobility features).
  Empirically ~70 ms per row at collection time — collection is the dominant cost
  of the whole pipeline (a 200-game corpus is ~tens of minutes).
- **Concern (overfitting/bias):** with the champion in seat 1 and weaker
  opponents elsewhere, the champion's rows skew to rank-1 outcomes (low label
  diversity). The new `trajectory_diagnostics` flags this (`rank_skew`).

### Feature generation (`rich_features.py`)
- **Working:** every value is clamped/`tanh`-squashed and a final pass replaces
  non-finite values with 0.0. Versioned, append-only.
- **Bug found & fixed:** piece-count divisors assumed the standard Blokus set;
  this engine is non-standard → `remaining_tetrominoes` exceeded 1.0. Now derived
  from `engine.pieces`. The `feature_audit` test guards against regressions.
- **Concern (redundancy):** several features are near-duplicates —
  `corner_count == frontier_size` (identical formula), and `frontier_size`,
  `corner_quality_score`, `new_corner_generation_potential` are all frontier
  functions. Redundant collinear inputs do not hurt a clamped linear model much
  but add cost and dilute feature-importance reads.

### Label generation (`td_selfplay.margin_labels`, `td_learning.terminal_value`)
- **Working:** rank/score/margin blend is bounded and configurable. Competition
  ranking handles ties.
- **Assumption (possibly incorrect) — RESOLVED 2026-06-25:** `normalized_final_score
  = tanh((score − 40)/20)` hardcoded a "neutral" score of 40 and a spread of 20.
  Against the committed corpus the real terminal-score mean is **~82** (median 83,
  std 19), so the centre of 40 saturated the score component: **75%** of terminal
  rows mapped to `|v| > 0.9` (mean 0.89), collapsing it to ≈ +1. `score_center` /
  `score_spread` are now `TDConfig` fields defaulting to the calibrated `(82, 19)`;
  the score component now spans `[−0.98, +0.97]` (≈18% saturated) and the blended
  terminal value separates ranks (1→0.82, 2→0.22, 3→−0.26, 4→−0.89). The rank-value
  map `{1:1.0, 2:0.5, 3:-0.25, 4:-1.0}` is still hand-picked (open in `tasks/TODO.md`).
- **Assumption:** rank values `{1:1.0, 2:0.5, 3:-0.25, 4:-1.0}` are arbitrary.
  Reasonable, but unvalidated against actual win equity.

### TD update (`td_learning.train_td`)
- **Working:** semi-gradient TD(0) with error clipping and L2 — numerically
  stable; SE-feature slots seeded from `DEFAULT_WEIGHTS` so under-trained phases
  degrade gracefully. **Phase-correct bootstrap now implemented.**
- **Limiting strength gains:** the model is **linear** and is ultimately
  **projected to 8 features**. Even a perfectly trained 45-feature linear value is
  squeezed through an 8-dimensional bottleneck before it can influence the agent.
- **Noise:** sparse reward + bootstrapping off an *untrained* neighbour phase
  early in training injects noise (mitigated by the prior seeding and by training
  all phases together).
- **Instability risk:** `alpha`, `gamma`, `l2`, `clip` are fixed; no learning-rate
  schedule. With a thin corpus the per-phase fit can swing run-to-run — the new
  `learning_diagnostics.weight_drift` measures exactly this.

### Candidate generation (`selfplay_core.build_td_candidate`)
- **Working:** clones champion, swaps weights, tags metadata, falls back to
  regression if no artifact. Metadata stripped before engine/persist. Solid.

### Promotion evaluation (`selfplay_core.evaluate_candidate`, `gauntlet`)
- **Working:** unchanged conservative 6-gate gauntlet; rotating 4-agent battery
  always co-presents champion+candidate; TrueSkill conservative ranking. This is
  the right safety bar and must not be weakened (per constraints).
- **Concern:** the gauntlet measures *promotion*, not *effect size*. A candidate
  can be genuinely-but-marginally better and never promote, and the report only
  said "not promoted". The new experiment harness adds effect sizes + CIs +
  TrueSkill Δμ so "no promotion" can be distinguished from "no improvement".

### Nightly flow (`nightly_run.py`)
- **Working:** durable, resumable, atomic per-generation state; TD mode wired with
  regression fallback. Now also appends a `learning_history.jsonl` row pairing
  training loss with candidate strength (for loss→strength correlation).
- **Concern:** TD training itself is **not** invoked by the nightly run — the
  operator must run `python -m training.td_learning` to refresh the artifact. The
  nightly run only *consumes* the artifact. This is a deliberate separation but
  means a stale artifact can silently persist.

### Reporting / status emails (`status_report.py`, `diagnostics.py`)
- **Working:** Learning Method section, promotion-failure breakdown, diagnosis
  detectors (regression/stagnation/stale-Elo). Now extended with **Strength** and
  **Experiment** sections and loss-trend.
- **Gap closed:** previously no observability tied loss to strength; now wired.

---

## 4. The six audit questions, answered

**1. What is working well?**
The plumbing. Determinism, durability/resume, the additive trajectory schema, the
untouched regression fallback, the conservative promotion gates, and clean
candidate metadata handling are all solid and well-tested.

**2. What assumptions are potentially incorrect?**
(a) That 8 projected weights can carry the value learned over 45 features — the
central architectural bet, and the most likely reason TD won't beat regression.
(b) The `tanh((score−40)/20)` score normalisation centre (40) and the arbitrary
rank-value map. (c) That a champion-vs-weak-opponents roster yields
representative value targets.

**3. What parts are likely limiting strength gains?**
The 45→8 projection (dominant), the linear value model, and thin/biased
trajectory coverage. The *learner* is not the limiter.

**4. What parts introduce noise into training?**
Random-seat trajectories, sparse-reward bootstrapping off under-trained phases,
and small per-phase corpora producing high run-to-run weight drift.

**5. What parts may create overfitting?**
Low label diversity (rank-skewed champion rows), and re-training on a corpus that
keeps accumulating self-play from the *same* champion (the model can fit the
roster, not the game). Trajectory dedup/provenance is deferred (see TODO).

**6. What parts may create instability?**
Fixed learning rate with a thin corpus; cross-phase bootstrap before neighbour
phases are trained; no convergence check. `learning_diagnostics.weight_drift` now
surfaces it; a learning-rate schedule is deferred.

---

## 5. Strengths

- Clean separation of concerns; regression path fully preserved.
- Deterministic + resumable + atomic state.
- Conservative, unchanged promotion gates (no premature promotion).
- Versioned, append-only feature/trajectory schema.
- Now: feature-normalisation audit, trajectory-quality diagnostics, learning
  diagnostics, and a reproducible experiment framework with confidence intervals.

## 6. Weaknesses (ranked by impact on strength)

1. **45→8 projection bottleneck** — the rich model cannot reach the agent. _High._
2. **Unvalidated that TD > regression** — no committed corpus existed. _High._
3. **Linear value model** — no feature interactions. _Medium._
4. **Trajectory coverage/bias** — roster-bound, rank-skewed, no dedup. _Medium._
5. **Label normalisation assumptions** (score centre, rank map). _Low–Medium._
6. **No learning-rate schedule / convergence check.** _Low._

## 7. Risk assessment

| Risk | Likelihood | Impact | Mitigation (status) |
|---|---|---|---|
| TD never beats regression because of the 8-feature bottleneck | High | High | Richer leaf evaluator (deferred, see roadmap); measure with experiment harness first |
| Stale TD artifact silently used | Medium | Medium | Surface `feature_set_version` + age in report (partial); auto-train hook (deferred) |
| Overfitting to champion roster | Medium | Medium | Trajectory dedup/provenance (deferred); diagnostics flag rank skew (done) |
| Unbounded/NaN feature poisoning linear fit | Low (now) | High | `feature_audit` + test invariant (done) |
| Run-to-run weight instability | Medium | Low | `weight_drift` diagnostic (done); LR schedule (deferred) |
| Promotion gate too strict to ever promote a small gain | Medium | Medium | Experiment harness reports effect size + CI so humans can decide (done); gates unchanged by constraint |

## 8. Recommended priorities

1. **Generate a real trajectory corpus and run the comparison harness**
   (`python -m training.experiments.compare`). This is the gate for everything
   else. _(Infra done; run it.)_
2. **If TD ≈ regression: prototype a richer leaf evaluator** that consumes more of
   the 45 features at MCTS leaves (not per rollout step). This attacks the actual
   bottleneck. _(Deferred — see roadmap/TODO; do not start before step 1.)_
3. **Calibrate label normalisation** from observed score distributions
   (diagnostics expose them). _(Small, low-risk; deferred to roadmap.)_
4. **Only then** consider TD(λ), boosting, or a value network — all explicitly
   out of scope until TD validation shows measurable gains.

---

## 9. Strength over time (Part 6 assessment)

Measured from the committed rating timeline (`training/ratings_db.champion_elo_series`):

| Metric | Value |
|---|---|
| Recorded runs | 19 |
| Promotions | **0** |
| Champion Elo (first → last) | 1174.6 → 1139.8 (**−34.8**) |
| Elo range | 1093.3 – 1339.0 |
| Net improvement rate | **≈ −1.9 Elo/run** (i.e. slightly negative) |

**Is the champion getting stronger?** No — over 19 runs Elo is flat-to-declining
and **nothing has ever been promoted**. The swings (±~125 Elo) are consistent with
rating noise from a fixed-strength agent, not learning.

**Is TD outperforming regression?** Unknown — TD had never been run on committed
data. The comparison harness (`training/experiments/`) is validated end-to-end but
a statistically meaningful verdict (≥100 games × ≥10 seeds) needs hours of compute;
at small scale it runs correctly and produces the full metric/CI/recommendation
report. Until that run completes, the honest answer is **no evidence either way**.

**Is learning plateauing?** Yes, on the evidence available: 0 promotions in 19
runs, negative Elo slope, zero promotion frequency. Either the seed champion is
near a local optimum for the 8-feature evaluator, or candidates cannot clear the
(correctly conservative) gates because the 8-feature ceiling caps achievable gains
— which points back to the projection bottleneck (§6, `docs/RICH_FEATURE_ANALYSIS.md`).

The new **Strength** section in `training/status.md` now surfaces these numbers
(current/best Elo + TrueSkill, promotion frequency, improvement rate) every run.

---

_Changes made during this audit are listed in the Phase-2 deliverable summary and
reflected in `FEATURES.md` / `tasks/TODO.md`._
