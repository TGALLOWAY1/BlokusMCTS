# Roadmap

> High-level direction. Last audited: 2026-05-28.
> Near-term ranked work: [Prioritized TODO](PRIORITIZED_TODO.md).

## Where the project is

The 10-layer MCTS optimization program is **complete** (each layer has arena
results and a written report in `archive/reports/`). The validated best-of-layers
configuration is known (see [`KEY_FINDINGS.md`](../../KEY_FINDINGS.md)). The open
frontier is (a) hardening the codebase for continued development and (b)
strengthening and extending the research results.

## Horizons

### Now — foundation (quality)
- MCTS-core unit tests, fixed packaging, and CI (items 1–3).
- Retire RL-era residue; add an engine/browser sync guard.

### Next — headline experiment & validity
- Combined best-of-all-layers agent vs baseline tournament (item 4).
- Multi-seed 100+ game validation to firm up strength claims (item 7).

### Later — research extensions
- Expanded evaluator features (integrate `center_proximity` and top win-prob
  features; item 8).
- Revisit a cheap learned evaluator (distillation/quantization) only if it fits
  the time budget.
- TD-UCT learning experiment (large; justified by R² < 0.5).

## Operational champion track

The champion self-improvement program runs on its own cadence; the canonical,
live plan and status are:
- [`docs/overnight_training_roadmap_2026-05-14.md`](../overnight_training_roadmap_2026-05-14.md) — live Night-1 reset + Nights 2–7 plan.
- [`docs/CHAMPION_PROGRESSION.md`](../CHAMPION_PROGRESSION.md) — canonical champion-status narrative.
- [`docs/arena_run_registry.md`](../arena_run_registry.md) — per-run status labels.

Superseded roadmaps are preserved in
[`docs/_archived-2026-05/`](../_archived-2026-05/ARCHIVE_RATIONALE.md).
