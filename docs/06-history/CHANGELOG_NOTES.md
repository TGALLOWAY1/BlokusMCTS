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

## Phase 7 — Nightly multi-agent training reliability (Jun 2026)
- **Approach-comparison budget actually compares all approaches (2026-06-29).**
  The nightly framework had been silently degenerate: a training report showed
  three of four approaches getting 0 games every run ("time budget exhausted")
  while `td_learning` alone ran ~199 min against a 45-min budget. Root cause —
  the eval deadline was only checked *between* `(arena, seed)` sub-batteries, so
  the first uninterruptible 100-game battery ate the whole budget and every later
  approach (including `baseline_mcts`, the one able to lift the champion off the
  sub-heuristic floor) was skipped.
- Fix landed on three fronts: **game-granular interruption** (`run_experiment`
  takes a `deadline` checked before each game), a **fair per-candidate budget
  split** (each remaining candidate gets an equal share of the time left,
  recomputed so unused time rolls forward), and a **self-consistent workflow
  config**. Also fixed a **false-positive regression alarm** — a fixed champion's
  Elo move is sampling variance, not a skill regression, so it is downgraded from
  a `regression` warn to an `elo_variance` info.
- **Short eval gate** (`EVAL_MIN_TOTAL_GAMES = 20`) chosen as the starting point
  so all four approaches fit one CI run; a backlog item tracks A/B-testing a
  longer eval with a relaxed promotion gate.
- **Health-verified (2026-06-29):** a smoke run on a temp state copy evaluated
  **4/4 approaches** within a tight budget (vs 1/4 before the fix), confirming the
  fair split no longer starves any approach. 44 training tests pass.

## Phase 8 — Training-failure audit follow-ups (Jun 2026)

The 2026-06-29 training-failure audit confirmed the champion was never getting
*worse* — the same `gen0` champion had simply never been promoted, while its Elo
was updated through small, time-starved samples, so a noisy decline read as a
regression. PR #180 fixed the promotion-failure reporting bug, added the
`benchmark_v2` MCTS anchors, and the `audit_training_state` diagnostic. This phase
implements the four remaining recommended fixes:

- **Fixed-champion measurement-drift reporting (#5).** When `last_promoted_generation`
  is null the agent under measurement is byte-for-byte fixed, so Elo movement is
  rating *drift*, not strength. The comparison record now carries a `champion_status`
  block; the markdown retitles the Elo trajectory as "fixed-champion measurement
  drift", the email subject annotates the delta `(…, drift)`, and the verdict reports
  `➖ STEADY — fixed-champion measurement drift` instead of `✅ GOING WELL` on a
  noise-driven rise (unless a candidate actually promoted this run).
- **History schema versioning (#3).** Every `history.jsonl` row is stamped with
  `schema_version`/`kind`; `classify_history_row` classifies older unstamped rows
  structurally, so the diagnostic validates legacy and approach-comparison rows
  separately and no longer flags the 123 legacy rows as "missing result-like
  fields".
- **Per-game play-quality diagnostics (#2).** Each arena game record now carries a
  `play_quality` block (avg/min/max legal moves per turn, pass rate, invalid-move
  count, game length, board occupancy, piece usage by size overall + per agent,
  final-score min/max/spread), computed at record time with negligible overhead.
- **Two-stage promotion (#4, opt-in `--two-stage-promotion`).** The 20-game gate
  is the *screen*; before promoting, only the leading candidate is re-evaluated over
  a 60-game confirmation sample and must clear the gate again, so a lucky short run
  can no longer promote on its own. Default behavior is unchanged when the flag is off.

Health-verified: 132 related tests pass; the `audit_training_state` diagnostic on
the real state shows 0 false "missing result-like fields" (123 legacy + 8
approach-comparison rows correctly distinguished).

> This file is a high-level summary, not a per-commit changelog. For commit-level
> history use `git log`; for arena-run-level history see the run registry.
