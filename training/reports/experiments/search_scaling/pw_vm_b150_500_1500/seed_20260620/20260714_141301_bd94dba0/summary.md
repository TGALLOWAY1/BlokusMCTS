# Arena Run Summary: 20260714_141301_bd94dba0

## Overview
- Seed: `20260620`
- Seat policy: `round_robin`
- Games: `6/6` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `mcts_it150`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `mcts_it1500`: win_rate=0.583, win_points=3.50, outright=3, shared=1
- `mcts_it500`: win_rate=0.417, win_points=2.50, outright=2, shared=1

## Win Rates by Seat
- `heuristic`: seat0: 0.000 (1 games), seat1: 0.000 (1 games), seat2: 0.000 (2 games), seat3: 0.000 (2 games)
- `mcts_it150`: seat0: 0.000 (2 games), seat1: 0.000 (1 games), seat2: 0.000 (1 games), seat3: 0.000 (2 games)
- `mcts_it1500`: seat0: 1.000 (1 games), seat1: 0.500 (2 games), seat2: 0.500 (2 games), seat3: 0.500 (1 games)
- `mcts_it500`: seat0: 0.500 (2 games), seat1: 0.500 (2 games), seat2: 0.500 (1 games), seat3: 0.000 (1 games)

## Score Stats
- `heuristic`: mean=69.16666666666667, median=70.5, std=3.0230595245361753, p25=66.25, p75=71.75, min=65.0, max=72.0
- `mcts_it150`: mean=73.83333333333333, median=74.5, std=2.6718699236468995, p25=72.5, p75=75.75, min=69.0, max=77.0
- `mcts_it1500`: mean=87.66666666666667, median=84.5, std=13.646326326972481, p25=78.0, p75=98.5, min=70.0, max=108.0
- `mcts_it500`: mean=90.33333333333333, median=84.0, std=12.710450643291745, p25=81.75, p75=102.0, min=77.0, max=108.0

## Pairwise Matchups
- `heuristic__vs__mcts_it150`: heuristic>mcts_it150=0, mcts_it150>heuristic=5, tie=1 (total=6)
- `heuristic__vs__mcts_it1500`: heuristic>mcts_it1500=0, mcts_it1500>heuristic=6, tie=0 (total=6)
- `heuristic__vs__mcts_it500`: heuristic>mcts_it500=0, mcts_it500>heuristic=6, tie=0 (total=6)
- `mcts_it1500__vs__mcts_it500`: mcts_it1500>mcts_it500=3, mcts_it500>mcts_it1500=2, tie=1 (total=6)
- `mcts_it150__vs__mcts_it1500`: mcts_it150>mcts_it1500=0, mcts_it1500>mcts_it150=6, tie=0 (total=6)
- `mcts_it150__vs__mcts_it500`: mcts_it150>mcts_it500=0, mcts_it500>mcts_it150=6, tie=0 (total=6)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=35.40587202084744, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=1953.5365948885665
- `mcts_it150`: avg_time_ms=4960.248117263501, avg_sims_per_move=150.0, sims_per_sec=30.2404227477945, win_rate_per_sec=0.0, score_per_sec=14.885008085858846
- `mcts_it1500`: avg_time_ms=43293.36627804, avg_sims_per_move=1500.0, sims_per_sec=34.64734043471357, win_rate_per_sec=0.013473965724610832, score_per_sec=2.0249445631843708
- `mcts_it500`: avg_time_ms=14503.59380746088, avg_sims_per_move=500.0, sims_per_sec=34.47421422839297, win_rate_per_sec=0.02872851185699414, score_per_sec=6.228341370596329

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `mcts_it1500` | 32.51 | 8.19 | **7.93** | 6 |
| 2 | `mcts_it500` | 32.10 | 8.19 | **7.55** | 6 |
| 3 | `mcts_it150` | 21.48 | 8.03 | **-2.59** | 6 |
| 4 | `heuristic` | 14.13 | 8.04 | **-9.99** | 6 |

## Score Margins (winner - last place)
- Mean: `26.17`, Median: `27.5`, Std: `10.67`, Range: `[13.0, 38.0]`

## Score by Seat Position
- `heuristic`: P1: 72.0±0.0 (n=1), P2: 65.0±0.0 (n=1), P3: 71.5±0.5 (n=2), P4: 67.5±2.5 (n=2)
- `mcts_it150`: P1: 72.0±3.0 (n=2), P2: 72.0±0.0 (n=1), P3: 76.0±0.0 (n=1), P4: 75.5±1.5 (n=2)
- `mcts_it1500`: P1: 103.0±0.0 (n=1), P2: 80.0±4.0 (n=2), P3: 77.5±7.5 (n=2), P4: 108.0±0.0 (n=1)
- `mcts_it500`: P1: 94.5±13.5 (n=2), P2: 80.5±3.5 (n=2), P3: 108.0±0.0 (n=1), P4: 84.0±0.0 (n=1)
