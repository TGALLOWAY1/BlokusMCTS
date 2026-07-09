# Nightly Training — Approach Comparison

_Run `20260709T094111Z` · generated 2026-07-09T09:41:11.134594+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +77 TD rows (labels from `gen140@teacher:1200`) · +60 snapshot rows (corpus 636) · 2830.9s of 2700.0s budget

## Champion Elo trajectory

- Current: **1395.9** · Best: 1409.9 · Gap to best: -13.9
- Rolling avg: 1386.2 · Trend/step: 1.1029
- Elo noise floor (σ over fixed-config tail): ±33.5 (spread 102.6, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 55 | 40% | -157.1 | -11.52 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 48 | 43% | -108.9 | -8.02 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 47 | 39% | -92.3 | -9.93 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 1276 rows — [sprt] rich_leaf: inconclusive after 55 paired games (21W-3D-31L, pairwise 41%, Δelo≈-64, LLR=-1.60 in [-2.94,2.94])
- Games: 55 · Win rate (battery): 0.22 · Runtime: 5371.2s
- Elo Δ vs champion: -157.1 · TrueSkill μ Δ: -11.52
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 1276, 'rows_by_phase': {'early': 372, 'mid': 506, 'late': 398}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.007015, 'mean_abs_td_error': 0.042947, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 636 snapshot rows — [sprt] heuristic_tune: inconclusive after 48 paired games (20W-1D-27L, pairwise 43%, Δelo≈-51, LLR=-1.15 in [-2.94,2.94])
- Games: 48 · Win rate (battery): 0.31 · Runtime: 5407.0s
- Elo Δ vs champion: -108.9 · TrueSkill μ Δ: -8.02
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 636, 'r2_global': 0.5933666770997379, 'r2_by_phase': {'early': 0.6129089703156279, 'mid': 0.7423533250597738, 'late': 0.8171620836430009}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 47 paired games (18W-1D-28L, pairwise 39%, Δelo≈-75, LLR=-1.49 in [-2.94,2.94])
- Games: 47 · Win rate (battery): 0.31 · Runtime: 5327.7s
- Elo Δ vs champion: -92.3 · TrueSkill μ Δ: -9.93
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

