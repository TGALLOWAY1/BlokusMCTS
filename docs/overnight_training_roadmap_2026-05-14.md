# Overnight Training Roadmap — 2026-05-14

> **Superseded by [`docs/CHAMPION_PROGRESSION.md`](CHAMPION_PROGRESSION.md)
> for the champion narrative.** The Night-1 reset plan and operational
> details below are still the live execution plan; this banner exists so
> readers know the canonical champion-status story lives in
> `CHAMPION_PROGRESSION.md`.

## Why this exists

The previous roadmap (`overnight_training_roadmap_2026-05-07.md`) executed
Night 1 across PRs #146–#148. The data exposed a flaw in the premise:
`champion v1` (in `data/champion_registry.json`, promoted 2026-04-29 with
all win-rate fields `null`) loses to `pool_peer_500ms` at the same time
budget — **40% / 43% WR across the gauntlets**. The May 14 v2 run
confirmed: TrueSkill conservative `pool_peer_500ms = 29.45` vs
`champion = 19.65` (Δμ ≈ 10 in favor of the simpler peer).

The cause is a configuration mistake, not a search problem. `champion v1`
includes features that `KEY_FINDINGS.md` and `TODO.md` explicitly
documented as harmful, and is missing the single largest measured win in
the program (Layer 8 root parallelization). This roadmap resets the
champion before continuing the original plan.

## Recoverable assets from Nights 1 (PRs #146/#147/#148)

Reusable as-is:

- `arena_runs/20260507_034719_002f9dab/` (40 games, v1 config)
- `arena_runs/20260508_033725_002f9dab/` (40 games, v1 config)
- `arena_runs/20260510_133320_002f9dab/` (40 games, v1 config)
- `arena_runs/champion_gauntlet_v2/{20260508,20260510,20260514}_*` (60 games each)
- ~3,200 `se_*`-enriched snapshot rows for evaluator refit (Night 3 input)
- TrueSkill anchors for `pool_peer_500ms` (μ=50.55), `pool_heuristic` (μ=12.58),
  `pool_l45_100ms` (μ=−2.51) from the May 14 run

Not reusable: any "champion is the best" claim. The recorded data shows
the opposite — these games are evidence of the regression, not a baseline
to defend.

## Champion v1 vs `KEY_FINDINGS.md`

| Feature in champion v1 (`config/champion_arena_params.json`) | Empirical verdict |
|---|---|
| `state_eval_phase_weights` | L6: **0% WR** in 25 games — "failed in practice" |
| `adaptive_exploration_enabled` | L9: **8% WR**, harmful with RAVE (double-exploration) |
| `opponent_modeling_enabled` + `alliance` + `kingmaker` | L7: "no reliable competitive advantage", **2.4× slower** |
| `sufficiency_threshold_enabled`, `loss_avoidance_enabled` | L9: inconclusive, confounded by adaptive C |
| _missing_ `num_workers: 2, parallel_strategy: "root"` | L8 strength: **46% WR, TrueSkill #1** |

The new `champion_minimal` (in `config/champion_minimal_params.json`)
keeps only the validated layers: PW (L3), random + cutoff-5 + minimax
α=0.25 (L4), RAVE k=1000 (L5), calibrated single-vector
`state_eval_weights` (L6), root parallelization 2-worker (L8), adaptive
rollout depth (L9). Total iteration budget identical to v1
(250 iter at 500 ms × 0.5 iter/ms) so the comparison is apples-to-apples
on search work.

## Operational target (unchanged from prior roadmap)

Web-facing Challenge Champion achieves ≥70% WR vs `pool_heuristic` over
≥240 games at ≤30 s p95 move latency, with positive pairwise margin vs
the prior Arena Champion.

## The plan

Each night = one ~8 h slot. All runs use `python scripts/arena.py --config <config>`
unless noted. Outputs land in `arena_runs/<run_id>/`.

### Night 1 — Champion reset (gated promotion to v2)

```
python scripts/arena.py --config scripts/arena_config_night1_champion_reset.json
```

- 60 games × 4 agents: `champion_minimal`, `champion_v1`, `pool_peer_500ms`,
  `pool_heuristic`. Round-robin seat policy.
- **Promotion gate**: `champion_minimal` must beat `champion_v1` by Δμ ≥ 0.5
  TrueSkill **and** have a positive pairwise record. If pass, register as
  `v2` in `data/champion_registry.json`. If fail, do not run Nights 2–4 with
  the new champion — investigate first.
- Wall-clock estimate: champion_minimal should run faster per move than v1
  (no opponent-modeling overhead, parallelization), so total ≤3 h.
- Outputs include 1,920 `se_*`-enriched snapshot rows for Night 3.

### Night 2 — Layer 8 (workers × budget) Pareto sweep

- Grid: `num_workers ∈ {1, 2, 4}` × `thinking_time_ms ∈ {250, 500, 1000}`,
  24 games each, fixed pool = `pool_heuristic` + `pool_l45_100ms`.
