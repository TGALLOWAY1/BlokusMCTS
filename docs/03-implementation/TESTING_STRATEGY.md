# Testing Strategy

> How testing works, what's covered, and the gaps. Last audited: 2026-05-28.
> Pre-merge steps: [Regression Checklist](../04-quality/REGRESSION_CHECKLIST.md).

## Frameworks & config

- **Python:** `pytest` (+ `pytest-asyncio`, `asyncio_mode=auto`). Many suites use
  `unittest.TestCase` but run under pytest. Config in `pyproject.toml`:
  `testpaths=["tests"]`, `pythonpath=[".", "browser_python"]` (so tests import
  `engine.*`/`mcts.*` without installing the package).
- **Frontend:** `vitest` (`npm test`) with `@testing-library/react` + `jsdom`;
  `eslint` (`npm run lint`, max-warnings 0).
- **Type/lint (Python):** `ruff check .`, `mypy .` (strict-ish settings).

## How to run

```bash
pip install -r requirements.txt   # NOTE: `pip install -e .` currently fails — see Technical Debt
pytest                            # full suite
pytest tests/test_engine.py -q    # a single file
ruff check . && mypy .
cd frontend && npm install && npm run lint && npm test && npm run build
```

## Coverage map (`tests/`, ~38 `test_*.py`)

| Area | Tests | Status |
|---|---|---|
| Engine core (board, bitboard, pieces, game-over, pass, results) | `test_engine`, `test_bitboard_basic`, `test_pieces_orientations`, `test_piece_shapes_match`, `test_game_over_logic`, `test_pass_turn`, `test_game_result`, `test_frontier_basic` | Good |
| Engine equivalence (guards browser mirror) | `test_move_generation_equivalence`, `test_legality_bitboard_equivalence`, `test_worker_bridge_save_load` | Good |
| MCTS layers | `test_layer3_action_reduction`, `test_layer5_rave_history`, `test_layer6_eval_refinement`, `test_layer7_opponent_modeling`, `test_layer8_parallelization`, `test_layer9_meta_optimization` | Per-layer only |
| Analytics / metrics | `test_arena_stats`, `test_arena_stats_missing_agents`, `test_baseline_analysis`, `test_metrics_v2`, `test_mobility_metrics`, `test_advanced_metrics_snapshot`, `test_trueskill_rating` | Good |
| Web API | `test_analysis_payload`, `test_analysis_steps_endpoints`, `test_history_payload`, `test_move_error_messages`, `test_deploy_profile_constraints`, `test_webapi_strategy_logger` | Good |
| Challenge Champion | `test_challenge_champion_profile`, `test_challenge_budget`, `test_challenge_gameplay_stats` | Good |
| Agent behavior / telemetry | `test_agent_timeout_behavior`, `test_telemetry`, `test_audit_invariants` | Good |
| Visualization | `test_frontier_video_renderer`, `test_legal_move_count_plot` | Spot |
| Performance | `tests/performance_test.py`, `benchmarks/` | Manual |

Analytics also has its own tests under `analytics/metrics/tests/`.

## Gaps (prioritized)

1. **MCTS core has no dedicated unit test** — UCB1 selection math, expansion of
   untried moves, rollout cutoff, and backup/Q-value updates are only exercised
   indirectly via the per-layer suites. Add `tests/test_mcts_core.py`.
2. **No end-to-end / integration test** of a full game via the API or a full
   arena run (only unit-level coverage).
3. **No CI** enforces any of the above ([Risk Register](../04-quality/RISK_REGISTER.md)).
4. **Frontend tests** exist (vitest configured) but coverage breadth is Unknown
   from static inspection.

## Audit run (2026-05-28)

A smoke subset was run during this documentation pass after installing deps via
`requirements.txt` (the editable install path is broken). Results:

```
pytest tests/test_engine.py tests/test_bitboard_basic.py \
       tests/test_pieces_orientations.py tests/test_game_over_logic.py \
       tests/test_arena_stats.py tests/test_layer5_rave_history.py \
       tests/test_move_generation_equivalence.py
→ 96 passed in 296s
```

All 96 tests in the smoke subset passed (engine, bitboard, pieces, game-over,
arena stats, Layer 5 RAVE, and engine/browser move-gen equivalence). Runtime is
dominated by numba JIT warmup on first import.

> `pip install -e .` failed with "Multiple top-level packages discovered in a
> flat-layout" — `pyproject.toml` needs setuptools package-discovery config.
> Tests run fine without it thanks to the pytest `pythonpath` setting.
