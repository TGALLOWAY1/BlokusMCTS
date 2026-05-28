# Next Agent Tasks

> Self-contained prompts another agent (or you) can execute directly. Each
> follows the docs-first workflow ([AGENT_WORKFLOW](../07-ai-context/AGENT_WORKFLOW.md)).
> Last audited: 2026-05-28. Pick from the top of [Prioritized TODO](PRIORITIZED_TODO.md).

---

## Task 1 — Add MCTS-core unit tests

**Context to read first:** `mcts/mcts_agent.py` (`MCTSNode`, `MCTSAgent`
selection/expansion/rollout/backup), `engine/board.py`, `engine/move_generator.py`,
an existing layer test (`tests/test_layer3_action_reduction.py`) for setup
patterns, and `docs/03-implementation/TESTING_STRATEGY.md`.
**Goal:** Add `tests/test_mcts_core.py` directly covering the UCB1 loop.
**Non-goals:** Do not change `MCTSAgent` behavior; do not add new features.
**Acceptance criteria:**
- UCB1 child selection picks the expected child given known visit/Q values.
- Expansion creates children for untried legal moves only.
- Rollout respects `rollout_cutoff_depth` (depth 0 → pure static eval).
- Backup increments visits and updates Q up the path.
- Tests are deterministic (fixed seed, small board/position).
**Checks:** `pytest tests/test_mcts_core.py -q`; sanity-mutate the UCB formula and
confirm a failure.
**Commit:** `test: add dedicated MCTS-core unit tests for UCB/expansion/backup`.

## Task 2 — Fix the editable install (packaging)

**Context to read first:** `pyproject.toml`, `docs/04-quality/TECHNICAL_DEBT.md`
(packaging row), repo top-level layout.
**Goal:** Make `pip install -e .` succeed by adding setuptools package discovery.
**Non-goals:** No restructure into `src/`; no dependency changes.
**Acceptance criteria:**
- Add `[tool.setuptools.packages.find]` (include `engine, mcts, agents,
  analytics, webapi, schemas, league, utils, browser_python`; exclude `tests`,
  `archive`, `scripts`, `benchmarks` as appropriate).
- `pip install -e .` succeeds in a clean venv; `python -c "import mcts, engine,
  analytics"` works.
**Checks:** clean venv → `pip install -e .` → import smoke; `pytest -q` still passes.
**Commit:** `build: configure setuptools package discovery so editable install works`.

## Task 3 — Add a CI workflow

**Context to read first:** `pyproject.toml` (ruff/mypy/pytest config),
`frontend/package.json` (lint/test/build), `docs/04-quality/REGRESSION_CHECKLIST.md`.
**Goal:** Add `.github/workflows/ci.yml` enforcing quality gates on PRs.
**Non-goals:** No deploy automation; no secrets.
**Acceptance criteria:**
- Python job: install `requirements.txt`, run `pytest`, `ruff check .`, `mypy .`.
- Frontend job: `npm ci`, `npm run lint`, `npm test`, `npm run build`.
- Triggers on push + pull_request.
**Checks:** workflow runs green (locally reproduce the commands first).
**Commit:** `ci: add GitHub Actions workflow for pytest, ruff, mypy, and frontend`.

## Task 4 — Combined best-of-all-layers tournament

**Context to read first:** `KEY_FINDINGS.md` (best settings), `docs/arena.md`,
an existing `scripts/arena_config_layer9_adaptive.json` for config shape,
`analytics/tournament/arena_runner.py::build_agent`.
**Goal:** Create `scripts/arena_config_combined.json` pitting the integrated
best-of-layers agent against the baseline and run it.
**Non-goals:** Do not enable not-recommended features (phase weights, opponent
modeling, tree parallel, adaptive-C, GBT).
**Acceptance criteria:**
- Combined agent: `rollout_policy=random`, `rollout_cutoff_depth=5`,
  `minimax_backup_alpha=0.25`, calibrated `state_eval_weights`,
  `rave_enabled=true`/`rave_k=1000`, `num_workers=2`/`parallel_strategy=root`,
  `adaptive_rollout_depth_enabled=true`, vs a default baseline.
- A run completes and writes `arena_runs/<ts>_<id>/` with a summary.
**Checks:** `python scripts/arena.py --config scripts/arena_config_combined.json --num-games 4 --verbose` (smoke), then a full run.
**Commit:** `arena: add combined best-of-layers vs baseline tournament config + report`.

---

When done with any task, update the affected docs (`FEATURE_INVENTORY`,
`KNOWN_ISSUES`, `TESTING_STRATEGY`, etc.) and append an entry to
[`AUDIT_LOG`](../06-history/AUDIT_LOG.md) per the workflow.
