# Training State Audit

## Champion
- Identity: `champion` gen140
- Champion params consistent with champion.json: True
- Last promoted generation: 140

## Latest generation
- Generation: 176
- Run: 20260711T021059Z (229 games, Elo 1271.1489606670468)
- Recent Elo trend per recorded game/run point: -9.254

## Promotion decisions
- rich_leaf / rich_leaf: games=85 promoted=False reason=HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- heuristic_tuning / heuristic_tune: games=72 promoted=False reason=HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement'].
- mcts_param_sweep / mcts_sweep: games=72 promoted=False reason=HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'trueskill_improvement'].

## Gate satisfiability
- Required: 20 games over 2 seeds
- Latest max candidate games: 85 over 2 seeds
- Any candidate satisfiable under latest counts: True
- All created candidates satisfy game floor: True
- Under game floor: {}
- Candidate game counts: {'rich_leaf': 85, 'heuristic_tune': 72, 'mcts_sweep': 72}

## Benchmark pool
- Version: benchmark_v2
- Opponents: heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical
- Stable MCTS anchors: 3

## State/history validation
- History rows: 176
- By kind: {'legacy_generation': 123, 'approach_comparison': 53}
- Approach-comparison rows: 53 · legacy rows: 123 · unknown rows: 0
- Malformed rows: 0
- Duplicate keys: 0
- Missing result-like fields (approach rows only): 0

