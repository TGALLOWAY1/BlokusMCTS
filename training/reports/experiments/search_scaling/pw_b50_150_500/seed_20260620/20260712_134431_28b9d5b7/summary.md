# Arena Run Summary: 20260712_134431_28b9d5b7

## Overview
- Seed: `20260620`
- Seat policy: `round_robin`
- Games: `12/12` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.083, win_points=1.00, outright=1, shared=0
- `mcts_it150`: win_rate=0.375, win_points=4.50, outright=4, shared=1
- `mcts_it50`: win_rate=0.250, win_points=3.00, outright=3, shared=0
- `mcts_it500`: win_rate=0.292, win_points=3.50, outright=3, shared=1

## Win Rates by Seat
- `heuristic`: seat0: 0.000 (3 games), seat1: 0.000 (3 games), seat2: 0.333 (3 games), seat3: 0.000 (3 games)
- `mcts_it150`: seat0: 0.000 (3 games), seat1: 0.667 (3 games), seat2: 0.333 (3 games), seat3: 0.500 (3 games)
- `mcts_it50`: seat0: 0.333 (3 games), seat1: 0.333 (3 games), seat2: 0.000 (3 games), seat3: 0.333 (3 games)
- `mcts_it500`: seat0: 0.500 (3 games), seat1: 0.333 (3 games), seat2: 0.000 (3 games), seat3: 0.333 (3 games)

## Score Stats
- `heuristic`: mean=66.16666666666667, median=66.0, std=6.189148209209048, p25=63.0, p75=70.0, min=54.0, max=77.0
- `mcts_it150`: mean=82.41666666666667, median=81.5, std=13.219041400780752, p25=75.0, p75=84.0, min=61.0, max=108.0
- `mcts_it50`: mean=78.75, median=74.5, std=15.056144924913548, p25=69.5, p75=84.25, min=57.0, max=108.0
- `mcts_it500`: mean=76.5, median=74.5, std=9.543758868146938, p25=70.0, p75=79.0, min=65.0, max=103.0

## Pairwise Matchups
- `heuristic__vs__mcts_it150`: heuristic>mcts_it150=1, mcts_it150>heuristic=11, tie=0 (total=12)
- `heuristic__vs__mcts_it50`: heuristic>mcts_it50=2, mcts_it50>heuristic=10, tie=0 (total=12)
- `heuristic__vs__mcts_it500`: heuristic>mcts_it500=4, mcts_it500>heuristic=8, tie=0 (total=12)
- `mcts_it150__vs__mcts_it50`: mcts_it150>mcts_it50=7, mcts_it50>mcts_it150=4, tie=1 (total=12)
- `mcts_it150__vs__mcts_it500`: mcts_it150>mcts_it500=6, mcts_it500>mcts_it150=5, tie=1 (total=12)
- `mcts_it50__vs__mcts_it500`: mcts_it50>mcts_it500=6, mcts_it500>mcts_it50=6, tie=0 (total=12)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=31.216464941183144, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=2.6695313992262344, score_per_sec=2119.6079309856304
- `mcts_it150`: avg_time_ms=3885.93576343049, avg_sims_per_move=150.0, sims_per_sec=38.60074101368586, win_rate_per_sec=0.09650185253421464, score_per_sec=21.20896270140851
- `mcts_it50`: avg_time_ms=1387.358338052776, avg_sims_per_move=50.0, sims_per_sec=36.03971564417697, win_rate_per_sec=0.1801985782208849, score_per_sec=56.762552139578744
- `mcts_it500`: avg_time_ms=13816.82130708123, avg_sims_per_move=500.0, sims_per_sec=36.18777350357321, win_rate_per_sec=0.021109534543751043, score_per_sec=5.536729346046702

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `mcts_it150` | 31.20 | 7.95 | **7.34** | 12 |
| 2 | `mcts_it50` | 29.44 | 7.92 | **5.68** | 12 |
| 3 | `mcts_it500` | 25.51 | 7.93 | **1.70** | 12 |
| 4 | `heuristic` | 13.91 | 7.84 | **-9.60** | 12 |

## Score Margins (winner - last place)
- Mean: `28.42`, Median: `20.5`, Std: `14.96`, Range: `[7.0, 54.0]`

## Score by Seat Position
- `heuristic`: P1: 66.33±3.33 (n=3), P2: 65.33±4.1 (n=3), P3: 69.67±4.06 (n=3), P4: 63.33±4.67 (n=3)
- `mcts_it150`: P1: 69.67±4.48 (n=3), P2: 92.0±8.0 (n=3), P3: 82.33±1.2 (n=3), P4: 85.67±11.46 (n=3)
- `mcts_it50`: P1: 87.33±11.1 (n=3), P2: 73.0±6.03 (n=3), P3: 74.67±2.91 (n=3), P4: 80.0±14.93 (n=3)
- `mcts_it500`: P1: 73.33±2.85 (n=3), P2: 83.67±10.09 (n=3), P3: 71.33±3.28 (n=3), P4: 77.67±4.1 (n=3)
