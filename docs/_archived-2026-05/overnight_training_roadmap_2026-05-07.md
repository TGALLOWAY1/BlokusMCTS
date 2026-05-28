# Champion Portfolio Readiness — Findings + Next-Week Overnight Plan

> **Superseded by [`docs/CHAMPION_PROGRESSION.md`](CHAMPION_PROGRESSION.md).**
> Retained for historical context. Champion status claims in this document
> predate the v1 reset and should not be used as the current narrative.

## Context

Recent work (PRs #139–#143, all merged 2026-05-04) built infrastructure for
continuous champion improvement:

- **PR #139** — `scripts/champion_arena.py` (883 LOC): 20-strategy `POOL_CATALOG`,
  persistent TrueSkill across runs (μ−3σ promotion rule, ≥20 games).
- **PR #140** — `scripts/champion_loop.py` v1 + `data/champion_registry.json`:
  iterative loop, snapshot collection at fixed plies, evaluator weight refit.
- **PR #141** — `scripts/champion_loop.py` v2: 5-tier 11-opponent pool,
  retrain trigger every 200 cumulative games.
- **PR #142** — Champion Gauntlet v1 spec (40 games, seed 20260503, Tier 3/4/5).
- **PR #143** — Champion Gauntlet v2 spec (60 games, seed 20260601, swaps
  Tier 4 for Tier 0 `pool_heuristic` "human proxy"); **`se_*` features now
  inlined in arena snapshots** by `analytics/tournament/arena_runner.py`.

The user asked: analyse results, flag gaps in portfolio readiness, plan next
week's overnight runs to advance the champion to human-beating skill.

## Findings (analysis of PRs #139–#143)

1. **Specifications, not results.** `arena_runs/champion_gauntlet_v1/` and
   `…/champion_gauntlet_v2/` contain only `run_config.json` + `summary.md`. No
   `summary.json`, `games.jsonl`, or `snapshots.csv` exist. The gauntlets have
   **never been executed**. `data/champion_registry.json` shows v1 promoted
   2026-04-29 with all win-rate/TrueSkill fields `null`.
2. **Two competing pool systems.** `champion_arena.POOL_CATALOG` (named
   checkpoints, persistent ratings) and `champion_loop.MCTS_VARIANTS`
   (ephemeral, no global rating) both write `data/champion_state.json` with
   incompatible schemas. Running both will corrupt state.
3. **Refit is unconditional.** `champion_loop.run_loop()` writes refit weights
   in-place and overwrites `data/layer6_calibrated_weights.json` with no
   validation arena, no rollback, no version pinning.
4. **No human baseline executed.** Gauntlet v2's `pool_heuristic` Tier 0 is the
   only human-proxy in the design and has not been benchmarked.
5. **No Layer 8 parallelization deployed.** Champion runs single-core at 500 ms.
   `mcts/parallel.py` exists (`ProcessPoolExecutor` root-parallel) and the
   arena agent factory honours `num_workers`, but no production data exists at
   `num_workers > 1`.
6. **Challenge Champion disables too much.** `config/challenge_champion_config.json`
   turns off `opponent_modeling_enabled`, `alliance_detection_enabled`, and
   `adaptive_exploration_enabled`. This is the web-facing artifact — by design
   it is weaker than the Arena Champion. It has not been benchmarked.
7. **Sample sizes are statistically thin.** 40-/60-game gauntlets give
   Wilson-95 CI of roughly ±15% / ±12%. A measured 70% WR could plausibly be
   58%. Multi-seed scaling is required to claim "beats humans".
8. **No tests** for `champion_arena.py` or `champion_loop.py`.

## Portfolio Readiness Gaps

| Gap | Risk | Mitigation in plan |
|---|---|---|
| Gauntlets not executed | We have no real WR vs heuristic baseline | Nights 1–2 |
| Refit applies without gating | Bad weights silently degrade champion | Night 3 (explicit backup + offline candidate + validation arena) |
| Pool fragmentation (champion_arena vs champion_loop) | Corrupted shared state | Use `champion_arena.py` only for promotions; `champion_loop.py --refit` only with state backup. Treat unification as a follow-up code task, not overnight work. |
| Single-core ceiling | Cannot scale thinking time without slowing latency | Night 4 (Layer 8 sweep) |
| Challenge Champion under-featured | Web-facing agent is weaker than research champion | Night 5 (re-enable selectively, benchmark vs heuristic + Arena Champion) |
| Statistical thinness | Cannot defensively claim ≥70% WR vs heuristic | Night 6 (4 seeds × 60 = 240 games) |
| No test coverage on champion infra | Refactors will silently break it | Out of scope this week; flag for follow-up |

## Next Week's Overnight Run Plan

**Operational target:** Challenge Champion (web-facing artifact) achieves
≥70% WR vs `pool_heuristic` over ≥240 games at ≤30 s p95 move latency, with
positive pairwise margin vs Arena Champion v1.

Each night = one ~8 h slot. All runs use `python scripts/arena.py --config <config>`
unless noted. Outputs land in `arena_runs/<run_id>/`.

### Night 1 — Execute Gauntlets v1 + v2 (foundation)
```
python scripts/arena.py --config scripts/arena_config_champion_gauntlet.json
python scripts/arena.py --config scripts/arena_config_champion_gauntlet_v2.json
```
- Wall clock: ~2 h (v1) + ~1.5 h (v2). Fits one slot.
- Outputs: 1280 + 1920 = **3200 `se_*`-enriched snapshot rows** combined.
- Baseline TrueSkill numbers for champion vs Tier 0/3/5 challengers.

