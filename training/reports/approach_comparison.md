# Nightly Training — Approach Comparison

_Run `20260709T021000Z` · generated 2026-07-09T02:10:00.571123+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +76 TD rows (labels from `gen140@teacher:1200`) · +64 snapshot rows (corpus 576) · 2752.7s of 2700.0s budget

## Champion Elo trajectory

- Current: **1409.9** · Best: 1409.9 · Gap to best: 0.0
- Rolling avg: 1371.2 · Trend/step: 1.0708
- Elo noise floor (σ over fixed-config tail): ±33.6 (spread 102.6, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 59 | 45% | -9.0 | -7.38 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 51 | 40% | -40.6 | -6.93 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 50 | 37% | -142.3 | -11.96 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 1199 rows — [sprt] rich_leaf: inconclusive after 59 paired games (25W-4D-30L, pairwise 46%, Δelo≈-30, LLR=-1.04 in [-2.94,2.94])
- Games: 59 · Win rate (battery): 0.26 · Runtime: 5447.0s
- Elo Δ vs champion: -9.0 · TrueSkill μ Δ: -7.38
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1199, 'rows_by_phase': {'early': 350, 'mid': 477, 'late': 372}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.006775, 'mean_abs_td_error': 0.041191, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 576 snapshot rows — [sprt] heuristic_tune: inconclusive after 51 paired games (20W-1D-30L, pairwise 40%, Δelo≈-69, LLR=-1.52 in [-2.94,2.94])
- Games: 51 · Win rate (battery): 0.29 · Runtime: 5367.9s
- Elo Δ vs champion: -40.6 · TrueSkill μ Δ: -6.93
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 576, 'r2_global': 0.6066370021708452, 'r2_by_phase': {'early': 0.6215655134572886, 'mid': 0.744106515591376, 'late': 0.8142454971418335}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 50 paired games (18W-1D-31L, pairwise 37%, Δelo≈-92, LLR=-1.86 in [-2.94,2.94])
- Games: 50 · Win rate (battery): 0.29 · Runtime: 5337.7s
- Elo Δ vs champion: -142.3 · TrueSkill μ Δ: -11.96
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

