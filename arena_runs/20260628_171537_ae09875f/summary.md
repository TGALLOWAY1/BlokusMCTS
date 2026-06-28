# Arena Run Summary: 20260628_171537_ae09875f

## Overview
- Seed: `20260604`
- Seat policy: `round_robin`
- Games: `12/12` completed
- Error games: `0`

## Win Rates by Agent
- `pool_heuristic`: win_rate=0.167, win_points=2.00, outright=2, shared=0
- `sweep_1w_2000ms`: win_rate=0.083, win_points=1.00, outright=1, shared=0
- `sweep_4w_2000ms`: win_rate=0.417, win_points=5.00, outright=5, shared=0
- `sweep_8w_2000ms`: win_rate=0.333, win_points=4.00, outright=4, shared=0

## Win Rates by Seat
- `pool_heuristic`: seat0: 0.000 (3 games), seat1: 0.333 (3 games), seat2: 0.333 (3 games), seat3: 0.000 (3 games)
- `sweep_1w_2000ms`: seat0: 0.333 (3 games), seat1: 0.000 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `sweep_4w_2000ms`: seat0: 0.000 (3 games), seat1: 0.667 (3 games), seat2: 0.667 (3 games), seat3: 0.333 (3 games)
- `sweep_8w_2000ms`: seat0: 0.333 (3 games), seat1: 0.667 (3 games), seat2: 0.000 (3 games), seat3: 0.333 (3 games)

## Score Stats
- `pool_heuristic`: mean=82.33333333333333, median=83.5, std=9.348202441586773, p25=75.25, p75=87.75, min=70.0, max=98.0
- `sweep_1w_2000ms`: mean=84.75, median=87.0, std=6.8571738590569025, p25=77.0, p75=90.25, min=74.0, max=93.0
- `sweep_4w_2000ms`: mean=90.83333333333333, median=90.5, std=8.668269082630562, p25=83.75, p75=94.75, min=80.0, max=112.0
- `sweep_8w_2000ms`: mean=90.08333333333333, median=90.5, std=6.210989364738028, p25=84.75, p75=92.75, min=80.0, max=101.0

## Pairwise Matchups
- `pool_heuristic__vs__sweep_1w_2000ms`: pool_heuristic>sweep_1w_2000ms=5, sweep_1w_2000ms>pool_heuristic=7, tie=0 (total=12)
- `pool_heuristic__vs__sweep_4w_2000ms`: pool_heuristic>sweep_4w_2000ms=2, sweep_4w_2000ms>pool_heuristic=10, tie=0 (total=12)
- `pool_heuristic__vs__sweep_8w_2000ms`: pool_heuristic>sweep_8w_2000ms=4, sweep_8w_2000ms>pool_heuristic=8, tie=0 (total=12)
- `sweep_1w_2000ms__vs__sweep_4w_2000ms`: sweep_1w_2000ms>sweep_4w_2000ms=3, sweep_4w_2000ms>sweep_1w_2000ms=9, tie=0 (total=12)
- `sweep_1w_2000ms__vs__sweep_8w_2000ms`: sweep_1w_2000ms>sweep_8w_2000ms=2, sweep_8w_2000ms>sweep_1w_2000ms=10, tie=0 (total=12)
- `sweep_4w_2000ms__vs__sweep_8w_2000ms`: sweep_4w_2000ms>sweep_8w_2000ms=5, sweep_8w_2000ms>sweep_4w_2000ms=6, tie=1 (total=12)

## Time and Simulation Efficiency
- `pool_heuristic`: avg_time_ms=24.921222422133393, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=6.687740426354217, score_per_sec=3303.743770618983
- `sweep_1w_2000ms`: avg_time_ms=15943.226086983987, avg_sims_per_move=1000.0, sims_per_sec=62.72256283290103, win_rate_per_sec=0.005226880236075085, score_per_sec=5.315737200088362
- `sweep_4w_2000ms`: avg_time_ms=6294.928467379207, avg_sims_per_move=1000.0, sims_per_sec=158.85804027513183, win_rate_per_sec=0.06619085011463827, score_per_sec=14.429605324991142
- `sweep_8w_2000ms`: avg_time_ms=6691.665458896933, avg_sims_per_move=1000.0, sims_per_sec=149.43962846654946, win_rate_per_sec=0.04981320948884982, score_per_sec=13.462019864361665

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `sweep_4w_2000ms` | 33.24 | 7.96 | **9.37** | 12 |
| 2 | `sweep_8w_2000ms` | 31.64 | 7.96 | **7.77** | 12 |
| 3 | `sweep_1w_2000ms` | 19.32 | 7.83 | **-4.17** | 12 |
| 4 | `pool_heuristic` | 15.93 | 7.89 | **-7.74** | 12 |

## Score Margins (winner - last place)
- Mean: `19.75`, Median: `20.0`, Std: `7.43`, Range: `[10.0, 37.0]`

## Score by Seat Position
- `pool_heuristic`: P1: 79.33±9.33 (n=3), P2: 80.0±5.77 (n=3), P3: 83.67±3.33 (n=3), P4: 86.33±5.21 (n=3)
- `sweep_1w_2000ms`: P1: 80.67±6.17 (n=3), P2: 88.33±2.19 (n=3), P3: 84.0±3.79 (n=3), P4: 86.0±4.58 (n=3)
- `sweep_4w_2000ms`: P1: 85.67±2.19 (n=3), P2: 96.33±9.24 (n=3), P3: 95.0±2.08 (n=3), P4: 86.33±2.91 (n=3)
- `sweep_8w_2000ms`: P1: 90.0±0.58 (n=3), P2: 94.33±5.24 (n=3), P3: 88.33±2.67 (n=3), P4: 87.67±5.36 (n=3)
