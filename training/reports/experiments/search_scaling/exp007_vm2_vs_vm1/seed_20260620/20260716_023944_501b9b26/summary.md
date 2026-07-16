# Arena Run Summary: 20260716_023944_501b9b26

## Overview
- Seed: `20260620`
- Seat policy: `round_robin`
- Games: `10/10` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `random`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `vm1_500`: win_rate=0.450, win_points=4.50, outright=4, shared=1
- `vm2_500`: win_rate=0.550, win_points=5.50, outright=5, shared=1

## Win Rates by Seat
- `heuristic`: seat0: 0.000 (2 games), seat1: 0.000 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (2 games)
- `random`: seat0: 0.000 (2 games), seat1: 0.000 (2 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `vm1_500`: seat0: 0.500 (3 games), seat1: 0.333 (3 games), seat2: 0.500 (2 games), seat3: 0.500 (2 games)
- `vm2_500`: seat0: 0.667 (3 games), seat1: 0.500 (2 games), seat2: 0.500 (2 games), seat3: 0.500 (3 games)

## Score Stats
- `heuristic`: mean=70.4, median=73.0, std=9.404254356406996, p25=61.0, p75=79.0, min=56.0, max=81.0
- `random`: mean=52.6, median=53.5, std=6.873136110975833, p25=46.0, p75=56.0, min=44.0, max=65.0
- `vm1_500`: mean=93.3, median=85.0, std=11.072939989000211, p25=84.0, p75=106.75, min=84.0, max=108.0
- `vm2_500`: mean=96.4, median=108.0, std=14.381933110677437, p25=80.25, p75=108.0, min=74.0, max=108.0

## Pairwise Matchups
- `heuristic__vs__random`: heuristic>random=9, random>heuristic=1, tie=0 (total=10)
- `heuristic__vs__vm1_500`: heuristic>vm1_500=0, vm1_500>heuristic=10, tie=0 (total=10)
- `heuristic__vs__vm2_500`: heuristic>vm2_500=1, vm2_500>heuristic=9, tie=0 (total=10)
- `random__vs__vm1_500`: random>vm1_500=0, vm1_500>random=10, tie=0 (total=10)
- `random__vs__vm2_500`: random>vm2_500=0, vm2_500>random=10, tie=0 (total=10)
- `vm1_500__vs__vm2_500`: vm1_500>vm2_500=4, vm2_500>vm1_500=5, tie=1 (total=10)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=29.647155375787616, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=2374.5954412035976
- `random`: avg_time_ms=0.04346516539941915, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=1210164.4964798163
- `vm1_500`: avg_time_ms=11071.929773863623, avg_sims_per_move=500.0, sims_per_sec=45.15924596815083, win_rate_per_sec=0.04064332137133575, score_per_sec=8.426715297656946
- `vm2_500`: avg_time_ms=11423.658111307881, avg_sims_per_move=500.0, sims_per_sec=43.76881688231438, win_rate_per_sec=0.04814569857054582, score_per_sec=8.438627894910212

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `vm1_500` | 36.10 | 8.09 | **11.83** | 10 |
| 2 | `vm2_500` | 35.02 | 8.07 | **10.80** | 10 |
| 3 | `heuristic` | 22.07 | 7.87 | **-1.54** | 10 |
| 4 | `random` | 7.30 | 7.89 | **-16.36** | 10 |

## Score Margins (winner - last place)
- Mean: `53.4`, Median: `52.5`, Std: `9.47`, Range: `[32.0, 64.0]`

## Score by Seat Position
- `heuristic`: P1: 71.0±1.0 (n=2), P2: 70.33±6.89 (n=3), P3: 72.33±8.17 (n=3), P4: 67.0±9.0 (n=2)
- `random`: P1: 51.0±5.0 (n=2), P2: 52.5±8.5 (n=2), P3: 51.0±3.21 (n=3), P4: 55.33±5.49 (n=3)
- `vm1_500`: P1: 92.33±7.84 (n=3), P2: 92.0±8.0 (n=3), P3: 93.5±9.5 (n=2), P4: 96.5±11.5 (n=2)
- `vm2_500`: P1: 100.0±8.0 (n=3), P2: 91.0±17.0 (n=2), P3: 93.5±14.5 (n=2), P4: 98.33±9.67 (n=3)
