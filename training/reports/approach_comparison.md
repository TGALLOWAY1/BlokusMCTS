# Nightly Training — Approach Comparison

_Run `20260630T021503Z` · generated 2026-06-30T02:15:03.395598+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v1 — opponents heuristic, random; seeds [20260620, 20260621]

## Champion Elo trajectory

- Current: **1015.4** · Best: 1379.2 · Gap to best: -363.9
- Rolling avg: 1026.7 · Trend/step: -1.0899
- Elo noise floor (σ over fixed-config tail): ±80.7 (spread 244.2, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| baseline_mcts | Yes | 2 | 100% | +111.4 | +3.86 | No | HOLD baseline: failed ['conservative:enough_games', 'min_total_games']. |
| td_learning | Yes | 20 | 53% | +74.6 | +0.67 | No | HOLD td: failed []. |
| mcts_param_sweep | Yes | 2 | 100% | +82.6 | +2.78 | No | HOLD mcts_sweep: failed ['conservative:enough_games', 'min_total_games']. |
| heuristic_tuning | Yes | 0 | — | — | — | No | heuristic: re-fit Layer-6 weights from 44832 snapshot rows — not evaluated this run (time budget exhausted) |

## Detail

### baseline_mcts (`baseline`)

- Created: yes — baseline: corrected weak-champion search settings (heuristic rollouts, no shallow cutoff, ~2x iterations)
- Games: 2 · Win rate (battery): 1.00 · Runtime: 5166.5s
- Elo Δ vs champion: +111.4 · TrueSkill μ Δ: +3.86
- Gate: HOLD baseline: failed ['conservative:enough_games', 'min_total_games'].
- Metrics: `{'overrides': {'rollout_policy': 'heuristic', 'rollout_cutoff_depth': None, 'adaptive_rollout_depth_enabled': False, 'iterations_per_ms': 1.0}}`

### td_learning (`td`)

- Created: yes — td: trained on 1611 trajectory rows (td_loss=0.010128)
- Games: 20 · Win rate (battery): 0.30 · Runtime: 2402.4s
- Elo Δ vs champion: +74.6 · TrueSkill μ Δ: +0.67
- Gate: HOLD td: failed [].
- Metrics: `{'source_rows': 1611, 'rows_by_phase': {'early': 505, 'mid': 669, 'late': 437}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.010128, 'td_loss_by_phase': {'early': 0.007831, 'mid': 0.007764, 'late': 0.016401}, 'mean_abs_td_error': 0.070134, 'learning_method': 'temporal_difference'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search)
- Games: 2 · Win rate (battery): 1.00 · Runtime: 5032.1s
- Elo Δ vs champion: +82.6 · TrueSkill μ Δ: +2.78
- Gate: HOLD mcts_sweep: failed ['conservative:enough_games', 'min_total_games'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 44832 snapshot rows — not evaluated this run (time budget exhausted)
- Games: 0 · Win rate (battery): — · Runtime: —s
- Elo Δ vs champion: — · TrueSkill μ Δ: —
- Metrics: `{'training_rows': 44832, 'r2_global': 0.3365017454081656, 'r2_by_phase': {'early': 0.25201791865280476, 'mid': 0.3853658236844436, 'late': 0.7502781453404764}, 'learning_method': 'regression'}`

