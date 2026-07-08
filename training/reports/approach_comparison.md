# Nightly Training — Approach Comparison

_Run `20260708T135509Z` · generated 2026-07-08T13:55:09.075144+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +80 TD rows (labels from `gen140@teacher:1200`) · +128 snapshot rows (corpus 416) · 2961.4s of 2700.0s budget

## Champion Elo trajectory

- Current: **1392.4** · Best: 1398.4 · Gap to best: -6.0
- Rolling avg: 1357.5 · Trend/step: 1.0098
- Elo noise floor (σ over fixed-config tail): ±33.2 (spread 91.1, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 56 | 44% | -67.8 | -8.83 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 50 | 44% | -141.5 | -7.85 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 48 | 38% | -108.4 | -10.54 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 1041 rows — [sprt] rich_leaf: inconclusive after 56 paired games (23W-4D-29L, pairwise 45%, Δelo≈-37, LLR=-1.14 in [-2.94,2.94])
- Games: 56 · Win rate (battery): 0.26 · Runtime: 5341.0s
- Elo Δ vs champion: -67.8 · TrueSkill μ Δ: -8.83
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1041, 'rows_by_phase': {'early': 306, 'mid': 419, 'late': 316}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.006701, 'mean_abs_td_error': 0.038584, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 416 snapshot rows — [sprt] heuristic_tune: inconclusive after 50 paired games (21W-2D-27L, pairwise 44%, Δelo≈-42, LLR=-1.06 in [-2.94,2.94])
- Games: 50 · Win rate (battery): 0.29 · Runtime: 5351.3s
- Elo Δ vs champion: -141.5 · TrueSkill μ Δ: -7.85
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 416, 'r2_global': 0.6365916738736255, 'r2_by_phase': {'early': 0.6067556104327269, 'mid': 0.758989431560022, 'late': 0.8210336779745138}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 48 paired games (18W-1D-29L, pairwise 39%, Δelo≈-81, LLR=-1.62 in [-2.94,2.94])
- Games: 48 · Win rate (battery): 0.30 · Runtime: 5260.4s
- Elo Δ vs champion: -108.4 · TrueSkill μ Δ: -10.54
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

