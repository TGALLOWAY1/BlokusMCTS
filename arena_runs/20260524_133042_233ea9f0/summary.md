# Arena Run Summary: 20260524_133042_233ea9f0

## Overview
- Seed: `20260602`
- Seat policy: `round_robin`
- Games: `24/24` completed
- Error games: `0`

## Win Rates by Agent
- `ch_1w_500ms`: win_rate=0.167, win_points=4.00, outright=4, shared=0
- `ch_4w_500ms`: win_rate=0.375, win_points=9.00, outright=9, shared=0
- `ch_8w_500ms`: win_rate=0.438, win_points=10.50, outright=10, shared=1
- `pool_heuristic`: win_rate=0.021, win_points=0.50, outright=0, shared=1

## Win Rates by Seat
- `ch_1w_500ms`: seat0: 0.167 (6 games), seat1: 0.333 (6 games), seat2: 0.000 (6 games), seat3: 0.167 (6 games)
- `ch_4w_500ms`: seat0: 0.500 (6 games), seat1: 0.500 (6 games), seat2: 0.167 (6 games), seat3: 0.333 (6 games)
- `ch_8w_500ms`: seat0: 0.583 (6 games), seat1: 0.333 (6 games), seat2: 0.333 (6 games), seat3: 0.500 (6 games)
- `pool_heuristic`: seat0: 0.000 (6 games), seat1: 0.083 (6 games), seat2: 0.000 (6 games), seat3: 0.000 (6 games)

## Score Stats
- `ch_1w_500ms`: mean=86.08333333333333, median=85.5, std=7.493979064704026, p25=79.0, p75=91.0, min=76.0, max=101.0
- `ch_4w_500ms`: mean=91.875, median=90.5, std=7.886235371413495, p25=87.75, p75=97.0, min=77.0, max=112.0
- `ch_8w_500ms`: mean=91.20833333333333, median=92.5, std=6.396477980541758, p25=86.5, p75=95.25, min=75.0, max=100.0
- `pool_heuristic`: mean=80.08333333333333, median=81.5, std=6.93972061557396, p25=74.5, p75=85.0, min=67.0, max=91.0

## Pairwise Matchups
- `ch_1w_500ms__vs__ch_4w_500ms`: ch_1w_500ms>ch_4w_500ms=9, ch_4w_500ms>ch_1w_500ms=15, tie=0 (total=24)
- `ch_1w_500ms__vs__ch_8w_500ms`: ch_1w_500ms>ch_8w_500ms=8, ch_8w_500ms>ch_1w_500ms=16, tie=0 (total=24)
- `ch_1w_500ms__vs__pool_heuristic`: ch_1w_500ms>pool_heuristic=16, pool_heuristic>ch_1w_500ms=7, tie=1 (total=24)
- `ch_4w_500ms__vs__ch_8w_500ms`: ch_4w_500ms>ch_8w_500ms=10, ch_8w_500ms>ch_4w_500ms=14, tie=0 (total=24)
- `ch_4w_500ms__vs__pool_heuristic`: ch_4w_500ms>pool_heuristic=20, pool_heuristic>ch_4w_500ms=2, tie=2 (total=24)
- `ch_8w_500ms__vs__pool_heuristic`: ch_8w_500ms>pool_heuristic=20, pool_heuristic>ch_8w_500ms=3, tie=1 (total=24)

## Time and Simulation Efficiency
- `ch_1w_500ms`: avg_time_ms=4614.179499907679, avg_sims_per_move=250.0, sims_per_sec=54.18081372972205, win_rate_per_sec=0.03612054248648137, score_per_sec=18.656260194267627
- `ch_4w_500ms`: avg_time_ms=1792.4244659859062, avg_sims_per_move=248.0, sims_per_sec=138.36008417994336, win_rate_per_sec=0.20921383696564017, score_per_sec=51.25739005658184
- `ch_8w_500ms`: avg_time_ms=1889.3853041088635, avg_sims_per_move=248.0, sims_per_sec=131.2596215608707, win_rate_per_sec=0.23155679206806826, score_per_sec=48.27407788923823
- `pool_heuristic`: avg_time_ms=30.73319948994917, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.6778771386996841, score_per_sec=2605.7597211615857

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `ch_8w_500ms` | 37.08 | 7.64 | **14.15** | 24 |
| 2 | `ch_4w_500ms` | 33.49 | 7.61 | **10.66** | 24 |
| 3 | `ch_1w_500ms` | 20.48 | 7.50 | **-2.02** | 24 |
| 4 | `pool_heuristic` | 9.21 | 7.55 | **-13.43** | 24 |

## Score Margins (winner - last place)
- Mean: `19.46`, Median: `19.0`, Std: `7.12`, Range: `[7.0, 33.0]`

## Score by Seat Position
- `ch_1w_500ms`: P1: 88.67±2.04 (n=6), P2: 92.0±3.11 (n=6), P3: 79.67±1.63 (n=6), P4: 84.0±3.32 (n=6)
- `ch_4w_500ms`: P1: 94.33±2.43 (n=6), P2: 91.5±3.77 (n=6), P3: 93.0±3.85 (n=6), P4: 88.67±3.36 (n=6)
- `ch_8w_500ms`: P1: 92.67±2.39 (n=6), P2: 87.17±3.73 (n=6), P3: 92.0±2.86 (n=6), P4: 93.0±0.68 (n=6)
- `pool_heuristic`: P1: 77.83±3.48 (n=6), P2: 80.67±3.25 (n=6), P3: 80.83±3.12 (n=6), P4: 81.0±2.18 (n=6)
