# Nightly Training — Approach Comparison

_Run `20260710T150635Z` · generated 2026-07-10T15:06:35.698011+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +116 TD rows (labels from `gen140@teacher:1200`) · +64 snapshot rows (corpus 1020) · 2719.4s of 2700.0s budget

## Champion Elo trajectory

- Current: **1284.1** · Best: 1409.9 · Gap to best: -125.8
- Rolling avg: 1358.6 · Trend/step: 1.1724
- Elo noise floor (σ over fixed-config tail): ±36.9 (spread 125.8, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 80 | 45% | -90.3 | -8.75 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 70 | 46% | +93.8 | -1.32 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 69 | 42% | +60.4 | -7.62 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 1700 rows — [sprt] rich_leaf: inconclusive after 80 paired games (34W-4D-42L, pairwise 45%, Δelo≈-35, LLR=-1.53 in [-2.94,2.94])
- Games: 80 · Win rate (battery): 0.33 · Runtime: 5456.1s
- Elo Δ vs champion: -90.3 · TrueSkill μ Δ: -8.75
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1700, 'rows_by_phase': {'early': 493, 'mid': 662, 'late': 545}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.006954, 'mean_abs_td_error': 0.045717, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 1020 snapshot rows — [sprt] heuristic_tune: inconclusive after 70 paired games (31W-2D-37L, pairwise 46%, Δelo≈-30, LLR=-1.19 in [-2.94,2.94])
- Games: 70 · Win rate (battery): 0.34 · Runtime: 5432.0s
- Elo Δ vs champion: +93.8 · TrueSkill μ Δ: -1.32
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement'].
- Metrics: `{'training_rows': 1020, 'r2_global': 0.5769981278158323, 'r2_by_phase': {'early': 0.546385733074361, 'mid': 0.7106026858949928, 'late': 0.7829950558458972}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 69 paired games (28W-2D-39L, pairwise 42%, Δelo≈-56, LLR=-1.77 in [-2.94,2.94])
- Games: 69 · Win rate (battery): 0.33 · Runtime: 5367.0s
- Elo Δ vs champion: +60.4 · TrueSkill μ Δ: -7.62
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

