# Arena Run Summary: 20260614_135743_ca1ba49d

## Overview
- Seed: `20260514`
- Seat policy: `round_robin`
- Games: `60/60` completed
- Error games: `0`

## Win Rates by Agent
- `champion_minimal`: win_rate=0.367, win_points=22.00, outright=22, shared=0
- `champion_v1`: win_rate=0.258, win_points=15.50, outright=15, shared=1
- `pool_heuristic`: win_rate=0.017, win_points=1.00, outright=1, shared=0
- `pool_peer_500ms`: win_rate=0.358, win_points=21.50, outright=21, shared=1

## Win Rates by Seat
- `champion_minimal`: seat0: 0.533 (15 games), seat1: 0.467 (15 games), seat2: 0.200 (15 games), seat3: 0.267 (15 games)
- `champion_v1`: seat0: 0.300 (15 games), seat1: 0.200 (15 games), seat2: 0.333 (15 games), seat3: 0.200 (15 games)
- `pool_heuristic`: seat0: 0.000 (15 games), seat1: 0.000 (15 games), seat2: 0.000 (15 games), seat3: 0.067 (15 games)
- `pool_peer_500ms`: seat0: 0.600 (15 games), seat1: 0.433 (15 games), seat2: 0.200 (15 games), seat3: 0.200 (15 games)

## Score Stats
- `champion_minimal`: mean=91.61666666666666, median=92.0, std=6.050045913508059, p25=87.75, p75=96.0, min=78.0, max=104.0
- `champion_v1`: mean=87.43333333333334, median=87.0, std=8.885131150160673, p25=81.75, p75=93.25, min=70.0, max=112.0
- `pool_heuristic`: mean=76.48333333333333, median=77.5, std=7.3518516186211365, p25=71.0, p75=81.0, min=61.0, max=94.0
- `pool_peer_500ms`: mean=92.73333333333333, median=90.5, std=11.757078246268879, p25=85.0, p75=99.0, min=73.0, max=124.0

## Pairwise Matchups
- `champion_minimal__vs__champion_v1`: champion_minimal>champion_v1=38, champion_v1>champion_minimal=22, tie=0 (total=60)
- `champion_minimal__vs__pool_heuristic`: champion_minimal>pool_heuristic=55, pool_heuristic>champion_minimal=4, tie=1 (total=60)
- `champion_minimal__vs__pool_peer_500ms`: champion_minimal>pool_peer_500ms=30, pool_peer_500ms>champion_minimal=30, tie=0 (total=60)
- `champion_v1__vs__pool_heuristic`: champion_v1>pool_heuristic=49, pool_heuristic>champion_v1=10, tie=1 (total=60)
- `champion_v1__vs__pool_peer_500ms`: champion_v1>pool_peer_500ms=23, pool_peer_500ms>champion_v1=35, tie=2 (total=60)
- `pool_heuristic__vs__pool_peer_500ms`: pool_heuristic>pool_peer_500ms=4, pool_peer_500ms>pool_heuristic=55, tie=1 (total=60)

## Time and Simulation Efficiency
- `champion_minimal`: avg_time_ms=4042.2558654082723, avg_sims_per_move=250.0, sims_per_sec=61.846654027861675, win_rate_per_sec=0.09070842590753045, score_per_sec=22.66473714607704
- `champion_v1`: avg_time_ms=4688.1776048326365, avg_sims_per_move=250.0, sims_per_sec=53.325624810437354, win_rate_per_sec=0.05510314563745193, score_per_sec=18.649748517036954
- `pool_heuristic`: avg_time_ms=33.7308550469655, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.4941074468305254, score_per_sec=2267.459073505281
- `pool_peer_500ms`: avg_time_ms=5423.494196111034, avg_sims_per_move=250.0, sims_per_sec=46.09574399088779, win_rate_per_sec=0.06607056638693916, score_per_sec=17.098447971019976

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `champion_minimal` | 39.38 | 6.89 | **18.72** | 60 |
| 2 | `pool_peer_500ms` | 36.15 | 6.89 | **15.48** | 60 |
| 3 | `champion_v1` | 32.00 | 6.88 | **11.37** | 60 |
| 4 | `pool_heuristic` | -6.95 | 7.02 | **-28.01** | 60 |

## Score Margins (winner - last place)
- Mean: `24.48`, Median: `21.5`, Std: `11.73`, Range: `[7.0, 55.0]`

## Score by Seat Position
- `champion_minimal`: P1: 94.33±2.03 (n=15), P2: 90.27±1.16 (n=15), P3: 90.53±1.54 (n=15), P4: 91.33±1.37 (n=15)
- `champion_v1`: P1: 90.4±2.06 (n=15), P2: 86.07±2.67 (n=15), P3: 88.6±1.86 (n=15), P4: 84.67±2.51 (n=15)
- `pool_heuristic`: P1: 77.27±1.49 (n=15), P2: 78.2±2.03 (n=15), P3: 75.93±1.79 (n=15), P4: 74.53±2.31 (n=15)
- `pool_peer_500ms`: P1: 96.47±3.49 (n=15), P2: 94.07±3.06 (n=15), P3: 94.07±2.72 (n=15), P4: 86.33±2.53 (n=15)
