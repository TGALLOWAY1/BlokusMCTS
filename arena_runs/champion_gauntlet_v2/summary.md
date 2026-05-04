# Champion Gauntlet v2

## Overview

- **Run type**: Champion self-improvement gauntlet — reference run v2
- **Champion version**: v1 (configuration identical to Gauntlet v1 for direct comparability)
- **Games**: 60 (round-robin seat rotation, 5 complete rotations for 4 players)
- **Seed**: `20260601`
- **Snapshots**: fixed-ply at plies 8, 16, 24, 32, 40, 48, 56, 64
- **Snapshot enrichment**: every snapshot row now includes `se_` state-evaluator features
  (`se_squares_placed`, `se_accessible_corners`, `se_reachable_empty_squares`, etc.) extracted
  directly during the arena run — no separate `collect_layer6_data.py` pass needed
- **Purpose**: Establish confidence-interval-tight champion v1 win rates, validate v1 TrueSkill
  estimates from Gauntlet v1, and generate a combined 1280-row snapshot dataset (v1) +
  1920-row dataset (v2) for evaluator weight recalibration

To reproduce:
```bash
python scripts/arena.py --config scripts/arena_config_champion_gauntlet_v2.json
```

To run the full improvement loop (which uses this config internally):
```bash
python scripts/champion_loop.py --iterations 1 --games-per-iter 60 --seed 20260601
```

---

## Relationship to Gauntlet v1

Gauntlet v2 is a direct extension of v1 (`seed=20260503`, 40 games). Key changes:

| Parameter | v1 | v2 |
|-----------|----|----|
| Games | 40 | 60 (+50%) |
| Seed | 20260503 | 20260601 |
| Challengers | 3 (Tier 3/4/5) | 3 (Tier 0/3/5) |
| se_ features in snapshots | No | Yes |
| Snapshot rows (this run) | 1280 | 1920 |

The challenger swap (Tier 4 `pool_l9_partial_200ms` → Tier 0 `pool_heuristic`) serves two purposes:
1. Provides a weaker lower anchor for TrueSkill calibration, spreading the leaderboard
2. Measures the champion's advantage over a human-proxy baseline directly

---

## Champion Configuration (v1 — unchanged)

| Layer | Feature | Setting |
|-------|---------|---------|
| 1/2 | UCB1 exploration | C = 1.414, transposition table |
| 3 | Progressive widening | c = 2.0, α = 0.5 |
| 4 | Rollout policy | random, cutoff depth = 5, minimax α = 0.25 |
| 5 | RAVE | k = 1000 |
| 6 | Evaluator weights | Calibrated from 13K+ self-play states, phase-dependent (early/mid/late) |
| 7 | Opponent modeling | Alliance detection (threshold 2×avg), king-maker awareness (gap 15) |
| 9 | Meta-optimization | Adaptive C (BF-normalized), adaptive rollout depth, sufficiency threshold, loss avoidance |

**Thinking time**: 500 ms → ~250 iterations per move at 0.5 iter/ms

---

## Challenger Pool

| Agent | Tier | Budget | Differentiating features |
|-------|------|--------|--------------------------|
| `pool_heuristic` | 0 — Baseline | instant | Pure move-scoring heuristic, no lookahead |
| `pool_l45_100ms` | 3 — L4+5 enhanced | 100 ms (50 iter) | Rollout cutoff, minimax, RAVE — no opponent model, no L9 |
| `pool_peer_500ms` | 5 — Near-peer | 500 ms (250 iter) | Same budget, L3/4/5/9 — **no opponent model** |

**Key tests this run:**
- **Tier 0 gap**: Does the champion's win rate vs `pool_heuristic` validate a human-proxy margin?
  A consistent >60% win rate suggests the champion would beat an average human player.
- **Tier 5 gap (opponent modeling)**: Carries over from v1 — does Layer 7 provide net advantage
  vs an equal-budget agent with identical MCTS structure?

---

## Expected Outcomes

Based on v1 results and Layer 1-9 experiment history:

| Matchup (champion vs) | Expected WR | 95% CI (60 games) | Basis |
|----------------------|-------------|-------------------|-------|
| `pool_heuristic` | 70–85% | ±12 pp | Human-proxy gap (no MCTS lookahead) |
| `pool_l45_100ms` | 55–70% | ±13 pp | 5× more iterations + L7+L9 |
| `pool_peer_500ms` | 45–55% | ±13 pp | Equal iterations; L7 advantage only |

_Win rate CI assumes 15 games per matchup in 4-player round-robin (60 ÷ 4 seats)._

---

## Snapshot Dataset

With `snapshots.enabled=true` at 8 fixed plies per game × 4 players per ply × 60 games:

- **Expected rows**: 1920 (if all games reach all checkpoints)
- **se_ feature columns** (new in v2): `se_squares_placed`, `se_remaining_piece_area`,
  `se_accessible_corners`, `se_reachable_empty_squares`, `se_largest_remaining_piece_size`,
  `se_opponent_avg_mobility`, `se_center_proximity`, `se_territory_enclosure_area`
- **Combined with v1**: 1280 + 1920 = 3200 rows — exceeds the 1000-row threshold in
  `champion_loop.py` for automatic evaluator recalibration

### Evaluator Recalibration Pipeline

Once v2 snapshots are available, run:

```bash
# Inline recalibration via champion loop
python scripts/champion_loop.py --retrain

# Or via the standalone analysis script (full regression + SHAP)
python scripts/analyze_layer6_features.py \
  --input arena_runs/champion_gauntlet_v2/snapshots.parquet
```

The v2 snapshots include `phase_board_occupancy` (from the winprob feature set), enabling
per-phase regression (early/mid/late) to derive updated `state_eval_phase_weights` for the
next champion version.

---

## History and Provenance

| Run | Seed | Games | Snapshot rows | Notes |
|-----|------|-------|---------------|-------|
| [PR #139](https://github.com/TGALLOWAY1/MCTS_Laboratory/pull/139) | various | — | — | Champion arena infrastructure |
| [PR #140](https://github.com/TGALLOWAY1/MCTS_Laboratory/pull/140) | — | — | — | Champion loop + registry |
| [PR #141](https://github.com/TGALLOWAY1/MCTS_Laboratory/pull/141) | — | — | — | Champion loop v2 (5-tier pool) |
| Gauntlet v1 ([PR #142](https://github.com/TGALLOWAY1/MCTS_Laboratory/pull/142)) | 20260503 | 40 | 1280 | Reference spec established |
| **Gauntlet v2 (this run)** | **20260601** | **60** | **1920** | Extended games + se_ enrichment |

---

## Next Steps After Running

1. **Verify win rates** against expected ranges above; large deviations indicate evaluator drift.
2. **Run recalibration** if combined snapshot rows ≥ 1000 (threshold in `champion_loop.py`).
3. **Promote champion v2** if new weights improve validation mini-tournament win rate.
4. **Extend to Gauntlet v3** with the recalibrated champion, using `seed=20260701`.
