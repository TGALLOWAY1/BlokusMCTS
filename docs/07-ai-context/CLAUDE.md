# AI Context (docs tree)

> Entry point for AI agents working from the `docs/` tree. The **authoritative**
> project rules live in the repo-root [`CLAUDE.md`](../../CLAUDE.md) (agent
> selection, MCTS parameter reference, FEATURES.md maintenance rule). This file
> adds the documentation/context conventions. Last audited: 2026-05-28.

## Read these first
- [`CONTEXT_LOADING_PROTOCOL.md`](CONTEXT_LOADING_PROTOCOL.md) — load the smallest
  relevant doc bundle per task type.
- [`AGENT_WORKFLOW.md`](AGENT_WORKFLOW.md) — inspect-before-coding,
  update-docs-after, commit discipline.
- [`../00-overview/DOCUMENTATION_INDEX.md`](../00-overview/DOCUMENTATION_INDEX.md) — map of all docs.

## Hard rules (from root CLAUDE.md — do not violate)
- **Use `"type": "mcts"` (`MCTSAgent`) for all arena/eval.** `fast_mcts` /
  `gameplay_fast_mcts` are archived and rejected by the arena runner.
- **Maintain `FEATURES.md`** when adding/changing/removing functionality, and
  mirror status in [FEATURE_INVENTORY](../01-product/FEATURE_INVENTORY.md).

## Status-label discipline
Use exactly: `Implemented | Partial | Stubbed | Broken | Designed only |
Deprecated | Unknown`. Document **actual** behavior; mark inferences as inferred;
cite evidence with `path:line`.

## Documentation map (where things live)
- What works / status → `01-product/FEATURE_INVENTORY.md`, `01-product/CURRENT_BEHAVIOR.md`
- How it's built → `02-architecture/*`, `03-implementation/*`
- Risks / issues / tests → `04-quality/*`
- What to do next → `05-planning/*`
- Why decisions were made → `06-history/DECISION_LOG.md`
- Screens & visuals → `01-product/SCREEN_INVENTORY.md`, `08-visuals/*`
- Kept topic docs (canonical) → `docs/arena.md`, `docs/engine/*`, `docs/metrics/*`,
  `docs/telemetry/*`, `docs/webapi/*`, `docs/CHAMPION_PROGRESSION.md`
- Archived (avoid) → `docs/_archived-2026-05/`, `archive/`
