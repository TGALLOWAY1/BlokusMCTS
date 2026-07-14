# Arena Run Summary: 20260713_210632_6dc6fb52

## Overview
- Seed: `20260620`
- Seat policy: `round_robin`
- Games: `12/12` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `mcts_it150`: win_rate=0.278, win_points=3.33, outright=3, shared=1
- `mcts_it50`: win_rate=0.194, win_points=2.33, outright=1, shared=3
- `mcts_it500`: win_rate=0.528, win_points=6.33, outright=5, shared=3

## Win Rates by Seat
- `heuristic`: seat0: 0.000 (3 games), seat1: 0.000 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `mcts_it150`: seat0: 0.444 (3 games), seat1: 0.000 (3 games), seat2: 0.667 (3 games), seat3: 0.000 (3 games)
- `mcts_it50`: seat0: 0.000 (3 games), seat1: 0.000 (3 games), seat2: 0.333 (3 games), seat3: 0.444 (3 games)
- `mcts_it500`: seat0: 0.667 (3 games), seat1: 0.111 (3 games), seat2: 1.000 (3 games), seat3: 0.333 (3 games)

## Score Stats
- `heuristic`: mean=67.75, median=68.0, std=8.115058019919923, p25=62.25, p75=73.0, min=53.0, max=80.0
- `mcts_it150`: mean=85.0, median=80.0, std=12.773670837573146, p25=76.25, p75=88.75, min=73.0, max=108.0
- `mcts_it50`: mean=85.33333333333333, median=81.0, std=14.0909742585655, p25=77.0, p75=90.0, min=64.0, max=108.0
- `mcts_it500`: mean=91.66666666666667, median=84.0, std=14.12641340027806, p25=81.0, p75=108.0, min=72.0, max=108.0

## Pairwise Matchups
- `heuristic__vs__mcts_it150`: heuristic>mcts_it150=1, mcts_it150>heuristic=11, tie=0 (total=12)
- `heuristic__vs__mcts_it50`: heuristic>mcts_it50=2, mcts_it50>heuristic=10, tie=0 (total=12)
- `heuristic__vs__mcts_it500`: heuristic>mcts_it500=1, mcts_it500>heuristic=11, tie=0 (total=12)
- `mcts_it150__vs__mcts_it50`: mcts_it150>mcts_it50=4, mcts_it50>mcts_it150=6, tie=2 (total=12)
- `mcts_it150__vs__mcts_it500`: mcts_it150>mcts_it500=3, mcts_it500>mcts_it150=8, tie=1 (total=12)
- `mcts_it50__vs__mcts_it500`: mcts_it50>mcts_it500=2, mcts_it500>mcts_it50=6, tie=4 (total=12)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=34.1837269166841, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=1981.9371996835475
- `mcts_it150`: avg_time_ms=4415.465949920186, avg_sims_per_move=150.0, sims_per_sec=33.97149965627329, win_rate_per_sec=0.06291018454865423, score_per_sec=19.250516471888194
- `mcts_it50`: avg_time_ms=1476.9157003938105, avg_sims_per_move=50.0, sims_per_sec=33.854335752993755, win_rate_per_sec=0.13165575015053127, score_per_sec=57.77806635177602
- `mcts_it500`: avg_time_ms=14297.745761992057, avg_sims_per_move=500.0, sims_per_sec=34.97054768795502, win_rate_per_sec=0.03691335589284141, score_per_sec=6.411267076125087

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `mcts_it500` | 34.60 | 8.03 | **10.52** | 12 |
| 2 | `mcts_it50` | 29.60 | 7.91 | **5.88** | 12 |
| 3 | `mcts_it150` | 26.87 | 7.89 | **3.19** | 12 |
| 4 | `heuristic` | 9.17 | 7.82 | **-14.29** | 12 |

## Score Margins (winner - last place)
- Mean: `35.42`, Median: `38.0`, Std: `12.28`, Range: `[10.0, 55.0]`

## Score by Seat Position
- `heuristic`: P1: 74.33±5.67 (n=3), P2: 61.67±2.19 (n=3), P3: 70.67±3.53 (n=3), P4: 64.33±5.67 (n=3)
- `mcts_it150`: P1: 87.0±8.08 (n=3), P2: 78.67±3.18 (n=3), P3: 96.67±11.33 (n=3), P4: 77.67±2.33 (n=3)
- `mcts_it50`: P1: 80.33±2.03 (n=3), P2: 79.0±3.61 (n=3), P3: 97.67±10.33 (n=3), P4: 84.33±12.81 (n=3)
- `mcts_it500`: P1: 100.0±8.0 (n=3), P2: 79.67±1.33 (n=3), P3: 108.0±0.0 (n=3), P4: 79.0±3.61 (n=3)
