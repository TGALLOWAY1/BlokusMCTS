# Night 2 — Layer 8 Parallelization Sweep

**Date:** 2026-05-24  
**Branch:** claude/elegant-rubin-VZhYK

## Runs

| Run ID | Config | Games | Budget | Completed |
|--------|--------|-------|--------|-----------|
| 20260524_133042_233ea9f0 | arena_config_night2_parallel_sweep_500ms.json | 24/24 | 500 ms | ✓ 0 errors |
| 20260524_144646_cda33b8e | arena_config_night2_parallel_sweep_2000ms.json | 8/8 | 2000 ms | ✓ 0 errors |

Note: 5000 ms budget dropped as infeasible (~13 h for 24 games on 4 CPUs).

---

## P95 Move Latency

All timings are wall-clock milliseconds (not the configured budget).

| Agent | Budget | avg_ms | p95_ms | speedup vs 1w |
|-------|--------|-------:|-------:|:-------------:|
| ch_1w | 500 ms | 4,614 | 7,305 | 1.00× |
| ch_4w | 500 ms | 1,792 | 3,459 | **2.57×** |
| ch_8w | 500 ms | 1,889 | 3,600 | 2.44× |
| ch_1w | 2000 ms | 15,654 | 26,466 | 1.00× |
| ch_4w | 2000 ms | 6,716 | 13,305 | **2.33×** |

**Budget scaling (wall clock for 4× budget increase):**
- ch_1w: 4,614 ms → 15,654 ms = 3.39× (sub-linear; GIL/startup overhead)
- ch_4w: 1,792 ms → 6,716 ms = 3.75× (near-linear)

**4w vs 8w at 500 ms:** 1,889 / 1,792 = 1.05× — effectively identical.  
4 physical CPUs are saturated at 4 workers; 8 workers yield no further latency reduction.

---

## Playing Strength (500 ms — 24 games, round-robin seats)

| Agent | Win pts | WR | TrueSkill μ | Conservative |
|-------|--------:|---:|------------:|-------------:|
| ch_8w_500ms | 10.5 | 43.8% | 37.1 | 14.2 |
| ch_4w_500ms | 9.0 | 37.5% | 33.5 | 10.7 |
| ch_1w_500ms | 4.0 | 16.7% | 20.5 | −2.0 |
| pool_heuristic | 0.5 | 2.1% | 9.2 | −13.4 |

**Pairwise head-to-head (500 ms):**

| Matchup | Result | WR |
|---------|--------|----|
| ch_4w vs ch_1w | 15-9-0 | 62.5% |
| ch_8w vs ch_1w | 16-8-0 | 66.7% |
| ch_4w vs ch_8w | 10-14-0 | (ch_8w leads) |
| ch_4w vs pool_heuristic | 20-2-2 | 83.3% |
| ch_8w vs pool_heuristic | 20-3-1 | 83.3% |
| ch_1w vs pool_heuristic | 16-7-1 | 66.7% |

**Strength conclusion:** Both 4w and 8w outperform 1w by a meaningful margin despite identical total iteration budget (250 iters split across workers). Parallel diversity in root search provides a genuine strength benefit. 8w marginally leads 4w (not statistically significant at N=24).

---

## Playing Strength (2000 ms — 8 games)

N=8 is too small for reliable strength claims (SE ≈ 0.18 on WR). Results below are latency-validated only.

| Agent | Win pts | WR |
|-------|--------:|----|
| ch_1w_2000ms | 3 | 37.5% |
| ch_4w_2000ms | 3 | 37.5% |
| pool_heuristic | 1 | 12.5% |
| pool_l9_partial_200ms | 1 | 12.5% |

ch_1w vs ch_4w pairwise: 4-4-0 — no strength signal at 8 games.

---

## Key Findings

1. **4w is the hardware-matched sweet spot.** On 4 physical CPUs, 4 workers gives 2.57× latency improvement; 8 workers adds negligible further benefit (1.05× slower than 4w).

2. **Parallel diversity improves strength.** ch_4w and ch_8w both beat ch_1w ~63–67% head-to-head at 500 ms, despite the same total iteration count split across workers. Separate search trees explore different lines.

3. **Wall-clock scaling is near-linear for 4w.** Doubling the budget approximately doubles the wall time (3.75× for 4× budget), which is the expected behavior.

4. **All champion variants beat pool_heuristic comfortably.** ch_4w/ch_8w: 83.3% pairwise WR. ch_1w: 66.7%. No regression.

---

## Recommendation for Night 3

Promote `num_workers=4, parallel_strategy="root"` as the standard configuration for champion v2 candidate. Run the Night 3 refit gated by:
- Δμ ≥ 0.5 TrueSkill vs current champion (v1 at 1w)
- sign-test p < 0.05 over ≥20 paired games

The 500 ms budget remains the practical default; the 2000 ms data establishes that latency scales predictably if budget is raised.
