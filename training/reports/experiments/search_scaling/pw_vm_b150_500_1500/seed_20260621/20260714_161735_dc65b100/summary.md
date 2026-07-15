# Arena Run Summary: 20260714_161735_dc65b100

## Overview
- Seed: `20260621`
- Seat policy: `round_robin`
- Games: `6/6` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `mcts_it150`: win_rate=0.167, win_points=1.00, outright=1, shared=0
- `mcts_it1500`: win_rate=0.250, win_points=1.50, outright=1, shared=1
- `mcts_it500`: win_rate=0.583, win_points=3.50, outright=3, shared=1

## Win Rates by Seat
- `heuristic`: seat0: 0.000 (1 games), seat1: 0.000 (1 games), seat2: 0.000 (2 games), seat3: 0.000 (2 games)
- `mcts_it150`: seat0: 0.000 (2 games), seat1: 0.000 (1 games), seat2: 1.000 (1 games), seat3: 0.000 (2 games)
- `mcts_it1500`: seat0: 0.000 (1 games), seat1: 0.250 (2 games), seat2: 0.500 (2 games), seat3: 0.000 (1 games)
- `mcts_it500`: seat0: 0.750 (2 games), seat1: 0.500 (2 games), seat2: 1.000 (1 games), seat3: 0.000 (1 games)

## Score Stats
- `heuristic`: mean=63.0, median=61.0, std=5.259911279353167, p25=59.5, p75=66.25, min=57.0, max=72.0
- `mcts_it150`: mean=81.16666666666667, median=82.0, std=3.9334745737353156, p25=81.0, p75=83.75, min=73.0, max=85.0
- `mcts_it1500`: mean=88.33333333333333, median=82.5, std=14.383632673594278, p25=78.0, p75=102.0, min=72.0, max=108.0
- `mcts_it500`: mean=92.83333333333333, median=94.0, std=14.55354099714415, p25=84.25, p75=106.75, min=69.0, max=108.0

## Pairwise Matchups
- `heuristic__vs__mcts_it150`: heuristic>mcts_it150=0, mcts_it150>heuristic=6, tie=0 (total=6)
- `heuristic__vs__mcts_it1500`: heuristic>mcts_it1500=0, mcts_it1500>heuristic=6, tie=0 (total=6)
- `heuristic__vs__mcts_it500`: heuristic>mcts_it500=0, mcts_it500>heuristic=6, tie=0 (total=6)
- `mcts_it1500__vs__mcts_it500`: mcts_it1500>mcts_it500=2, mcts_it500>mcts_it1500=3, tie=1 (total=6)
- `mcts_it150__vs__mcts_it1500`: mcts_it150>mcts_it1500=3, mcts_it1500>mcts_it150=3, tie=0 (total=6)
- `mcts_it150__vs__mcts_it500`: mcts_it150>mcts_it500=1, mcts_it500>mcts_it150=5, tie=0 (total=6)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=41.686647375027775, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=1511.2752875814117
- `mcts_it150`: avg_time_ms=4530.263227328919, avg_sims_per_move=150.0, sims_per_sec=33.11065880126379, win_rate_per_sec=0.036789620890293105, score_per_sec=17.916545373572745
- `mcts_it1500`: avg_time_ms=43071.10240952722, avg_sims_per_move=1500.0, sims_per_sec=34.82613437050554, win_rate_per_sec=0.00580435572841759, score_per_sec=2.050872357374215
- `mcts_it500`: avg_time_ms=14329.933951882755, avg_sims_per_move=500.0, sims_per_sec=34.89199613054092, win_rate_per_sec=0.040707328818964404, score_per_sec=6.478280614903763

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `mcts_it500` | 31.92 | 8.19 | **7.35** | 6 |
| 2 | `mcts_it1500` | 28.67 | 8.12 | **4.32** | 6 |
| 3 | `mcts_it150` | 27.05 | 8.09 | **2.77** | 6 |
| 4 | `heuristic` | 12.49 | 8.05 | **-11.65** | 6 |

## Score Margins (winner - last place)
- Mean: `36.5`, Median: `41.0`, Std: `14.07`, Range: `[13.0, 51.0]`

## Score by Seat Position
- `heuristic`: P1: 68.0±0.0 (n=1), P2: 61.0±0.0 (n=1), P3: 65.5±6.5 (n=2), P4: 59.0±2.0 (n=2)
- `mcts_it150`: P1: 82.5±1.5 (n=2), P2: 83.0±0.0 (n=1), P3: 85.0±0.0 (n=1), P4: 77.0±4.0 (n=2)
- `mcts_it1500`: P1: 81.0±0.0 (n=1), P2: 96.0±12.0 (n=2), P3: 92.5±15.5 (n=2), P4: 72.0±0.0 (n=1)
- `mcts_it500`: P1: 96.5±11.5 (n=2), P2: 96.0±12.0 (n=2), P3: 103.0±0.0 (n=1), P4: 69.0±0.0 (n=1)
