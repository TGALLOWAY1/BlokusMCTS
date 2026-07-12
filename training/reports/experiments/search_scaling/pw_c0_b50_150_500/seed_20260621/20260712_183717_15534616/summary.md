# Arena Run Summary: 20260712_183717_15534616

## Overview
- Seed: `20260621`
- Seat policy: `round_robin`
- Games: `12/12` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.583, win_points=7.00, outright=7, shared=0
- `mcts_it150`: win_rate=0.083, win_points=1.00, outright=1, shared=0
- `mcts_it50`: win_rate=0.333, win_points=4.00, outright=4, shared=0
- `mcts_it500`: win_rate=0.000, win_points=0.00, outright=0, shared=0

## Win Rates by Seat
- `heuristic`: seat0: 0.667 (3 games), seat1: 0.667 (3 games), seat2: 0.333 (3 games), seat3: 0.667 (3 games)
- `mcts_it150`: seat0: 0.000 (3 games), seat1: 0.000 (3 games), seat2: 0.000 (3 games), seat3: 0.333 (3 games)
- `mcts_it50`: seat0: 0.333 (3 games), seat1: 0.333 (3 games), seat2: 0.000 (3 games), seat3: 0.667 (3 games)
- `mcts_it500`: seat0: 0.000 (3 games), seat1: 0.000 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)

## Score Stats
- `heuristic`: mean=73.08333333333333, median=74.0, std=7.0764672604972105, p25=70.5, p75=79.25, min=56.0, max=81.0
- `mcts_it150`: mean=73.0, median=70.0, std=9.882644720249063, p25=69.0, p75=73.25, min=61.0, max=103.0
- `mcts_it50`: mean=72.41666666666667, median=70.0, std=4.609018936341611, p25=70.0, p75=75.0, min=65.0, max=83.0
- `mcts_it500`: mean=67.83333333333333, median=69.0, std=5.320296566504123, p25=65.5, p75=71.5, min=56.0, max=74.0

## Pairwise Matchups
- `heuristic__vs__mcts_it150`: heuristic>mcts_it150=7, mcts_it150>heuristic=5, tie=0 (total=12)
- `heuristic__vs__mcts_it50`: heuristic>mcts_it50=8, mcts_it50>heuristic=4, tie=0 (total=12)
- `heuristic__vs__mcts_it500`: heuristic>mcts_it500=9, mcts_it500>heuristic=3, tie=0 (total=12)
- `mcts_it150__vs__mcts_it50`: mcts_it150>mcts_it50=2, mcts_it50>mcts_it150=9, tie=1 (total=12)
- `mcts_it150__vs__mcts_it500`: mcts_it150>mcts_it500=7, mcts_it500>mcts_it150=3, tie=2 (total=12)
- `mcts_it50__vs__mcts_it500`: mcts_it50>mcts_it500=8, mcts_it500>mcts_it50=3, tie=1 (total=12)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=26.948553971023003, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=21.64618309244254, score_per_sec=2711.9575102960152
- `mcts_it150`: avg_time_ms=1071.9988870848879, avg_sims_per_move=150.0, sims_per_sec=139.9255184003955, win_rate_per_sec=0.07773639911133085, score_per_sec=68.09708562152582
- `mcts_it50`: avg_time_ms=414.8198914188909, avg_sims_per_move=50.0, sims_per_sec=120.53423915852989, win_rate_per_sec=0.8035615943901993, score_per_sec=174.5737563812708
- `mcts_it500`: avg_time_ms=4505.300300121307, avg_sims_per_move=500.0, sims_per_sec=110.98039346823057, win_rate_per_sec=0.0, score_per_sec=15.056340047189947

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `mcts_it50` | 29.89 | 7.93 | **6.11** | 12 |
| 2 | `heuristic` | 28.91 | 8.00 | **4.92** | 12 |
| 3 | `mcts_it150` | 22.77 | 7.86 | **-0.80** | 12 |
| 4 | `mcts_it500` | 18.47 | 7.84 | **-5.06** | 12 |

## Score Margins (winner - last place)
- Mean: `15.33`, Median: `15.0`, Std: `8.21`, Range: `[1.0, 35.0]`

## Score by Seat Position
- `heuristic`: P1: 72.67±3.84 (n=3), P2: 74.67±3.18 (n=3), P3: 68.33±6.94 (n=3), P4: 76.67±2.85 (n=3)
- `mcts_it150`: P1: 70.67±1.2 (n=3), P2: 71.0±1.53 (n=3), P3: 69.67±5.21 (n=3), P4: 80.67±11.17 (n=3)
- `mcts_it50`: P1: 72.67±3.93 (n=3), P2: 74.33±4.33 (n=3), P3: 69.67±0.33 (n=3), P4: 73.0±1.53 (n=3)
- `mcts_it500`: P1: 68.0±1.15 (n=3), P2: 67.67±4.1 (n=3), P3: 63.0±3.79 (n=3), P4: 72.67±0.88 (n=3)
