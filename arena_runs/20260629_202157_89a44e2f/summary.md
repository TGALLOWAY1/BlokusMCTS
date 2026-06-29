# Arena Run Summary: 20260629_202157_89a44e2f

## Overview
- Seed: `20260603`
- Seat policy: `round_robin`
- Games: `60/60` completed
- Error games: `0`

## Win Rates by Agent
- `champ_v3`: win_rate=0.567, win_points=34.00, outright=34, shared=0
- `pool_heuristic`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `pool_l45_100ms`: win_rate=0.017, win_points=1.00, outright=1, shared=0
- `pool_peer_500ms`: win_rate=0.417, win_points=25.00, outright=25, shared=0

## Win Rates by Seat
- `champ_v3`: seat0: 0.800 (15 games), seat1: 0.467 (15 games), seat2: 0.533 (15 games), seat3: 0.467 (15 games)
- `pool_heuristic`: seat0: 0.000 (15 games), seat1: 0.000 (15 games), seat2: 0.000 (15 games), seat3: 0.000 (15 games)
- `pool_l45_100ms`: seat0: 0.000 (15 games), seat1: 0.000 (15 games), seat2: 0.000 (15 games), seat3: 0.067 (15 games)
- `pool_peer_500ms`: seat0: 0.467 (15 games), seat1: 0.467 (15 games), seat2: 0.533 (15 games), seat3: 0.200 (15 games)

## Score Stats
- `champ_v3`: mean=100.0, median=100.0, std=11.222002198063112, p25=93.75, p75=105.0, min=74.0, max=124.0
- `pool_heuristic`: mean=78.3, median=79.0, std=7.387602227155077, p25=72.0, p75=82.25, min=59.0, max=99.0
- `pool_l45_100ms`: mean=73.75, median=75.0, std=9.348128154876783, p25=66.75, p75=80.0, min=53.0, max=103.0
- `pool_peer_500ms`: mean=95.1, median=95.0, std=8.320056089554527, p25=90.0, p75=100.0, min=77.0, max=122.0

## Pairwise Matchups
- `champ_v3__vs__pool_heuristic`: champ_v3>pool_heuristic=55, pool_heuristic>champ_v3=5, tie=0 (total=60)
- `champ_v3__vs__pool_l45_100ms`: champ_v3>pool_l45_100ms=57, pool_l45_100ms>champ_v3=3, tie=0 (total=60)
- `champ_v3__vs__pool_peer_500ms`: champ_v3>pool_peer_500ms=34, pool_peer_500ms>champ_v3=26, tie=0 (total=60)
- `pool_heuristic__vs__pool_l45_100ms`: pool_heuristic>pool_l45_100ms=41, pool_l45_100ms>pool_heuristic=18, tie=1 (total=60)
- `pool_heuristic__vs__pool_peer_500ms`: pool_heuristic>pool_peer_500ms=2, pool_peer_500ms>pool_heuristic=57, tie=1 (total=60)
- `pool_l45_100ms__vs__pool_peer_500ms`: pool_l45_100ms>pool_peer_500ms=3, pool_peer_500ms>pool_l45_100ms=57, tie=0 (total=60)

## Time and Simulation Efficiency
- `champ_v3`: avg_time_ms=2687.9739438108004, avg_sims_per_move=250.0, sims_per_sec=93.00685394500864, win_rate_per_sec=0.21081553560868627, score_per_sec=37.202741578003454
- `pool_heuristic`: avg_time_ms=22.462073612342433, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=3485.875852395738
- `pool_l45_100ms`: avg_time_ms=1061.687532872507, avg_sims_per_move=50.0, sims_per_sec=47.09483577029464, win_rate_per_sec=0.01569827859009821, score_per_sec=69.46488276118458
- `pool_peer_500ms`: avg_time_ms=2797.2944517381893, avg_sims_per_move=250.0, sims_per_sec=89.37207159033773, win_rate_per_sec=0.1489534526505629, score_per_sec=33.99713603296447

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `champ_v3` | 53.14 | 7.11 | **31.80** | 60 |
| 2 | `pool_peer_500ms` | 52.09 | 7.04 | **30.98** | 60 |
| 3 | `pool_heuristic` | 5.84 | 6.76 | **-14.45** | 60 |
| 4 | `pool_l45_100ms` | -8.56 | 6.92 | **-29.31** | 60 |

## Score Margins (winner - last place)
- Mean: `33.97`, Median: `32.5`, Std: `12.53`, Range: `[13.0, 65.0]`

## Score by Seat Position
- `champ_v3`: P1: 105.6±2.5 (n=15), P2: 100.87±3.16 (n=15), P3: 99.0±3.04 (n=15), P4: 94.53±2.45 (n=15)
- `pool_heuristic`: P1: 81.8±1.82 (n=15), P2: 78.8±1.67 (n=15), P3: 77.4±2.07 (n=15), P4: 75.2±1.89 (n=15)
- `pool_l45_100ms`: P1: 79.0±1.82 (n=15), P2: 74.67±1.63 (n=15), P3: 69.27±2.72 (n=15), P4: 72.07±2.81 (n=15)
- `pool_peer_500ms`: P1: 96.53±1.99 (n=15), P2: 98.87±2.67 (n=15), P3: 93.87±1.7 (n=15), P4: 91.13±1.84 (n=15)
