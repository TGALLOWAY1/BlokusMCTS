# Arena Run Summary: 20260712_060417_de5a1a78

## Overview
- Seed: `20260620`
- Seat policy: `round_robin`
- Games: `12/12` completed
- Error games: `0`

## Win Rates by Agent
- `heuristic`: win_rate=0.167, win_points=2.00, outright=2, shared=0
- `mcts_it150`: win_rate=0.167, win_points=2.00, outright=2, shared=0
- `mcts_it50`: win_rate=0.500, win_points=6.00, outright=6, shared=0
- `mcts_it500`: win_rate=0.167, win_points=2.00, outright=2, shared=0

## Win Rates by Seat
- `heuristic`: seat0: 0.333 (3 games), seat1: 0.000 (3 games), seat2: 0.333 (3 games), seat3: 0.000 (3 games)
- `mcts_it150`: seat0: 0.333 (3 games), seat1: 0.333 (3 games), seat2: 0.000 (3 games), seat3: 0.000 (3 games)
- `mcts_it50`: seat0: 0.333 (3 games), seat1: 0.667 (3 games), seat2: 0.667 (3 games), seat3: 0.333 (3 games)
- `mcts_it500`: seat0: 0.333 (3 games), seat1: 0.000 (3 games), seat2: 0.333 (3 games), seat3: 0.000 (3 games)

## Score Stats
- `heuristic`: mean=71.91666666666667, median=71.5, std=3.4751099103321734, p25=68.75, p75=74.5, min=67.0, max=77.0
- `mcts_it150`: mean=75.66666666666667, median=77.0, std=6.289320754704402, p25=71.0, p75=79.25, min=62.0, max=84.0
- `mcts_it50`: mean=76.75, median=76.0, std=4.692636075100363, p25=72.0, p75=80.25, min=71.0, max=84.0
- `mcts_it500`: mean=73.25, median=71.0, std=11.66279697728351, p25=68.5, p75=74.0, min=60.0, max=108.0

## Pairwise Matchups
- `heuristic__vs__mcts_it150`: heuristic>mcts_it150=4, mcts_it150>heuristic=7, tie=1 (total=12)
- `heuristic__vs__mcts_it50`: heuristic>mcts_it50=3, mcts_it50>heuristic=9, tie=0 (total=12)
- `heuristic__vs__mcts_it500`: heuristic>mcts_it500=7, mcts_it500>heuristic=4, tie=1 (total=12)
- `mcts_it150__vs__mcts_it50`: mcts_it150>mcts_it50=4, mcts_it50>mcts_it150=8, tie=0 (total=12)
- `mcts_it150__vs__mcts_it500`: mcts_it150>mcts_it500=8, mcts_it500>mcts_it150=4, tie=0 (total=12)
- `mcts_it50__vs__mcts_it500`: mcts_it50>mcts_it500=9, mcts_it500>mcts_it50=3, tie=0 (total=12)

## Time and Simulation Efficiency
- `heuristic`: avg_time_ms=25.76176157426271, avg_sims_per_move=None, sims_per_sec=None, win_rate_per_sec=6.469536882647613, score_per_sec=2791.6051648624457
- `mcts_it150`: avg_time_ms=2885.3969827846245, avg_sims_per_move=150.0, sims_per_sec=51.98591420693826, win_rate_per_sec=0.057762126896598064, score_per_sec=26.224005611055524
- `mcts_it50`: avg_time_ms=1017.5341307844745, avg_sims_per_move=50.0, sims_per_sec=49.13840085290522, win_rate_per_sec=0.49138400852905223, score_per_sec=75.42744530920952
- `mcts_it500`: avg_time_ms=10115.558532568124, avg_sims_per_move=500.0, sims_per_sec=49.42880794868582, win_rate_per_sec=0.016476269316228608, score_per_sec=7.241320364482473

## TrueSkill Ratings
- Converged: `False`

| Rank | Agent | mu | sigma | Conservative (mu-3sigma) | Games |
|------|-------|----|-------|-------------------------|-------|
| 1 | `mcts_it50` | 32.08 | 7.98 | **8.13** | 12 |
| 2 | `mcts_it150` | 27.36 | 7.94 | **3.53** | 12 |
| 3 | `heuristic` | 21.84 | 7.88 | **-1.80** | 12 |
| 4 | `mcts_it500` | 18.85 | 7.83 | **-4.64** | 12 |

## Score Margins (winner - last place)
- Mean: `15.33`, Median: `12.5`, Std: `8.81`, Range: `[5.0, 40.0]`

## Score by Seat Position
- `heuristic`: P1: 72.0±2.65 (n=3), P2: 73.0±2.65 (n=3), P3: 71.0±2.65 (n=3), P4: 71.67±1.45 (n=3)
- `mcts_it150`: P1: 74.67±6.57 (n=3), P2: 78.0±3.79 (n=3), P3: 75.67±2.6 (n=3), P4: 74.33±3.28 (n=3)
- `mcts_it50`: P1: 75.0±2.65 (n=3), P2: 76.33±2.6 (n=3), P3: 78.33±3.84 (n=3), P4: 77.33±3.53 (n=3)
- `mcts_it500`: P1: 85.33±11.33 (n=3), P2: 65.0±3.21 (n=3), P3: 73.33±3.33 (n=3), P4: 69.33±2.73 (n=3)
