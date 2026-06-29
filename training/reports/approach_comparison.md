# Nightly Training — Approach Comparison

_Run `20260629T102152Z` · generated 2026-06-29T10:21:52.730846+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v1 — opponents heuristic, random; seeds [20260620, 20260621]

## Champion Elo trajectory

- Current: **1030.9** · Best: 1379.2 · Gap to best: -348.3
- Rolling avg: 1086.2 · Trend/step: -0.734
- Elo noise floor (σ over fixed-config tail): ±64.4 (spread 227.6, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| baseline_mcts | Yes | 2 | 100% | +111.4 | +3.86 | No | HOLD baseline: failed ['conservative:enough_games', 'min_total_games']. |
| td_learning | Yes | 20 | 53% | +74.6 | +0.67 | No | HOLD td: failed []. |
| mcts_param_sweep | Yes | 2 | 100% | +82.6 | +2.78 | No | HOLD mcts_sweep: failed ['conservative:enough_games', 'min_total_games']. |
| heuristic_tuning | Yes | 1 | 100% | +58.2 | +1.93 | No | HOLD heuristic_tune: failed ['conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'min_total_games']. |

## Detail

### baseline_mcts (`baseline`)

- Created: yes — baseline: corrected weak-champion search settings (heuristic rollouts, no shallow cutoff, ~2x iterations)
- Games: 2 · Win rate (battery): 1.00 · Runtime: 5144.4s
- Elo Δ vs champion: +111.4 · TrueSkill μ Δ: +3.86
- Gate: HOLD baseline: failed ['conservative:enough_games', 'min_total_games'].
- Metrics: `{'overrides': {'rollout_policy': 'heuristic', 'rollout_cutoff_depth': None, 'adaptive_rollout_depth_enabled': False, 'iterations_per_ms': 1.0}}`

### td_learning (`td`)

- Created: yes — td: trained on 1611 trajectory rows (td_loss=0.010128)
- Games: 20 · Win rate (battery): 0.30 · Runtime: 2391.8s
- Elo Δ vs champion: +74.6 · TrueSkill μ Δ: +0.67
- Gate: HOLD td: failed [].
- Metrics: `{'source_rows': 1611, 'rows_by_phase': {'early': 505, 'mid': 669, 'late': 437}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.010128, 'td_loss_by_phase': {'early': 0.007831, 'mid': 0.007764, 'late': 0.016401}, 'mean_abs_td_error': 0.070134, 'learning_method': 'temporal_difference'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search)
- Games: 2 · Win rate (battery): 1.00 · Runtime: 5016.6s
- Elo Δ vs champion: +82.6 · TrueSkill μ Δ: +2.78
- Gate: HOLD mcts_sweep: failed ['conservative:enough_games', 'min_total_games'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 44832 snapshot rows
- Games: 1 · Win rate (battery): 1.00 · Runtime: 113.9s
- Elo Δ vs champion: +58.2 · TrueSkill μ Δ: +1.93
- Gate: HOLD heuristic_tune: failed ['conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'min_total_games'].
- Metrics: `{'training_rows': 44832, 'r2_global': 0.3365017454081656, 'r2_by_phase': {'early': 0.25201791865280476, 'mid': 0.3853658236844436, 'late': 0.7502781453404764}, 'learning_method': 'regression'}`

