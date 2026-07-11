# Nightly Training — Approach Comparison

_Run `20260711T021059Z` · generated 2026-07-11T02:10:59.339899+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +115 TD rows (labels from `gen140@teacher:1200`) · +92 snapshot rows (corpus 1240) · 2813.0s of 2700.0s budget

## Champion Elo trajectory

- Current: **1271.1** · Best: 1409.9 · Gap to best: -138.7
- Rolling avg: 1338.4 · Trend/step: 1.176
- Elo noise floor (σ over fixed-config tail): ±41.6 (spread 138.7, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 85 | 43% | -186.1 | -12.95 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 72 | 44% | +32.0 | -3.56 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 72 | 44% | +116.5 | -4.27 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 1892 rows — [sprt] rich_leaf: inconclusive after 85 paired games (35W-3D-47L, pairwise 43%, Δelo≈-49, LLR=-2.02 in [-2.94,2.94])
- Games: 85 · Win rate (battery): 0.28 · Runtime: 5444.9s
- Elo Δ vs champion: -186.1 · TrueSkill μ Δ: -12.95
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1892, 'rows_by_phase': {'early': 548, 'mid': 731, 'late': 613}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.007777, 'mean_abs_td_error': 0.049667, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 1240 snapshot rows — [sprt] heuristic_tune: inconclusive after 72 paired games (31W-2D-39L, pairwise 44%, Δelo≈-39, LLR=-1.44 in [-2.94,2.94])
- Games: 72 · Win rate (battery): 0.33 · Runtime: 5330.5s
- Elo Δ vs champion: +32.0 · TrueSkill μ Δ: -3.56
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement'].
- Metrics: `{'training_rows': 1240, 'r2_global': 0.5707796263116103, 'r2_by_phase': {'early': 0.5263199159773515, 'mid': 0.7022022551694524, 'late': 0.7824031861700954}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 72 paired games (31W-2D-39L, pairwise 44%, Δelo≈-39, LLR=-1.44 in [-2.94,2.94])
- Games: 72 · Win rate (battery): 0.33 · Runtime: 5363.7s
- Elo Δ vs champion: +116.5 · TrueSkill μ Δ: -4.27
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

