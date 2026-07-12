# Phase 3 — Minimal Trusted Search

- **Purpose:** verify that the minimal search configuration — default `MCTSAgent`: plain UCT +
  maxⁿ per-player vector backup, one tree, one thread, iteration budget, deterministic seeds,
  all experimental layers off — is correct at the node level before measuring whether more
  compute buys strength (Phase 4).

- **Work completed:**
  1. **Node-statistics inspection CLI** — `python -m mcts_lab.node_stats`: runs a seeded
     single-tree search on a `board_state_v1` JSON position (or seeded random plies) and
     prints the root-children table (visits, share, acting-player Q), tree size, and depth
     histogram. Its `run_search_with_root` helper is also the test harness for node-internal
     assertions.
  2. **Search-semantics suite** — `tests/test_minimal_search_semantics.py`: minimal-config
     defaults pinned (all layers off); root visit conservation; pass-node sentinel expansion;
     terminal-rollout reward vectors (winner's own entry carries the bonus); single-legal-move
     short-circuit; same-seed tree-statistics determinism.
  3. **Defect found and fixed — rollout reward baseline.** Verification on the endgame-pocket
     position (two moves: I5 fills a 5-cell pocket → final RED score 6; monomino wastes it →
     final 2) showed BOTH root children at exactly Q = 0.0 with a 40/40 visit split: the
     pre-existing tactical test passed only by move-ordering tie-break. Cause: `_rollout`
     measured per-player rewards as score deltas **from the expanded leaf's own board**, so
     the points banked by the move that created the leaf were subtracted out of its own value —
     sibling comparisons erased exactly the component that differed. End-of-game rollouts
     (the only ones that return deltas; cutoff-hit rollouts return static evals) were blind to
     immediate gains precisely where precision matters most. Fix: `rollout_reward_baseline`
     parameter, default **"root"** — deltas measured from the search-root board, shared by all
     sibling leaves, so child values reflect true final-score differences ("leaf" retained for
     A/B only). Propagated to root-parallel workers via config extraction. Decision D-014.

- **Components changed:** `mcts/mcts_agent.py` (baseline param + capture at `select_action`),
  `mcts/parallel.py` (worker baseline + config propagation), `mcts_lab/node_stats.py` (new).

- **Tests added:** `tests/test_minimal_search_semantics.py` (9, including the A/B pin:
  legacy "leaf" baseline → Q 0.0/0.0 blind; "root" → Q 5.0/1.0 exact separation).

- **Experiments run:** distinguishing probe on the pocket position (Q values above —
  deterministic, the smallest experiment separating "backup bug" from "value-signal bug");
  bounded post-fix sanity arena (champion/baseline/heuristic/random, 4 games, seed 20260620,
  100 ms budgets: champion 62.5% first-place, no collapse — sanity only, not a strength claim).

- **Results / gate criteria → evidence:**
  | Criterion | Evidence |
  |---|---|
  | Search deterministic under fixed seeds | same-seed root-signature equality test; iteration budgets |
  | Multiplayer backup semantics verified | `test_maxn_backprop.py` (mover-credited vectors) + root-children Q perspective assertions |
  | Terminal positions produce correct decisions | pocket position: correct move now wins on **value** (Q 5.0 > 1.0) and visits, not tie-break; terminal reward vector tests |
  | Search benchmarkable independently of learning | `mcts_lab.node_stats` CLI + `run_search_with_root` harness |

- **Unexpected findings:**
  1. The reward-baseline defect above — a plausible contributor to the training plateau
     (candidate evaluators were trained against arena outcomes played by agents whose endgame
     search was value-blind between sibling moves).
  2. The CLI makes the **branching-vs-budget pathology** directly visible: at a 16-ply midgame
     position with 317 legal moves, 200 iterations produce a pure depth-1 tree (every
     iteration expands a fresh root child, 1 visit each); 1 500 iterations reach depth 2 with
     visits concentrating. Phase 4's scaling study must quantify exactly this.

- **Gate result:** **PASS** — after the fix; the pre-fix configuration fails the
  terminal-decision criterion (documented above rather than hidden).

- **Remaining risks:** the fix changes rollout rewards for every MCTS agent (champion
  included): absolute ratings drift across this boundary; era note added to `DATA_LINEAGE.md`.
  The "leaf" option must not silently reappear in configs (constructor validates values).
  Reward scale remains O(score points)+bonus vs static-eval's tanh×100 — two currencies in one
  tree (cutoff vs terminal paths); flagged as a Phase 4/5 measurement item, not changed here.

- **Decision:** D-014 in `../DECISIONS.md`.
- **Next phase:** Phase 4 — the mandatory search-scaling gate (strength vs iteration budget,
  fixed opponents/seeds per `BENCHMARK_PROTOCOL.md`), now measurable with trustworthy
  node-level semantics.

- **Reproduction commands:**
  ```bash
  python -m pytest tests/test_minimal_search_semantics.py tests/test_maxn_backprop.py \
    tests/test_tactical_positions.py -q
  python -m mcts_lab.node_stats --random-plies 16 --board-seed 20260620 --iterations 200
  python -m mcts_lab.node_stats --random-plies 16 --board-seed 20260620 --iterations 1500
  python -m mcts_lab.eval --agents champion,baseline --games 4 --seeds 20260620 --thinking-ms 100
  ```

- **Artifacts:** this PR; `mcts_lab/node_stats.py`; the A/B regression pin in
  `tests/test_minimal_search_semantics.py`.
