# Context Loading Protocol

> For AI agents working in this repo. Last audited: 2026-05-28.
> **Do not load all docs for every task.** Load the smallest relevant bundle
> below, plus the specific source files you will touch.

Always-useful anchors (cheap): root [`README.md`](../../README.md),
[`CLAUDE.md`](../../CLAUDE.md), and
[`PROJECT_SNAPSHOT.md`](../00-overview/PROJECT_SNAPSHOT.md).

## MCTS / search work
Read:
- `docs/00-overview/PROJECT_SNAPSHOT.md`
- `docs/01-product/FEATURE_INVENTORY.md` (MCTS rows + recommended vs not)
- `KEY_FINDINGS.md` (validated settings)
- root `CLAUDE.md` (Layer 4–9 parameter reference)
- source: `mcts/mcts_agent.py`, `mcts/state_evaluator.py`
Do not read: night results, champion roadmaps, frontend/telemetry docs.

## Engine work
Read:
- `docs/02-architecture/DATA_MODEL.md` (engine entities)
- `docs/engine/move-generation-optimization.md`
- `docs/04-quality/REGRESSION_CHECKLIST.md` (equivalence tests)
- source: `engine/`, and the `browser_python/engine/` mirror (keep in sync!)
Do not read: planning/history docs.

## Arena / experiment work
Read:
- `docs/arena.md`, `docs/datasets.md`
- `docs/config/agents/QUICK_START.md`
- `docs/CHAMPION_PROGRESSION.md` + `docs/arena_run_registry.md` (status)
- source: `scripts/arena.py`, `analytics/tournament/arena_runner.py`

## Frontend / UI work
Read:
- `docs/01-product/SCREEN_INVENTORY.md`, `docs/01-product/USER_FLOWS.md`
- `docs/03-implementation/ROUTE_INVENTORY.md`
- `docs/frontend/README.md`, `docs/08-visuals/VISUAL_REGRESSION_PLAN.md`
- source: `frontend/src/`

## Backend / API work
Read:
- `docs/02-architecture/API_INVENTORY.md` + `docs/03-implementation/ROUTE_INVENTORY.md`
- `docs/02-architecture/DATA_MODEL.md`, `docs/webapi/README.md`
- `docs/04-quality/SECURITY_AND_PRIVACY_NOTES.md`
- source: `webapi/`

## Bug-fix work
Read:
- `docs/04-quality/KNOWN_ISSUES.md` + `docs/04-quality/REGRESSION_CHECKLIST.md`
- only the specific feature/screen/API doc for the affected area
Do not read: the full backlog, decision log, or archived docs.

## Research / evaluation-calibration work
Read:
- `KEY_FINDINGS.md`, `docs/datasets.md`, `docs/02-architecture/DATA_MODEL.md`
- source: `scripts/analyze_layer6_features.py`, `mcts/state_evaluator.py`,
  `analytics/winprob/`

## Documentation work
Read:
- `docs/00-overview/DOCUMENTATION_INDEX.md`
- `docs/06-history/AUDIT_LOG.md`
- `docs/07-ai-context/AGENT_WORKFLOW.md`

## Planning work
Read:
- `docs/05-planning/PRIORITIZED_TODO.md` + `docs/05-planning/NEXT_AGENT_TASKS.md`
- `docs/05-planning/ROADMAP.md`

---
**Avoid loading:** `docs/_archived-2026-05/**`, `archive/**`, old night/roadmap
results, and unrelated metrics/telemetry docs unless directly relevant.
