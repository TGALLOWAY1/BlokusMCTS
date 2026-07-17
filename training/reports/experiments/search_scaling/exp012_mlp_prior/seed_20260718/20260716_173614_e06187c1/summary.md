# Arena Run Summary: 20260716_173614_e06187c1

## Overview
- Seed: `20260718`
- Seat policy: `round_robin`
- Games: `10/10` completed
- Error games: `0`

## Win Rates by Agent
- `base_500_a`: win_rate=0.600, win_points=6.00, outright=6, shared=0
- `base_500_b`: win_rate=0.200, win_points=2.00, outright=2, shared=0
- `prior_500_a`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `prior_500_b`: win_rate=0.200, win_points=2.00, outright=2, shared=0

## Win Rates by Seat
- `base_500_a`: seat0: 0.000 (2 games), seat1: 1.000 (3 games), seat2: 1.000 (3 games), seat3: 0.000 (2 games)
- `base_500_b`: seat0: 0.000 (2 games), seat1: 1.000 (2 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `prior_500_a`: seat0: 0.000 (3 games), seat1: 0.000 (2 games), seat2: 0.000 (2 games), seat3: 0.000 (3 games)
- `prior_500_b`: seat0: 0.000 (3 games), seat1: 0.000 (3 games), seat2: 1.000 (2 games), seat3: 0.000 (2 games)

## Score Stats
- `base_500_a`: mean=94.6, median=103.0, std=16.799999999999997, p25=103.0, p75=103.0, min=61.0, max=103.0
- `base_500_b`: mean=78.0, median=73.0, std=16.61324772583615, p25=64.0, p75=81.0, min=61.0, max=108.0
- `prior_500_a`: mean=70.4, median=70.0, std=8.345058418010026, p25=63.0, p75=77.0, min=61.0, max=81.0
- `prior_500_b`: mean=81.6, median=78.5, std=14.270248771482576, p25=69.75, p75=82.0, min=68.0, max=108.0

## Pairwise Matchups
- `base_500_a__vs__base_500_b`: base_500_a>base_500_b=6, base_500_b>base_500_a=4, tie=0 (total=10)
- `base_500_a__vs__prior_500_a`: base_500_a>prior_500_a=8, prior_500_a>base_500_a=2, tie=0 (total=10)
- `base_500_a__vs__prior_500_b`: base_500_a>prior_500_b=8, prior_500_b>base_500_a=2, tie=0 (total=10)
- `base_500_b__vs__prior_500_a`: base_500_b>prior_500_a=5, prior_500_a>base_500_b=3, tie=2 (total=10)
- `base_500_b__vs__prior_500_b`: base_500_b>prior_500_b=5, prior_500_b>base_500_b=5, tie=0 (total=10)
- `prior_500_a__vs__prior_500_b`: prior_500_a>prior_500_b=0, prior_500_b>prior_500_a=10, tie=0 (total=10)

## Time and Simulation Efficiency
- `base_500_a`: avg_time_ms=9567.34816882075, avg_sims_per_move=500.0, sims_per_sec=52.26108543111888, win_rate_per_sec=0.06271330251734265, score_per_sec=9.88779736356769
- `base_500_b`: avg_time_ms=10911.954769509377, avg_sims_per_move=500.0, sims_per_sec=45.8213042998602, win_rate_per_sec=0.01832852171994408, score_per_sec=7.148123470778191
- `prior_500_a`: avg_time_ms=13809.11057605976, avg_sims_per_move=500.0, sims_per_sec=36.20798003217005, win_rate_per_sec=0.0, score_per_sec=5.098083588529543
- `prior_500_b`: avg_time_ms=12818.689020474752, avg_sims_per_move=500.0, sims_per_sec=39.00554878906658, win_rate_per_sec=0.015602219515626632, score_per_sec=6.365705562375665

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `base_500_a` | 30.70 | 8.08 | **6.47** | 10 |
| 2 | `prior_500_b` | 28.74 | 7.95 | **4.89** | 10 |
| 3 | `base_500_b` | 25.36 | 8.00 | **1.36** | 10 |
| 4 | `prior_500_a` | 15.30 | 7.87 | **-8.30** | 10 |

## Score Margins (winner - last place)
- Mean: `43.4`, Median: `42.0`, Std: `3.04`, Range: `[40.0, 47.0]`

## Score by Seat Position
- `base_500_a`: P1: 103.0±0.0 (n=2), P2: 103.0±0.0 (n=3), P3: 103.0±0.0 (n=3), P4: 61.0±0.0 (n=2)
- `base_500_b`: P1: 81.0±0.0 (n=2), P2: 108.0±0.0 (n=2), P3: 73.0±0.0 (n=3), P4: 61.0±0.0 (n=3)
- `prior_500_a`: P1: 77.0±0.0 (n=3), P2: 81.0±0.0 (n=2), P3: 61.0±0.0 (n=2), P4: 63.0±0.0 (n=3)
- `prior_500_b`: P1: 68.0±0.0 (n=3), P2: 82.0±0.0 (n=3), P3: 108.0±0.0 (n=2), P4: 75.0±0.0 (n=2)
