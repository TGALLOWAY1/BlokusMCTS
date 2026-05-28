# Regression Checklist

> Run before merging changes that touch the engine, MCTS, arena, API, or
> frontend. Last audited: 2026-05-28.

## Setup
- [ ] Deps installed: `pip install -r requirements.txt` (note: `pip install -e .`
      currently fails — see [Technical Debt](TECHNICAL_DEBT.md)). Tests import via
      pytest `pythonpath = [".", "browser_python"]`.

## Python — core & engine
- [ ] `pytest tests/test_engine.py tests/test_bitboard_basic.py tests/test_pieces_orientations.py tests/test_game_over_logic.py tests/test_pass_turn.py`
- [ ] `pytest tests/test_move_generation_equivalence.py tests/test_legality_bitboard_equivalence.py` (guards engine/browser parity)
- [ ] `pytest tests/test_game_result.py tests/test_audit_invariants.py`

## Python — MCTS layers
- [ ] `pytest tests/test_layer3_action_reduction.py tests/test_layer5_rave_history.py tests/test_layer6_eval_refinement.py tests/test_layer7_opponent_modeling.py tests/test_layer8_parallelization.py tests/test_layer9_meta_optimization.py`
- [ ] (Gap) MCTS-core UCB/selection/backup — no dedicated test yet ([Known Issues](KNOWN_ISSUES.md)).

## Python — analytics & API
- [ ] `pytest tests/test_arena_stats.py tests/test_trueskill_rating.py tests/test_metrics_v2.py tests/test_mobility_metrics.py`
- [ ] `pytest tests/test_analysis_steps_endpoints.py tests/test_move_error_messages.py tests/test_deploy_profile_constraints.py tests/test_worker_bridge_save_load.py`

## Full suite & quality gates
- [ ] `pytest` (all of `tests/`)
- [ ] `ruff check .`
- [ ] `mypy .`

## Arena smoke (documented commands actually run)
- [ ] `python scripts/arena.py --config scripts/arena_config.json --num-games 4 --verbose`
- [ ] Confirm a new `arena_runs/<ts>_<id>/` with `summary.json`, `games.jsonl`,
      `snapshots.parquet`, `run_config.json`.

## Frontend
- [ ] `cd frontend && npm install`
- [ ] `npm run lint` (max-warnings 0)
- [ ] `npm test` (vitest)
- [ ] `npm run build` (tsc + vite)
- [ ] Manual: `npm run dev`, open `/`, click **Run Demo Game**, verify AI-vs-AI
      plays and **Explain This Move** shows candidates; open `/benchmark` matrix.

## Visual
- [ ] Re-capture screenshots if UI changed; update
      [Screenshot Manifest](../08-visuals/SCREENSHOT_MANIFEST.md).
