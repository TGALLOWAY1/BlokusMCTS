# Training State Audit

## Champion
- Identity: `champion` gen0
- Champion params consistent with champion.json: True
- Last promoted generation: None

## Latest generation
- Generation: 134
- Run: 20260630T143130Z (49 games, Elo 1220.3197587086327)
- Recent Elo trend per recorded game/run point: 5.269

## Promotion decisions
- baseline_mcts / baseline: games=11 promoted=False reason=HOLD baseline: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'beats_champion_head_to_head', 'elo_improvement', 'min_total_games'].
- td_learning / td: games=15 promoted=False reason=HOLD td: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement', 'min_total_games'].
- mcts_param_sweep / mcts_sweep: games=9 promoted=False reason=HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'min_total_games'].
- heuristic_tuning / heuristic_tune: games=14 promoted=False reason=HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'conservative:enough_games', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement', 'min_total_games'].

## Gate satisfiability
- Required: 20 games over 2 seeds
- Latest max candidate games: 15 over 2 seeds
- Any candidate satisfiable under latest counts: False
- All created candidates satisfy game floor: False
- Under game floor: {'baseline': 11, 'td': 15, 'mcts_sweep': 9, 'heuristic_tune': 14}
- Candidate game counts: {'baseline': 11, 'td': 15, 'mcts_sweep': 9, 'heuristic_tune': 14}

## Benchmark pool
- Version: benchmark_v2
- Opponents: heuristic, random, baseline_mcts_fast, baseline_mcts_strong
- Stable MCTS anchors: 2

## State/history validation
- History rows: 134
- By kind: {'legacy_generation': 123, 'approach_comparison': 11}
- Approach-comparison rows: 11 · legacy rows: 123 · unknown rows: 0
- Malformed rows: 0
- Duplicate keys: 0
- Missing result-like fields (approach rows only): 0

