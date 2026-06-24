# Rich Feature Normalisation Audit

_Samples: 1611 · status: ✅ OK_

**No issues detected.** All features finite and in range.

## Feature statistics (by variance share)

| Feature | min | max | mean | std | var% | %=0 | %=1 |
|---|---|---|---|---|---|---|---|
| `corner_quality_score` | 0.001 | 1.000 | 0.507 | 0.425 | 5.9% | 0% | 37% |
| `trapped_region_count` | 0.000 | 1.000 | 0.644 | 0.423 | 5.8% | 17% | 53% |
| `leader_mobility_pressure` | 0.000 | 1.000 | 0.493 | 0.397 | 5.1% | 4% | 29% |
| `opponent_mobility_max` | 0.000 | 1.000 | 0.528 | 0.395 | 5.1% | 4% | 32% |
| `opponent_mobility_avg` | 0.000 | 1.000 | 0.440 | 0.388 | 4.9% | 4% | 21% |
| `legal_move_count` | 0.003 | 1.000 | 0.407 | 0.370 | 4.4% | 0% | 17% |
| `legal_move_count_large_pieces` | 0.000 | 1.000 | 0.326 | 0.363 | 4.3% | 10% | 12% |
| `rank_so_far` | 0.000 | 1.000 | 0.478 | 0.360 | 4.2% | 26% | 21% |
| `new_corner_generation_potential` | 0.020 | 1.000 | 0.677 | 0.340 | 3.8% | 0% | 39% |
| `remaining_singletons` | 0.000 | 1.000 | 0.868 | 0.339 | 3.7% | 13% | 87% |
| `opponent_mobility_min` | 0.000 | 1.000 | 0.294 | 0.338 | 3.7% | 24% | 7% |
| `remaining_dominoes` | 0.000 | 1.000 | 0.877 | 0.328 | 3.5% | 12% | 88% |
| `remaining_pentominoes` | 0.000 | 1.000 | 0.444 | 0.313 | 3.2% | 6% | 7% |
| `total_playable_piece_area` | 0.011 | 0.989 | 0.522 | 0.305 | 3.0% | 0% | 0% |
| `remaining_trominoes` | 0.000 | 1.000 | 0.831 | 0.303 | 3.0% | 7% | 73% |
| `playable_piece_count` | 0.048 | 0.952 | 0.565 | 0.292 | 2.8% | 0% | 0% |
| `remaining_tetrominoes` | 0.000 | 1.000 | 0.761 | 0.291 | 2.7% | 2% | 48% |
| `squares_placed` | 0.000 | 0.977 | 0.428 | 0.263 | 2.3% | 6% | 0% |
| `remaining_piece_area` | 0.023 | 1.000 | 0.572 | 0.263 | 2.3% | 0% | 6% |
| `awkward_piece_penalty` | 0.023 | 1.000 | 0.572 | 0.263 | 2.3% | 0% | 6% |
| `remaining_area` | 0.023 | 1.000 | 0.572 | 0.263 | 2.3% | 0% | 6% |
| `remaining_piece_count` | 0.048 | 1.000 | 0.612 | 0.249 | 2.0% | 0% | 6% |
| `completion_ratio` | 0.000 | 0.952 | 0.388 | 0.249 | 2.0% | 6% | 0% |
| `accessible_corners` | 0.025 | 1.000 | 0.427 | 0.240 | 1.9% | 0% | 0% |
| `corner_count` | 0.025 | 1.000 | 0.427 | 0.240 | 1.9% | 0% | 0% |
| `frontier_size` | 0.025 | 1.000 | 0.427 | 0.240 | 1.9% | 0% | 0% |
| `avg_legal_move_area` | 0.200 | 1.000 | 0.671 | 0.208 | 1.4% | 0% | 1% |
| `quadrant_balance` | 0.000 | 0.853 | 0.127 | 0.199 | 1.3% | 59% | 0% |
| `score_margin_vs_leader` | -0.716 | 0.800 | -0.188 | 0.183 | 1.1% | 15% | 0% |
| `score_margin_vs_next_player` | -0.572 | 0.896 | -0.120 | 0.175 | 1.0% | 13% | 0% |
| `max_legal_move_area` | 0.200 | 1.000 | 0.925 | 0.167 | 0.9% | 0% | 78% |
| `center_proximity` | 0.000 | 0.625 | 0.420 | 0.167 | 0.9% | 6% | 0% |
| `frontier_to_opponent_distance` | 0.000 | 1.000 | 0.073 | 0.166 | 0.9% | 67% | 1% |
| `piece_diversity_score` | 0.200 | 1.000 | 0.918 | 0.164 | 0.9% | 0% | 75% |
| `opponent_avg_mobility` | 0.025 | 0.717 | 0.401 | 0.158 | 0.8% | 0% | 0% |
| `opponent_corner_pressure` | 0.025 | 0.717 | 0.401 | 0.158 | 0.8% | 0% | 0% |
| `edge_pressure` | 0.000 | 1.000 | 0.137 | 0.139 | 0.6% | 6% | 1% |
| `trapped_region_area` | 0.000 | 0.547 | 0.186 | 0.127 | 0.5% | 17% | 0% |
| `frontier_density` | 0.003 | 0.467 | 0.150 | 0.116 | 0.4% | 0% | 0% |
| `reachable_empty_squares` | 0.300 | 1.000 | 0.959 | 0.110 | 0.4% | 0% | 82% |
| `largest_remaining_piece_size` | 0.400 | 1.000 | 0.986 | 0.062 | 0.1% | 0% | 94% |
| `largest_reachable_region` | 0.450 | 1.000 | 0.990 | 0.056 | 0.1% | 0% | 95% |
| `legal_move_count_medium_pieces` | 0.000 | 0.210 | 0.056 | 0.053 | 0.1% | 10% | 0% |
| `legal_move_count_small_pieces` | 0.000 | 0.145 | 0.057 | 0.037 | 0.0% | 6% | 0% |
| `territory_enclosure_area` | 0.000 | 0.000 | 0.000 | 0.000 | 0.0% | 100% | 0% |
