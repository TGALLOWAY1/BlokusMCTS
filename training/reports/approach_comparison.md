# Nightly Training — Approach Comparison

_Run `20260708T192653Z` · generated 2026-07-08T19:26:53.513745+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +82 TD rows (labels from `gen140@teacher:1200`) · +96 snapshot rows (corpus 512) · 2720.5s of 2700.0s budget

## Champion Elo trajectory

- Current: **1359.0** · Best: 1398.4 · Gap to best: -39.4
- Rolling avg: 1364.7 · Trend/step: 1.0313
- Elo noise floor (σ over fixed-config tail): ±32.9 (spread 91.1, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 58 | 43% | -21.9 | -8.20 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 51 | 44% | -65.2 | -5.91 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 51 | 38% | -64.0 | -9.05 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 1123 rows — [sprt] rich_leaf: inconclusive after 58 paired games (23W-4D-31L, pairwise 43%, Δelo≈-48, LLR=-1.40 in [-2.94,2.94])
- Games: 58 · Win rate (battery): 0.27 · Runtime: 5426.2s
- Elo Δ vs champion: -21.9 · TrueSkill μ Δ: -8.20
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1123, 'rows_by_phase': {'early': 328, 'mid': 448, 'late': 347}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.007203, 'mean_abs_td_error': 0.041795, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 512 snapshot rows — [sprt] heuristic_tune: inconclusive after 51 paired games (22W-1D-28L, pairwise 44%, Δelo≈-41, LLR=-1.05 in [-2.94,2.94])
- Games: 51 · Win rate (battery): 0.29 · Runtime: 5392.9s
- Elo Δ vs champion: -65.2 · TrueSkill μ Δ: -5.91
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 512, 'r2_global': 0.6263589958779143, 'r2_by_phase': {'early': 0.6171776829099009, 'mid': 0.768825712151003, 'late': 0.8213661440706272}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 51 paired games (19W-1D-31L, pairwise 38%, Δelo≈-83, LLR=-1.75 in [-2.94,2.94])
- Games: 51 · Win rate (battery): 0.30 · Runtime: 5425.8s
- Elo Δ vs champion: -64.0 · TrueSkill μ Δ: -9.05
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

