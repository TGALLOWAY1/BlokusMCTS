# Night 1 Results — Champion Gauntlets v1 + v2

**Date executed:** 2026-05-08 (run) / 2026-05-14 (resumed + completed)  
**Branch:** claude/kind-dijkstra-5nfSG  
**Plan reference:** docs/overnight_training_roadmap_2026-05-07.md

## Run IDs

| Run | Config | Run directory |
|-----|--------|---------------|
| Gauntlet v1 | scripts/arena_config_champion_gauntlet.json | arena_runs/20260508_033725_002f9dab/ |
| Gauntlet v2 | scripts/arena_config_champion_gauntlet_v2.json | arena_runs/champion_gauntlet_v2/20260508_060102_e8621532/ |

## Gauntlet v1 (40 games, seed 20260503)

Agents: champion · pool_l9_partial_200ms · pool_l45_100ms · pool_peer_500ms

| Agent | Win Rate | Outright Wins | TrueSkill μ | Conservative (μ−3σ) |
|-------|----------|---------------|-------------|----------------------|
| pool_peer_500ms | 0.525 | 21/40 | 47.93 | 25.74 |
| **champion** | **0.375** | **15/40** | **38.24** | **16.35** |
| pool_l45_100ms | 0.075 | 3/40 | 9.19 | −12.27 |
| pool_l9_partial_200ms | 0.025 | 1/40 | 5.97 | −15.27 |

**Pairwise champion results:**
- champion vs pool_l45_100ms: 31W/8L/1T (WR=0.775)
- champion vs pool_l9_partial_200ms: 33W/7L/0T (WR=0.825)
- champion vs pool_peer_500ms: 16W/24L/0T (WR=0.400)

Completed: 40/40 games, 0 errors  
Snapshot rows: 1272 (expected 1280; 8 rows short — 1 game ended before ply 64)  
se_* features: present ✓

## Gauntlet v2 (60 games, seed 20260601)

Agents: champion · pool_heuristic (Tier 0 human proxy) · pool_l45_100ms · pool_peer_500ms

| Agent | Win Rate | Outright Wins | TrueSkill μ | Conservative (μ−3σ) |
|-------|----------|---------------|-------------|----------------------|
| pool_peer_500ms | 0.492 | 29/60 | 50.60 | 29.49 |
| **champion** | **0.383** | **23/60** | **41.25** | **20.43** |
| pool_heuristic | 0.117 | 7/60 | 11.94 | −8.34 |
| pool_l45_100ms | 0.008 | 0/60 | −2.51 | −23.30 |

**Pairwise champion vs pool_heuristic (Tier 0 human proxy):**
- 39W / 17L / 4T out of 60 comparisons
- Point estimate WR: **0.650**
- Wilson-95 CI: [0.524, 0.758]
- Wilson-95 lower bound: **0.524** (below 0.65 threshold for headline claim)

Completed: 60/60 games, 0 errors  
Snapshot rows: 1344 (42 resumed games × 4 × 8; first 18 games' snapshots lost to interruption)  
se_* features: present ✓

## Night 1 Verification

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| V1 summary.json | present | ✓ | PASS |
| V1 games.jsonl | 40 lines | 40 | PASS |
| V1 snapshots.csv (se_* cols) | present | ✓ | PASS |
| V2 summary.json | present | ✓ | PASS |
| V2 games.jsonl | 60 lines | 60 | PASS |
| V2 snapshots.csv (se_* cols) | present | ✓ | PASS |
| Total snapshot rows | 3200 | 2616 | PARTIAL — 576 rows missing (18 interrupted v2 games) |

**Total games played: 100 (40+60). All results valid.**

The 576 missing snapshot rows are a consequence of the v2 run being interrupted at game 18 by session expiry; the resumed run only captures snapshots for games 19–60. Game results in games.jsonl are complete and unaffected.

## Key Findings

1. **Champion beats pool_heuristic 65%** of the time in direct comparisons (WR 0.650), but Wilson-95 LB is 0.524 — not yet sufficient for the ≥70% headline claim. Night 5 (4 seeds × 60 games = 240 games) is needed.
2. **Champion is rank 2 in both gauntlets**, consistently behind pool_peer_500ms (same time budget, no opponent modeling). This gap motivates the Layer 8 parallelization sweep (Night 2).
3. **Champion dominates lower tiers**: WR 0.775 vs pool_l45_100ms, 0.825 vs pool_l9_partial_200ms.
4. **Baseline TrueSkill established**: champion μ=38.2 (v1), μ=41.3 (v2); conservative ratings 16.3 and 20.4 respectively.

## Follow-ups

- Night 2: Layer 8 parallelization sweep to close gap on pool_peer_500ms
- Night 5: 4-seed × 60-game run for headline WR claim with Wilson-95 LB ≥ 0.65
- Consider re-running v2 game 1–18 snapshot recovery as a short supplementary run to reach 3200 rows for Night 3 refit
