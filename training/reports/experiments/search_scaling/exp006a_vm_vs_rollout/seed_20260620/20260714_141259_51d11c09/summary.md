# Arena Run Summary: 20260714_141259_51d11c09

## Overview
- Seed: `20260620`
- Seat policy: `round_robin`
- Games: `10/10` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.100, win_points=1.00, outright=1, shared=0
- `random`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `rollout500`: win_rate=0.650, win_points=6.50, outright=5, shared=3
- `vm500`: win_rate=0.250, win_points=2.50, outright=1, shared=3

## Win Rates by Seat
- `heuristic`: seat0: 0.000 (2 games), seat1: 0.000 (3 games), seat2: 0.000 (3 games), seat3: 0.500 (2 games)
- `random`: seat0: 0.000 (2 games), seat1: 0.000 (2 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `rollout500`: seat0: 0.667 (3 games), seat1: 0.833 (3 games), seat2: 0.250 (2 games), seat3: 0.750 (2 games)
- `vm500`: seat0: 0.167 (3 games), seat1: 0.250 (2 games), seat2: 0.250 (2 games), seat3: 0.333 (3 games)

## Score Stats
- `heuristic`: mean=70.6, median=71.5, std=7.337574531137657, p25=67.5, p75=74.5, min=54.0, max=84.0
- `random`: mean=50.7, median=51.5, std=5.9, p25=45.0, p75=55.0, min=42.0, max=59.0
- `rollout500`: mean=102.2, median=108.0, std=10.514751542475931, p25=104.25, p75=108.0, min=79.0, max=108.0
- `vm500`: mean=94.5, median=94.0, std=12.792575972023775, p25=84.0, p75=108.0, min=76.0, max=108.0

## Pairwise Matchups
- `heuristic__vs__random`: heuristic>random=10, random>heuristic=0, tie=0 (total=10)
- `heuristic__vs__rollout500`: heuristic>rollout500=1, rollout500>heuristic=9, tie=0 (total=10)
- `heuristic__vs__vm500`: heuristic>vm500=1, vm500>heuristic=9, tie=0 (total=10)
- `random__vs__rollout500`: random>rollout500=0, rollout500>random=10, tie=0 (total=10)
- `random__vs__vm500`: random>vm500=0, vm500>random=10, tie=0 (total=10)
- `rollout500__vs__vm500`: rollout500>vm500=6, vm500>rollout500=1, tie=3 (total=10)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=35.756889173687334, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=2.796663868443782, score_per_sec=1974.4446911213097
- `random`: avg_time_ms=0.04737082031613937, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=1070279.1224986739
- `rollout500`: avg_time_ms=11606.612208960712, avg_sims_per_move=500.0, sims_per_sec=43.07889253110243, win_rate_per_sec=0.05600256029043317, score_per_sec=8.805325633357338
- `vm500`: avg_time_ms=14076.677911352403, avg_sims_per_move=500.0, sims_per_sec=35.51974429966644, win_rate_per_sec=0.017759872149833218, score_per_sec=6.713231672636957

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `rollout500` | 36.25 | 8.09 | **11.98** | 10 |
| 2 | `vm500` | 34.62 | 8.06 | **10.45** | 10 |
| 3 | `heuristic` | 23.49 | 7.88 | **-0.14** | 10 |
| 4 | `random` | 6.09 | 7.90 | **-17.61** | 10 |

## Score Margins (winner - last place)
- Mean: `54.4`, Median: `56.5`, Std: `10.89`, Range: `[25.0, 66.0]`

## Score by Seat Position
- `heuristic`: P1: 71.5±0.5 (n=2), P2: 63.33±4.7 (n=3), P3: 71.33±2.73 (n=3), P4: 79.5±4.5 (n=2)
- `random`: P1: 58.5±0.5 (n=2), P2: 49.5±6.5 (n=2), P3: 48.0±3.0 (n=3), P4: 49.0±3.0 (n=3)
- `rollout500`: P1: 100.0±8.0 (n=3), P2: 106.33±1.67 (n=3), P3: 93.5±14.5 (n=2), P4: 108.0±0.0 (n=2)
- `vm500`: P1: 91.0±8.54 (n=3), P2: 92.0±16.0 (n=2), P3: 96.5±11.5 (n=2), P4: 98.33±7.31 (n=3)
