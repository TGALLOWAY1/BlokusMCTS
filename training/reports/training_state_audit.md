# Training State Audit

## Champion
- Identity: `champion` gen140
- Champion params consistent with champion.json: True
- Last promoted generation: 140

## Latest generation
- Generation: 140
- Run: 20260702T022345Z (100 games, Elo 1200.5590404407358)
- Recent Elo trend per recorded game/run point: 19.406

## Promotion decisions
- baseline_mcts / baseline: games=60 promoted=True reason=PROMOTE baseline: beats champion (48-12), Δμ +20.12, ΔElo +94.7, 60 games over 2 seeds.
- heuristic_tuning / heuristic_tune: games=20 promoted=False reason=HOLD heuristic_tune: failed ['conservative_promotes_candidate', 'conservative:win_rate_ci_conclusive', 'beats_champion_head_to_head', 'elo_improvement', 'trueskill_improvement'].

## Gate satisfiability
- Required: 20 games over 2 seeds
- Latest max candidate games: 60 over 2 seeds
- Any candidate satisfiable under latest counts: True
- All created candidates satisfy game floor: True
- Under game floor: {}
- Candidate game counts: {'baseline': 60, 'heuristic_tune': 20}

## Benchmark pool
- Version: benchmark_v2
- Opponents: heuristic, random, baseline_mcts_fast, baseline_mcts_strong, best_historical
- Stable MCTS anchors: 3

## State/history validation
- History rows: 140
- By kind: {'legacy_generation': 123, 'approach_comparison': 17}
- Approach-comparison rows: 17 · legacy rows: 123 · unknown rows: 0
- Malformed rows: 0
- Duplicate keys: 0
- Missing result-like fields (approach rows only): 0

