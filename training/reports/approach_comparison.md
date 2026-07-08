# Nightly Training — Approach Comparison

_Run `20260707T204421Z` · generated 2026-07-07T20:44:21.739303+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]
**Data refresh:** +76 TD rows (labels from `gen140@teacher:1200`) · +96 snapshot rows (corpus 96) · 2831.8s of 2700.0s budget

## Champion Elo trajectory

- Current: **1377.3** · Best: 1398.4 · Gap to best: -21.1
- Rolling avg: 1331.4 · Trend/step: 0.9312
- Elo noise floor (σ over fixed-config tail): ±30.9 (spread 91.1, n=20)
- Move beyond noise floor? **no (within noise)**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| rich_leaf | Yes | 92 | 43% | -172.8 | -13.40 | No | HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | No | 0 | — | — | — | No | heuristic: only 96 snapshot rows (need 200) |
| mcts_param_sweep | Yes | 79 | 42% | -133.7 | -12.76 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### rich_leaf (`rich_leaf`)

- Created: yes — rich_leaf: 45-feature TD leaf value (subset 'score') replacing rollouts; trained on 808 rows — [sprt] rich_leaf: inconclusive after 92 paired games (38W-4D-50L, pairwise 43%, Δelo≈-46, LLR=-2.08 in [-2.94,2.94])
- Games: 92 · Win rate (battery): 0.30 · Runtime: 8083.2s
- Elo Δ vs champion: -172.8 · TrueSkill μ Δ: -13.40
- Gate: HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'source_rows': 808, 'rows_by_phase': {'early': 242, 'mid': 331, 'late': 235}, 'trained_phases': {'early': True, 'mid': True, 'late': True}, 'td_loss': 0.0066, 'mean_abs_td_error': 0.035707, 'learning_method': 'temporal_difference', 'feature_subset': 'score'}`

### heuristic_tuning (`heuristic_tune`)

- Created: no — heuristic: only 96 snapshot rows (need 200)

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 79 paired games (32W-3D-44L, pairwise 42%, Δelo≈-53, LLR=-1.98 in [-2.94,2.94])
- Games: 79 · Win rate (battery): 0.32 · Runtime: 8014.7s
- Elo Δ vs champion: -133.7 · TrueSkill μ Δ: -12.76
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

