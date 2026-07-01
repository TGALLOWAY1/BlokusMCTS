# Nightly Training — Approach Comparison

_Run `20260701T023158Z` · generated 2026-07-01T02:31:58.073799+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong; seeds [20260620, 20260621]

## Champion Elo trajectory — ⚠️ fixed-champion measurement drift

> The champion has **never been promoted** (`last_promoted_generation` = None), so the agent under measurement is byte-for-byte fixed. The Elo numbers below are rating **variance of an unchanged agent**, not a learned strength change. Read them as measurement deltas until a promotion actually changes the champion.

- Current: **1223.1** · Best: 1379.2 · Gap to best: -156.1
- Rolling avg: 1178.8 · Trend/step: -0.9107
- Elo noise floor (σ over fixed-config tail): ±79.1 (spread 244.2, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| baseline_mcts | Yes | 10 | 50% | -36.2 | +2.88 | No | HOLD baseline: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'beats_champion_head_to_head', 'elo_improvement', 'min_total_games']. |
| td_learning | Yes | 15 | 40% | -79.1 | -4.73 | No | HOLD td: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement', 'min_total_games']. |
| mcts_param_sweep | Yes | 9 | 56% | +35.6 | +4.97 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'min_total_games']. |
| heuristic_tuning | Yes | 14 | 50% | -59.5 | -0.82 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement', 'min_total_games']. |

## Detail

### baseline_mcts (`baseline`)

- Created: yes — baseline: corrected weak-champion search settings (heuristic rollouts, no shallow cutoff, ~2x iterations)
- Games: 10 · Win rate (battery): 0.30 · Runtime: 5370.6s
- Elo Δ vs champion: -36.2 · TrueSkill μ Δ: +2.88
- Gate: HOLD baseline: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'beats_champion_head_to_head', 'elo_improvement', 'min_total_games'].
- Metrics: `{'overrides': {'rollout_policy': 'heuristic', 'rollout_cutoff_depth': None, 'adaptive_rollout_depth_enabled': False, 'iterations_per_ms': 1.0}}`

### td_learning (`td`)

- Created: yes — td: trained on 1611 trajectory rows (td_loss=0.010128)
- Games: 15 · Win rate (battery): 0.17 · Runtime: 5687.5s
- Elo Δ vs champion: -79.1 · TrueSkill μ Δ: -4.73
- Gate: HOLD td: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement', 'min_total_games'].
- Metrics: `{'source_rows': 1611, 'rows_by_phase': {'early': 505, 'mid': 669, 'late': 437}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.010128, 'td_loss_by_phase': {'early': 0.007831, 'mid': 0.007764, 'late': 0.016401}, 'mean_abs_td_error': 0.070134, 'learning_method': 'temporal_difference'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search)
- Games: 9 · Win rate (battery): 0.33 · Runtime: 4830.2s
- Elo Δ vs champion: +35.6 · TrueSkill μ Δ: +4.97
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'min_total_games'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 44832 snapshot rows
- Games: 14 · Win rate (battery): 0.36 · Runtime: 4597.4s
- Elo Δ vs champion: -59.5 · TrueSkill μ Δ: -0.82
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement', 'min_total_games'].
- Metrics: `{'training_rows': 44832, 'r2_global': 0.3365017454081656, 'r2_by_phase': {'early': 0.25201791865280476, 'mid': 0.3853658236844436, 'late': 0.7502781453404764}, 'learning_method': 'regression'}`