### Night 2 — Layer 8 Parallelization Sweep
- Goal: find the (workers, budget) Pareto point that maximises strength while
  keeping p95 move latency ≤ 30 s.
- Grid: `num_workers ∈ {1, 4, 8}` × `thinking_time_ms ∈ {500, 2000, 5000}`,
  24 games each, fixed pool = `pool_heuristic` + `pool_l9_partial_200ms`.
- Why second night: highest variance, first-time use of `mcts/parallel.py` in
  overnight setting. Night 7 is held in reserve to absorb its failure modes.

### Night 3 — Refit + Validation Arena (gated promotion to v2)
1. **Backup** `data/champion_state.json`, `data/champion_registry.json`,
   `data/layer6_calibrated_weights.json` to `data/_backup_<date>/`.
2. Run `python scripts/champion_loop.py --refit` against the cumulative 3200
   snapshots from Night 1. (This is destructive — backup is the safety net.)
3. **Build a `champion_v2_candidate` config manually** using the new weights.
4. Run a fresh **120-game validation arena**: `champion_v1 (old weights)` vs
   `champion_v2_candidate (new)` + `pool_heuristic` + `pool_l9_partial_200ms`.
5. **Promotion gate**: Δμ ≥ 0.5 TrueSkill **and** sign-test p < 0.05 over the
   pairwise champion-vs-candidate games. If pass, update `champion_registry.json`
   to v2; if fail, restore from backup.

### Night 4 — Challenge Champion Benchmark (web-facing artifact)
- Edit `config/challenge_champion_config.json` to selectively re-enable
  `opponent_modeling_enabled=true`, `alliance_detection_enabled=true`,
  `adaptive_exploration_enabled=true`. Keep `loss_avoidance` and
  `sufficiency_threshold` off (UX risk).
- Run 60-game arena: Challenge Champion (30 s adaptive cap) vs
  `pool_heuristic` and Arena Champion (whichever of v1/v2 won Night 3).
- Records the win rate the **public-facing agent actually delivers**.

### Night 5 — Multi-Seed Heuristic-Baseline Test (headline statistical run)
- Re-run Gauntlet v2 with seeds `{20260601, 20260602, 20260603, 20260604}`,
  60 games each = **240 games** total.
- Headline number: cumulative WR of champion vs `pool_heuristic` with
  Wilson-95 CI < ±6%. **This is the "beats humans" claim**, not Night 1.

### Night 6 — Promotion Gauntlet (only if Night 3 promoted v2)
- Run `champion_arena.py` against the full `POOL_CATALOG` for v2, accumulating
  TrueSkill against named checkpoints. Goal: confirm v2 holds top-1 conservative
  rating (μ−3σ) across the full opponent landscape.
- If Night 3 did not promote, use this slot to extend Night 5 to 360 games.

### Night 7 — Spare / rerun
- Reserved for any failed run. Otherwise: capture replay traces from the
  Challenge Champion benchmark for qualitative review (do moves look sensible?
  Any obvious blunders?).

## Critical Files

- `scripts/arena.py` — entry point for all per-night arena calls.
- `scripts/arena_config_champion_gauntlet.json` — Night 1 (v1).
- `scripts/arena_config_champion_gauntlet_v2.json` — Night 1 (v2), Night 5.
- `scripts/champion_loop.py` — Night 3 (`--refit` is destructive; back up first).
- `scripts/champion_arena.py` — Night 6 (full POOL_CATALOG promotion).
- `analytics/tournament/arena_runner.py` — produces `summary.json`,
  `games.jsonl`, `snapshots.csv` per run; honours `num_workers`.
- `mcts/parallel.py` — Night 2 root parallelization.
- `config/challenge_champion_config.json` — Night 4 selective re-enables.
- `config/champion_arena_params.json` — canonical v1 hyperparameters; build
  v2 candidate config from this + new weights.
- `data/layer6_calibrated_weights.json` — overwritten by `--refit`; back up.
- `data/champion_registry.json`, `data/champion_state.json` — back up before
  Night 3.

## Verification

- **Per-night smoke**: every config above already exists; no new code is
  required. Validate by running each config with `--num-games 4` first to
  confirm no parse errors before launching the overnight slot.
- **Output sanity**: each completed run writes
  `arena_runs/<run_id>/{summary.json, games.jsonl, snapshots.csv}` with
  `se_*` columns present in snapshots (test: `head -1 snapshots.csv | grep se_`).
- **Promotion correctness (Night 3)**: confirm
  `data/_backup_<date>/champion_state.json` exists before mutation; confirm
  `data/champion_registry.json` shows `v2` only on validation pass.
- **Headline claim (Night 5)**: cumulative WR vs `pool_heuristic` with
  Wilson-95 CI lower bound ≥ 0.65 to defensively call ≥70% target met.
- **Latency claim (Night 4)**: p95 of move-latency column in `games.jsonl`
  ≤ 30 000 ms across all Challenge Champion games.

## Out of Scope (deferred follow-ups)

- Unifying `champion_arena.POOL_CATALOG` and `champion_loop.MCTS_VARIANTS`
  into a single source of truth.
- Test coverage on `champion_arena.py` / `champion_loop.py`.
- Reviving the GBT learned evaluator (26 ms inference cost remains the
  blocker; revisit only after Night 5 result).
- Imitation learning from human-game data (no data exists; collection is a
  separate project).
