# Known Issues

> Concrete, evidence-backed issues. Last audited: 2026-05-28.
> Severity: Low | Medium | High | Critical. Status: Open | Mitigated | Closed.

---

## Issue: RL-era identity persists in metadata, routes, and naming
Status: Open
Severity: Low
User impact: Confuses new readers/agents about what the project is; the deploy
build still ships dead RL surface area.
Technical cause: The project pivoted from an RL environment (v1) to MCTS; RL code
was archived but several references remain.
Relevant files: `pyproject.toml` (`name="blokus-rl"`, description "Reinforcement
Learning Environment"); `webapi/routes_research.py` `/api/training-runs*`;
`frontend/src/pages/{TrainingHistory,TrainingRunDetail}.tsx` + routes
`/training`, `/training/:runId`; `TrainEval` page name.
Suggested fix: Rename the package; remove or clearly label the legacy training
routes/pages; rename `TrainEval` to a Layer-Progression name.
Verification: `grep -ri "reinforcement\|training-runs\|MaskablePPO" --include=*.py --include=*.toml`.

## Issue: `last_move` is not tracked in GameManager
Status: Open
Severity: Low
User impact: Clients cannot show the opponent's last move from server state.
Technical cause: Field hard-coded to `None`.
Relevant files: `webapi/game_manager.py` (`last_move=None  # TODO: Track last move`).
Suggested fix: Record the last applied move on the game record and return it.
Verification: create game, make a move, assert `last_move` is populated.

## Issue: MCTS core has no dedicated unit tests
Status: Open
Severity: Medium
User impact: Regressions in selection/expansion/backup could pass CI-less and
silently change agent strength.
Technical cause: Tests target per-layer features and the engine, not the core
UCB1 loop in isolation.
Relevant files: `mcts/mcts_agent.py`; `tests/test_layer*.py` (indirect coverage).
Suggested fix: Add focused tests for UCB1 selection math, expansion of untried
moves, rollout cutoff, and backup/Q-value updates on a tiny deterministic board.
Verification: new `tests/test_mcts_core.py` passes; mutating the UCB formula
fails it.

## Issue: In-memory game state is not recoverable
Status: Open
Severity: Medium
User impact: A backend restart drops all in-flight games.
Technical cause: `GameManager` keeps games in a process-local dict.
Relevant files: `webapi/game_manager.py`.
Suggested fix: Optionally rehydrate from MongoDB, or document as dev-only.
Verification: restart server mid-game; confirm behavior matches docs.

## Issue: Engine logic is duplicated in `browser_python/engine/`
Status: Open
Severity: Medium
User impact: Browser play can diverge from server/arena results if the mirror
drifts.
Technical cause: `browser_python/` is a hand-maintained Pyodide copy of
`engine/` + `mcts/` + `agents/`.
Relevant files: `engine/`, `mcts/`, `browser_python/`; equivalence partly guarded
by `tests/test_worker_bridge_save_load.py` and move-gen equivalence tests.
Suggested fix: Add a sync check or single-source build; expand equivalence tests.
Verification: diff core modules vs their browser mirror.

## Issue: No CI pipeline
Status: Open
Severity: Medium
User impact: Tests/lint/type checks are not enforced on changes.
Technical cause: No `.github/workflows/` committed.
Relevant files: (none) — see [Next Agent Tasks](../05-planning/NEXT_AGENT_TASKS.md).
Suggested fix: Add a workflow running `pytest`, `ruff check`, `mypy`, and
`frontend` `npm run lint`/`vitest`.
Verification: workflow runs green on a PR.

## Issue: `docs/mcts-analysis-mode/01-how-to-use.md` references archived FastMCTSAgent
Status: Open
Severity: Low
User impact: Doc points at an agent type the arena now rejects.
Technical cause: Written before FastMCTS was archived.
Relevant files: `docs/mcts-analysis-mode/01-how-to-use.md`.
Suggested fix: Replace with "MCTSAgent with diagnostics enabled".
Verification: no remaining `FastMCTS` references in active docs.

---

See also: [Technical Debt](TECHNICAL_DEBT.md), [Risk Register](RISK_REGISTER.md),
and the owner open questions in
[`CODE_QUALITY_AUDIT_NOTES.md`](../../CODE_QUALITY_AUDIT_NOTES.md).
