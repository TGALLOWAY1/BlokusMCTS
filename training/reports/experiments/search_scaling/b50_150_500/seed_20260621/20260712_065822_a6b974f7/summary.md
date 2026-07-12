# Arena Run Summary: 20260712_065822_a6b974f7

## Overview
- Seed: `20260621`
- Seat policy: `round_robin`
- Games: `12/12` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `mcts_it150`: win_rate=0.528, win_points=6.33, outright=6, shared=1
- `mcts_it50`: win_rate=0.194, win_points=2.33, outright=2, shared=1
- `mcts_it500`: win_rate=0.278, win_points=3.33, outright=3, shared=1

## Win Rates by Seat
- `heuristic`: seat0: 0.000 (3 games), seat1: 0.000 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `mcts_it150`: seat0: 0.444 (3 games), seat1: 0.333 (3 games), seat2: 0.667 (3 games), seat3: 0.667 (3 games)
- `mcts_it50`: seat0: 0.333 (3 games), seat1: 0.333 (3 games), seat2: 0.000 (3 games), seat3: 0.111 (3 games)
- `mcts_it500`: seat0: 0.333 (3 games), seat1: 0.444 (3 games), seat2: 0.333 (3 games), seat3: 0.000 (3 games)

## Score Stats
- `heuristic`: mean=67.91666666666667, median=68.5, std=6.047841671942884, p25=64.75, p75=72.25, min=53.0, max=77.0
- `mcts_it150`: mean=82.91666666666667, median=80.5, std=14.761765552338995, p25=75.25, p75=88.75, min=54.0, max=108.0
- `mcts_it50`: mean=78.25, median=76.5, std=11.106492095466807, p25=73.75, p75=81.0, min=58.0, max=108.0
- `mcts_it500`: mean=73.58333333333333, median=74.5, std=12.010123044979828, p25=69.0, p75=77.0, min=52.0, max=103.0

## Pairwise Matchups
- `heuristic__vs__mcts_it150`: heuristic>mcts_it150=1, mcts_it150>heuristic=11, tie=0 (total=12)
- `heuristic__vs__mcts_it50`: heuristic>mcts_it50=1, mcts_it50>heuristic=11, tie=0 (total=12)
- `heuristic__vs__mcts_it500`: heuristic>mcts_it500=5, mcts_it500>heuristic=7, tie=0 (total=12)
- `mcts_it150__vs__mcts_it50`: mcts_it150>mcts_it50=7, mcts_it50>mcts_it150=4, tie=1 (total=12)
- `mcts_it150__vs__mcts_it500`: mcts_it150>mcts_it500=8, mcts_it500>mcts_it150=3, tie=1 (total=12)
- `mcts_it50__vs__mcts_it500`: mcts_it50>mcts_it500=6, mcts_it500>mcts_it50=5, tie=1 (total=12)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=28.40754262827179, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=2390.796963869538
- `mcts_it150`: avg_time_ms=2990.076977411906, avg_sims_per_move=150.0, sims_per_sec=50.16593256065072, win_rate_per_sec=0.17650976271340066, score_per_sec=27.730612721026368
- `mcts_it50`: avg_time_ms=1069.405192109548, avg_sims_per_move=50.0, sims_per_sec=46.75496282318227, win_rate_per_sec=0.18182485542348656, score_per_sec=73.17151681828024
- `mcts_it500`: avg_time_ms=10062.128036068036, avg_sims_per_move=500.0, sims_per_sec=49.6912778497484, win_rate_per_sec=0.02760626547208245, score_per_sec=7.31289972355464

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `mcts_it150` | 34.61 | 8.02 | **10.53** | 12 |
| 2 | `mcts_it50` | 29.60 | 7.92 | **5.85** | 12 |
| 3 | `mcts_it500` | 19.81 | 7.90 | **-3.91** | 12 |
| 4 | `heuristic` | 16.08 | 7.80 | **-7.31** | 12 |

## Score Margins (winner - last place)
- Mean: `27.67`, Median: `23.0`, Std: `14.99`, Range: `[9.0, 56.0]`

## Score by Seat Position
- `heuristic`: P1: 72.33±1.2 (n=3), P2: 68.0±0.58 (n=3), P3: 64.0±0.58 (n=3), P4: 67.33±7.31 (n=3)
- `mcts_it150`: P1: 84.67±11.79 (n=3), P2: 71.33±8.69 (n=3), P3: 89.0±7.09 (n=3), P4: 86.67±8.76 (n=3)
- `mcts_it50`: P1: 77.0±3.51 (n=3), P2: 87.33±10.4 (n=3), P3: 69.67±6.39 (n=3), P4: 79.0±2.52 (n=3)
- `mcts_it500`: P1: 81.67±11.05 (n=3), P2: 69.67±8.95 (n=3), P3: 73.0±1.53 (n=3), P4: 70.0±6.08 (n=3)
