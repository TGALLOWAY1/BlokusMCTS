# Champion Gauntlet v1

## Overview

- **Run type**: Champion self-improvement gauntlet (reference specification)
- **Champion version**: v1
- **Games**: 40 (round-robin seat rotation)
- **Seed**: `20260503`
- **Snapshots**: fixed-ply at plies 8, 16, 24, 32, 40, 48, 56, 64
- **Purpose**: Establish champion v1 baseline TrueSkill and generate initial snapshot data for evaluator refinement

To reproduce:
```
python scripts/champion_loop.py --iterations 1 --games-per-iter 40 --seed 20260503
```

---

## Champion Configuration (v1)

The champion encodes all beneficial MCTS layers identified through the Layer 1-9 experiments:

| Layer | Feature | Setting |
|-------|---------|---------|
| 1/2 | UCB1 exploration | C = 1.414, transposition table |
| 3 | Progressive widening | c = 2.0, α = 0.5 |
| 4 | Rollout policy | random, cutoff depth = 5, minimax α = 0.25 |
| 5 | RAVE | k = 1000 (β ≈ 0.18 at N=100) |
| 6 | Evaluator weights | Calibrated from 13K+ self-play states, phase-dependent (early/mid/late) |
| 7 | Opponent modeling | Alliance detection (threshold 2×avg), king-maker awareness (gap 15), adaptive profiles |
| 9 | Meta-optimization | Adaptive C (BF-normalized), adaptive rollout depth, sufficiency threshold, loss avoidance |

**Thinking time**: 500 ms → ~250 iterations per move at 0.5 iter/ms

---

## Challenger Pool (this run)

Three challengers were selected to span the difficulty spectrum:

| Agent | Tier | Budget | Differentiating features |
|-------|------|--------|--------------------------|
| `pool_l45_100ms` | 3 — L4+5 enhanced | 100 ms (50 iter) | Rollout cutoff, minimax, RAVE — no opponent model, no L9 |
| `pool_l9_partial_200ms` | 4 — L9 partial | 200 ms (100 iter) | Full L9 adaptive meta-opts — no opponent model, half budget |
| `pool_peer_500ms` | 5 — Near-peer | 500 ms (250 iter) | Same budget as champion, same L3/4/5/9 — **no opponent model** |

**Key test**: Does opponent modeling (Layer 7) provide a net win-rate advantage vs the near-peer at equal budget?  
**Secondary test**: Does the champion's advantage over pool_l45_100ms reflect the expected ~L7+L9 compound gain?

---

## Expected Outcomes (based on Layer 1-9 experiment history)

### Win rate estimates

| Matchup (champion vs) | Expected champion WR | Basis |
|----------------------|----------------------|-------|
| `pool_l45_100ms` | 55–70% | 5× more iterations + L7+L9 |
| `pool_l9_partial_200ms` | 50–60% | 2.5× more iterations + L7 |
| `pool_peer_500ms` | 45–55% | Equal iterations; L7 advantage only |

**Overall expected champion WR**: ~0.40–0.55 (4-player: 25% is neutral)

### TrueSkill trajectory

Starting from μ = 25, σ = 8.33 for all agents:

- After 40 games each player appears in ~10 games (round-robin).  
- σ should drop to ~6–7 range after 40 games; convergence (σ < 6.5) likely requires 100+ games.
- Champion's μ expected to settle above 26–28 once σ converges.

### Snapshot yield

- 40 games × 8 checkpoints × 4 players = **1280 snapshot rows**
- Phase distribution: ~30% early, ~40% mid, ~30% late (empirical from existing runs)
- 1280 rows exceeds the 1000-row threshold in `champion_loop.py` for triggering evaluator recalibration

---

## Evaluator Refinement Pipeline

After this run completes, `champion_loop.py` will:

1. Accumulate snapshot rows into `data/champion_registry.json` → `snapshot_csv_paths`
2. Run inline regression (`analyze_layer6_features.py` / `train_eval_model.py`) on all accumulated rows
3. Validate new weights in a mini-tournament (10 games) before promoting
4. If promoted: bump champion to v2, update `state_eval_weights` in the registry

---

## Relationship to Previous Arena Runs

| Prior run | Date | Purpose | Key finding |
|-----------|------|---------|-------------|
| `20260325_021148_78fbdc50` | 2026-03-25 | L6 phase vs single weights | Phase weights hurt at this budget |
| `20260325_033805_9b3944b6` | 2026-03-25 | L4 combined (cutoff + minimax) | cutoff=5 + minimax α=0.25 best |
| `20260325_201856_32cf0875` | 2026-03-25 | L3 PW + PH combined | PW dominates; PW+PH best overall |

The champion v1 incorporates all three winning configurations (PW from L3, cutoff+minimax from L4, RAVE from L5) plus opponent modeling (L7) and adaptive meta-optimization (L9) on top.

---

## How to Run

```bash
# Single iteration, 40 games (this specification)
python scripts/champion_loop.py --iterations 1 --games-per-iter 40

# Extended multi-iteration training run (produces evaluator recalibration after iteration 1)
python scripts/champion_loop.py --iterations 10 --games-per-iter 40

# View progress after runs complete
python scripts/champion_loop.py --show

# Force evaluator recalibration after any run
python scripts/champion_loop.py --retrain
```

Results land in `arena_runs/{timestamp}_{hash}/` with full `summary.json`, `summary.md`,
`games.jsonl`, and `snapshots.csv/parquet`. TrueSkill and iteration history are persisted
to `data/champion_registry.json`; the Markdown progress report is at `data/champion_progress.md`.
