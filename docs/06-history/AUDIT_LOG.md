# Audit Log

Chronological log of documentation/audit passes. Newest first.

---

# Audit Entry
Date: 2026-06-30
Scope: Training-failure audit follow-up implementation (Phase 8)
Agent: Claude Code (blokus-mcts-audit-followup session)
Summary: Implemented the four remaining recommended fixes from the 2026-06-29
training-failure audit (PR #180 had landed the promotion-failure reporting fix,
`benchmark_v2` MCTS anchors, and the `audit_training_state` diagnostic):
- #5 Fixed-champion measurement-drift reporting — `champion_status` block on the
  comparison record; drift framing in the markdown trajectory, email subject, and
  email verdict when `last_promoted_generation` is null.
- #3 History schema versioning — `schema_version`/`kind` stamps + structural
  `classify_history_row`; diagnostic validates legacy vs approach rows separately.
- #2 Per-game play-quality diagnostics — `play_quality` block in each arena game
  record (legal-move counts, pass/invalid rates, occupancy, piece usage by size,
  score distribution).
- #4 Two-stage promotion — opt-in `--two-stage-promotion`: 20-game screen then a
  60-game confirmation of the leading candidate before promotion.
Files changed: `training/state_store.py`, `training/nightly_run.py`,
`training/evaluation/{report,head_to_head,__init__}.py`, `training/email_summary.py`,
`training/diagnostics/audit_training_state.py`, `analytics/tournament/arena_runner.py`,
`FEATURES.md`, `docs/06-history/CHANGELOG_NOTES.md`; tests added/updated under
`tests/test_training_{promotion_gate,email,dryrun}.py`, `tests/test_arena_play_quality.py`.
Findings: the diagnostic on real state now reports 0 false "missing result-like
fields" (123 legacy + 8 approach rows distinguished). 132 related tests pass.

---

# Audit Entry
Date: 2026-05-28
Scope: Repository-wide documentation infrastructure + audit (this docs pass)
Agent: Claude Code (docs-infrastructure session)
Summary: Established a numbered `/docs/00-overview … /docs/08-visuals`
documentation system over an already heavily-documented repo. Audited the
existing 47-file `docs/` tree, archived stale RL-era (v1) and superseded
point-in-time docs, and migrated current behavior/architecture/quality/planning
into evidence-backed, status-labeled docs. No application/product code changed
(docs-first), aside from pointer additions to root `README.md` / `CLAUDE.md` /
`FEATURES.md`.
Files inspected: root `README.md`, `FEATURES.md`, `KEY_FINDINGS.md`, `TODO.md`,
`CLAUDE.md`, `CODE_QUALITY_AUDIT_NOTES.md`, `pyproject.toml`, `.env.example`,
`frontend/package.json`, all 47 files under `docs/`, and (via exploration
agents) `engine/`, `mcts/`, `agents/`, `analytics/`, `scripts/`, `tests/`.
Docs changed:
- Archived 13 docs → `docs/_archived-2026-05/` with `ARCHIVE_RATIONALE.md`.
- Added the full numbered system: `00-overview/` (README, DOCUMENTATION_INDEX,
  PROJECT_SNAPSHOT), `01-product/` (brief, feature inventory, current behavior,
  user flows, screen inventory), `02-architecture/` (architecture, system map,
  data model, API, state, integrations), `03-implementation/` (codebase + route
  inventory, config, testing strategy), `04-quality/` (known issues, tech debt,
  risk register, regression checklist, security), `05-planning/` (backlog,
  prioritized TODO, roadmap, next agent tasks), `06-history/` (decision log,
  changelog notes, this log), `07-ai-context/` (context-loading protocol, agent
  workflow, CLAUDE entry, prompt inventory), `08-visuals/` (screenshot manifest,
  visual regression plan, flow diagrams).
- Extended root `CLAUDE.md` and `README.md` with documentation pointers; fixed a
  stale FastMCTS reference in `docs/mcts-analysis-mode/01-how-to-use.md`.
- Ran a 96-passing pytest smoke subset; attempted live frontend screenshot
  capture (blocked by network allowlist — documented in the manifest).
Findings:
- Documentation quality was already high; the main gap was navigability and a
  single status-labeled view of what works vs. is partial/not-recommended.
- v1 (RL) residue persists in metadata: `pyproject.toml` name `blokus-rl`,
  description "Reinforcement Learning Environment".
- Test coverage is strong per-layer and on the engine but **lacks dedicated
  MCTS-core unit tests** (UCB selection, expansion, backup) and integration/e2e
  tests; no CI is configured.
- `docs/README.md` index described `evaluation.md` as "state evaluation design"
  but the file was actually an RL evaluation protocol — corrected by archiving.
- `engine/` and `browser_python/engine/` are intentionally mirrored; drift is a
  standing risk (see Risk Register).
Open questions: see [`CODE_QUALITY_AUDIT_NOTES.md`](../../CODE_QUALITY_AUDIT_NOTES.md)
"Open Questions for Project Owner" (persistence model, browser mirror sync,
piece-id source of truth, structured API error codes, archive test-discovery).
Next recommended action: After this pass, prioritize [Next Agent Tasks](../05-planning/NEXT_AGENT_TASKS.md)
— add MCTS-core unit tests and a minimal CI workflow.
Commit: see branch `claude/codebase-docs-infrastructure-PdgpN` history.
