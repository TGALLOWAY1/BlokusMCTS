# Temporal-Difference Learning for the Blokus State Evaluator

Status: **Implemented** (opt-in). Regression learning remains the default and is
fully preserved as a fallback.

This document explains the temporal-difference (TD) learning pipeline that
augments the Layer-6 state-evaluator learning loop with richer features, richer
labels, and trajectory-based value learning — without disturbing the existing
regression path or the conservative promotion gates.

---

## 1. How the old regression learning worked

The legacy ("regression") learner, still the default, works like this:

1. **Snapshots.** During self-play the arena captures board snapshots at fixed
   plies `[8, 16, 24, 32, 40, 48, 56, 64]`. For each snapshot row it records the
   eight `se_` state-evaluator features and, after the game ends, the player's
   `final_score` and `final_rank`. Rows accumulate in
   `data/champion_snapshots.csv`.
2. **Refit.** `scripts.champion_loop.refit_evaluator_weights` fits a separate
   `LinearRegression` of the eight features onto `final_score` for each game
   phase (early / mid / late, by board occupancy), normalises the coefficients
   to `WEIGHT_SCALE = 0.30`, and emits `state_eval_phase_weights`.
3. **Candidate.** `selfplay_core.build_candidate` clones the champion and swaps
   in the fitted phase weights.
4. **Promotion.** The candidate is run through the conservative 6-gate gauntlet
   (`analytics.tournament.gauntlet`) and promoted only if every gate passes.

Limitations: the label is a single fixed-ply→final-score regression (no credit
assignment over time), and the feature space is only eight values.

---

## 2. How TD learning works

TD learning replaces the regression *learner* (not the promotion system) with a
linear value model trained from **trajectories** rather than isolated snapshots.

### Value model

Per game phase we learn `V(s) = w · f(s) + b`, where `f(s)` is the **rich**
feature vector (`rich_blokus_v1`, see §3). Phases are learned independently.

### TD(0) update

For each player's ordered transition `(s_t → s_{t+1})`:

```
target = reward_t + γ · V(s_{t+1})        # non-terminal
target = terminal_value                    # terminal (see §4)
error  = clip(target − V(s_t), clip_lo, clip_hi)
w     += α · (error · f(s_t)) − α · l2 · w
b     += α · error
```

Reward is sparse (0 on every non-terminal step); all signal enters through the
terminal value. The bootstrap `V(s_{t+1})` is evaluated with the **next state's**
phase model, which may differ from the current state's when a transition crosses
a phase boundary (`next_phase` is stored per row; all three phase models are held
simultaneously and updated in an interleaved loop). This corrected a prior
simplification where the current phase's weights were used regardless.

### Agent-compatible projection

The live agent's `BlokusStateEvaluator` only consumes the **eight** Layer-6
features (the rich features are far too slow for per-rollout evaluation). The
rich `rich_blokus_v1` set is therefore a strict **superset** whose first eight
entries are exactly the agent's features. After training, the learned per-phase
rich weights are *projected* onto those eight names and rescaled to
`WEIGHT_SCALE = 0.30`, producing a `state_eval_phase_weights` dict in the exact
format the agent already accepts. Because the eight projected weights are partial
coefficients learned while controlling for the other ~37 features, they are
better-conditioned than a plain 8-feature regression. The full rich weight
vectors are also stored in the artifact for transparency / future use.

---

## 3. Richer features (`rich_blokus_v1`)

Defined in `training/rich_features.py` as `RICH_FEATURE_NAMES` (45 features).
The first eight are the agent's existing features; the additions are:

- **Mobility / move-space:** `legal_move_count`, small/medium/large piece move
  counts, `playable_piece_count`, `total_playable_piece_area`,
  `avg_legal_move_area`, `max_legal_move_area`.
- **Corner / frontier:** `corner_count`, `corner_quality_score`, `frontier_size`,
  `frontier_density`, `frontier_to_opponent_distance`,
  `new_corner_generation_potential`.
- **Piece inventory:** `remaining_piece_count`, singletons / dominoes /
  trominoes / tetrominoes / pentominoes counts, `awkward_piece_penalty`,
  `piece_diversity_score`.
- **Territory & blocking:** `largest_reachable_region`, `trapped_region_count`,
  `trapped_region_area`, opponent mobility avg/max/min, `opponent_corner_pressure`,
  `leader_mobility_pressure`.
- **Score / race:** `score_margin_vs_leader`, `score_margin_vs_next_player`,
  `rank_so_far`, `completion_ratio`, `remaining_area`.
- **Center / board-position:** `edge_pressure`, `quadrant_balance` (plus the SE
  `center_proximity` and `territory_enclosure_area`).

All values are finite floats normalised to keep the linear value in range. Legal
move enumeration — the expensive part — is memoised per board state by
`FeatureCache`, so a 4-player snapshot enumerates each player's moves at most
once.

The feature set is **versioned and append-only**: names and positions are stable
because they become part of persisted training artifacts.

---

## 4. Labels and terminal value

Collected per terminal trajectory row (raw, so the blend stays configurable at
train time): `final_score`, `final_rank`, `won_game`, `top_2_finish`,
`score_margin_to_winner`, `score_margin_to_next`, `score_margin_over_last`,
`winner_id`.

At training time these are blended into a terminal value in roughly `[-1, 1]`:

```
normalized_rank_value:   1st = 1.0, 2nd = 0.5, 3rd = -0.25, 4th = -1.0
normalized_final_score:  tanh((score − score_center) / score_spread)
normalized_score_margin: tanh(score_margin_to_next / 20)

terminal_value = w_rank · rank_value
               + w_score · normalized_final_score
               + w_margin · normalized_score_margin
```

