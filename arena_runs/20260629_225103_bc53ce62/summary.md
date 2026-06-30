# Arena Run Summary: 20260629_225103_bc53ce62

## Overview
- Seed: `20260604`
- Seat policy: `round_robin`
- Games: `60/60` completed
- Error games: `0`

## Win Rates by Agent
- `champ_v3`: win_rate=0.542, win_points=32.50, outright=32, shared=1
- `pool_heuristic`: win_rate=0.047, win_points=2.83, outright=2, shared=2
- `pool_l45_100ms`: win_rate=0.022, win_points=1.33, outright=1, shared=1
- `pool_peer_500ms`: win_rate=0.389, win_points=23.33, outright=22, shared=3

## Win Rates by Seat
- `champ_v3`: seat0: 0.533 (15 games), seat1: 0.433 (15 games), seat2: 0.667 (15 games), seat3: 0.533 (15 games)
- `pool_heuristic`: seat0: 0.067 (15 games), seat1: 0.067 (15 games), seat2: 0.056 (15 games), seat3: 0.000 (15 games)
- `pool_l45_100ms`: seat0: 0.000 (15 games), seat1: 0.000 (15 games), seat2: 0.067 (15 games), seat3: 0.022 (15 games)
- `pool_peer_500ms`: seat0: 0.489 (15 games), seat1: 0.333 (15 games), seat2: 0.400 (15 games), seat3: 0.333 (15 games)

## Score Stats
- `champ_v3`: mean=98.35, median=98.5, std=10.796334254427903, p25=91.75, p75=102.5, min=76.0, max=124.0
- `pool_heuristic`: mean=77.36666666666666, median=78.5, std=8.780597296818076, p25=71.0, p75=84.0, min=60.0, max=101.0
- `pool_l45_100ms`: mean=74.9, median=75.0, std=7.986864215698174, p25=70.0, p75=81.0, min=58.0, max=95.0
- `pool_peer_500ms`: mean=94.81666666666666, median=94.0, std=9.363923085734717, p25=89.75, p75=98.0, min=76.0, max=122.0

## Pairwise Matchups
- `champ_v3__vs__pool_heuristic`: champ_v3>pool_heuristic=53, pool_heuristic>champ_v3=7, tie=0 (total=60)
- `champ_v3__vs__pool_l45_100ms`: champ_v3>pool_l45_100ms=57, pool_l45_100ms>champ_v3=3, tie=0 (total=60)
- `champ_v3__vs__pool_peer_500ms`: champ_v3>pool_peer_500ms=34, pool_peer_500ms>champ_v3=25, tie=1 (total=60)
- `pool_heuristic__vs__pool_l45_100ms`: pool_heuristic>pool_l45_100ms=35, pool_l45_100ms>pool_heuristic=18, tie=7 (total=60)
- `pool_heuristic__vs__pool_peer_500ms`: pool_heuristic>pool_peer_500ms=4, pool_peer_500ms>pool_heuristic=54, tie=2 (total=60)
- `pool_l45_100ms__vs__pool_peer_500ms`: pool_l45_100ms>pool_peer_500ms=3, pool_peer_500ms>pool_l45_100ms=54, tie=3 (total=60)

## Time and Simulation Efficiency
- `champ_v3`: avg_time_ms=2755.3837288880786, avg_sims_per_move=250.0, sims_per_sec=90.73146414379323, win_rate_per_sec=0.19658483897821866, score_per_sec=35.69375799416826
- `pool_heuristic`: avg_time_ms=22.36708956670797, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=2.11123678301488, score_per_sec=3458.950992972378
- `pool_l45_100ms`: avg_time_ms=1040.7016319445413, avg_sims_per_move=50.0, sims_per_sec=48.04451003557615, win_rate_per_sec=0.02135311557136718, score_per_sec=71.97067603329309
- `pool_peer_500ms`: avg_time_ms=2803.662178988125, avg_sims_per_move=250.0, sims_per_sec=89.16908815677213, win_rate_per_sec=0.13870747046609, score_per_sec=33.81886283492511

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `pool_peer_500ms` | 49.30 | 7.02 | **28.25** | 60 |
| 2 | `champ_v3` | 49.46 | 7.10 | **28.15** | 60 |
| 3 | `pool_heuristic` | 8.30 | 6.79 | **-12.08** | 60 |
| 4 | `pool_l45_100ms` | -4.99 | 6.93 | **-25.77** | 60 |

## Score Margins (winner - last place)
- Mean: `30.58`, Median: `29.5`, Std: `12.53`, Range: `[6.0, 61.0]`

## Score by Seat Position
- `champ_v3`: P1: 98.27±2.46 (n=15), P2: 95.47±2.63 (n=15), P3: 103.2±3.18 (n=15), P4: 96.47±2.77 (n=15)
- `pool_heuristic`: P1: 79.73±1.69 (n=15), P2: 78.13±2.36 (n=15), P3: 79.6±1.99 (n=15), P4: 72.0±2.61 (n=15)
- `pool_l45_100ms`: P1: 78.73±2.13 (n=15), P2: 72.2±1.84 (n=15), P3: 74.93±2.42 (n=15), P4: 73.73±1.67 (n=15)
- `pool_peer_500ms`: P1: 93.93±2.39 (n=15), P2: 97.4±2.66 (n=15), P3: 96.4±1.97 (n=15), P4: 91.53±2.63 (n=15)
