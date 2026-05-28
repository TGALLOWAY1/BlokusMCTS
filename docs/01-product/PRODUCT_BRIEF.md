# Product Brief

> What the product is and who it's for. Last audited: 2026-05-28.

## The question

Can a **well-tuned evaluation function beat brute-force search** in 4-player
Blokus MCTS? `MCTS_Laboratory` answers it through a systematic, layered
optimization program backed by reproducible tournaments and ML analysis of
self-play data.

## Audiences

- **Researchers / the author** — run arena experiments, calibrate evaluation
  weights, compare agents with rigorous statistics (TrueSkill, bootstrap CIs).
- **Recruiters / collaborators** — read the "engine → laboratory" story and the
  explainable, in-browser demo (`RecruiterStoryPage`, AI Scoreboard).
- **Players** — play Blokus against the MCTS agent in the browser, with
  move explanations.
- **Future AI agents** — extend the agent or engine using the docs in this tree
  and the [Context Loading Protocol](../07-ai-context/CONTEXT_LOADING_PROTOCOL.md).

## What it delivers

1. **A fast Blokus engine** (`engine/`) — bitboard legality + frontier move
   generation, thousands of simulations/second.
2. **A configurable MCTS agent** (`mcts/mcts_agent.py`) — UCB1 with RAVE,
   progressive widening/history, configurable rollout policies, phase-dependent
   evaluation, opponent modeling, parallelization, and adaptive meta-optimization.
3. **A reproducible arena** (`scripts/arena.py`) — deterministic seeding,
   round-robin scheduling, structured JSON/Markdown/Parquet artifacts.
4. **An ML calibration pipeline** — self-play → 13K+ labeled states → regression
   / Random Forest / SHAP → calibrated evaluation weights.
5. **A web frontend** — interactive board, in-browser MCTS via Pyodide, MCTS
   visualizations, move-impact telemetry, and a results dashboard.

## The headline result

ML-calibrated weights + shallow rollouts (depth 5, 25 iterations) beat 1,000
iterations of default static evaluation. **Rollout quality dominates iteration
quantity.** Full detail and the "what didn't work" list:
[`KEY_FINDINGS.md`](../../KEY_FINDINGS.md).

## Boundaries (what it is not)

- Not an AlphaZero-style learned MCTS — no neural policy/value network drives
  search. (A GBT evaluator was tried and shelved; see Layer 2.)
- Not distributed — parallelization is single-machine (measured on 4 cores).
- Not a general board-game framework — everything is Blokus-specific.

See the [Feature Inventory](FEATURE_INVENTORY.md) for per-feature status and
[Current Behavior](CURRENT_BEHAVIOR.md) for what actually runs today.
