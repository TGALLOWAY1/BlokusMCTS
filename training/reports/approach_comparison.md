# Nightly Training — Approach Comparison

_Run `20260709T151326Z` · generated 2026-07-09T15:13:26.645968+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +77 TD rows (labels from `gen140@teacher:1200`) · +32 snapshot rows (corpus 668) · 2744.7s of 2700.0s budget

## Champion Elo trajectory

- Current: **1405.3** · Best: 1409.9 · Gap to best: -4.6
- Rolling avg: 1392.5 · Trend/step: 1.1364
- Elo noise floor (σ over fixed-config tail): ±33.8 (spread 102.6, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 56 | 42% | -35.8 | -8.47 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 48 | 38% | -119.7 | -8.72 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 49 | 38% | -126.2 | -11.25 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 1353 rows — [sprt] rich_leaf: inconclusive after 56 paired games (22W-3D-31L, pairwise 42%, Δelo≈-56, LLR=-1.49 in [-2.94,2.94])
- Games: 56 · Win rate (battery): 0.25 · Runtime: 5445.6s
- Elo Δ vs champion: -35.8 · TrueSkill μ Δ: -8.47
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1353, 'rows_by_phase': {'early': 394, 'mid': 535, 'late': 424}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.00698, 'mean_abs_td_error': 0.042981, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 668 snapshot rows — [sprt] heuristic_tune: inconclusive after 48 paired games (18W-1D-29L, pairwise 39%, Δelo≈-81, LLR=-1.62 in [-2.94,2.94])
- Games: 48 · Win rate (battery): 0.23 · Runtime: 5373.9s
- Elo Δ vs champion: -119.7 · TrueSkill μ Δ: -8.72
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 668, 'r2_global': 0.5963643510095015, 'r2_by_phase': {'early': 0.606713674057397, 'mid': 0.746695048876352, 'late': 0.8119688998041619}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 49 paired games (18W-1D-30L, pairwise 38%, Δelo≈-87, LLR=-1.74 in [-2.94,2.94])
- Games: 49 · Win rate (battery): 0.30 · Runtime: 5397.0s
- Elo Δ vs champion: -126.2 · TrueSkill μ Δ: -11.25
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

