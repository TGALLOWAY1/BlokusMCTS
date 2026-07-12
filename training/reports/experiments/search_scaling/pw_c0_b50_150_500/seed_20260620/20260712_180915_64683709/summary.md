# Arena Run Summary: 20260712_180915_64683709

## Overview
- Seed: `20260620`
- Seat policy: `round_robin`
- Games: `12/12` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.250, win_points=3.00, outright=3, shared=0
- `mcts_it150`: win_rate=0.167, win_points=2.00, outright=2, shared=0
- `mcts_it50`: win_rate=0.417, win_points=5.00, outright=5, shared=0
- `mcts_it500`: win_rate=0.167, win_points=2.00, outright=2, shared=0

## Win Rates by Seat
- `heuristic`: seat0: 0.333 (3 games), seat1: 0.333 (3 games), seat2: 0.000 (3 games), seat3: 0.333 (3 games)
- `mcts_it150`: seat0: 0.667 (3 games), seat1: 0.000 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `mcts_it50`: seat0: 0.667 (3 games), seat1: 0.667 (3 games), seat2: 0.333 (3 games), seat3: 0.000 (3 games)
- `mcts_it500`: seat0: 0.333 (3 games), seat1: 0.333 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)

## Score Stats
- `heuristic`: mean=71.66666666666667, median=70.0, std=5.312459150169743, p25=68.0, p75=73.25, min=64.0, max=81.0
- `mcts_it150`: mean=72.16666666666667, median=74.0, std=5.030462757595523, p25=68.25, p75=75.75, min=64.0, max=79.0
- `mcts_it50`: mean=71.16666666666667, median=70.0, std=6.853628398317363, p25=65.0, p75=77.25, min=61.0, max=83.0
- `mcts_it500`: mean=72.91666666666667, median=69.5, std=10.77387529577398, p25=68.75, p75=75.0, min=55.0, max=103.0

## Pairwise Matchups
- `heuristic__vs__mcts_it150`: heuristic>mcts_it150=5, mcts_it150>heuristic=5, tie=2 (total=12)
- `heuristic__vs__mcts_it50`: heuristic>mcts_it50=6, mcts_it50>heuristic=6, tie=0 (total=12)
- `heuristic__vs__mcts_it500`: heuristic>mcts_it500=6, mcts_it500>heuristic=5, tie=1 (total=12)
- `mcts_it150__vs__mcts_it50`: mcts_it150>mcts_it50=6, mcts_it50>mcts_it150=6, tie=0 (total=12)
- `mcts_it150__vs__mcts_it500`: mcts_it150>mcts_it500=7, mcts_it500>mcts_it150=5, tie=0 (total=12)
- `mcts_it50__vs__mcts_it500`: mcts_it50>mcts_it500=7, mcts_it500>mcts_it50=5, tie=0 (total=12)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=27.4201893842359, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=9.117369559224384, score_per_sec=2613.64594031099
- `mcts_it150`: avg_time_ms=1084.3030197360504, avg_sims_per_move=150.0, sims_per_sec=138.33771304677745, win_rate_per_sec=0.15370857005197494, score_per_sec=66.55581083250516
- `mcts_it50`: avg_time_ms=434.2584621503157, avg_sims_per_move=50.0, sims_per_sec=115.13880409472095, win_rate_per_sec=0.9594900341226748, score_per_sec=163.88089782815285
- `mcts_it500`: avg_time_ms=4337.16217262485, avg_sims_per_move=500.0, sims_per_sec=115.28275404500266, win_rate_per_sec=0.03842758468166755, score_per_sec=16.812068298229555

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `mcts_it150` | 27.93 | 7.91 | **4.18** | 12 |
| 2 | `heuristic` | 26.10 | 7.92 | **2.33** | 12 |
| 3 | `mcts_it50` | 23.14 | 7.92 | **-0.62** | 12 |
| 4 | `mcts_it500` | 22.69 | 7.86 | **-0.90** | 12 |

## Score Margins (winner - last place)
- Mean: `14.58`, Median: `11.0`, Std: `8.93`, Range: `[5.0, 39.0]`

## Score by Seat Position
- `heuristic`: P1: 72.0±4.0 (n=3), P2: 73.0±4.04 (n=3), P3: 68.67±2.33 (n=3), P4: 73.0±3.51 (n=3)
- `mcts_it150`: P1: 70.67±3.33 (n=3), P2: 73.33±3.84 (n=3), P3: 76.67±1.33 (n=3), P4: 68.0±1.53 (n=3)
- `mcts_it50`: P1: 77.0±0.58 (n=3), P2: 77.33±3.84 (n=3), P3: 65.33±2.6 (n=3), P4: 65.0±0.0 (n=3)
- `mcts_it500`: P1: 75.0±3.51 (n=3), P2: 80.33±11.35 (n=3), P3: 70.67±1.67 (n=3), P4: 65.67±5.46 (n=3)
