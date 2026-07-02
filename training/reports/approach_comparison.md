# Nightly Training — Approach Comparison

_Run `20260702T022345Z` · generated 2026-07-02T02:23:45.735952+00:00_

**Promoted this run:** baseline
**Two-stage promotion:** confirmation passed ✅ for `baseline` — screen 20 games → confirm 60/60 games. PROMOTE baseline: beats champion (48-12), Δμ +20.12, ΔElo +94.7, 60 games over 2 seeds.
**Benchmark pool:** benchmark_v2 — opponents heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical; seeds [20260620, 20260621]

## Champion Elo trajectory

- Current: **1200.6** · Best: 1379.2 · Gap to best: -178.7
- Rolling avg: 1219.3 · Trend/step: -0.7673
- Elo noise floor (σ over fixed-config tail): ±84.5 (spread 244.2, n=20)
- Move beyond noise floor? **yes**

## Approaches

| Approach | Created | Games | Win% vs Champ | Elo Δ | TrueSkill Δ | Promoted | Reason |
|---|---|---|---|---|---|---|---|
| baseline_mcts | Yes | 60 | 80% | +94.7 | +20.12 | Yes | PROMOTE baseline: beats champion (48-12), Δμ +20.12, ΔElo +94.7, 60 games over 2 seeds. |
| heuristic_tuning | Yes | 20 | 45% | -2.5 | -2.00 | No | HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement']. |

## Detail

### baseline_mcts (`baseline`)

- Created: yes — baseline: corrected weak-champion search settings (greedy-sample rollouts, cutoff 12, RAVE/minimax off, move ordering on)
- Games: 60 · Win rate (battery): 0.66 · Runtime: 11059.4s
- Elo Δ vs champion: +94.7 · TrueSkill μ Δ: +20.12
- Gate: PROMOTE baseline: beats champion (48-12), Δμ +20.12, ΔElo +94.7, 60 games over 2 seeds.
- Metrics: `{'overrides': {'rollout_policy': 'greedy_sample', 'rollout_cutoff_depth': 12, 'adaptive_rollout_depth_enabled': False, 'iterations_per_ms': 0.5, 'rave_enabled': False, 'minimax_backup_alpha': 0.0, 'heuristic_move_ordering': True, 'num_workers': 1}}`

### heuristic_tuning (`heuristic_tune`)

- Created: yes — heuristic: re-fit Layer-6 weights from 44832 snapshot rows
- Games: 20 · Win rate (battery): 0.30 · Runtime: 2638.5s
- Elo Δ vs champion: -2.5 · TrueSkill μ Δ: -2.00
- Gate: HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- Metrics: `{'training_rows': 44832, 'r2_global': 0.3365017454081656, 'r2_by_phase': {'early': 0.25201791865280476, 'mid': 0.3853658236844436, 'late': 0.7502781453404764}, 'learning_method': 'regression'}`

