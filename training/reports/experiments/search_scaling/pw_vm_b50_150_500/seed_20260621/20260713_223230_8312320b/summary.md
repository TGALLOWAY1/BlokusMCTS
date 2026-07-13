# Arena Run Summary: 20260713_223230_8312320b

## Overview
- Seed: `20260621`
- Seat policy: `round_robin`
- Games: `12/12` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `mcts_it150`: win_rate=0.625, win_points=7.50, outright=7, shared=1
- `mcts_it50`: win_rate=0.125, win_points=1.50, outright=1, shared=1
- `mcts_it500`: win_rate=0.250, win_points=3.00, outright=3, shared=0

## Win Rates by Seat
- `heuristic`: seat0: 0.000 (3 games), seat1: 0.000 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `mcts_it150`: seat0: 1.000 (3 games), seat1: 0.333 (3 games), seat2: 0.833 (3 games), seat3: 0.333 (3 games)
- `mcts_it50`: seat0: 0.333 (3 games), seat1: 0.167 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `mcts_it500`: seat0: 0.667 (3 games), seat1: 0.000 (3 games), seat2: 0.333 (3 games), seat3: 0.000 (3 games)

## Score Stats
- `heuristic`: mean=68.08333333333333, median=67.0, std=4.768967975941499, p25=65.75, p75=70.75, min=60.0, max=76.0
- `mcts_it150`: mean=90.58333333333333, median=84.0, std=14.390149022469812, p25=79.75, p75=108.0, min=71.0, max=108.0
- `mcts_it50`: mean=80.58333333333333, median=80.5, std=8.391050126308519, p25=76.0, p75=84.0, min=69.0, max=103.0
- `mcts_it500`: mean=85.66666666666667, median=81.5, std=12.591884511682736, p25=76.75, p75=88.75, min=70.0, max=108.0

## Pairwise Matchups
- `heuristic__vs__mcts_it150`: heuristic>mcts_it150=0, mcts_it150>heuristic=12, tie=0 (total=12)
- `heuristic__vs__mcts_it50`: heuristic>mcts_it50=1, mcts_it50>heuristic=10, tie=1 (total=12)
- `heuristic__vs__mcts_it500`: heuristic>mcts_it500=1, mcts_it500>heuristic=11, tie=0 (total=12)
- `mcts_it150__vs__mcts_it50`: mcts_it150>mcts_it50=8, mcts_it50>mcts_it150=3, tie=1 (total=12)
- `mcts_it150__vs__mcts_it500`: mcts_it150>mcts_it500=8, mcts_it500>mcts_it150=4, tie=0 (total=12)
- `mcts_it50__vs__mcts_it500`: mcts_it50>mcts_it500=4, mcts_it500>mcts_it50=6, tie=2 (total=12)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=34.42424979998338, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=1977.772463566256
- `mcts_it150`: avg_time_ms=4220.099869180233, avg_sims_per_move=150.0, sims_per_sec=35.54418251934354, win_rate_per_sec=0.14810076049726476, score_per_sec=21.464736888070238
- `mcts_it50`: avg_time_ms=1497.489961273467, avg_sims_per_move=50.0, sims_per_sec=33.38920546584496, win_rate_per_sec=0.08347301366461239, score_per_sec=53.812269475786785
- `mcts_it500`: avg_time_ms=14581.758040967195, avg_sims_per_move=500.0, sims_per_sec=34.28941823031617, win_rate_per_sec=0.01714470911515809, score_per_sec=5.874920323460838

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `mcts_it150` | 35.50 | 8.01 | **11.47** | 12 |
| 2 | `mcts_it500` | 28.86 | 7.92 | **5.09** | 12 |
| 3 | `mcts_it50` | 26.87 | 7.91 | **3.14** | 12 |
| 4 | `heuristic` | 9.03 | 7.82 | **-14.42** | 12 |

## Score Margins (winner - last place)
- Mean: `31.33`, Median: `37.0`, Std: `11.95`, Range: `[14.0, 48.0]`

## Score by Seat Position
- `heuristic`: P1: 66.67±0.88 (n=3), P2: 68.33±4.1 (n=3), P3: 72.0±2.65 (n=3), P4: 65.33±2.91 (n=3)
- `mcts_it150`: P1: 108.0±0.0 (n=3), P2: 84.0±12.01 (n=3), P3: 83.0±1.0 (n=3), P4: 87.33±7.84 (n=3)
- `mcts_it50`: P1: 83.0±1.0 (n=3), P2: 76.33±4.33 (n=3), P3: 87.33±8.09 (n=3), P4: 75.67±2.96 (n=3)
- `mcts_it500`: P1: 98.0±7.64 (n=3), P2: 79.33±4.67 (n=3), P3: 88.33±9.87 (n=3), P4: 77.0±1.53 (n=3)
