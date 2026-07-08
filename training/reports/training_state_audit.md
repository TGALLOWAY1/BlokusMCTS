# Training State Audit

## Champion
- Identity: `champion` gen140
- Champion params consistent with champion.json: True
- Last promoted generation: 140

## Latest generation
- Generation: 166
- Run: 20260708T135509Z (154 games, Elo 1392.3923911328511)
- Recent Elo trend per recorded game/run point: 0.611

## Promotion decisions
- rich_leaf / rich_leaf: games=56 promoted=False reason=HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- heuristic_tuning / heuristic_tune: games=50 promoted=False reason=HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- mcts_param_sweep / mcts_sweep: games=48 promoted=False reason=HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].

## Gate satisfiability
- Required: 20 games over 2 seeds
- Latest max candidate games: 56 over 2 seeds
- Any candidate satisfiable under latest counts: True
- All created candidates satisfy game floor: True
- Under game floor: {}
- Candidate game counts: {'rich_leaf': 56, 'heuristic_tune': 50, 'mcts_sweep': 48}

## Benchmark pool
- Version: benchmark_v2
- Opponents: heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical
- Stable MCTS anchors: 3

## State/history validation
- History rows: 166
- By kind: {'legacy_generation': 123, 'approach_comparison': 43}
- Approach-comparison rows: 43 · legacy rows: 123 · unknown rows: 0
- Malformed rows: 0
- Duplicate keys: 0
- Missing result-like fields (approach rows only): 0

