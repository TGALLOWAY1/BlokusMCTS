# Nightly Training — Approach Comparison

_Run `20260706T151300Z` · generated 2026-07-06T15:13:00.131540+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]

## Champion Elo trajectory

- Current: **1388.6** · Best: 1398.4 · Gap to best: -9.8
- Rolling avg: 1393.4 · Trend/step: 0.8352
- Elo noise floor (σ over fixed-config tail): ±56.0 (spread 197.8, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| policy_prior | Yes | 20 | 53% | -31.5 | -4.71 | No | HOLD policy: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'elo_improvement', 'trueskill_improvement']. |
| baseline_mcts | Yes | 20 | 47% | -81.9 | -6.22 | No | HOLD baseline: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 20 | 45% | -61.7 | -3.93 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### policy_prior (`policy`)

- Created: yes — policy: distilled 678 decisions (loss=3.418671, top1=0.5324)
- Games: 20 · Win rate (battery): 0.35 · Runtime: 4509.7s
- Elo Δ vs champion: -31.5 · TrueSkill μ Δ: -4.71
- Gate: HOLD policy: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'n_samples': 678, 'loss': 3.418671, 'top1_agreement': 0.5324, 'learning_method': 'visit_count_distillation'}`

### baseline_mcts (`baseline`)

- Created: yes — baseline: corrected weak-champion search settings (greedy-sample rollouts, cutoff 12, RAVE/minimax off, move ordering on)
- Games: 20 · Win rate (battery): 0.38 · Runtime: 4436.6s
- Elo Δ vs champion: -81.9 · TrueSkill μ Δ: -6.22
- Gate: HOLD baseline: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'overrides': {'rollout_policy': 'greedy_sample', 'rollout_cutoff_depth': 12, 'adaptive_rollout_depth_enabled': False, 'iterations_per_ms': 0.5, 'rave_enabled': False, 'minimax_backup_alpha': 0.0, 'heuristic_move_ordering': True, 'num_workers': 1}}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 44832 snapshot rows
- Games: 20 · Win rate (battery): 0.35 · Runtime: 4452.3s
- Elo Δ vs champion: -61.7 · TrueSkill μ Δ: -3.93
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 44832, 'r2_global': 0.3365017454081656, 'r2_by_phase': {'early': 0.25201791865280476, 'mid': 0.3853658236844436, 'late': 0.7502781453404764}, 'learning_method': 'regression'}`

