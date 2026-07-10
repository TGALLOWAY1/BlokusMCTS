# Nightly Training — Approach Comparison

_Run `20260709T204602Z` · generated 2026-07-09T20:46:02.680958+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +79 TD rows (labels from `gen140@teacher:1200`) · +128 snapshot rows (corpus 796) · 2867.5s of 2700.0s budget

## Champion Elo trajectory

- Current: **1360.8** · Best: 1409.9 · Gap to best: -49.1
- Rolling avg: 1386.2 · Trend/step: 1.1519
- Elo noise floor (σ over fixed-config tail): ±33.5 (spread 102.6, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 61 | 42% | +65.3 | -5.46 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 54 | 42% | -42.7 | -6.83 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 52 | 37% | -118.8 | -11.23 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 1432 rows — [sprt] rich_leaf: inconclusive after 61 paired games (25W-2D-34L, pairwise 43%, Δelo≈-52, LLR=-1.49 in [-2.94,2.94])
- Games: 61 · Win rate (battery): 0.30 · Runtime: 5364.2s
- Elo Δ vs champion: +65.3 · TrueSkill μ Δ: -5.46
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1432, 'rows_by_phase': {'early': 416, 'mid': 562, 'late': 454}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.007338, 'mean_abs_td_error': 0.044581, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 796 snapshot rows — [sprt] heuristic_tune: inconclusive after 54 paired games (22W-1D-31L, pairwise 42%, Δelo≈-58, LLR=-1.42 in [-2.94,2.94])
- Games: 54 · Win rate (battery): 0.31 · Runtime: 5450.8s
- Elo Δ vs champion: -42.7 · TrueSkill μ Δ: -6.83
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 796, 'r2_global': 0.5752149800494617, 'r2_by_phase': {'early': 0.5767925220486969, 'mid': 0.7320954047463458, 'late': 0.7784507159742341}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 52 paired games (19W-1D-32L, pairwise 38%, Δelo≈-89, LLR=-1.88 in [-2.94,2.94])
- Games: 52 · Win rate (battery): 0.30 · Runtime: 5223.2s
- Elo Δ vs champion: -118.8 · TrueSkill μ Δ: -11.23
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

