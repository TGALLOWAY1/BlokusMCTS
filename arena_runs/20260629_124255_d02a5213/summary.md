# Arena Run Summary: 20260629_124255_d02a5213

## Overview
- Seed: `20260606`
- Seat policy: `round_robin`
- Games: `60/60` completed
- Error games: `0`

## Win Rates by Agent
- `challenge_champ_500ms`: win_rate=0.467, win_points=28.00, outright=27, shared=2
- `champ_v3`: win_rate=0.483, win_points=29.00, outright=28, shared=2
- `pool_heuristic`: win_rate=0.000, win_points=0.00, outright=0, shared=0
- `pool_l9_partial_200ms`: win_rate=0.050, win_points=3.00, outright=3, shared=0

## Win Rates by Seat
- `challenge_champ_500ms`: seat0: 0.567 (15 games), seat1: 0.467 (15 games), seat2: 0.633 (15 games), seat3: 0.200 (15 games)
- `champ_v3`: seat0: 0.667 (15 games), seat1: 0.433 (15 games), seat2: 0.467 (15 games), seat3: 0.367 (15 games)
- `pool_heuristic`: seat0: 0.000 (15 games), seat1: 0.000 (15 games), seat2: 0.000 (15 games), seat3: 0.000 (15 games)
- `pool_l9_partial_200ms`: seat0: 0.067 (15 games), seat1: 0.000 (15 games), seat2: 0.133 (15 games), seat3: 0.000 (15 games)

## Score Stats
- `challenge_champ_500ms`: mean=98.96666666666667, median=97.0, std=11.969359028601136, p25=92.0, p75=101.0, min=75.0, max=124.0
- `champ_v3`: mean=96.86666666666666, median=95.0, std=10.70897857978165, p25=92.0, p75=102.25, min=62.0, max=124.0
- `pool_heuristic`: mean=75.5, median=75.0, std=8.028075734570521, p25=70.0, p75=81.0, min=57.0, max=92.0
- `pool_l9_partial_200ms`: mean=76.45, median=76.0, std=9.555844633870239, p25=70.75, p75=82.0, min=57.0, max=103.0

## Pairwise Matchups
- `challenge_champ_500ms__vs__champ_v3`: challenge_champ_500ms>champ_v3=29, champ_v3>challenge_champ_500ms=29, tie=2 (total=60)
- `challenge_champ_500ms__vs__pool_heuristic`: challenge_champ_500ms>pool_heuristic=54, pool_heuristic>challenge_champ_500ms=5, tie=1 (total=60)
- `challenge_champ_500ms__vs__pool_l9_partial_200ms`: challenge_champ_500ms>pool_l9_partial_200ms=53, pool_l9_partial_200ms>challenge_champ_500ms=6, tie=1 (total=60)
- `champ_v3__vs__pool_heuristic`: champ_v3>pool_heuristic=57, pool_heuristic>champ_v3=3, tie=0 (total=60)
- `champ_v3__vs__pool_l9_partial_200ms`: champ_v3>pool_l9_partial_200ms=54, pool_l9_partial_200ms>champ_v3=6, tie=0 (total=60)
- `pool_heuristic__vs__pool_l9_partial_200ms`: pool_heuristic>pool_l9_partial_200ms=30, pool_l9_partial_200ms>pool_heuristic=29, tie=1 (total=60)

## Time and Simulation Efficiency
- `challenge_champ_500ms`: avg_time_ms=2759.394819581446, avg_sims_per_move=250.0, sims_per_sec=90.59957575694834, win_rate_per_sec=0.16911920807963687, score_per_sec=35.86535205631728
- `champ_v3`: avg_time_ms=2807.524860962063, avg_sims_per_move=250.0, sims_per_sec=89.04640648999694, win_rate_per_sec=0.17215638588066076, score_per_sec=34.50251430132415
- `pool_heuristic`: avg_time_ms=22.276686271053205, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=0.0, score_per_sec=3389.193486021585
- `pool_l9_partial_200ms`: avg_time_ms=1870.6991391167394, avg_sims_per_move=100.0, sims_per_sec=53.45595018941182, win_rate_per_sec=0.026727975094705914, score_per_sec=40.86707391980534

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `champ_v3` | 56.26 | 7.07 | **35.05** | 60 |
| 2 | `challenge_champ_500ms` | 42.21 | 7.04 | **21.08** | 60 |
| 3 | `pool_l9_partial_200ms` | 2.81 | 6.78 | **-17.54** | 60 |
| 4 | `pool_heuristic` | 0.72 | 6.80 | **-19.67** | 60 |

## Score Margins (winner - last place)
- Mean: `33.9`, Median: `30.5`, Std: `13.87`, Range: `[10.0, 67.0]`

## Score by Seat Position
- `challenge_champ_500ms`: P1: 102.2±2.64 (n=15), P2: 99.27±2.96 (n=15), P3: 104.13±3.1 (n=15), P4: 90.27±2.74 (n=15)
- `champ_v3`: P1: 97.93±2.36 (n=15), P2: 98.6±3.81 (n=15), P3: 97.2±2.19 (n=15), P4: 93.73±2.62 (n=15)
- `pool_heuristic`: P1: 74.0±1.94 (n=15), P2: 81.0±2.23 (n=15), P3: 73.73±2.03 (n=15), P4: 73.27±1.63 (n=15)
- `pool_l9_partial_200ms`: P1: 78.93±2.19 (n=15), P2: 73.13±2.02 (n=15), P3: 78.87±3.05 (n=15), P4: 74.87±2.46 (n=15)
