# TD Feature Importance (per phase)

## early

| rank | feature | |weight| |
|---|---|---|
| 1 | `opponent_avg_mobility` | 0.3665 |
| 2 | `rank_so_far` | 0.3166 |
| 3 | `center_proximity` | 0.2435 |
| 4 | `accessible_corners` | 0.2396 |
| 5 | `largest_remaining_piece_size` | 0.2260 |
| 6 | `score_margin_vs_leader` | 0.1613 |
| 7 | `opponent_mobility_min` | 0.1332 |
| 8 | `legal_move_count_large_pieces` | 0.1258 |
| 9 | `trapped_region_area` | 0.1145 |
| 10 | `remaining_tetrominoes` | 0.0985 |
| 11 | `opponent_corner_pressure` | 0.0953 |
| 12 | `remaining_trominoes` | 0.0902 |

## mid

| rank | feature | |weight| |
|---|---|---|
| 1 | `accessible_corners` | 0.3927 |
| 2 | `opponent_avg_mobility` | 0.3542 |
| 3 | `center_proximity` | 0.3023 |
| 4 | `largest_remaining_piece_size` | 0.2183 |
| 5 | `corner_count` | 0.1827 |
| 6 | `frontier_size` | 0.1827 |
| 7 | `trapped_region_area` | 0.1607 |
| 8 | `new_corner_generation_potential` | 0.1503 |
| 9 | `legal_move_count` | 0.1422 |
| 10 | `quadrant_balance` | 0.1342 |
| 11 | `score_margin_vs_leader` | 0.1286 |
| 12 | `legal_move_count_large_pieces` | 0.1239 |

## late

| rank | feature | |weight| |
|---|---|---|
| 1 | `accessible_corners` | 0.3730 |
| 2 | `opponent_avg_mobility` | 0.3520 |
| 3 | `center_proximity` | 0.3116 |
| 4 | `largest_remaining_piece_size` | 0.1861 |
| 5 | `score_margin_vs_leader` | 0.1693 |
| 6 | `score_margin_vs_next_player` | 0.1622 |
| 7 | `corner_count` | 0.1531 |
| 8 | `frontier_size` | 0.1531 |
| 9 | `quadrant_balance` | 0.1529 |
| 10 | `new_corner_generation_potential` | 0.1509 |
| 11 | `reachable_empty_squares` | 0.1250 |
| 12 | `squares_placed` | 0.0955 |
