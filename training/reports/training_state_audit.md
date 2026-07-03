# Training State Audit

## Champion
- Identity: `champion` gen140
- Champion params consistent with champion.json: True
- Last promoted generation: 140

## Latest generation
- Generation: 144
- Run: 20260703T015513Z (40 games, Elo 1389.7891263868444)
- Recent Elo trend per recorded game/run point: 23.102

## Promotion decisions
- baseline_mcts / baseline: games=20 promoted=False reason=HOLD baseline: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- heuristic_tuning / heuristic_tune: games=20 promoted=False reason=HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].

## Gate satisfiability
- Required: 20 games over 2 seeds
- Latest max candidate games: 20 over 2 seeds
- Any candidate satisfiable under latest counts: True
- All created candidates satisfy game floor: True
- Under game floor: {}
- Candidate game counts: {'baseline': 20, 'heuristic_tune': 20}

## Benchmark pool
- Version: benchmark_v2
- Opponents: heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical
- Stable MCTS anchors: 3

## State/history validation
- History rows: 144
- By kind: {'legacy_generation': 123, 'approach_comparison': 21}
- Approach-comparison rows: 21 · legacy rows: 123 · unknown rows: 0
- Malformed rows: 0
- Duplicate keys: 0
- Missing result-like fields (approach rows only): 0

