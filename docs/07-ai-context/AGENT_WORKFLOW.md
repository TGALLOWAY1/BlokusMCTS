# Agent Workflow

> How an AI agent should work in this repo. Last audited: 2026-05-28.

## Before coding
1. Load the smallest context bundle from
   [Context Loading Protocol](CONTEXT_LOADING_PROTOCOL.md) plus the files you'll edit.
2. `git status` — if there are uncommitted changes you did not make, **do not
   overwrite them**; report and stop if unsafe.
3. Check whether behavior is `Implemented | Partial | Stubbed | Broken |
   Designed only | Deprecated | Unknown` in
   [FEATURE_INVENTORY](../01-product/FEATURE_INVENTORY.md) before assuming it works.

## While coding
- This is a **documentation-first** repo: do not refactor product code unless the
  task asks for it.
- Reuse existing utilities; check `analytics/tournament/arena_runner.py`,
  `mcts/champion_profile.py`, and `engine/` before writing new code.
- Keep the `browser_python/` mirror in sync if you change `engine/`/`mcts/`/`agents/`.
- Respect validated findings: do not re-enable not-recommended features (phase
  weights, opponent modeling, tree parallel, adaptive-C, GBT) in default/champion
  configs. See [`KEY_FINDINGS.md`](../../KEY_FINDINGS.md).

## After coding
1. Run the relevant parts of the
   [Regression Checklist](../04-quality/REGRESSION_CHECKLIST.md).
2. Update affected docs **in the same change**:
   - new/changed/removed feature → root [`FEATURES.md`](../../FEATURES.md) **and**
     [FEATURE_INVENTORY](../01-product/FEATURE_INVENTORY.md).
   - new bug or fix → [KNOWN_ISSUES](../04-quality/KNOWN_ISSUES.md).
   - design choice → [DECISION_LOG](../06-history/DECISION_LOG.md).
   - any audit/refactor pass → append to [AUDIT_LOG](../06-history/AUDIT_LOG.md).
   - UI change → re-capture screenshots + update
     [SCREENSHOT_MANIFEST](../08-visuals/SCREENSHOT_MANIFEST.md).
3. Mark behavior accurately: only call something `Implemented` if it actually
   works; otherwise `Partial`/`Stubbed`/`Broken` with evidence.

## Committing
- Small, focused commits; never bundle unrelated changes.
- Create new commits (don't amend published ones); don't skip hooks.
- Don't commit secrets (`.env`) or large binaries.
- Push to the working branch; open a PR only if explicitly asked.

## Avoiding context bloat
- Don't load the full decision log, archived docs, or unrelated inventories.
- Prefer the inventories/tables in `docs/` over re-greping the whole tree.
- Use `path:line` references rather than pasting large code blocks.
