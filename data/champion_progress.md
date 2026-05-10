# Champion Self-Improvement Progress
_Updated: 2026-05-10 03:31 UTC_

**Generation:** 2  **Snapshot rows accumulated:** 256  **Last weight re-fit:** generation 2

## TrueSkill Leaderboard
| Rank | Agent | μ | σ | μ-3σ | Games |
|------|-------|---|---|------|-------|
| 1 | mcts_high_c | 31.69 | 8.28 | 6.86 | 4 |
| 2 | mcts_opp_model | 30.03 | 8.24 | 5.32 | 4 |
| 3 | champion ★ | 30.29 | 8.33 | 5.29 | 8 |
| 4 | ckpt_v1 | 29.05 | 8.22 | 4.39 | 4 |
| 5 | heuristic | 24.48 | 7.96 | 0.59 | 8 |
| 6 | random | 8.99 | 7.97 | -14.90 | 8 |

## Champion TrueSkill Trend
| Gen | μ | σ | μ-3σ | WR% | AvgScore | Challengers | Refitted |
|-----|---|---|------|-----|----------|-------------|----------|
| 1 | 29.05 | 8.22 | 4.39 | 37.5% | 98.5 | heuristic, random, mcts_opp_model | No |
| 2 | 30.29 | 8.33 | 5.29 | 0.0% | 96.8 | heuristic, random, mcts_high_c | Yes |

## Current Champion Parameters
```json
{
  "deterministic_time_budget": true,
  "iterations_per_ms": 0.5,
  "exploration_constant": 1.414,
  "rollout_policy": "random",
  "rollout_cutoff_depth": 5,
  "minimax_backup_alpha": 0.25,
  "rave_enabled": true,
  "rave_k": 1000,
  "progressive_widening_enabled": true,
  "pw_c": 2.0,
  "pw_alpha": 0.5,
  "adaptive_rollout_depth_enabled": true,
  "adaptive_rollout_depth_base": 5,
  "adaptive_rollout_depth_avg_bf": 80.0,
  "state_eval_phase_weights": {
    "early": {
      "squares_placed": -0.02789619325112288,
      "remaining_piece_area": 0.027896193251122862,
      "accessible_corners": 0.2423071628237157,
      "reachable_empty_squares": 0.0,
      "largest_remaining_piece_size": 0.0,
      "opponent_avg_mobility": -0.3,
      "center_proximity": 0.0683186119736731,
      "territory_enclosure_area": 0.0
    },
    "mid": {
      "squares_placed": 0.04326693872809452,
      "remaining_piece_area": -0.043266938728094596,
      "accessible_corners": 0.009215671208488667,
      "reachable_empty_squares": 0.01204463292296519,
      "largest_remaining_piece_size": 0.0031529865683591705,
      "opponent_avg_mobility": -0.1506317267237639,
      "center_proximity": 0.3,
      "territory_enclosure_area": 0.0
    },
    "late": {
      "squares_placed": 0.0808811350364791,
      "remaining_piece_area": -0.08088113503647902,
      "accessible_corners": 0.0003862540198106459,
      "reachable_empty_squares": 0.030152165309350415,
      "largest_remaining_piece_size": -0.021144212914686218,
      "opponent_avg_mobility": -0.06510652498788876,
      "center_proximity": 0.3,
      "territory_enclosure_area": 0.0
    }
  }
}
```
