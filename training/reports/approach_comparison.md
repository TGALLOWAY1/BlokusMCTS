# Nightly Training — Approach Comparison

_Run `20260703T190141Z` · generated 2026-07-03T19:01:41.526746+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]

## Champion Elo trajectory

- Current: **1396.0** · Best: 1396.0 · Gap to best: 0.0
- Rolling avg: 1391.7 · Trend/step: 0.0363
- Elo noise floor (σ over fixed-config tail): ±141.5 (spread 381.7, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| baseline_mcts | Yes | 20 | 47% | -81.9 | -6.22 | No | HOLD baseline: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 20 | 45% | -61.7 | -3.93 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### baseline_mcts (`baseline`)

- Created: yes — baseline: corrected weak-champion search settings (greedy-sample rollouts, cutoff 12, RAVE/minimax off, move ordering on)
- Games: 20 · Win rate (battery): 0.38 · Runtime: 4811.0s
- Elo Δ vs champion: -81.9 · TrueSkill μ Δ: -6.22
- Gate: HOLD baseline: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'overrides': {'rollout_policy': 'greedy_sample', 'rollout_cutoff_depth': 12, 'adaptive_rollout_depth_enabled': False, 'iterations_per_ms': 0.5, 'rave_enabled': False, 'minimax_backup_alpha': 0.0, 'heuristic_move_ordering': True, 'num_workers': 1}}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 44832 snapshot rows
- Games: 20 · Win rate (battery): 0.35 · Runtime: 4787.0s
- Elo Δ vs champion: -61.7 · TrueSkill μ Δ: -3.93
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 44832, 'r2_global': 0.3365017454081656, 'r2_by_phase': {'early': 0.25201791865280476, 'mid': 0.3853658236844436, 'late': 0.7502781453404764}, 'learning_method': 'regression'}`

