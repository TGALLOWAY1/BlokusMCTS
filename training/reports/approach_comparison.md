# Nightly Training — Approach Comparison

_Run `20260711T075529Z` · generated 2026-07-11T07:55:29.365327+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +77 TD rows (labels from `gen140@teacher:1200`) · +128 snapshot rows (corpus 1368) · 2922.6s of 2700.0s budget

## Champion Elo trajectory

- Current: **1418.1** · Best: 1418.1 · Gap to best: 0.0
- Rolling avg: 1350.3 · Trend/step: 1.2056
- Elo noise floor (σ over fixed-config tail): ±43.0 (spread 146.9, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 56 | 43% | -33.4 | -6.47 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 50 | 39% | -145.7 | -10.22 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 49 | 38% | -126.2 | -11.25 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 1969 rows — [sprt] rich_leaf: inconclusive after 56 paired games (23W-2D-31L, pairwise 43%, Δelo≈-50, LLR=-1.34 in [-2.94,2.94])
- Games: 56 · Win rate (battery): 0.28 · Runtime: 5346.6s
- Elo Δ vs champion: -33.4 · TrueSkill μ Δ: -6.47
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1969, 'rows_by_phase': {'early': 569, 'mid': 759, 'late': 641}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.008906, 'mean_abs_td_error': 0.049254, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 1368 snapshot rows — [sprt] heuristic_tune: inconclusive after 50 paired games (19W-1D-30L, pairwise 39%, Δelo≈-78, LLR=-1.63 in [-2.94,2.94])
- Games: 50 · Win rate (battery): 0.26 · Runtime: 5375.9s
- Elo Δ vs champion: -145.7 · TrueSkill μ Δ: -10.22
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 1368, 'r2_global': 0.5683256993979396, 'r2_by_phase': {'early': 0.5303202289364941, 'mid': 0.6969582125619713, 'late': 0.7811359841296063}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 49 paired games (18W-1D-30L, pairwise 38%, Δelo≈-87, LLR=-1.74 in [-2.94,2.94])
- Games: 49 · Win rate (battery): 0.30 · Runtime: 5317.2s
- Elo Δ vs champion: -126.2 · TrueSkill μ Δ: -11.25
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

