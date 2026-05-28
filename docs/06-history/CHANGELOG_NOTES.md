# Changelog Notes

> Condensed milestone timeline. Last audited: 2026-05-28.
> Full narrative: [`docs/project-history.md`](../project-history.md). Decisions:
> [DECISION_LOG](DECISION_LOG.md). Per-run arena status:
> [`docs/arena_run_registry.md`](../arena_run_registry.md).

## Phase 1 — RL foundation (Nov–Dec 2025)
- Full-stack RL scaffold: engine, agents, frontend, PettingZoo/Gymnasium wrappers,
  MaskablePPO training.
- VecEnv compatibility; throughput benchmarks.
- **Frontier + bitboard move generation (M6)** — made simulation throughput a
  first-class concern (the turning point).
- Canonical `GameResult`, win detection, dead-agent handling.

## Phase 2 — From training to evaluation (Jan–Feb 2026)
- Self-play league & Elo training; agent registry.
- Stage-3 analytics platform (logging, metrics, tournament utilities,
  Analysis/History pages).
- **Browser-side MCTS via Pyodide** — zero-backend-cost gameplay.

## Phase 3 — MCTS research tooling (Mar 2026)
- Reproducible arena runner + learned evaluator integration; snapshot datasets.
- Fair-time tuning & multiseed benchmarks; metrics v2 & move-delta telemetry.
- **RL archival** (2026-03-06) → `archive/rl/`; MCTS-first reframing.
- MCTS analysis mode (search introspection UI).
- Performance re-audit (bitboard regression fix); end-to-end eval-model pipeline.
- Layer 1 baseline characterization.

## Phase 4 — Layered MCTS optimization (Mar–Apr 2026)
- Layers 1–10, each with arena experiments and a report in `archive/reports/`.
  Headline: rollout quality > iteration quantity; calibrated weights (76% WR);
  RAVE k=1000; root parallelism; adaptive rollout depth. See
  [`KEY_FINDINGS.md`](../../KEY_FINDINGS.md) and [DECISION_LOG](DECISION_LOG.md).

## Phase 5 — Champion program (Apr–May 2026)
- Champion self-improvement loop, registry, gated promotion. `champion_v1`
  documented as a failed candidate; `champion_minimal` is the current candidate;
  no validated champion yet. Canonical:
  [`docs/CHAMPION_PROGRESSION.md`](../CHAMPION_PROGRESSION.md).

## Phase 6 — Documentation infrastructure (May 2026)
- This pass: numbered `docs/00-08` system, archived stale RL-era/superseded docs,
  status-labeled inventories, risk register, planning, and AI-context protocol.

> This file is a high-level summary, not a per-commit changelog. For commit-level
> history use `git log`; for arena-run-level history see the run registry.
