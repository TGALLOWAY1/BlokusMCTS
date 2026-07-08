# Nightly Training — Approach Comparison

_Run `20260708T021620Z` · generated 2026-07-08T02:16:20.417320+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +80 TD rows (labels from `gen140@teacher:1200`) · +96 snapshot rows (corpus 192) · 2827.3s of 2700.0s budget

## Champion Elo trajectory

- Current: **1320.6** · Best: 1398.4 · Gap to best: -77.8
- Rolling avg: 1334.1 · Trend/step: 0.942
- Elo noise floor (σ over fixed-config tail): ±33.5 (spread 91.1, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 87 | 45% | -44.8 | -8.65 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | No | 0 | — | — | — | No | heuristic: only 192 snapshot rows (need 200) |
| mcts_param_sweep | Yes | 77 | 43% | -32.4 | -9.26 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 888 rows — [sprt] rich_leaf: inconclusive after 87 paired games (38W-3D-46L, pairwise 45%, Δelo≈-32, LLR=-1.55 in [-2.94,2.94])
- Games: 87 · Win rate (battery): 0.31 · Runtime: 8149.3s
- Elo Δ vs champion: -44.8 · TrueSkill μ Δ: -8.65
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 888, 'rows_by_phase': {'early': 264, 'mid': 360, 'late': 264}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.006766, 'mean_abs_td_error': 0.038489, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: no — heuristic: only 192 snapshot rows (need 200)

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 77 paired games (32W-3D-42L, pairwise 44%, Δelo≈-45, LLR=-1.73 in [-2.94,2.94])
- Games: 77 · Win rate (battery): 0.32 · Runtime: 8038.5s
- Elo Δ vs champion: -32.4 · TrueSkill μ Δ: -9.26
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

