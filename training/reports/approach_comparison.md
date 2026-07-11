# Nightly Training — Approach Comparison

_Run `20260710T203915Z` · generated 2026-07-10T20:39:15.920933+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +77 TD rows (labels from `gen140@teacher:1200`) · +128 snapshot rows (corpus 1148) · 2734.3s of 2700.0s budget

## Champion Elo trajectory

- Current: **1393.8** · Best: 1409.9 · Gap to best: -16.0
- Rolling avg: 1356.3 · Trend/step: 1.1956
- Elo noise floor (σ over fixed-config tail): ±36.9 (spread 125.8, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 67 | 46% | +19.7 | -3.11 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 58 | 44% | -45.8 | -6.65 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 57 | 36% | -172.5 | -17.09 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 1777 rows — [sprt] rich_leaf: inconclusive after 67 paired games (30W-2D-35L, pairwise 46%, Δelo≈-26, LLR=-1.05 in [-2.94,2.94])
- Games: 67 · Win rate (battery): 0.31 · Runtime: 5424.9s
- Elo Δ vs champion: +19.7 · TrueSkill μ Δ: -3.11
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1777, 'rows_by_phase': {'early': 515, 'mid': 689, 'late': 573}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.011991, 'mean_abs_td_error': 0.05652, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 1148 snapshot rows — [sprt] heuristic_tune: inconclusive after 58 paired games (25W-1D-32L, pairwise 44%, Δelo≈-42, LLR=-1.21 in [-2.94,2.94])
- Games: 58 · Win rate (battery): 0.29 · Runtime: 5394.6s
- Elo Δ vs champion: -45.8 · TrueSkill μ Δ: -6.65
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 1148, 'r2_global': 0.5682755261191035, 'r2_by_phase': {'early': 0.5265567816870288, 'mid': 0.7003771081637896, 'late': 0.7823227665312322}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 57 paired games (20W-1D-36L, pairwise 36%, Δelo≈-100, LLR=-2.26 in [-2.94,2.94])
- Games: 57 · Win rate (battery): 0.28 · Runtime: 5350.1s
- Elo Δ vs champion: -172.5 · TrueSkill μ Δ: -17.09
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

