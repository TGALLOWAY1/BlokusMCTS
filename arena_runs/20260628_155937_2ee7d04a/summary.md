# Arena Run Summary: 20260628_155937_2ee7d04a

## Overview
- Seed: `20260603`
- Seat policy: `round_robin`
- Games: `24/24` completed
- Error games: `0`

## Win Rates by Agent
- `pool_heuristic`: win_rate=0.042, win_points=1.00, outright=1, shared=0
- `sweep_1w_500ms`: win_rate=0.292, win_points=7.00, outright=7, shared=0
- `sweep_4w_500ms`: win_rate=0.333, win_points=8.00, outright=8, shared=0
- `sweep_8w_500ms`: win_rate=0.333, win_points=8.00, outright=8, shared=0

## Win Rates by Seat
- `pool_heuristic`: seat0: 0.000 (6 games), seat1: 0.000 (6 games), seat2: 0.167 (6 games), seat3: 0.000 (6 games)
- `sweep_1w_500ms`: seat0: 0.500 (6 games), seat1: 0.167 (6 games), seat2: 0.500 (6 games), seat3: 0.000 (6 games)
- `sweep_4w_500ms`: seat0: 0.333 (6 games), seat1: 0.333 (6 games), seat2: 0.500 (6 games), seat3: 0.167 (6 games)
- `sweep_8w_500ms`: seat0: 0.333 (6 games), seat1: 0.500 (6 games), seat2: 0.167 (6 games), seat3: 0.333 (6 games)

## Score Stats
- `pool_heuristic`: mean=80.5, median=82.0, std=8.789197915623474, p25=74.0, p75=88.0, min=64.0, max=97.0
- `sweep_1w_500ms`: mean=90.45833333333333, median=92.0, std=10.103543795234534, p25=84.5, p75=94.0, min=72.0, max=118.0
- `sweep_4w_500ms`: mean=91.04166666666667, median=90.5, std=9.048384601070453, p25=85.5, p75=97.25, min=76.0, max=110.0
- `sweep_8w_500ms`: mean=91.04166666666667, median=90.0, std=8.955813599122205, p25=85.5, p75=94.0, min=77.0, max=114.0

## Pairwise Matchups
- `pool_heuristic__vs__sweep_1w_500ms`: pool_heuristic>sweep_1w_500ms=4, sweep_1w_500ms>pool_heuristic=19, tie=1 (total=24)
- `pool_heuristic__vs__sweep_4w_500ms`: pool_heuristic>sweep_4w_500ms=5, sweep_4w_500ms>pool_heuristic=19, tie=0 (total=24)
- `pool_heuristic__vs__sweep_8w_500ms`: pool_heuristic>sweep_8w_500ms=6, sweep_8w_500ms>pool_heuristic=17, tie=1 (total=24)
- `sweep_1w_500ms__vs__sweep_4w_500ms`: sweep_1w_500ms>sweep_4w_500ms=10, sweep_4w_500ms>sweep_1w_500ms=13, tie=1 (total=24)
- `sweep_1w_500ms__vs__sweep_8w_500ms`: sweep_1w_500ms>sweep_8w_500ms=12, sweep_8w_500ms>sweep_1w_500ms=12, tie=0 (total=24)
- `sweep_4w_500ms__vs__sweep_8w_500ms`: sweep_4w_500ms>sweep_8w_500ms=13, sweep_8w_500ms>sweep_4w_500ms=10, tie=1 (total=24)

## Time and Simulation Efficiency
- `pool_heuristic`: avg_time_ms=24.540615100031573, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=1.697865619782817, score_per_sec=3280.2763774204027
- `sweep_1w_500ms`: avg_time_ms=3789.943846156088, avg_sims_per_move=250.0, sims_per_sec=65.96403803015708, win_rate_per_sec=0.07695804436851661, score_per_sec=23.867987760578504
- `sweep_4w_500ms`: avg_time_ms=2228.1497891029617, avg_sims_per_move=248.0, sims_per_sec=111.30310951843286, win_rate_per_sec=0.14960095365380757, score_per_sec=40.8597604666962
- `sweep_8w_500ms`: avg_time_ms=2315.851201860415, avg_sims_per_move=248.0, sims_per_sec=107.08805462145918, win_rate_per_sec=0.1439355572869075, score_per_sec=39.31239908398661

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `sweep_4w_500ms` | 34.99 | 7.67 | **11.99** | 24 |
| 2 | `sweep_8w_500ms` | 29.06 | 7.58 | **6.32** | 24 |
| 3 | `sweep_1w_500ms` | 26.26 | 7.56 | **3.59** | 24 |
| 4 | `pool_heuristic` | 9.92 | 7.45 | **-12.44** | 24 |

## Score Margins (winner - last place)
- Mean: `22.08`, Median: `20.0`, Std: `10.74`, Range: `[3.0, 44.0]`

## Score by Seat Position
- `pool_heuristic`: P1: 87.83±1.58 (n=6), P2: 82.17±3.33 (n=6), P3: 80.67±4.01 (n=6), P4: 71.33±1.99 (n=6)
- `sweep_1w_500ms`: P1: 98.17±4.69 (n=6), P2: 86.5±2.84 (n=6), P3: 90.0±5.13 (n=6), P4: 87.17±2.85 (n=6)
- `sweep_4w_500ms`: P1: 90.33±4.45 (n=6), P2: 94.83±3.59 (n=6), P3: 90.0±2.11 (n=6), P4: 89.0±4.93 (n=6)
- `sweep_8w_500ms`: P1: 92.67±2.68 (n=6), P2: 98.5±4.95 (n=6), P3: 86.67±2.42 (n=6), P4: 86.33±2.59 (n=6)
