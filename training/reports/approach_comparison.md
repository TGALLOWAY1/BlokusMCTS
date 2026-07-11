# Nightly Training — Approach Comparison

_Run `20260711T132811Z` · generated 2026-07-11T13:28:11.272057+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +73 TD rows (labels from `gen140@teacher:1200`) · +96 snapshot rows (corpus 1464) · 2821.0s of 2700.0s budget

## Champion Elo trajectory

- Current: **1407.5** · Best: 1418.1 · Gap to best: -10.5
- Rolling avg: 1354.9 · Trend/step: 1.2301
- Elo noise floor (σ over fixed-config tail): ±43.9 (spread 146.9, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 57 | 42% | -59.8 | -7.42 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 50 | 39% | -146.8 | -10.23 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 49 | 38% | -126.2 | -11.25 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 2042 rows — [sprt] rich_leaf: inconclusive after 57 paired games (23W-2D-32L, pairwise 42%, Δelo≈-55, LLR=-1.47 in [-2.94,2.94])
- Games: 57 · Win rate (battery): 0.27 · Runtime: 5392.1s
- Elo Δ vs champion: -59.8 · TrueSkill μ Δ: -7.42
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 2042, 'rows_by_phase': {'early': 591, 'mid': 788, 'late': 663}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.006957, 'mean_abs_td_error': 0.045112, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 1464 snapshot rows — [sprt] heuristic_tune: inconclusive after 50 paired games (19W-1D-30L, pairwise 39%, Δelo≈-78, LLR=-1.63 in [-2.94,2.94])
- Games: 50 · Win rate (battery): 0.28 · Runtime: 5384.5s
- Elo Δ vs champion: -146.8 · TrueSkill μ Δ: -10.23
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 1464, 'r2_global': 0.5728551705173878, 'r2_by_phase': {'early': 0.5365994517663655, 'mid': 0.7016808344811045, 'late': 0.7852704289667212}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 49 paired games (18W-1D-30L, pairwise 38%, Δelo≈-87, LLR=-1.74 in [-2.94,2.94])
- Games: 49 · Win rate (battery): 0.30 · Runtime: 5319.1s
- Elo Δ vs champion: -126.2 · TrueSkill μ Δ: -11.25
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

