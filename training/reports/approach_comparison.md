# Nightly Training — Approach Comparison

_Run `20260708T082317Z` · generated 2026-07-08T08:23:17.824595+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +73 TD rows (labels from `gen140@teacher:1200`) · +96 snapshot rows (corpus 288) · 2757.1s of 2700.0s budget

## Champion Elo trajectory

- Current: **1373.9** · Best: 1398.4 · Gap to best: -24.5
- Rolling avg: 1343.6 · Trend/step: 0.9732
- Elo noise floor (σ over fixed-config tail): ±33.2 (spread 91.1, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 61 | 43% | -31.6 | -8.55 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 54 | 39% | -42.6 | -6.98 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| mcts_param_sweep | Yes | 52 | 37% | -118.8 | -11.23 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 961 rows — [sprt] rich_leaf: inconclusive after 61 paired games (25W-3D-33L, pairwise 43%, Δelo≈-46, LLR=-1.39 in [-2.94,2.94])
- Games: 61 · Win rate (battery): 0.25 · Runtime: 5390.4s
- Elo Δ vs champion: -31.6 · TrueSkill μ Δ: -8.55
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 961, 'rows_by_phase': {'early': 286, 'mid': 390, 'late': 285}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.006585, 'mean_abs_td_error': 0.0363, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 288 snapshot rows — [sprt] heuristic_tune: inconclusive after 54 paired games (21W-0D-33L, pairwise 39%, Δelo≈-79, LLR=-1.74 in [-2.94,2.94])
- Games: 54 · Win rate (battery): 0.23 · Runtime: 5508.4s
- Elo Δ vs champion: -42.6 · TrueSkill μ Δ: -6.98
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 288, 'r2_global': 0.7129208705001022, 'r2_by_phase': {'early': 0.6791417950795213, 'mid': 0.7972007276200298, 'late': 0.830991516245801}, 'learning_method': 'regression'}`

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 52 paired games (19W-1D-32L, pairwise 38%, Δelo≈-89, LLR=-1.88 in [-2.94,2.94])
- Games: 52 · Win rate (battery): 0.30 · Runtime: 5260.1s
- Elo Δ vs champion: -118.8 · TrueSkill μ Δ: -11.23
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