- Pick the (workers, budget) cell that maximizes strength under the latency
  cap that matters for your web deploy (default: ≤30 s p95).
- This is the first overnight use of `mcts/parallel.py` outside of the L8
  strength run from 2026-03-26. Capture wall-time-per-move in `games.jsonl`
  for the latency analysis.

### Night 3 — Evaluator refit (gated)

1. **Backup** `data/layer6_calibrated_weights.json` to
   `data/_backup_<date>/` before any mutation.
2. Pool snapshots: 3,200 rows from PRs #146–#148 + 1,920 from Night 1 +
   ~432 from Night 2 = ~5,500 `se_*` rows.
3. Refit **single-vector** `state_eval_weights` only (NOT phase weights —
   L6 confirmed those are broken). Run via `scripts/champion_loop.py
   --refit` (back up `data/champion_state.json` first too — that script
   overwrites in-place).
4. Build `champion_v3_candidate` config from `champion_minimal` +
   refit weights.
5. **120-game validation arena**: `champion_v2 (Night 1 winner)` vs
   `champion_v3_candidate` + `pool_heuristic` + `pool_peer_500ms`.
6. **Promotion gate**: Δμ ≥ 0.5 **and** sign-test p < 0.05 over the
   pairwise champion-vs-candidate games. Restore from backup if fail.

### Night 4 — Multi-seed heuristic-baseline run (headline)

- Replays Night 1 with seeds `{20260514, 20260515, 20260516, 20260517}`,
  60 games each = **240 games**, against `pool_heuristic` only (drop
  the v1 incumbent and the peer; only `pool_heuristic` matters for the
  headline).
- Headline number: cumulative WR with Wilson-95 CI < ±6%. The "beats
  humans" claim lives or dies here, not in Night 1.

### Night 5 — Hyperparameter refinement around the new champion

- Local sweep: `exploration_constant ∈ {1.0, 1.414, 2.0}` × `rave_k ∈
  {500, 1000, 2000}`, 24 games each vs `pool_heuristic` + `pool_peer_500ms`.
- This is post-validation refinement, not architectural. Goal: squeeze
  another 1–3 μ out of the validated stack.

### Night 6 — Spare / extension

- Reserve for any failed run from Nights 1–5.
- If everything succeeded: extend Night 4 to 360 games (4 seeds × 90)
  for an even tighter headline CI, or run the original PR #145 plan's
  Night 6 (`champion_arena.py` against the full `POOL_CATALOG`).

### Night 7 — Optional: revisit opponent modeling at higher budget

The L7 conclusion ("no benefit at low iteration budgets") was made at
25 iter/move. If Night 2 unlocks 1,000+ iterations/move via
parallelization, the per-iteration overhead of opponent modeling
amortizes differently. Worth one targeted ablation:
`champion_v3 + opp_modeling` vs `champion_v3` at the highest-budget cell
from Night 2. **Only run this after Night 4 is in the bag** — don't
re-introduce a debunked feature before the simpler stack has its
headline number.

## Critical files

- `config/champion_minimal_params.json` — canonical v2 candidate (Night 1).
- `config/champion_arena_params.json` — incumbent v1 reference (Night 1 baseline).
- `scripts/arena_config_night1_champion_reset.json` — Night 1 arena config.
- `scripts/champion_loop.py` — Night 3 (`--refit` is destructive; back up first).
- `mcts/parallel.py` — Layer 8 root parallelization (Night 1, 2, all subsequent).
- `data/layer6_calibrated_weights.json` — overwritten by `--refit`; back up.
- `data/champion_registry.json` — update on Night 1 / Night 3 promotion.

## Verification

- **Per-night smoke**: every config above can be smoke-tested with
  `--num-games 4` first to confirm parsing + agent construction (run
  the Night 1 smoke as part of this PR).
- **Output sanity**: each completed run must write
  `arena_runs/<run_id>/{summary.json, games.jsonl, snapshots.csv}` with
  `se_*` columns present (`head -1 snapshots.csv | grep se_`).
- **Promotion correctness (Night 1)**: confirm `data/champion_registry.json`
  shows `v2` with non-null `avg_trueskill_mu` only on validation pass.
- **Headline claim (Night 4)**: cumulative WR vs `pool_heuristic` with
  Wilson-95 CI lower bound ≥ 0.65 to defensively claim ≥70%.
- **Latency claim (Night 2)**: p95 of move-latency column in `games.jsonl`
  ≤ 30,000 ms across all selected (workers, budget) cells.

## What's deliberately deferred

- Unifying `champion_arena.POOL_CATALOG` and `champion_loop.MCTS_VARIANTS`
  into a single source of truth (refactor work, not training).
- Test coverage on `champion_arena.py` / `champion_loop.py` (refactor work).
- Reviving the GBT learned evaluator (26 ms inference cost is still the
  blocker; revisit only if Night 4 stalls).
- Imitation learning from human-game data (no data exists).
