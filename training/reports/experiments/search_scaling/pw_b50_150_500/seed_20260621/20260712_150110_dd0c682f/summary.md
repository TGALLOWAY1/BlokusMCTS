# Arena Run Summary: 20260712_150110_dd0c682f

## Overview
- Seed: `20260621`
- Seat policy: `round_robin`
- Games: `12/12` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `mcts_it150`: win_rate=0.250, win_points=3.00, outright=3, shared=0
- `mcts_it50`: win_rate=0.417, win_points=5.00, outright=5, shared=0
- `mcts_it500`: win_rate=0.333, win_points=4.00, outright=4, shared=0

## Win Rates by Seat
- `heuristic`: seat0: 0.000 (3 games), seat1: 0.000 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `mcts_it150`: seat0: 0.333 (3 games), seat1: 0.000 (3 games), seat2: 0.333 (3 games), seat3: 0.333 (3 games)
- `mcts_it50`: seat0: 0.667 (3 games), seat1: 0.667 (3 games), seat2: 0.000 (3 games), seat3: 0.333 (3 games)
- `mcts_it500`: seat0: 0.667 (3 games), seat1: 0.333 (3 games), seat2: 0.333 (3 games), seat3: 0.000 (3 games)

## Score Stats
- `heuristic`: mean=66.91666666666667, median=67.0, std=6.550551291473278, p25=63.0, p75=69.25, min=54.0, max=80.0
- `mcts_it150`: mean=83.41666666666667, median=77.5, std=14.963613274280455, p25=74.0, p75=90.75, min=65.0, max=108.0
- `mcts_it50`: mean=83.83333333333333, median=84.0, std=10.89214803832967, p25=77.75, p75=84.0, min=69.0, max=108.0
- `mcts_it500`: mean=78.66666666666667, median=75.5, std=15.00740557932057, p25=69.75, p75=81.75, min=56.0, max=108.0

## Pairwise Matchups
- `heuristic__vs__mcts_it150`: heuristic>mcts_it150=2, mcts_it150>heuristic=10, tie=0 (total=12)
- `heuristic__vs__mcts_it50`: heuristic>mcts_it50=1, mcts_it50>heuristic=11, tie=0 (total=12)
- `heuristic__vs__mcts_it500`: heuristic>mcts_it500=3, mcts_it500>heuristic=9, tie=0 (total=12)
- `mcts_it150__vs__mcts_it50`: mcts_it150>mcts_it50=5, mcts_it50>mcts_it150=7, tie=0 (total=12)
- `mcts_it150__vs__mcts_it500`: mcts_it150>mcts_it500=6, mcts_it500>mcts_it150=6, tie=0 (total=12)
- `mcts_it50__vs__mcts_it500`: mcts_it50>mcts_it500=8, mcts_it500>mcts_it50=4, tie=0 (total=12)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=34.42102215957036, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=1944.0639024736593
- `mcts_it150`: avg_time_ms=4021.661668752147, avg_sims_per_move=150.0, sims_per_sec=37.29801568478097, win_rate_per_sec=0.06216335947463496, score_per_sec=20.7418409447032
- `mcts_it50`: avg_time_ms=1412.2051935771417, avg_sims_per_move=50.0, sims_per_sec=35.40561968431024, win_rate_per_sec=0.2950468307025853, score_per_sec=59.36342233736016
- `mcts_it500`: avg_time_ms=13931.015760810287, avg_sims_per_move=500.0, sims_per_sec=35.89113734309047, win_rate_per_sec=0.023927424895393644, score_per_sec=5.646872275312901

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `mcts_it50` | 33.15 | 7.99 | **9.17** | 12 |
| 2 | `mcts_it150` | 29.19 | 7.92 | **5.44** | 12 |
| 3 | `mcts_it500` | 24.55 | 7.92 | **0.80** | 12 |
| 4 | `heuristic` | 13.19 | 7.82 | **-10.26** | 12 |

## Score Margins (winner - last place)
- Mean: `30.25`, Median: `31.0`, Std: `14.83`, Range: `[11.0, 54.0]`

## Score by Seat Position
- `heuristic`: P1: 62.0±4.36 (n=3), P2: 68.0±1.0 (n=3), P3: 74.67±3.18 (n=3), P4: 63.0±2.31 (n=3)
- `mcts_it150`: P1: 89.0±9.5 (n=3), P2: 74.0±0.0 (n=3), P3: 89.67±9.53 (n=3), P4: 81.0±13.58 (n=3)
- `mcts_it50`: P1: 78.67±3.18 (n=3), P2: 98.33±7.31 (n=3), P3: 79.33±2.91 (n=3), P4: 79.0±5.0 (n=3)
- `mcts_it500`: P1: 94.0±14.0 (n=3), P2: 73.33±4.33 (n=3), P3: 77.0±3.79 (n=3), P4: 70.33±7.31 (n=3)
