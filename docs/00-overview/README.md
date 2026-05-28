# Documentation

This is the documentation home for **MCTS_Laboratory**. It is organized as a
numbered, status-labeled system designed for both humans and AI agents.

## Quick links
- **New here?** → [Project Snapshot](PROJECT_SNAPSHOT.md)
- **Full map** → [Documentation Index](DOCUMENTATION_INDEX.md)
- **What works / status** → [Feature Inventory](../01-product/FEATURE_INVENTORY.md)
- **How it's built** → [Architecture](../02-architecture/ARCHITECTURE.md)
- **What to do next** → [Prioritized TODO](../05-planning/PRIORITIZED_TODO.md) · [Next Agent Tasks](../05-planning/NEXT_AGENT_TASKS.md)
- **AI agents** → [Context Loading Protocol](../07-ai-context/CONTEXT_LOADING_PROTOCOL.md) · [Agent Workflow](../07-ai-context/AGENT_WORKFLOW.md)

## Layout

| Dir | Contents |
|---|---|
| `00-overview/` | Snapshot, this index/README |
| `01-product/` | Brief, feature inventory, current behavior, flows, screens |
| `02-architecture/` | Architecture, system map, data model, API, state, integrations |
| `03-implementation/` | Codebase + route inventory, config, testing strategy |
| `04-quality/` | Known issues, tech debt, risks, regression checklist, security |
| `05-planning/` | Backlog, prioritized TODO, roadmap, next agent tasks |
| `06-history/` | Decision log, changelog notes, audit log |
| `07-ai-context/` | Context-loading protocol, agent workflow, prompt inventory |
| `08-visuals/` | Screenshot manifest, visual regression plan, flow diagrams |
| `_archived-2026-05/` | Stale RL-era + superseded docs (with rationale) |

Topic docs that predate this system and remain canonical (arena, engine,
metrics, telemetry, champion progression, webapi, frontend) stay in their
existing folders and are linked from the [Documentation Index](DOCUMENTATION_INDEX.md).

## Conventions
- **Status labels:** `Implemented | Partial | Stubbed | Broken | Designed only |
  Deprecated | Unknown`. Document actual behavior; cite evidence with `path:line`.
- **Update docs with code:** see [Agent Workflow](../07-ai-context/AGENT_WORKFLOW.md).

> The previous topic-only index lives at [`docs/README.md`](../README.md); this
> file is the entry point for the numbered system.
