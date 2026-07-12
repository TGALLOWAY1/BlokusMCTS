# Nightly Training — Approach Comparison

_Run `20260711T190001Z` · generated 2026-07-11T19:00:01.605839+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +78 TD rows (labels from `gen140@teacher:1200`) · +64 snapshot rows (corpus 1528) · 2912.4s of 2700.0s budget

## Champion Elo trajectory

- Current: **1388.6** · Best: 1418.1 · Gap to best: -29.5
- Rolling avg: 1375.8 · Trend/step: 1.2471
- Elo noise floor (σ over fixed-config tail): ±42.5 (spread 146.9, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 56 | 39% | -60.1 | -9.62 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 48 | 40% | -117.3 | -9.71 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 48 | 38% | -108.4 | -10.54 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 2120 rows — [sprt] rich_leaf: inconclusive after 56 paired games (21W-2D-33L, pairwise 39%, Δelo≈-76, LLR=-1.82 in [-2.94,2.94])
- Games: 56 · Win rate (battery): 0.25 · Runtime: 5426.3s
- Elo Δ vs champion: -60.1 · TrueSkill μ Δ: -9.62
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 2120, 'rows_by_phase': {'early': 613, 'mid': 819, 'late': 688}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.008608, 'mean_abs_td_error': 0.050075, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 1528 snapshot rows — [sprt] heuristic_tune: inconclusive after 48 paired games (19W-0D-29L, pairwise 40%, Δelo≈-73, LLR=-1.47 in [-2.94,2.94])
- Games: 48 · Win rate (battery): 0.30 · Runtime: 5312.5s
- Elo Δ vs champion: -117.3 · TrueSkill μ Δ: -9.71
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 1528, 'r2_global': 0.572315694872479, 'r2_by_phase': {'early': 0.5450159665155492, 'mid': 0.6894504765208727, 'late': 0.7856898660626479}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 48 paired games (18W-1D-29L, pairwise 39%, Δelo≈-81, LLR=-1.62 in [-2.94,2.94])
- Games: 48 · Win rate (battery): 0.30 · Runtime: 5311.3s
- Elo Δ vs champion: -108.4 · TrueSkill μ Δ: -10.54
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

