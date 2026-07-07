# Training State Audit

## Champion
- Identity: `champion` gen140
- Champion params consistent with champion.json: True
- Last promoted generation: 140

## Latest generation
- Generation: 159
- Run: 20260706T195706Z (88 games, Elo 1307.269824723519)
- Recent Elo trend per recorded game/run point: -5.606

## Promotion decisions
- mcts_param_sweep / mcts_sweep: games=30 promoted=False reason=HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'trueskill_improvement'].
- progressive_widening / progressive_widening: games=29 promoted=False reason=HOLD progressive_widening: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'trueskill_improvement'].
- heuristic_tuning / heuristic_tune: games=29 promoted=False reason=HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:beats_runner_up_h2h', 'conservative:win_rate_ci_conclusive', 'trueskill_improvement'].

## Gate satisfiability
- Required: 20 games over 2 seeds
- Latest max candidate games: 30 over 2 seeds
- Any candidate satisfiable under latest counts: True
- All created candidates satisfy game floor: True
- Under game floor: {}
- Candidate game counts: {'mcts_sweep': 30, 'progressive_widening': 29, 'heuristic_tune': 29}

## Benchmark pool
- Version: benchmark_v2
- Opponents: heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical
- Stable MCTS anchors: 3

## State/history validation
- History rows: 159
- By kind: {'legacy_generation': 123, 'approach_comparison': 36}
- Approach-comparison rows: 36 · legacy rows: 123 · unknown rows: 0
- Malformed rows: 0
- Duplicate keys: 0
- Missing result-like fields (approach rows only): 0

