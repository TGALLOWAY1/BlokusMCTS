# Arena Run Summary: 20260514_024853_e8621532

## Overview
- Seed: `20260601`
- Seat policy: `round_robin`
- Games: `60/60` completed
- Error games: `0`

## Win Rates by Agent
- `champion`: win_rate=0.383, win_points=23.00, outright=23, shared=0
- `pool_heuristic`: win_rate=0.117, win_points=7.00, outright=7, shared=0
- `pool_l45_100ms`: win_rate=0.008, win_points=0.50, outright=0, shared=1
- `pool_peer_500ms`: win_rate=0.492, win_points=29.50, outright=29, shared=1

## Win Rates by Seat
- `champion`: seat0: 0.600 (15 games), seat1: 0.467 (15 games), seat2: 0.333 (15 games), seat3: 0.133 (15 games)
- `pool_heuristic`: seat0: 0.200 (15 games), seat1: 0.067 (15 games), seat2: 0.067 (15 games), seat3: 0.133 (15 games)
- `pool_l45_100ms`: seat0: 0.000 (15 games), seat1: 0.000 (15 games), seat2: 0.033 (15 games), seat3: 0.000 (15 games)
- `pool_peer_500ms`: seat0: 0.467 (15 games), seat1: 0.533 (15 games), seat2: 0.667 (15 games), seat3: 0.300 (15 games)

## Score Stats
- `champion`: mean=93.58333333333333, median=91.0, std=13.075794006059015, p25=83.75, p75=101.5, min=69.0, max=122.0
- `pool_heuristic`: mean=82.4, median=82.0, std=8.901685233707154, p25=77.75, p75=86.25, min=60.0, max=120.0
- `pool_l45_100ms`: mean=75.61666666666666, median=76.5, std=8.752317153506011, p25=67.0, p75=81.25, min=58.0, max=95.0
- `pool_peer_500ms`: mean=95.41666666666667, median=94.5, std=9.011643702578471, p25=90.75, p75=100.0, min=76.0, max=120.0

## Pairwise Matchups
- `champion__vs__pool_heuristic`: champion>pool_heuristic=39, pool_heuristic>champion=17, tie=4 (total=60)
- `champion__vs__pool_l45_100ms`: champion>pool_l45_100ms=52, pool_l45_100ms>champion=8, tie=0 (total=60)
- `champion__vs__pool_peer_500ms`: champion>pool_peer_500ms=26, pool_peer_500ms>champion=34, tie=0 (total=60)
- `pool_heuristic__vs__pool_l45_100ms`: pool_heuristic>pool_l45_100ms=42, pool_l45_100ms>pool_heuristic=17, tie=1 (total=60)
- `pool_heuristic__vs__pool_peer_500ms`: pool_heuristic>pool_peer_500ms=9, pool_peer_500ms>pool_heuristic=51, tie=0 (total=60)
- `pool_l45_100ms__vs__pool_peer_500ms`: pool_l45_100ms>pool_peer_500ms=1, pool_peer_500ms>pool_l45_100ms=58, tie=1 (total=60)

## Time and Simulation Efficiency
- `champion`: avg_time_ms=3578.9386137444967, avg_sims_per_move=250.0, sims_per_sec=69.85311204833303, win_rate_per_sec=0.10710810514077732, score_per_sec=26.14834827675933
- `pool_heuristic`: avg_time_ms=28.412199930163002, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=4.106217292340353, score_per_sec=2900.162613332958
- `pool_l45_100ms`: avg_time_ms=1371.7519797911225, avg_sims_per_move=50.0, sims_per_sec=36.44973780727732, win_rate_per_sec=0.006074956301212888, score_per_sec=55.124153477205745
- `pool_peer_500ms`: avg_time_ms=3856.794606910753, avg_sims_per_move=250.0, sims_per_sec=64.8206672847033, win_rate_per_sec=0.12748064565991649, score_per_sec=24.739888013661762

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `pool_peer_500ms` | 50.55 | 7.03 | **29.45** | 60 |
| 2 | `champion` | 40.48 | 6.94 | **19.65** | 60 |
| 3 | `pool_heuristic` | 12.58 | 6.75 | **-7.67** | 60 |
| 4 | `pool_l45_100ms` | -2.32 | 6.93 | **-23.10** | 60 |

## Score Margins (winner - last place)
- Mean: `29.98`, Median: `26.5`, Std: `13.37`, Range: `[3.0, 60.0]`

## Score by Seat Position
- `champion`: P1: 99.33±3.31 (n=15), P2: 94.87±3.51 (n=15), P3: 93.73±3.74 (n=15), P4: 86.4±2.33 (n=15)
- `pool_heuristic`: P1: 84.33±2.14 (n=15), P2: 78.2±1.78 (n=15), P3: 83.53±3.37 (n=15), P4: 83.53±1.36 (n=15)
- `pool_l45_100ms`: P1: 78.0±2.2 (n=15), P2: 74.4±2.46 (n=15), P3: 79.87±1.77 (n=15), P4: 70.2±2.0 (n=15)
- `pool_peer_500ms`: P1: 97.6±2.47 (n=15), P2: 96.47±1.58 (n=15), P3: 97.4±2.56 (n=15), P4: 90.2±2.32 (n=15)
