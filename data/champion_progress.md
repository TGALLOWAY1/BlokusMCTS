# Champion Self-Improvement Progress
_Updated: 2026-05-08 03:33 UTC_

**Generation:** 1  **Snapshot rows accumulated:** 128  **Last weight re-fit:** generation -1

## Human-Level Benchmark
The `pool_heuristic` agent plays at intermediate human amateur level.  
**Champion win rate goal:** pool_heuristic win rate < 15%.

_No data yet — run at least one generation._

## TrueSkill Leaderboard
| Rank | Agent | μ | σ | μ-3σ | Games |
|------|-------|---|---|------|-------|
| 1 | champion ★ | 30.92 | 8.26 | 6.14 | 4 |
| 2 | pool_heuristic | 29.24 | 8.22 | 4.58 | 4 |
| 3 | pool_deploy_medium | 20.12 | 8.13 | -4.26 | 4 |
| 4 | pool_mcts_100ms | 19.84 | 8.12 | -4.54 | 4 |

## Champion TrueSkill Trend
| Gen | μ | σ | μ-3σ | WR% | AvgScore | HeuristicWR% | Challengers | Refitted |
|-----|---|---|------|-----|----------|-------------|-------------|----------|
| 1 | 30.92 | 8.26 | 6.14 | 0.0% | 0.0 | — | pool_heuristic, pool_mcts_100ms, pool_deploy_medium | No |

## Current Champion Parameters
```json
{
  "deterministic_time_budget": true,
  "iterations_per_ms": 0.5,
  "exploration_constant": 1.414,
  "use_transposition_table": true,
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
  "state_eval_weights": {
    "squares_placed": 0.0295,
    "remaining_piece_area": -0.0295,
    "accessible_corners": 0.243,
    "reachable_empty_squares": 0.081,
    "largest_remaining_piece_size": -0.231,
    "opponent_avg_mobility": -0.3,
    "center_proximity": 0.0,
    "territory_enclosure_area": 0.0
  },
  "state_eval_phase_weights": {
    "early": {
      "squares_placed": -0.17599664484103847,
      "remaining_piece_area": 0.17599664484103822,
      "accessible_corners": 0.3,
      "reachable_empty_squares": 0.0,
      "largest_remaining_piece_size": 0.0,
      "opponent_avg_mobility": -0.05287834609528694,
      "center_proximity": 0.0,
      "territory_enclosure_area": 0.0
    },
    "mid": {
      "squares_placed": -0.00387502185581506,
      "remaining_piece_area": 0.0038750218558150614,
      "accessible_corners": 0.3,
      "reachable_empty_squares": 0.22774497158891033,
      "largest_remaining_piece_size": -0.238473591231953,
      "opponent_avg_mobility": -0.20277351241243552,
      "center_proximity": 0.0,
      "territory_enclosure_area": 0.0
    },
    "late": {
      "squares_placed": 0.3,
      "remaining_piece_area": -0.3,
      "accessible_corners": 0.17573409689186584,
      "reachable_empty_squares": 0.13361753070802862,
      "largest_remaining_piece_size": -0.08518919739412929,
      "opponent_avg_mobility": -0.06278383996091268,
      "center_proximity": 0.0,
      "territory_enclosure_area": 0.0
    }
  }
}
```
