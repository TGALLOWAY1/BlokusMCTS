# Arena Run Summary: 20260628_210150_3383f5f7

## Overview
- Seed: `20260605`
- Seat policy: `round_robin`
- Games: `120/120` completed
- Error games: `0`

## Win Rates by Agent
- `champ_new_weights`: win_rate=0.688, win_points=82.50, outright=81, shared=3
- `champ_old_weights`: win_rate=0.229, win_points=27.50, outright=25, shared=5
- `pool_heuristic`: win_rate=0.042, win_points=5.00, outright=5, shared=0
- `pool_l9_partial_200ms`: win_rate=0.042, win_points=5.00, outright=4, shared=2

## Win Rates by Seat
- `champ_new_weights`: seat0: 0.833 (30 games), seat1: 0.717 (30 games), seat2: 0.667 (30 games), seat3: 0.533 (30 games)
- `champ_old_weights`: seat0: 0.217 (30 games), seat1: 0.217 (30 games), seat2: 0.350 (30 games), seat3: 0.133 (30 games)
- `pool_heuristic`: seat0: 0.067 (30 games), seat1: 0.000 (30 games), seat2: 0.033 (30 games), seat3: 0.067 (30 games)
- `pool_l9_partial_200ms`: seat0: 0.050 (30 games), seat1: 0.050 (30 games), seat2: 0.033 (30 games), seat3: 0.033 (30 games)

## Score Stats
- `champ_new_weights`: mean=100.84166666666667, median=98.0, std=12.355158054656988, p25=93.0, p75=106.5, min=71.0, max=124.0
- `champ_old_weights`: mean=90.11666666666666, median=90.0, std=9.308762299874004, p25=85.0, p75=95.0, min=68.0, max=122.0
- `pool_heuristic`: mean=78.875, median=80.0, std=8.57473274607825, p25=73.0, p75=85.0, min=58.0, max=99.0
- `pool_l9_partial_200ms`: mean=78.64166666666667, median=79.0, std=9.580184265219303, p25=71.0, p75=86.0, min=58.0, max=108.0

## Pairwise Matchups
- `champ_new_weights__vs__champ_old_weights`: champ_new_weights>champ_old_weights=87, champ_old_weights>champ_new_weights=30, tie=3 (total=120)
- `champ_new_weights__vs__pool_heuristic`: champ_new_weights>pool_heuristic=106, pool_heuristic>champ_new_weights=12, tie=2 (total=120)
- `champ_new_weights__vs__pool_l9_partial_200ms`: champ_new_weights>pool_l9_partial_200ms=109, pool_l9_partial_200ms>champ_new_weights=11, tie=0 (total=120)
- `champ_old_weights__vs__pool_heuristic`: champ_old_weights>pool_heuristic=94, pool_heuristic>champ_old_weights=24, tie=2 (total=120)
- `champ_old_weights__vs__pool_l9_partial_200ms`: champ_old_weights>pool_l9_partial_200ms=92, pool_l9_partial_200ms>champ_old_weights=23, tie=5 (total=120)
- `pool_heuristic__vs__pool_l9_partial_200ms`: pool_heuristic>pool_l9_partial_200ms=65, pool_l9_partial_200ms>pool_heuristic=52, tie=3 (total=120)

## Time and Simulation Efficiency
- `champ_new_weights`: avg_time_ms=2878.983433062898, avg_sims_per_move=250.0, sims_per_sec=86.8362065335088, win_rate_per_sec=0.23879956796714918, score_per_sec=35.026831175399664
- `champ_old_weights`: avg_time_ms=2876.648322842063, avg_sims_per_move=250.0, sims_per_sec=86.90669555081578, win_rate_per_sec=0.07966447092158113, score_per_sec=31.326966856217396
- `pool_heuristic`: avg_time_ms=22.181085990298588, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=1.8784773065164866, score_per_sec=3555.9575412357094
- `pool_l9_partial_200ms`: avg_time_ms=1896.2030690218646, avg_sims_per_move=100.0, sims_per_sec=52.73696769807671, win_rate_per_sec=0.021973736540865298, score_per_sec=41.47323034722916

## TrueSkill Ratings
- Converged: `True`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `champ_new_weights` | 60.28 | 6.50 | **40.79** | 120 |
| 2 | `champ_old_weights` | 34.31 | 6.13 | **15.91** | 120 |
| 3 | `pool_heuristic` | 9.31 | 6.13 | **-9.09** | 120 |
| 4 | `pool_l9_partial_200ms` | -1.85 | 6.17 | **-20.36** | 120 |

## Score Margins (winner - last place)
- Mean: `30.56`, Median: `28.0`, Std: `14.37`, Range: `[3.0, 65.0]`

## Score by Seat Position
- `champ_new_weights`: P1: 102.77±2.05 (n=30), P2: 101.4±2.34 (n=30), P3: 102.4±2.22 (n=30), P4: 96.8±2.37 (n=30)
- `champ_old_weights`: P1: 92.27±1.84 (n=30), P2: 93.37±1.62 (n=30), P3: 87.63±1.64 (n=30), P4: 87.2±1.49 (n=30)
- `pool_heuristic`: P1: 81.77±1.46 (n=30), P2: 80.83±1.34 (n=30), P3: 76.2±1.76 (n=30), P4: 76.7±1.52 (n=30)
- `pool_l9_partial_200ms`: P1: 80.87±1.66 (n=30), P2: 78.67±1.85 (n=30), P3: 79.23±1.75 (n=30), P4: 75.8±1.71 (n=30)
