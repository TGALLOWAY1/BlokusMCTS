# Arena Run Summary: 20260524_144646_cda33b8e

## Overview
- Seed: `20260603`
- Seat policy: `round_robin`
- Games: `8/8` completed
- Error games: `0`

## Win Rates by Agent
- `ch_1w_2000ms`: win_rate=0.375, win_points=3.00, outright=3, shared=0
- `ch_4w_2000ms`: win_rate=0.375, win_points=3.00, outright=3, shared=0
- `pool_heuristic`: win_rate=0.125, win_points=1.00, outright=1, shared=0
- `pool_l9_partial_200ms`: win_rate=0.125, win_points=1.00, outright=1, shared=0

## Win Rates by Seat
- `ch_1w_2000ms`: seat0: 0.500 (2 games), seat1: 0.000 (2 games), seat2: 0.500 (2 games), seat3: 0.500 (2 games)
- `ch_4w_2000ms`: seat0: 0.500 (2 games), seat1: 0.500 (2 games), seat2: 0.000 (2 games), seat3: 0.500 (2 games)
- `pool_heuristic`: seat0: 0.000 (2 games), seat1: 0.000 (2 games), seat2: 0.000 (2 games), seat3: 0.500 (2 games)
- `pool_l9_partial_200ms`: seat0: 0.500 (2 games), seat1: 0.000 (2 games), seat2: 0.000 (2 games), seat3: 0.000 (2 games)

## Score Stats
- `ch_1w_2000ms`: mean=94.25, median=87.0, std=16.04485898972004, p25=83.25, p75=105.5, min=75.0, max=122.0
- `ch_4w_2000ms`: mean=89.0, median=88.0, std=9.810708435174291, p25=80.0, p75=98.25, min=75.0, max=102.0
- `pool_heuristic`: mean=84.25, median=83.5, std=4.175823272122517, p25=81.0, p75=87.75, min=78.0, max=90.0
- `pool_l9_partial_200ms`: mean=76.625, median=75.5, std=9.860749210886564, p25=71.0, p75=82.5, min=59.0, max=91.0

## Pairwise Matchups
- `ch_1w_2000ms__vs__ch_4w_2000ms`: ch_1w_2000ms>ch_4w_2000ms=4, ch_4w_2000ms>ch_1w_2000ms=4, tie=0 (total=8)
- `ch_1w_2000ms__vs__pool_heuristic`: ch_1w_2000ms>pool_heuristic=5, pool_heuristic>ch_1w_2000ms=3, tie=0 (total=8)
- `ch_1w_2000ms__vs__pool_l9_partial_200ms`: ch_1w_2000ms>pool_l9_partial_200ms=6, pool_l9_partial_200ms>ch_1w_2000ms=2, tie=0 (total=8)
- `ch_4w_2000ms__vs__pool_heuristic`: ch_4w_2000ms>pool_heuristic=4, pool_heuristic>ch_4w_2000ms=4, tie=0 (total=8)
- `ch_4w_2000ms__vs__pool_l9_partial_200ms`: ch_4w_2000ms>pool_l9_partial_200ms=6, pool_l9_partial_200ms>ch_4w_2000ms=1, tie=1 (total=8)
- `pool_heuristic__vs__pool_l9_partial_200ms`: pool_heuristic>pool_l9_partial_200ms=6, pool_l9_partial_200ms>pool_heuristic=1, tie=1 (total=8)

## Time and Simulation Efficiency
- `ch_1w_2000ms`: avg_time_ms=15654.310391253273, avg_sims_per_move=1000.0, sims_per_sec=63.88016942341596, win_rate_per_sec=0.023955063533780983, score_per_sec=6.020705968156953
- `ch_4w_2000ms`: avg_time_ms=6715.575195180959, avg_sims_per_move=1000.0, sims_per_sec=148.9075724619377, win_rate_per_sec=0.05584033967322664, score_per_sec=13.252773949112456
- `pool_heuristic`: avg_time_ms=31.814429131412723, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=3.929034825162973, score_per_sec=2648.1694721598437
- `pool_l9_partial_200ms`: avg_time_ms=2417.377603530884, avg_sims_per_move=100.0, sims_per_sec=41.36714092739894, win_rate_per_sec=0.051708926159248686, score_per_sec=31.697571735619444

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `pool_heuristic` | 29.21 | 8.04 | **5.10** | 8 |
| 2 | `ch_1w_2000ms` | 28.51 | 8.07 | **4.30** | 8 |
| 3 | `ch_4w_2000ms` | 28.28 | 8.07 | **4.08** | 8 |
| 4 | `pool_l9_partial_200ms` | 14.02 | 7.98 | **-9.94** | 8 |

## Score Margins (winner - last place)
- Mean: `30.0`, Median: `29.5`, Std: `13.36`, Range: `[13.0, 57.0]`

## Score by Seat Position
- `ch_1w_2000ms`: P1: 104.5±17.5 (n=2), P2: 82.5±1.5 (n=2), P3: 101.5±14.5 (n=2), P4: 88.5±13.5 (n=2)
- `ch_4w_2000ms`: P1: 88.5±8.5 (n=2), P2: 91.0±11.0 (n=2), P3: 80.5±5.5 (n=2), P4: 96.0±6.0 (n=2)
- `pool_heuristic`: P1: 81.5±3.5 (n=2), P2: 85.5±4.5 (n=2), P3: 84.0±3.0 (n=2), P4: 86.0±4.0 (n=2)
- `pool_l9_partial_200ms`: P1: 84.0±7.0 (n=2), P2: 66.5±7.5 (n=2), P3: 80.5±9.5 (n=2), P4: 75.5±4.5 (n=2)
