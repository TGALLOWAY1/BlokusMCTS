# CLAUDE.md — Project Guidelines for Claude Code

## What this repo is

A 4-player Blokus AI lab: game engine (`engine/`), canonical MCTS agent
(`mcts/mcts_agent.py`), seeded arena (`analytics/tournament/`), a durable
nightly training pipeline (`training/` + `mcts_lab/` CLIs), and a web demo
(`webapi/` + `frontend/`). Start with `README.md`, then `AUDIT_REPORT.md`
(July 2026: repo simplification, maxⁿ reward fix, new workflow).

## Canonical workflow (use these, not ad-hoc scripts)

```bash
python -m mcts_lab.checks        # fast sanity gate
python -m mcts_lab.eval --agents champion,baseline --games 10 --seeds 20260620,20260621
python -m mcts_lab.self_play --games 24
python -m mcts_lab.train
python -m mcts_lab.promote --candidate training/artifacts/candidates/<artifact>.json
```

Tests: `python -m pytest tests/ -q` (slow — MCTS tests play real games; use
`-n 4` with pytest-xdist and target specific files while iterating).

## Rules that keep the lab honest

- **Agent type:** always `"type": "mcts"` (MCTSAgent). The arena rejects the
  removed `fast_mcts` type by design — do not resurrect it.
- **Rewards are per-player (maxⁿ).** `MCTSAgent._rollout` and the leaf
  evaluators return a `Dict[Player, float]`; `_backpropagation` credits each
  node with the reward of the player who moved into it. Never reintroduce a
  single root-perspective scalar — that bug cost months of plateaued training
  (AUDIT_REPORT.md §3.1).
- **Champion changes go through the gate.** Only `mcts_lab.promote` (or the
  nightly `training.nightly_run`) may write `training/state/champion.json`.
  Never hand-edit champion params without a gated evaluation.
- **Rollout policies:** `greedy_sample` (default choice for strength/cost),
  `random` (fast, weak), `heuristic` (scores every legal move every step —
  ~10x slower, use only with short cutoffs), `two_ply` (very slow).
- **Layer-experiment conclusions from before the maxⁿ fix are invalid.**
  RAVE / minimax-backup / adaptive-depth verdicts must be re-measured before
  being trusted or re-enabled.
- **`browser_python/` is generated** by `scripts/build_browser_core.sh`
  (except `worker_bridge.py`, which is source). Never edit the generated
  copies; edit `engine/ mcts/ agents/` and rebuild the bundle.

## Key MCTS parameters (mcts/mcts_agent.py)

- `iterations` / `time_limit` / `deterministic_time_budget` + `iterations_per_ms`
- `exploration_constant` (default 1.414), `heuristic_move_ordering`
- `rollout_policy` (`greedy_sample` recommended), `greedy_sample_size` (12),
  `rollout_cutoff_depth` (cut rollout, static-eval all players), `max_rollout_moves`
- `state_eval_weights` / `state_eval_phase_weights` (Layer-6 evaluator)
- Experimental, off by default: `rave_enabled`/`rave_k`, `nst_enabled`,
  `minimax_backup_alpha`, `progressive_widening_enabled`, opponent modeling
  (`opponent_modeling_enabled`, …), parallelization (`num_workers`, …)

## Docs

`docs/README.md` is the index; keep new docs small and current. When you
change behavior, update the affected doc (or delete it if it's now wrong) in
the same commit. Do not create sprawling status/feature-inventory files —
README + AUDIT_REPORT are the source of truth.
