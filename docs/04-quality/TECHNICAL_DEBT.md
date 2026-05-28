# Technical Debt

> Debt that slows change or invites bugs. Last audited: 2026-05-28.
> The codebase is unusually clean (essentially one `TODO` marker); debt here is
> mostly structural/legacy, not littered code.

| Area | Debt | Severity | Evidence | Suggested action |
|---|---|---|---|---|
| Packaging | `pip install -e .` fails with modern setuptools — flat layout with many top-level packages and no `[tool.setuptools.packages.find]`. Error: "Multiple top-level packages discovered in a flat-layout." | High | `pyproject.toml`; reproduced 2026-05-28 | Add `[tool.setuptools.packages.find]` (or `py-modules`/`packages`) listing `engine, mcts, agents, analytics, webapi, schemas, league, utils, browser_python`. Tests work via pytest `pythonpath` without install, but the documented quickstart is broken. |
| Project identity | RL-era package name/description, `/training*` routes/pages, `TrainEval` naming | Low | `pyproject.toml`, `webapi/routes_research.py`, `frontend/src/pages/Training*` | Rename/remove; see [Known Issues](KNOWN_ISSUES.md). |
| Engine duplication | `engine/`+`mcts/`+`agents/` mirrored by hand in `browser_python/` | Medium | `browser_python/` | Single-source build or automated sync check. |
| Test coverage | No dedicated MCTS-core unit tests; few integration/e2e tests | Medium | `mcts/mcts_agent.py`, `tests/` | Add `tests/test_mcts_core.py`; an end-to-end gameplay test. |
| CI | None | Medium | no `.github/workflows/` | Add pytest + ruff + mypy + frontend lint workflow. |
| API errors | Generic string errors, no structured codes | Low | `webapi/game_manager.py` | Introduce error-code enum if clients need it. |
| Live state | In-memory `GameManager`, no recovery | Medium | `webapi/game_manager.py` | Rehydrate from Mongo or document dev-only. |
| Archive surface | Large `archive/` tree increases dead-code ambiguity and (potentially) test-discovery noise | Low | `archive/` | Confirm `archive/` is excluded from tooling/discovery. |
| Not-recommended features kept enabled-capable | Phase weights, opponent modeling, tree parallel, adaptive-C, GBT evaluator remain in the agent | Low | `mcts/mcts_agent.py` | Keep for research, but ensure defaults/champion configs exclude them (they do). |
| Dead code | `mcts/mcts.py` legacy core appears unused | Low | `mcts/mcts.py` | Confirm unused, then remove. |

Refactors already done (player-mapping constants, generic error messages, typed
agent container) are logged in
[`CODE_QUALITY_AUDIT_NOTES.md`](../../CODE_QUALITY_AUDIT_NOTES.md).
