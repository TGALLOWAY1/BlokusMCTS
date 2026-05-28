# Risk Register

> Risks to correctness, results validity, and operability. Last audited: 2026-05-28.

---

## Risk: Conclusions are conditional on the compute regime
Severity: High
Area: Research validity
Description: Full 50-move rollouts are infeasible (>2h/game), so all experiments
use `rollout_cutoff_depth` of 0/5/10 and ~25 games/tournament.
Why it matters: Agent-strength rankings may not hold at higher budgets or game
counts; TrueSkill is often unconverged (σ ~7.5) at 25 games.
Evidence: `KEY_FINDINGS.md`, `TODO.md`, `data/throughput_calibration.json`.
Suggested mitigation: Multi-seed 100+ game validation runs before publishing
strength claims; state the compute regime alongside results.
Owner: maintainer · Status: Open

## Risk: Engine/browser mirror drift produces inconsistent play
Severity: High
Area: Correctness
Description: `browser_python/` re-implements the engine + MCTS; divergence makes
browser results disagree with arena/server results.
Why it matters: Undermines the in-browser demo's credibility and reproducibility.
Evidence: `engine/` vs `browser_python/engine/`; `CODE_QUALITY_AUDIT_NOTES.md`.
Suggested mitigation: Equivalence tests on move-gen/legality (some exist); a
build step or sync check; CI to run both.
Owner: maintainer · Status: Open (partially mitigated by equivalence tests)

## Risk: No CI / no enforced checks
Severity: Medium
Area: Maintainability
Description: Tests, lint, and types are not enforced automatically.
Why it matters: Regressions (esp. in the untested MCTS core) can land silently.
Evidence: no `.github/workflows/`.
Suggested mitigation: Add a CI workflow (pytest, ruff, mypy, frontend lint/vitest).
Owner: maintainer · Status: Open

## Risk: Broken documented quickstart (`pip install -e .`)
Severity: Medium
Area: Onboarding
Description: The README's first step fails with current setuptools.
Why it matters: New contributors/agents hit an immediate wall.
Evidence: reproduced 2026-05-28; see [Technical Debt](TECHNICAL_DEBT.md).
Suggested mitigation: Add setuptools package discovery config; or document the
`pip install -r requirements.txt` path.
Owner: maintainer · Status: Open

## Risk: Unauthenticated API with broad data access
Severity: Medium
Area: Security
Description: No auth/route guards; ownership of games not enforced; `/debug/mongo`
exists.
Why it matters: If the research profile is ever exposed publicly, data is open
and debug endpoints leak internals.
Evidence: `webapi/routes_*.py` (no auth); `/debug/mongo`.
Suggested mitigation: Keep research profile local-only; gate or remove debug
endpoints in any shared deployment. See [Security & Privacy Notes](SECURITY_AND_PRIVACY_NOTES.md).
Owner: maintainer · Status: Open

## Risk: Loss of in-flight games on restart
Severity: Low
Area: Operability
Description: `GameManager` holds live games in memory only.
Why it matters: Restarts drop active games (acceptable for a dev tool).
Evidence: `webapi/game_manager.py`.
Suggested mitigation: Rehydrate from Mongo or document as dev-only.
Owner: maintainer · Status: Open

## Risk: MongoDB URI handling
Severity: Low
Area: Security
Description: Connection string is a secret supplied via env.
Why it matters: Committing a populated `.env` would leak credentials.
Evidence: `.env.example`.
Suggested mitigation: Keep `.env` gitignored; never commit secrets.
Owner: maintainer · Status: Mitigated (`.env.example` only)