Default blend weights are `0.50 / 0.30 / 0.20` (normalised to sum 1) and are
configurable via the `--blend-*-weight` flags / `TDConfig`.

`score_center` / `score_spread` default to the **calibrated** `(82, 19)` (CLI
`--score-center` / `--score-spread`). The original hardcoded `(40, 20)` sat far
below the committed corpus's mean terminal score (~82, median 83), so the score
component saturated — ~75% of terminal rows mapped to `|v| > 0.9`, collapsing it
to ≈ +1. Centring on the empirical mean keeps it informative: the score component
now spans `[−0.98, +0.97]` (≈18% saturated) and the blended terminal value
separates ranks cleanly (1→0.82, 2→0.22, 3→−0.26, 4→−0.89). The rank-value map is
still hand-picked — deriving it from observed win-equity is open (`tasks/TODO.md`).

## Integration with the nightly approach-comparison framework

TD reaches the nightly run as a first-class **approach** (PR #171): the `td`
generator (`training/approaches/td_learning.py`) re-trains the value model from the
trajectory corpus, writes `training/state/td_evaluator_weights.json`, and builds a
champion clone with the TD-learned `state_eval_phase_weights`; the `hybrid` approach
grafts those weights onto a stronger search. Both construct
`TDConfig(min_rows_per_phase=200)` and leave every other field at its default, so the
**calibrated** `score_center=82 / score_spread=19` are exactly what the nightly run
trains with — no per-approach plumbing needed. Created candidates are evaluated
against the fixed benchmark pool and only promoted through the statistical gate
(`training/evaluation/`); see `training/README.md`. Run a single approach with
`python -m training.nightly_run --dry-run --approaches td --games 8`.

---

## 5. How to run TD training

### Collect trajectories (self-play)

```bash
python -m training.td_selfplay \
    --num-games 200 \
    --seed 2026 \
    --output data/td_trajectories.csv \
    --verbose
```

Each row carries the current- and next-state rich features plus the outcome
labels. Rows are appended (additive), never overwriting. This file is separate
from `data/champion_snapshots.csv`, which is untouched.

### Train the evaluator

```bash
python -m training.td_learning \
    --input data/td_trajectories.csv \
    --output training/state/td_evaluator_weights.json
```

Useful flags: `--gamma`, `--alpha`, `--epochs`, `--l2`, `--clip-td-error LO HI`,
`--min-rows-per-phase`, `--blend-rank-weight`, `--blend-score-weight`,
`--blend-margin-weight`, `--dry-run` (train + print metrics without writing).

The output artifact contains `phase_weights` (agent-compatible),
`rich_phase_weights` (full vectors + bias), `training_metrics`, `config`, and
`feature_set_version`.

---

## 6. How TD candidates are promoted

In the nightly run, select TD mode:

```bash
python -m training.nightly_run --learning-mode td \
    --td-weights-path training/state/td_evaluator_weights.json
```

The TD candidate builder (`selfplay_core.build_td_candidate`):

1. loads `td_evaluator_weights.json`,
2. **clones** the current champion (never mutating it in place),
3. swaps in the TD-learned `state_eval_phase_weights`,
4. tags candidate metadata: `learning_method = "temporal_difference"`,
   `feature_set_version = "rich_blokus_v1"`, `training_rows`, `td_loss`.

The candidate then runs through the **unchanged** conservative 6-gate gauntlet.
If no TD artifact exists yet, the run **falls back to regression** so a cold
start still produces a candidate. Metadata is stripped before any config reaches
the engine or is persisted as the champion.

---

## 7. How to interpret TD metrics

Both `training/status.md` and the morning email show a **Learning Method**
section:

- **TD loss** — mean squared TD error over all rows. Lower is better; trending
  down across runs means the value model fits the trajectories better.
- **Mean abs TD error** — average magnitude of `target − V(s)`; a scale-free
  read on prediction error.
- **Rows by phase** — how much data each phase trained on. A phase below
  `min_rows_per_phase` keeps the default-weight prior and is flagged untrained.
- **Promotion result** — whether the candidate beat the champion through the
  gates. On failure the report shows the **failed gate**, the **runner-up**, the
  head-to-head win rates, the **TrueSkill μ margin**, games, and seeds — so it is
  obvious the agent did not improve and why.

A low TD loss with a failed promotion means the value model is self-consistent
but did not translate into stronger play — expected early, when trajectory
coverage is thin.

---

## 8. Known limitations

- **Phase-boundary bootstrap — FIXED (2026-06).** `V(s_{t+1})` now uses the next
  state's phase model (`next_phase` stored per row, derived for legacy rows by
  `trajectory_store.annotate_next_phase`). See `docs/TD_AUDIT.md`.
- **Only eight weights reach the *rollout* path.** The 8 projected weights drive
  the per-rollout-step static evaluation, because the rich features are too slow
  for per-step use. **Addressed (2026-06) for leaf evaluation:** the optional
  **rich leaf evaluator** (`mcts/rich_leaf_evaluator.py`, flag
  `rich_leaf_eval_enabled`) applies the full `rich_phase_weights` at MCTS leaves
  — called once per simulation, not per rollout step — so `score_margin_vs_leader`,
  `rank_so_far`, mobility, and territory can finally influence search. A cost-tiered
  feature subset (`score` default ≈0.8 ms/leaf) keeps it within the leaf budget by
  dropping the all-player opponent-mobility enumeration. See
  `docs/RICH_FEATURE_ANALYSIS.md §7`.
- **Linear value model.** No non-linear interactions (see follow-ups: gradient
  boosting / value network).
- **Self-play roster bias.** Trajectory quality is bounded by the opponents used
  during collection.
- **TD(0) only.** No eligibility traces yet.

See `tasks/TODO.md` for follow-up ideas.
