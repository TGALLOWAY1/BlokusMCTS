# TD Learning — Follow-up Ideas

Follow-up work for the temporal-difference learning pipeline
(`training/td_learning.py`, `training/td_selfplay.py`,
`training/rich_features.py`, `training/trajectory_store.py`). See
`docs/TD_LEARNING.md` for the current design and known limitations.

## Learning algorithm
- [ ] **TD(λ)** with eligibility traces — credit assignment beyond one step;
      removes the single-step bootstrap approximation.
- [ ] **Store next-state phase** in trajectory rows so the bootstrap value uses
      the correct phase weights across phase boundaries.
- [ ] **Learned value model with gradient boosting** (e.g. LightGBM/XGBoost) over
      the rich feature set — captures non-linear feature interactions the linear
      model cannot. Would need a faster path or a leaf-only evaluator to use in
      play.
- [ ] **AlphaZero-style policy/value network** — joint policy + value head trained
      from self-play, replacing the linear evaluator entirely.

## Policy / search integration
- [ ] **Policy learning from MCTS visit counts** — distil the search policy
      (normalised root visit counts) into a move-ranking model to bias rollouts /
      progressive widening.
- [ ] **Leaf evaluator using the rich model** — a slower, higher-fidelity leaf
      evaluation that consumes the full rich weight vector at MCTS leaves (vs the
      8-feature fast eval used per rollout step).

## Targets / multiplayer
- [ ] **Opponent-specific value targets** — condition the terminal value on the
      opponent roster so the evaluator learns matchup-aware values.
- [ ] **Multiplayer anti-kingmaking metrics** — terminal-value shaping that
      penalises handing the win to a third player; tie into Layer-7 opponent
      modeling (alliance / king-maker detection).
- [ ] **Per-seat value calibration** — account for first-move / seat advantage in
      the normalised score targets.

## Data / tooling
- [ ] **Trajectory dedup + provenance** — track collection roster + champion
      version per row and de-duplicate stale trajectories before training.
- [ ] **SQLite trajectory backend** — migrate `data/td_trajectories.csv` to a
      table if/when the corpus outgrows CSV.
- [ ] **Online TD updates** — update the value model incrementally during the
      nightly self-play loop rather than as a separate batch step.
- [ ] **Feature ablations** — measure each rich feature group's contribution to TD
      loss and promotion rate; prune low-value features.
