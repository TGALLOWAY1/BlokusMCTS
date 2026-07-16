# Arena Run Summary: 20260716_040034_07c2800d

## Overview
- Seed: `20260621`
- Seat policy: `round_robin`
- Games: `10/10` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `random`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `vm1_500`: win_rate=0.400, win_points=4.00, outright=2, shared=4
- `vm2_500`: win_rate=0.600, win_points=6.00, outright=4, shared=4

## Win Rates by Seat
- `heuristic`: seat0: 0.000 (2 games), seat1: 0.000 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (2 games)
- `random`: seat0: 0.000 (2 games), seat1: 0.000 (2 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `vm1_500`: seat0: 0.333 (3 games), seat1: 0.500 (3 games), seat2: 0.000 (2 games), seat3: 0.750 (2 games)
- `vm2_500`: seat0: 0.500 (3 games), seat1: 1.000 (2 games), seat2: 0.250 (2 games), seat3: 0.667 (3 games)

## Score Stats
- `heuristic`: mean=72.2, median=72.0, std=4.707440918375927, p25=70.25, p75=75.0, min=62.0, max=81.0
- `random`: mean=49.8, median=46.5, std=8.37615663654877, p25=45.25, p75=57.25, min=36.0, max=65.0
- `vm1_500`: mean=98.6, median=105.5, std=12.571396103854179, p25=89.5, p75=108.0, min=74.0, max=108.0
- `vm2_500`: mean=100.0, median=108.0, std=11.224972160321824, p25=88.0, p75=108.0, min=83.0, max=108.0

## Pairwise Matchups
- `heuristic__vs__random`: heuristic>random=10, random>heuristic=0, tie=0 (total=10)
- `heuristic__vs__vm1_500`: heuristic>vm1_500=1, vm1_500>heuristic=9, tie=0 (total=10)
- `heuristic__vs__vm2_500`: heuristic>vm2_500=0, vm2_500>heuristic=10, tie=0 (total=10)
- `random__vs__vm1_500`: random>vm1_500=0, vm1_500>random=10, tie=0 (total=10)
- `random__vs__vm2_500`: random>vm2_500=0, vm2_500>random=10, tie=0 (total=10)
- `vm1_500__vs__vm2_500`: vm1_500>vm2_500=2, vm2_500>vm1_500=4, tie=4 (total=10)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=27.39107197648991, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=2635.895377222554
- `random`: avg_time_ms=0.04869637295419197, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=1022663.4342324877
- `vm1_500`: avg_time_ms=11208.284318153494, avg_sims_per_move=500.0, sims_per_sec=44.60986051095931, win_rate_per_sec=0.035687888408767444, score_per_sec=8.797064492761175
- `vm2_500`: avg_time_ms=11227.289907022376, avg_sims_per_move=500.0, sims_per_sec=44.534344809896034, win_rate_per_sec=0.05344121377187523, score_per_sec=8.906868961979205

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `vm2_500` | 37.05 | 8.11 | **12.73** | 10 |
| 2 | `vm1_500` | 33.98 | 8.06 | **9.81** | 10 |
| 3 | `heuristic` | 23.41 | 7.87 | **-0.19** | 10 |
| 4 | `random` | 6.04 | 7.90 | **-17.66** | 10 |

## Score Margins (winner - last place)
- Mean: `52.7`, Median: `59.0`, Std: `16.9`, Range: `[18.0, 72.0]`

## Score by Seat Position
- `heuristic`: P1: 68.5±6.5 (n=2), P2: 72.0±1.53 (n=3), P3: 76.0±2.65 (n=3), P4: 70.5±1.5 (n=2)
- `random`: P1: 58.5±6.5 (n=2), P2: 46.5±0.5 (n=2), P3: 54.67±4.33 (n=3), P4: 41.33±2.73 (n=3)
- `vm1_500`: P1: 96.67±11.33 (n=3), P2: 100.33±7.67 (n=3), P3: 92.0±11.0 (n=2), P4: 105.5±2.5 (n=2)
- `vm2_500`: P1: 106.33±1.67 (n=3), P2: 95.5±12.5 (n=2), P3: 95.5±12.5 (n=2), P4: 99.67±8.33 (n=3)
