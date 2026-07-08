# Training State Audit

## Champion
- Identity: `champion` gen140
- Champion params consistent with champion.json: True
- Last promoted generation: 140

## Latest generation
- Generation: 164
- Run: 20260708T021620Z (164 games, Elo 1320.6496680510268)
- Recent Elo trend per recorded game/run point: -7.836

## Promotion decisions
- rich_leaf / rich_leaf: games=87 promoted=False reason=HOLD rich_leaf: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].
- heuristic_tuning / heuristic_tune: games=0 promoted=False reason=heuristic: only 192 snapshot rows (need 200)
- mcts_param_sweep / mcts_sweep: games=77 promoted=False reason=HOLD mcts_sweep: failed ['conservative_promotes_candidate', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].

## Gate satisfiability
- Required: 20 games over 2 seeds
- Latest max candidate games: 87 over 2 seeds
- Any candidate satisfiable under latest counts: True
- All created candidates satisfy game floor: True
- Under game floor: {}
- Candidate game counts: {'rich_leaf': 87, 'heuristic_tune': 0, 'mcts_sweep': 77}

## Benchmark pool
- Version: benchmark_v2
- Opponents: heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical
- Stable MCTS anchors: 3

## State/history validation
- History rows: 164
- By kind: {'legacy_generation': 123, 'approach_comparison': 41}
- Approach-comparison rows: 41 · legacy rows: 123 · unknown rows: 0
- Malformed rows: 0
- Duplicate keys: 0
- Missing result-like fields (approach rows only): 0

