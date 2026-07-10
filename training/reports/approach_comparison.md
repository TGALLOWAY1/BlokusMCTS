# Nightly Training — Approach Comparison

_Run `20260710T021746Z` · generated 2026-07-10T02:17:46.753287+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +78 TD rows (labels from `gen140@teacher:1200`) · +64 snapshot rows (corpus 860) · 2712.0s of 2700.0s budget

## Champion Elo trajectory

- Current: **1358.4** · Best: 1409.9 · Gap to best: -51.4
- Rolling avg: 1386.1 · Trend/step: 1.1653
- Elo noise floor (σ over fixed-config tail): ±33.0 (spread 102.6, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 60 | 47% | +30.7 | -4.53 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 52 | 37% | -124.4 | -10.32 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 51 | 38% | -64.0 | -9.05 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 1510 rows — [sprt] rich_leaf: inconclusive after 60 paired games (27W-3D-30L, pairwise 48%, Δelo≈-17, LLR=-0.78 in [-2.94,2.94])
- Games: 60 · Win rate (battery): 0.33 · Runtime: 5427.2s
- Elo Δ vs champion: +30.7 · TrueSkill μ Δ: -4.53
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1510, 'rows_by_phase': {'early': 438, 'mid': 591, 'late': 481}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.009508, 'mean_abs_td_error': 0.049808, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 860 snapshot rows — [sprt] heuristic_tune: inconclusive after 52 paired games (19W-1D-32L, pairwise 38%, Δelo≈-89, LLR=-1.88 in [-2.94,2.94])
- Games: 52 · Win rate (battery): 0.27 · Runtime: 5384.7s
- Elo Δ vs champion: -124.4 · TrueSkill μ Δ: -10.32
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 860, 'r2_global': 0.5872774055990098, 'r2_by_phase': {'early': 0.5868788289318725, 'mid': 0.739686731663407, 'late': 0.7866309153391726}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 51 paired games (19W-1D-31L, pairwise 38%, Δelo≈-83, LLR=-1.75 in [-2.94,2.94])
- Games: 51 · Win rate (battery): 0.30 · Runtime: 5403.4s
- Elo Δ vs champion: -64.0 · TrueSkill μ Δ: -9.05
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

