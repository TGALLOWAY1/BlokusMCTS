# Nightly Training — Approach Comparison

_Run `20260706T022231Z` · generated 2026-07-06T02:22:31.377317+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]

## Champion Elo trajectory

- Current: **1391.5** · Best: 1398.4 · Gap to best: -6.9
- Rolling avg: 1396.1 · Trend/step: 0.7295
- Elo noise floor (σ over fixed-config tail): ±71.9 (spread 197.8, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| policy_prior | Yes | 20 | 50% | -86.7 | -6.30 | No | HOLD policy: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| baseline_mcts | Yes | 20 | 47% | -81.9 | -6.22 | No | HOLD baseline: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 20 | 45% | -61.7 | -3.93 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### policy_prior (`policy`)

- Created: yes — policy: distilled 439 decisions (loss=3.417552, top1=0.5308)
- Games: 20 · Win rate (battery): 0.35 · Runtime: 2680.1s
- Elo Δ vs champion: -86.7 · TrueSkill μ Δ: -6.30
- Gate: HOLD policy: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'n_samples': 439, 'loss': 3.417552, 'top1_agreement': 0.5308, 'learning_method': 'visit_count_distillation'}`

### baseline_mcts (`baseline`)

- Created: yes — baseline: corrected weak-champion search settings (greedy-sample rollouts, cutoff 12, RAVE/minimax off, move ordering on)
- Games: 20 · Win rate (battery): 0.38 · Runtime: 2596.6s
- Elo Δ vs champion: -81.9 · TrueSkill μ Δ: -6.22
- Gate: HOLD baseline: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'overrides': {'rollout_policy': 'greedy_sample', 'rollout_cutoff_depth': 12, 'adaptive_rollout_depth_enabled': False, 'iterations_per_ms': 0.5, 'rave_enabled': False, 'minimax_backup_alpha': 0.0, 'heuristic_move_ordering': True, 'num_workers': 1}}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 44832 snapshot rows
- Games: 20 · Win rate (battery): 0.35 · Runtime: 2595.7s
- Elo Δ vs champion: -61.7 · TrueSkill μ Δ: -3.93
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 44832, 'r2_global': 0.3365017454081656, 'r2_by_phase': {'early': 0.25201791865280454, 'mid': 0.3853658236844435, 'late': 0.7502781453404764}, 'learning_method': 'regression'}`

