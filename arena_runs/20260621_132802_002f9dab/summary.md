# Arena Run Summary: 20260621_132802_002f9dab

## Overview
- Seed: `20260503`
- Seat policy: `round_robin`
- Games: `40/40` completed
- Error games: `0`

## Win Rates by Agent
- `champion`: win_rate=0.375, win_points=15.00, outright=15, shared=0
- `pool_l45_100ms`: win_rate=0.075, win_points=3.00, outright=3, shared=0
- `pool_l9_partial_200ms`: win_rate=0.025, win_points=1.00, outright=1, shared=0
- `pool_peer_500ms`: win_rate=0.525, win_points=21.00, outright=21, shared=0

## Win Rates by Seat
- `champion`: seat0: 0.400 (10 games), seat1: 0.400 (10 games), seat2: 0.400 (10 games), seat3: 0.300 (10 games)
- `pool_l45_100ms`: seat0: 0.000 (10 games), seat1: 0.300 (10 games), seat2: 0.000 (10 games), seat3: 0.000 (10 games)
- `pool_l9_partial_200ms`: seat0: 0.000 (10 games), seat1: 0.000 (10 games), seat2: 0.100 (10 games), seat3: 0.000 (10 games)
- `pool_peer_500ms`: seat0: 0.600 (10 games), seat1: 0.600 (10 games), seat2: 0.700 (10 games), seat3: 0.200 (10 games)

## Score Stats
- `champion`: mean=91.375, median=90.5, std=10.0962554939938, p25=85.75, p75=97.25, min=70.0, max=120.0
- `pool_l45_100ms`: mean=76.8, median=79.0, std=12.480384609458156, p25=68.75, p75=86.0, min=53.0, max=102.0
- `pool_l9_partial_200ms`: mean=77.475, median=76.5, std=8.740673601044715, p25=70.75, p75=83.25, min=65.0, max=97.0
- `pool_peer_500ms`: mean=96.85, median=93.5, std=10.877844455589535, p25=89.75, p75=101.5, min=73.0, max=122.0

## Pairwise Matchups
- `champion__vs__pool_l45_100ms`: champion>pool_l45_100ms=31, pool_l45_100ms>champion=8, tie=1 (total=40)
- `champion__vs__pool_l9_partial_200ms`: champion>pool_l9_partial_200ms=33, pool_l9_partial_200ms>champion=7, tie=0 (total=40)
- `champion__vs__pool_peer_500ms`: champion>pool_peer_500ms=16, pool_peer_500ms>champion=24, tie=0 (total=40)
- `pool_l45_100ms__vs__pool_l9_partial_200ms`: pool_l45_100ms>pool_l9_partial_200ms=20, pool_l9_partial_200ms>pool_l45_100ms=19, tie=1 (total=40)
- `pool_l45_100ms__vs__pool_peer_500ms`: pool_l45_100ms>pool_peer_500ms=5, pool_peer_500ms>pool_l45_100ms=35, tie=0 (total=40)
- `pool_l9_partial_200ms__vs__pool_peer_500ms`: pool_l9_partial_200ms>pool_peer_500ms=2, pool_peer_500ms>pool_l9_partial_200ms=37, tie=1 (total=40)

## Time and Simulation Efficiency
- `champion`: avg_time_ms=2981.580337532136, avg_sims_per_move=250.0, sims_per_sec=83.84815155003531, win_rate_per_sec=0.12577222732505297, score_per_sec=30.64649939153791
- `pool_l45_100ms`: avg_time_ms=1018.062041470997, avg_sims_per_move=50.0, sims_per_sec=49.1129203950626, win_rate_per_sec=0.07366938059259391, score_per_sec=75.43744572681616
- `pool_l9_partial_200ms`: avg_time_ms=1899.4952869415283, avg_sims_per_move=100.0, sims_per_sec=52.64556363338757, win_rate_per_sec=0.013161390908346893, score_per_sec=40.78715042496702
- `pool_peer_500ms`: avg_time_ms=2921.390769023769, avg_sims_per_move=250.0, sims_per_sec=85.57567945062743, win_rate_per_sec=0.17970892684631762, score_per_sec=33.152018219173065

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `pool_peer_500ms` | 47.93 | 7.40 | **25.74** | 40 |
| 2 | `champion` | 38.24 | 7.30 | **16.35** | 40 |
| 3 | `pool_l45_100ms` | 9.19 | 7.15 | **-12.27** | 40 |
| 4 | `pool_l9_partial_200ms` | 5.97 | 7.08 | **-15.27** | 40 |

## Score Margins (winner - last place)
- Mean: `30.07`, Median: `24.5`, Std: `15.82`, Range: `[8.0, 69.0]`

## Score by Seat Position
- `champion`: P1: 92.5±3.44 (n=10), P2: 89.5±2.61 (n=10), P3: 90.8±2.97 (n=10), P4: 92.7±4.13 (n=10)
- `pool_l45_100ms`: P1: 75.8±3.21 (n=10), P2: 85.2±2.96 (n=10), P3: 73.9±4.48 (n=10), P4: 72.3±4.35 (n=10)
- `pool_l9_partial_200ms`: P1: 84.0±3.18 (n=10), P2: 74.5±2.87 (n=10), P3: 76.9±2.34 (n=10), P4: 74.5±1.85 (n=10)
- `pool_peer_500ms`: P1: 94.6±1.77 (n=10), P2: 102.3±3.52 (n=10), P3: 102.6±4.11 (n=10), P4: 87.9±1.93 (n=10)
