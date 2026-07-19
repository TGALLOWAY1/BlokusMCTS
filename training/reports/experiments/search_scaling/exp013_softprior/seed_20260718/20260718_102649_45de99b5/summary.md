# Arena Run Summary: 20260718_102649_45de99b5

## Overview
- Seed: `20260718`
- Seat policy: `round_robin`
- Games: `10/10` completed
- Error games: `0`

## Win Rates by Agent
- `base_500_a`: win_rate=0.600, win_points=6.00, outright=6, shared=0
- `base_500_b`: win_rate=0.200, win_points=2.00, outright=2, shared=0
- `softprior_500_a`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `softprior_500_b`: win_rate=0.200, win_points=2.00, outright=2, shared=0

## Win Rates by Seat
- `base_500_a`: seat0: 0.000 (2 games), seat1: 1.000 (3 games), seat2: 1.000 (3 games), seat3: 0.000 (2 games)
- `base_500_b`: seat0: 0.000 (2 games), seat1: 1.000 (2 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `softprior_500_a`: seat0: 0.000 (3 games), seat1: 0.000 (2 games), seat2: 0.000 (2 games), seat3: 0.000 (3 games)
- `softprior_500_b`: seat0: 0.000 (3 games), seat1: 0.000 (3 games), seat2: 1.000 (2 games), seat3: 0.000 (2 games)

## Score Stats
- `base_500_a`: mean=93.0, median=94.0, std=10.14889156509222, p25=85.0, p75=103.0, min=80.0, max=103.0
- `base_500_b`: mean=79.6, median=73.0, std=14.472042012100435, p25=70.0, p75=77.0, min=69.0, max=108.0
- `softprior_500_a`: mean=66.7, median=66.5, std=4.605431575867782, p25=63.0, p75=71.5, min=61.0, max=72.0
- `softprior_500_b`: mean=76.8, median=78.0, std=7.332121111929345, p25=69.0, p75=84.0, min=68.0, max=84.0

## Pairwise Matchups
- `base_500_a__vs__base_500_b`: base_500_a>base_500_b=8, base_500_b>base_500_a=2, tie=0 (total=10)
- `base_500_a__vs__softprior_500_a`: base_500_a>softprior_500_a=10, softprior_500_a>base_500_a=0, tie=0 (total=10)
- `base_500_a__vs__softprior_500_b`: base_500_a>softprior_500_b=8, softprior_500_b>base_500_a=2, tie=0 (total=10)
- `base_500_b__vs__softprior_500_a`: base_500_b>softprior_500_a=7, softprior_500_a>base_500_b=3, tie=0 (total=10)
- `base_500_b__vs__softprior_500_b`: base_500_b>softprior_500_b=5, softprior_500_b>base_500_b=5, tie=0 (total=10)
- `softprior_500_a__vs__softprior_500_b`: softprior_500_a>softprior_500_b=0, softprior_500_b>softprior_500_a=10, tie=0 (total=10)

## Time and Simulation Efficiency
- `base_500_a`: avg_time_ms=11754.418764208338, avg_sims_per_move=500.0, sims_per_sec=42.53719473756345, win_rate_per_sec=0.051044633685076134, score_per_sec=7.911918221186801
- `base_500_b`: avg_time_ms=13052.828531480778, avg_sims_per_move=500.0, sims_per_sec=38.305873611539546, win_rate_per_sec=0.015322349444615819, score_per_sec=6.098295078957095
- `softprior_500_a`: avg_time_ms=21391.681083556145, avg_sims_per_move=500.0, sims_per_sec=23.373572093141927, win_rate_per_sec=0.0, score_per_sec=3.1180345172251336
- `softprior_500_b`: avg_time_ms=20339.03298697658, avg_sims_per_move=500.0, sims_per_sec=24.58327297665323, win_rate_per_sec=0.009833309190661292, score_per_sec=3.775990729213936

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `base_500_a` | 37.25 | 8.11 | **12.92** | 10 |
| 2 | `softprior_500_b` | 28.52 | 7.95 | **4.66** | 10 |
| 3 | `base_500_b` | 23.09 | 7.97 | **-0.81** | 10 |
| 4 | `softprior_500_a` | 11.46 | 7.88 | **-12.18** | 10 |

## Score Margins (winner - last place)
- Mean: `29.0`, Median: `28.0`, Std: `14.03`, Range: `[14.0, 47.0]`

## Score by Seat Position
- `base_500_a`: P1: 103.0±0.0 (n=2), P2: 103.0±0.0 (n=3), P3: 85.0±0.0 (n=3), P4: 80.0±0.0 (n=2)
- `base_500_b`: P1: 77.0±0.0 (n=2), P2: 108.0±0.0 (n=2), P3: 73.0±0.0 (n=3), P4: 69.0±0.0 (n=3)
- `softprior_500_a`: P1: 72.0±0.0 (n=3), P2: 70.0±0.0 (n=2), P3: 61.0±0.0 (n=2), P4: 63.0±0.0 (n=3)
- `softprior_500_b`: P1: 68.0±0.0 (n=3), P2: 84.0±0.0 (n=3), P3: 84.0±0.0 (n=2), P4: 72.0±0.0 (n=2)
