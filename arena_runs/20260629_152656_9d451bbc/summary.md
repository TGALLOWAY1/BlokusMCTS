# Arena Run Summary: 20260629_152656_9d451bbc

## Overview
- Seed: `20260601`
- Seat policy: `round_robin`
- Games: `60/60` completed
- Error games: `0`

## Win Rates by Agent
- `champ_v3`: win_rate=0.692, win_points=41.50, outright=40, shared=3
- `pool_heuristic`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `pool_l45_100ms`: win_rate=0.008, win_points=0.50, outright=0, shared=1
- `pool_peer_500ms`: win_rate=0.300, win_points=18.00, outright=16, shared=4

## Win Rates by Seat
- `champ_v3`: seat0: 0.867 (15 games), seat1: 0.533 (15 games), seat2: 0.700 (15 games), seat3: 0.667 (15 games)
- `pool_heuristic`: seat0: 0.000 (15 games), seat1: 0.000 (15 games), seat2: 0.000 (15 games), seat3: 0.000 (15 games)
- `pool_l45_100ms`: seat0: 0.033 (15 games), seat1: 0.000 (15 games), seat2: 0.000 (15 games), seat3: 0.000 (15 games)
- `pool_peer_500ms`: seat0: 0.467 (15 games), seat1: 0.267 (15 games), seat2: 0.333 (15 games), seat3: 0.133 (15 games)

## Score Stats
- `champ_v3`: mean=100.8, median=99.5, std=12.864421220301104, p25=94.5, p75=105.0, min=56.0, max=124.0
- `pool_heuristic`: mean=76.93333333333334, median=76.0, std=8.146301137462464, p25=70.75, p75=83.0, min=59.0, max=92.0
- `pool_l45_100ms`: mean=73.78333333333333, median=74.0, std=9.597033685236056, p25=66.0, p75=80.0, min=56.0, max=101.0
- `pool_peer_500ms`: mean=95.55, median=95.5, std=9.11304010745042, p25=91.0, p75=98.0, min=77.0, max=122.0

## Pairwise Matchups
- `champ_v3__vs__pool_heuristic`: champ_v3>pool_heuristic=57, pool_heuristic>champ_v3=3, tie=0 (total=60)
- `champ_v3__vs__pool_l45_100ms`: champ_v3>pool_l45_100ms=57, pool_l45_100ms>champ_v3=2, tie=1 (total=60)
- `champ_v3__vs__pool_peer_500ms`: champ_v3>pool_peer_500ms=40, pool_peer_500ms>champ_v3=17, tie=3 (total=60)
- `pool_heuristic__vs__pool_l45_100ms`: pool_heuristic>pool_l45_100ms=34, pool_l45_100ms>pool_heuristic=25, tie=1 (total=60)
- `pool_heuristic__vs__pool_peer_500ms`: pool_heuristic>pool_peer_500ms=5, pool_peer_500ms>pool_heuristic=55, tie=0 (total=60)
- `pool_l45_100ms__vs__pool_peer_500ms`: pool_l45_100ms>pool_peer_500ms=0, pool_peer_500ms>pool_l45_100ms=58, tie=2 (total=60)

## Time and Simulation Efficiency
- `champ_v3`: avg_time_ms=2731.04952262885, avg_sims_per_move=250.0, sims_per_sec=91.53989992805232, win_rate_per_sec=0.25326038980094473, score_per_sec=36.90888765099069
- `pool_heuristic`: avg_time_ms=22.587893736223478, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=3405.9542793916116
- `pool_l45_100ms`: avg_time_ms=1066.6819221848205, avg_sims_per_move=50.0, sims_per_sec=46.87432960107546, win_rate_per_sec=0.00781238826684591, score_per_sec=69.17088571465368
- `pool_peer_500ms`: avg_time_ms=2815.3200336531095, avg_sims_per_move=250.0, sims_per_sec=88.79985117557112, win_rate_per_sec=0.10655982141068535, score_per_sec=33.93930311930328

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `champ_v3` | 58.71 | 7.20 | **37.11** | 60 |
| 2 | `pool_peer_500ms` | 48.03 | 7.00 | **27.04** | 60 |
| 3 | `pool_heuristic` | 2.77 | 6.78 | **-17.56** | 60 |
| 4 | `pool_l45_100ms` | -6.56 | 6.83 | **-27.05** | 60 |

## Score Margins (winner - last place)
- Mean: `36.0`, Median: `33.5`, Std: `14.17`, Range: `[10.0, 66.0]`

## Score by Seat Position
- `champ_v3`: P1: 104.87±3.17 (n=15), P2: 97.07±4.44 (n=15), P3: 101.0±2.86 (n=15), P4: 100.27±2.67 (n=15)
- `pool_heuristic`: P1: 78.07±2.02 (n=15), P2: 78.47±2.45 (n=15), P3: 74.73±2.0 (n=15), P4: 76.47±2.07 (n=15)
- `pool_l45_100ms`: P1: 79.33±2.63 (n=15), P2: 73.0±1.82 (n=15), P3: 70.33±2.48 (n=15), P4: 72.47±2.59 (n=15)
- `pool_peer_500ms`: P1: 96.67±1.12 (n=15), P2: 98.2±2.53 (n=15), P3: 99.53±2.53 (n=15), P4: 87.8±1.91 (n=15)
