# Champion Self-Improvement Progress
_Updated: 2026-06-28 20:49 UTC_

**Generation:** 0  **Snapshot rows accumulated:** 0  **Last weight re-fit:** generation 0

## TrueSkill Leaderboard
| Rank | Agent | μ | σ | μ-3σ | Games |
|------|-------|---|---|------|-------|
| 1 | champion ★ | 25.00 | 8.33 | 0.00 | 0 |

## Current Champion Parameters
```json
{
  "deterministic_time_budget": true,
  "iterations_per_ms": 10.0,
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
      "squares_placed": 0.11354182484350582,
      "remaining_piece_area": -0.11354182484350593,
      "accessible_corners": 0.08836305227314599,
      "reachable_empty_squares": 0.0,
      "largest_remaining_piece_size": 0.0,
      "opponent_avg_mobility": -0.3,
      "center_proximity": 0.0026248922266153534,
      "territory_enclosure_area": 0.0
    },
    "mid": {
      "squares_placed": 0.04988760327628422,
      "remaining_piece_area": -0.04988760327628426,
      "accessible_corners": 0.13638714041073274,
      "reachable_empty_squares": 0.11762983842748906,
      "largest_remaining_piece_size": -0.12002019921459996,
      "opponent_avg_mobility": -0.1807198509366564,
      "center_proximity": 0.3,
      "territory_enclosure_area": 0.0
    },
    "late": {
      "squares_placed": 0.15445700654515712,
      "remaining_piece_area": -0.15445700654515745,
      "accessible_corners": -0.010231676575125935,
      "reachable_empty_squares": 0.06146017633650651,
      "largest_remaining_piece_size": -0.06038569705663195,
      "opponent_avg_mobility": 0.05044375008467363,
      "center_proximity": 0.3,
      "territory_enclosure_area": 0.0
    }
  }
}
```
