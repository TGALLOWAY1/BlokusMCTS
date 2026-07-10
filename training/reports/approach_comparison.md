# Nightly Training — Approach Comparison

_Run `20260710T093326Z` · generated 2026-07-10T09:33:26.917975+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +74 TD rows (labels from `gen140@teacher:1200`) · +96 snapshot rows (corpus 956) · 2935.1s of 2700.0s budget

## Champion Elo trajectory

- Current: **1384.5** · Best: 1409.9 · Gap to best: -25.3
- Rolling avg: 1381.0 · Trend/step: 1.187
- Elo noise floor (σ over fixed-config tail): ±32.5 (spread 102.6, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 56 | 42% | -39.8 | -8.21 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 48 | 42% | -98.2 | -7.78 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 48 | 38% | -108.4 | -10.54 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 1584 rows — [sprt] rich_leaf: inconclusive after 56 paired games (22W-3D-31L, pairwise 42%, Δelo≈-56, LLR=-1.49 in [-2.94,2.94])
- Games: 56 · Win rate (battery): 0.29 · Runtime: 5399.9s
- Elo Δ vs champion: -39.8 · TrueSkill μ Δ: -8.21
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1584, 'rows_by_phase': {'early': 460, 'mid': 621, 'late': 503}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.007861, 'mean_abs_td_error': 0.045581, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 956 snapshot rows — [sprt] heuristic_tune: inconclusive after 48 paired games (20W-0D-28L, pairwise 42%, Δelo≈-58, LLR=-1.24 in [-2.94,2.94])
- Games: 48 · Win rate (battery): 0.30 · Runtime: 5310.3s
- Elo Δ vs champion: -98.2 · TrueSkill μ Δ: -7.78
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 956, 'r2_global': 0.5791214296822369, 'r2_by_phase': {'early': 0.5581904324480038, 'mid': 0.7090059846154786, 'late': 0.7816384715608355}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 48 paired games (18W-1D-29L, pairwise 39%, Δelo≈-81, LLR=-1.62 in [-2.94,2.94])
- Games: 48 · Win rate (battery): 0.30 · Runtime: 5355.8s
- Elo Δ vs champion: -108.4 · TrueSkill μ Δ: -10.54
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

