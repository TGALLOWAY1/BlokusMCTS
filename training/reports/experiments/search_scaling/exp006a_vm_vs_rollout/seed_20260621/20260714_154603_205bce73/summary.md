# Arena Run Summary: 20260714_154603_205bce73

## Overview
- Seed: `20260621`
- Seat policy: `round_robin`
- Games: `10/10` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.100, win_points=1.00, outright=1, shared=0
- `random`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `rollout500`: win_rate=0.200, win_points=2.00, outright=1, shared=2
- `vm500`: win_rate=0.700, win_points=7.00, outright=6, shared=2

## Win Rates by Seat
- `heuristic`: seat0: 0.000 (2 games), seat1: 0.333 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (2 games)
- `random`: seat0: 0.000 (2 games), seat1: 0.000 (2 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `rollout500`: seat0: 0.000 (3 games), seat1: 0.167 (3 games), seat2: 0.250 (2 games), seat3: 0.500 (2 games)
- `vm500`: seat0: 0.833 (3 games), seat1: 0.750 (2 games), seat2: 0.500 (2 games), seat3: 0.667 (3 games)

## Score Stats
- `heuristic`: mean=72.4, median=72.5, std=11.54296322440646, p25=63.25, p75=74.5, min=61.0, max=103.0
- `random`: mean=53.8, median=50.5, std=8.423775875461075, p25=47.25, p75=59.0, min=44.0, max=68.0
- `rollout500`: mean=83.5, median=80.5, std=11.94361754243663, p25=76.25, p75=83.75, min=69.0, max=108.0
- `vm500`: mean=96.0, median=103.0, std=12.790621564255586, p25=81.0, p75=108.0, min=80.0, max=108.0

## Pairwise Matchups
- `heuristic__vs__random`: heuristic>random=9, random>heuristic=1, tie=0 (total=10)
- `heuristic__vs__rollout500`: heuristic>rollout500=3, rollout500>heuristic=7, tie=0 (total=10)
- `heuristic__vs__vm500`: heuristic>vm500=1, vm500>heuristic=9, tie=0 (total=10)
- `random__vs__rollout500`: random>rollout500=0, rollout500>random=10, tie=0 (total=10)
- `random__vs__vm500`: random>vm500=0, vm500>random=10, tie=0 (total=10)
- `rollout500__vs__vm500`: rollout500>vm500=1, vm500>rollout500=7, tie=2 (total=10)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=34.416594638563964, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=2.905575088127676, score_per_sec=2103.6363638044377
- `random`: avg_time_ms=0.045308755465224816, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=1187408.4698992085
- `rollout500`: avg_time_ms=11786.699115914642, avg_sims_per_move=500.0, sims_per_sec=42.42069769346108, win_rate_per_sec=0.01696827907738443, score_per_sec=7.084256514808001
- `vm500`: avg_time_ms=13424.197482590627, avg_sims_per_move=500.0, sims_per_sec=37.24617435406716, win_rate_per_sec=0.052144644095694026, score_per_sec=7.151265475980896

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `vm500` | 39.23 | 8.15 | **14.79** | 10 |
| 2 | `rollout500` | 29.59 | 7.97 | **5.68** | 10 |
| 3 | `heuristic` | 23.51 | 7.91 | **-0.22** | 10 |
| 4 | `random` | 8.12 | 7.89 | **-15.56** | 10 |

## Score Margins (winner - last place)
- Mean: `44.9`, Median: `53.0`, Std: `17.14`, Range: `[13.0, 64.0]`

## Score by Seat Position
- `heuristic`: P1: 67.5±5.5 (n=2), P2: 79.0±12.34 (n=3), P3: 70.67±4.84 (n=3), P4: 70.0±3.0 (n=2)
- `random`: P1: 56.0±12.0 (n=2), P2: 53.0±7.0 (n=2), P3: 57.0±6.08 (n=3), P4: 49.67±1.2 (n=3)
- `rollout500`: P1: 76.67±3.84 (n=3), P2: 86.0±9.07 (n=3), P3: 91.5±16.5 (n=2), P4: 82.0±2.0 (n=2)
- `vm500`: P1: 104.67±1.67 (n=3), P2: 94.0±14.0 (n=2), P3: 94.0±14.0 (n=2), P4: 90.0±9.0 (n=3)
