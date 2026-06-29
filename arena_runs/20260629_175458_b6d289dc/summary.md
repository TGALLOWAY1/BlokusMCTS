# Arena Run Summary: 20260629_175458_b6d289dc

## Overview
- Seed: `20260602`
- Seat policy: `round_robin`
- Games: `60/60` completed
- Error games: `0`

## Win Rates by Agent
- `champ_v3`: win_rate=0.600, win_points=36.00, outright=36, shared=0
- `pool_heuristic`: win_rate=0.008, win_points=0.50, outright=0, shared=1
- `pool_l45_100ms`: win_rate=0.017, win_points=1.00, outright=1, shared=0
- `pool_peer_500ms`: win_rate=0.375, win_points=22.50, outright=22, shared=1

## Win Rates by Seat
- `champ_v3`: seat0: 0.800 (15 games), seat1: 0.667 (15 games), seat2: 0.333 (15 games), seat3: 0.600 (15 games)
- `pool_heuristic`: seat0: 0.033 (15 games), seat1: 0.000 (15 games), seat2: 0.000 (15 games), seat3: 0.000 (15 games)
- `pool_l45_100ms`: seat0: 0.067 (15 games), seat1: 0.000 (15 games), seat2: 0.000 (15 games), seat3: 0.000 (15 games)
- `pool_peer_500ms`: seat0: 0.333 (15 games), seat1: 0.600 (15 games), seat2: 0.367 (15 games), seat3: 0.200 (15 games)

## Score Stats
- `champ_v3`: mean=100.08333333333333, median=99.0, std=12.258727050101445, p25=93.0, p75=105.0, min=66.0, max=124.0
- `pool_heuristic`: mean=77.3, median=77.0, std=7.421365552690868, p25=73.0, p75=82.0, min=63.0, max=96.0
- `pool_l45_100ms`: mean=74.61666666666666, median=76.0, std=7.956321735296754, p25=70.0, p75=80.25, min=56.0, max=93.0
- `pool_peer_500ms`: mean=95.11666666666666, median=95.0, std=9.07210314952137, p25=89.0, p75=100.0, min=71.0, max=120.0

## Pairwise Matchups
- `champ_v3__vs__pool_heuristic`: champ_v3>pool_heuristic=54, pool_heuristic>champ_v3=6, tie=0 (total=60)
- `champ_v3__vs__pool_l45_100ms`: champ_v3>pool_l45_100ms=57, pool_l45_100ms>champ_v3=2, tie=1 (total=60)
- `champ_v3__vs__pool_peer_500ms`: champ_v3>pool_peer_500ms=36, pool_peer_500ms>champ_v3=24, tie=0 (total=60)
- `pool_heuristic__vs__pool_l45_100ms`: pool_heuristic>pool_l45_100ms=34, pool_l45_100ms>pool_heuristic=24, tie=2 (total=60)
- `pool_heuristic__vs__pool_peer_500ms`: pool_heuristic>pool_peer_500ms=4, pool_peer_500ms>pool_heuristic=55, tie=1 (total=60)
- `pool_l45_100ms__vs__pool_peer_500ms`: pool_l45_100ms>pool_peer_500ms=2, pool_peer_500ms>pool_l45_100ms=58, tie=0 (total=60)

## Time and Simulation Efficiency
- `champ_v3`: avg_time_ms=2731.755574129269, avg_sims_per_move=250.0, sims_per_sec=91.51624046001481, win_rate_per_sec=0.21963897710403552, score_per_sec=36.63700159749259
- `pool_heuristic`: avg_time_ms=22.811031398104127, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.36532032190468744, score_per_sec=3388.7113059878807
- `pool_l45_100ms`: avg_time_ms=1044.9409432381203, avg_sims_per_move=50.0, sims_per_sec=47.84959410725859, win_rate_per_sec=0.015949864702419533, score_per_sec=71.40754427273224
- `pool_peer_500ms`: avg_time_ms=2826.8629845425726, avg_sims_per_move=250.0, sims_per_sec=88.43725407528147, win_rate_per_sec=0.13265588111292223, score_per_sec=33.64742726717542

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `champ_v3` | 53.70 | 7.14 | **32.27** | 60 |
| 2 | `pool_peer_500ms` | 49.78 | 7.02 | **28.73** | 60 |
| 3 | `pool_heuristic` | 4.52 | 6.79 | **-15.85** | 60 |
| 4 | `pool_l45_100ms` | -5.37 | 6.82 | **-25.82** | 60 |

## Score Margins (winner - last place)
- Mean: `33.32`, Median: `32.0`, Std: `12.69`, Range: `[3.0, 66.0]`

## Score by Seat Position
- `champ_v3`: P1: 100.53±3.14 (n=15), P2: 99.73±2.28 (n=15), P3: 96.6±3.95 (n=15), P4: 103.47±3.25 (n=15)
- `pool_heuristic`: P1: 76.13±1.91 (n=15), P2: 79.27±2.34 (n=15), P3: 75.13±1.75 (n=15), P4: 78.67±1.64 (n=15)
- `pool_l45_100ms`: P1: 79.33±1.72 (n=15), P2: 75.27±2.23 (n=15), P3: 71.13±2.27 (n=15), P4: 72.73±1.5 (n=15)
- `pool_peer_500ms`: P1: 94.27±1.52 (n=15), P2: 97.27±1.94 (n=15), P3: 98.2±2.59 (n=15), P4: 90.73±2.88 (n=15)
