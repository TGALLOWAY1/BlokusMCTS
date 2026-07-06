# Backlog

> Candidate work items with rough scoring. Last audited: 2026-05-28.
> Score = user_impact + tech_risk_reduction + recruiter/demo_value − complexity
> (each −2…+3). Higher = do sooner. Ranked summary: [Prioritized TODO](PRIORITIZED_TODO.md).
> Ready-to-run prompts for the top items: [Next Agent Tasks](NEXT_AGENT_TASKS.md).

---

## Task: Test shorter promotion gate with a longer eval
Status: ✅ ADDRESSED (2026-07-06) — implemented as a *sequential* paired gate rather
than a fixed longer eval. `training/evaluation/sequential.py` (`--sequential-eval`)
runs a seat-balanced SPRT on the paired champion-vs-candidate outcome: decisive
candidates resolve in few games, borderline ones cost more, and the SPRT games double
as the conservative-gate evidence. See AUDIT_REPORT.md §7. Remaining variant to try:
tune `--sprt-elo1` down (chase smaller gains) once an off-Actions parallel runner
affords the extra games.
Priority: Medium (score +4)
Category: Training / evaluation quality
User impact: +2 · Tech risk: +1 · Demo: +0 · Complexity: −1
Why now: We currently run a SHORT eval gate — 20 games/candidate at full 500 ms
MCTS (`head_to_head.EVAL_MIN_TOTAL_GAMES = 20`) — so all four approaches fit one
CI budget. The open question is whether the promotion signal would be *less
noisy* with the opposite regime: a longer eval (60–100 games/candidate), made
affordable by a reduced **uniform** thinking-time override (applied to every
agent so the comparison stays fair), paired with a *shorter/relaxed promotion
gate* (smaller `min_mu_delta` / Elo-delta margin). More games at lower per-move
strength may estimate win-rate / Δμ more tightly than fewer games at full
strength.
Relevant files: `training/evaluation/head_to_head.py`
(`EVAL_MIN_TOTAL_GAMES`, the gauntlet `PromotionThresholds`),
`training/evaluation/promotion_gate.py` (`GateThresholds.min_mu_delta`),
`.github/workflows/nightly-mcts-training.yml` (`games`, `time_budget_minutes`,
and a new uniform `--thinking-time-ms`).
Dependencies: the game-granular / fair-split eval budget (already landed).
Acceptance: a documented A/B comparing promotion-decision stability (variance of
Δμ vs champion across repeated seeds) between (a) short-eval/strict-gate and
(b) long-eval/relaxed-gate at matched wall-clock cost.
Verification: run both configs over the fixed benchmark pool; compare Δμ spread
and false-promotion rate.

## Task: Add MCTS-core unit tests
Priority: High (score +7)
Category: Quality / correctness
User impact: +1 · Tech risk: +3 · Demo: +0 · Complexity: −1 (… nets used above)
Why now: The core search loop is the heart of the project and is only tested
indirectly; without CI a core regression is invisible.
Relevant files: `mcts/mcts_agent.py`; new `tests/test_mcts_core.py`.
Dependencies: none.
Acceptance: tests assert UCB1 child selection, expansion of untried moves,
rollout cutoff behavior, and backup Q/visit updates on a tiny deterministic board.
Verification: `pytest tests/test_mcts_core.py`; mutate UCB formula → test fails.

## Task: Fix editable install / packaging
Priority: High (score +6)
Category: Onboarding / DX
Why now: README step 1 (`pip install -e .`) fails with modern setuptools.
Relevant files: `pyproject.toml`.
Acceptance: `pip install -e .` succeeds; only intended top-level packages installed.
Verification: fresh venv → `pip install -e .` → `python -c "import mcts, engine"`.

## Task: Add CI workflow
Priority: High (score +6)
Category: Quality / infra
Why now: Nothing enforces tests/lint/types; pairs with the MCTS-core tests.
Relevant files: new `.github/workflows/ci.yml`.
Acceptance: CI runs `pytest`, `ruff check .`, `mypy .`, and frontend
`npm run lint`/`vitest` on PRs.
Verification: workflow green on a PR.

## Task: Combined best-of-all-layers tournament
Priority: Medium-High (score +5)
Category: Research
Why now: Individual layers are validated; the integrated agent vs baseline is the
natural headline experiment (open item in `TODO.md` Priority 3).
Relevant files: new `scripts/arena_config_combined.json`; `scripts/arena.py`.
Acceptance: config combines `random` rollout + cutoff 5 + α0.25 + calibrated
weights + RAVE k1000 + root 2w + adaptive depth vs baseline; run + report.
Verification: `python scripts/arena.py --config scripts/arena_config_combined.json --verbose`.

## Task: Retire RL-era residue
Priority: Medium (score +4)
Category: Clarity
Why now: Package name, `/training*` routes/pages, and `TrainEval` naming mislead.
Relevant files: `pyproject.toml`, `webapi/routes_research.py`,
`frontend/src/pages/Training*`, `frontend/src/App.tsx`.
Acceptance: package renamed; legacy training routes/pages removed or clearly
labelled legacy.
Verification: grep shows no active "Reinforcement Learning" identity.

## Task: Engine/browser mirror sync guard
Priority: Medium (score +4)
Category: Correctness
Relevant files: `engine/`, `mcts/`, `browser_python/`.
Acceptance: a check (test or script) flags drift between core and the Pyodide mirror.
Verification: intentionally edit one copy → guard fails.

## Task: Multi-seed 100+ game validation runs
Priority: Medium (score +3)
Category: Research validity
Why now: Current claims rest on 25-game single-seed runs (TrueSkill unconverged).
Relevant files: arena configs; `analytics/tournament/`.
Acceptance: headline results reproduced at ≥100 games, multi-seed, with CIs.

## Task: Expanded evaluator features (center_proximity weight, top win-prob features)
Priority: Medium (score +3)
Category: Research
Why now: `center_proximity` is the #1 RF feature (36%) but carries zero weight.
Relevant files: `mcts/state_evaluator.py`, `data/layer6_calibrated_weights.json`,
`scripts/analyze_layer6_features.py`.
Acceptance: refit weights including center_proximity; arena vs current calibrated.

## Task: Track `last_move` in GameManager
Priority: Low (score +2)
Relevant files: `webapi/game_manager.py`. Acceptance: API returns last applied move.

## Task: Structured API error codes
Priority: Low (score +2)
Relevant files: `webapi/game_manager.py`, `schemas/move.py`.
Acceptance: clients receive `NOT_YOUR_TURN`/`INVALID_MOVE` codes.

## Task: Reduce learned-evaluator inference cost (deferred)
Priority: Low (score +1)
Category: Research (large)
Why now: GBT model (~26ms) is unusable in budget; the sub-0.5ms
`BlokusStateEvaluator` likely supersedes it. Revisit only with distillation.

## Task: TD-UCT learning (deferred, research)
Priority: Low (score +1)
Why now: R²=0.136 ≪ 0.5 threshold; large effort, uncertain payoff.
