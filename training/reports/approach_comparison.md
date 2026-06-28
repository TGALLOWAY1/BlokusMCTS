# Nightly Training — Approach Comparison

_Run `20260628T023102Z` · generated 2026-06-28T02:31:02.308444+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v1 — opponents heuristic, random; seeds [20260620, 20260621]

## Champion Elo trajectory

- Current: **1157.5** · Best: 1379.2 · Gap to best: -221.7
- Rolling avg: 1178.7 · Trend/step: -0.3156
- Elo noise floor (σ over fixed-config tail): ±50.0 (spread 155.4, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| td_learning | Yes | 100 | 47% | +30.5 | -8.16 | No | HOLD td: failed ['beats_champion_head_to_head', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 0 | — | — | — | No | mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — not evaluated this run (time budget exhausted) |
| heuristic_tuning | Yes | 0 | — | — | — | No | heuristic: re-fit Layer-6 weights from 44832 snapshot rows — not evaluated this run (time budget exhausted) |
| baseline_mcts | Yes | 0 | — | — | — | No | baseline: corrected weak-champion search settings (heuristic rollouts, no shallow cutoff, ~2x iterations) — not evaluated this run (time budget exhausted) |

## Detail

### td_learning (`td`)

- Created: yes — td: trained on 1611 trajectory rows (td_loss=0.010128)
- Games: 100 · Win rate (battery): 0.28 · Runtime: 11932.8s
- Elo Δ vs champion: +30.5 · TrueSkill μ Δ: -8.16
- Gate: HOLD td: failed ['beats_champion_head_to_head', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1611, 'rows_by_phase': {'early': 505, 'mid': 669, 'late': 437}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.010128, 'td_loss_by_phase': {'early': 0.007831, 'mid': 0.007764, 'late': 0.016401}, 'mean_abs_td_error': 0.070134, 'learning_method': 'temporal_difference'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — not evaluated this run (time budget exhausted)
- Games: 0 · Win rate (battery): — · Runtime: —s
- Elo Δ vs champion: — · TrueSkill μ Δ: —
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 44832 snapshot rows — not evaluated this run (time budget exhausted)
- Games: 0 · Win rate (battery): — · Runtime: —s
- Elo Δ vs champion: — · TrueSkill μ Δ: —
- Metrics: `{'training_rows': 44832, 'r2_global': 0.3365017454081656, 'r2_by_phase': {'early': 0.25201791865280476, 'mid': 0.3853658236844436, 'late': 0.7502781453404764}, 'learning_method': 'regression'}`

### baseline_mcts (`baseline`)

- Created: yes — baseline: corrected weak-champion search settings (heuristic rollouts, no shallow cutoff, ~2x iterations) — not evaluated this run (time budget exhausted)
- Games: 0 · Win rate (battery): — · Runtime: —s
- Elo Δ vs champion: — · TrueSkill μ Δ: —
- Metrics: `{'overrides': {'rollout_policy': 'heuristic', 'rollout_cutoff_depth': None, 'adaptive_rollout_depth_enabled': False, 'iterations_per_ms': 1.0}}`

