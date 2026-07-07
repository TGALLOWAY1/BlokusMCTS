# Nightly Training — Approach Comparison

_Run `20260707T151216Z` · generated 2026-07-07T15:12:16.174195+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]

## Champion Elo trajectory

- Current: **1323.1** · Best: 1398.4 · Gap to best: -75.3
- Rolling avg: 1333.7 · Trend/step: 0.8953
- Elo noise floor (σ over fixed-config tail): ±31.0 (spread 91.1, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| mcts_param_sweep | Yes | 29 | 48% | -25.1 | -3.80 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |
| progressive_widening | Yes | 28 | 52% | -21.1 | -4.07 | No | HOLD progressive_widening: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'elo_improvement', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 27 | 52% | -62.7 | -3.55 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 29 paired games (14W-0D-15L, pairwise 48%, Δelo≈-12, LLR=-0.79 in [-2.94,2.94])
- Games: 29 · Win rate (battery): 0.34 · Runtime: 6580.5s
- Elo Δ vs champion: -25.1 · TrueSkill μ Δ: -3.80
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

### progressive_widening (`progressive_widening`)

- Created: yes — progressive_widening: focus search on top moves via PW (pw_c=2.0, pw_alpha=0.5) on the corrected strong maxⁿ search — re-measuring the layer post-maxⁿ-fix — [sprt] progressive_widening: inconclusive after 28 paired games (14W-1D-13L, pairwise 52%, Δelo≈+12, LLR=-0.38 in [-2.94,2.94])
- Games: 28 · Win rate (battery): 0.38 · Runtime: 6247.1s
- Elo Δ vs champion: -21.1 · TrueSkill μ Δ: -4.07
- Gate: HOLD progressive_widening: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'progressive_widening_enabled': True, 'pw_c': 2.0, 'pw_alpha': 0.5, 'learning_method': None}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 44832 snapshot rows — [sprt] heuristic_tune: inconclusive after 27 paired games (14W-0D-13L, pairwise 52%, Δelo≈+13, LLR=-0.34 in [-2.94,2.94])
- Games: 27 · Win rate (battery): 0.41 · Runtime: 6108.6s
- Elo Δ vs champion: -62.7 · TrueSkill μ Δ: -3.55
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 44832, 'r2_global': 0.3365017454081656, 'r2_by_phase': {'early': 0.25201791865280476, 'mid': 0.3853658236844436, 'late': 0.7502781453404764}, 'learning_method': 'regression'}`

