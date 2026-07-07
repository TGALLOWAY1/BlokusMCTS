# Nightly Training — Approach Comparison

_Run `20260706T195706Z` · generated 2026-07-06T19:57:06.670613+00:00_

**Promoted this run:** none
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]

## Champion Elo trajectory

- Current: **1307.3** · Best: 1398.4 · Gap to best: -91.1
- Rolling avg: 1375.1 · Trend/step: 0.8463
- Elo noise floor (σ over fixed-config tail): ±46.6 (spread 197.8, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| mcts_param_sweep | Yes | 30 | 50% | +12.7 | -1.58 | No | HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'trueskill_improvement']. |
| progressive_widening | Yes | 29 | 54% | +13.4 | -3.13 | No | HOLD progressive_widening: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'trueskill_improvement']. |
| heuristic_tuning | Yes | 29 | 55% | +12.4 | -1.60 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'trueskill_improvement']. |

## Detail

### mcts_param_sweep (`mcts_sweep`)

- Created: yes — mcts_sweep: exploration_constant 1.414 -> 1.0 over grid [0.7, 1.0, 1.414, 2.0] (on corrected strong search) — [sprt] mcts_sweep: inconclusive after 30 paired games (15W-0D-15L, pairwise 50%, Δelo≈-0, LLR=-0.60 in [-2.94,2.94])
- Games: 30 · Win rate (battery): 0.33 · Runtime: 6594.2s
- Elo Δ vs champion: +12.7 · TrueSkill μ Δ: -1.58
- Gate: HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'trueskill_improvement'].
- Metrics: `{'swept_param': 'exploration_constant', 'grid': [0.7, 1.0, 1.414, 2.0], 'chosen': 1.0, 'previous': 1.414}`

### progressive_widening (`progressive_widening`)

- Created: yes — progressive_widening: focus search on top moves via PW (pw_c=2.0, pw_alpha=0.5) on the corrected strong maxⁿ search — re-measuring the layer post-maxⁿ-fix — [sprt] progressive_widening: inconclusive after 29 paired games (15W-1D-13L, pairwise 53%, Δelo≈+24, LLR=-0.19 in [-2.94,2.94])
- Games: 29 · Win rate (battery): 0.40 · Runtime: 6271.3s
- Elo Δ vs champion: +13.4 · TrueSkill μ Δ: -3.13
- Gate: HOLD progressive_widening: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'trueskill_improvement'].
- Metrics: `{'progressive_widening_enabled': True, 'pw_c': 2.0, 'pw_alpha': 0.5, 'learning_method': None}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 44832 snapshot rows — [sprt] heuristic_tune: inconclusive after 29 paired games (16W-0D-13L, pairwise 55%, Δelo≈+36, LLR=+0.02 in [-2.94,2.94])
- Games: 29 · Win rate (battery): 0.45 · Runtime: 6250.5s
- Elo Δ vs champion: +12.4 · TrueSkill μ Δ: -1.60
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'trueskill_improvement'].
- Metrics: `{'training_rows': 44832, 'r2_global': 0.3365017454081656, 'r2_by_phase': {'early': 0.25201791865280476, 'mid': 0.3853658236844436, 'late': 0.7502781453404764}, 'learning_method': 'regression'}`

