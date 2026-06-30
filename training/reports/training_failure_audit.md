# Blokus MCTS Training Failure Audit

Generated: 2026-06-29

## Executive summary

The current evidence does **not** show that the champion checkpoint itself is getting worse. It shows that the same `gen0` champion has never been promoted, while its Elo is being updated through small, time-starved, non-stationary evaluation samples. The recent decline from gen126 to gen131 is therefore best interpreted as rating noise/drift under a fixed champion rather than a learned policy regression.

The operational failure is clearer: the nightly approach-comparison run does not reliably collect enough games for every candidate to satisfy promotion gates. The latest run collected 33 total games across four candidates, with per-candidate counts of 2, 20, 2, and 9. Candidates with impressive win rates over 1–9 games correctly fail as insufficient evidence. The suspicious `HOLD td: failed []` was a reporting bug in the wrapper gate: the lower-level conservative decision did not promote the candidate, but no explicit wrapper criterion explained that fact.

## Root cause hypotheses

1. **Primary confirmed cause: evaluation starvation.** The workflow budget and full-strength MCTS game time are insufficient for four approaches to each obtain the 20-game minimum. The default `--games 10` also meant two benchmark arenas × two seeds × ten games = 40 potential games per candidate, not the 20 games described in the workflow comment.
2. **Primary confirmed reporting bug: empty promotion-failure list.** The promotion wrapper required the conservative gauntlet to promote the same candidate, but did not add that requirement as an explicit criterion. When all other wrapper criteria passed, reports could say `failed []` even though `passed=False`.
3. **Likely rating-design issue: fixed champion, mutable measurement context.** `latest.json` and `champion.json` agree that the champion is still `gen0`, and `last_promoted_generation` is `null`. Elo movement without a champion change is therefore not a direct measure of training improvement.
4. **Benchmark weakness: benchmark pool has only heuristic and random unless checkpoints exist.** With zero promotions, there are no historical champions/checkpoints, so the stable pool lacks strong fixed MCTS anchors.
5. **Remaining risk: state/history includes legacy rows.** Recent multi-agent rows are coherent, but older `history.jsonl` rows are not shaped like approach-comparison result rows. Diagnostics now count malformed/missing result-like rows instead of silently trusting the file.

## Evidence from code and state

### Champion identity and checkpoint consistency

- Current durable state reports generation `131`, Elo `1014.8475`, `last_promoted_generation: null`, and champion `{name: champion, version: gen0}`.
- `training/state/champion.json` also reports version `gen0` and has params equal to `latest.json` `champion_params` according to the new diagnostic command.
- The latest multi-agent history rows all have `promoted: false` and `winner: null`; no checkpoint promotion has occurred.

Conclusion: the same champion is being evaluated and labelled champion. The champion checkpoint is not being replaced by weaker candidates; the visible Elo fall is movement of a fixed agent's rating.

### Promotion logic

- The wrapper gate in `training/evaluation/promotion_gate.py` requires:
  - lower-level conservative gauntlet promotion of the same candidate,
  - head-to-head candidate wins over champion,
  - non-negative Elo delta,
  - TrueSkill μ delta ≥ 0.5,
  - minimum games and seeds.
- The lower-level gauntlet in `analytics/tournament/gauntlet.py` independently requires top conservative TrueSkill ranking, head-to-head over runner-up, μ margin, Wilson CI above random baseline, multiple seeds, and enough games.
- For the latest report:
  - `baseline_mcts`: 2 games, 100% vs champion, not enough games.
  - `mcts_param_sweep`: 2 games, 100% vs champion, not enough games.
  - `heuristic_tuning`: 9 games, 67% vs champion, not enough games and CI inconclusive.
  - `td_learning`: 20 games, +74.6 Elo, +0.67 μ, but the conservative gauntlet did not promote it. The old report rendered this as `failed []`; that was a diagnostic/reporting bug, not evidence that the gate promoted and was ignored.

Implemented fix: `conservative_promotes_candidate` is now an explicit wrapper criterion, so this case will report a concrete failed gate.

### Training budget and game count

- Latest run had 33 total games. The latest per-candidate counts were baseline 2, td 20, mcts_sweep 2, heuristic_tune 9.
- The workflow default claimed `10 games/arena x 2 pool seeds = 20`, but the evaluator can create two benchmark arenas, so the attempted cap was actually 40 games per candidate.
- Runtime evidence in the latest comparison record showed baseline consumed 4730 seconds for only 2 games, indicating full-strength evaluation is too slow for the existing budget and candidate roster.

Implemented workflow changes:

- Default games reduced from 10 to 5, giving 5 games × 2 arenas × 2 seeds = 20 planned games per candidate.
- Default time budget increased from 210 to 330 minutes, still under the 350-minute job timeout.
- Added uniform `--thinking-time-ms 100` so evaluation is faster and comparable across agents.
- Added `python -m training.diagnostics.audit_training_state` to the report step.

### Opponent pool / benchmark issue

The benchmark pool currently always includes `heuristic` and `random`, and includes `best_historical` only if checkpoints exist. Since there have been no promotions, there is no historical checkpoint, so the current pool is only heuristic + random plus champion and candidate in each arena.

Recommended benchmark suite:

1. `random` fixed seed anchor.
2. `heuristic` fixed deterministic anchor.
3. `baseline_mcts_fast` fixed 100 ms / fixed iterations anchor.
4. `baseline_mcts_strong` fixed 500 ms or fixed-iteration anchor, if budget allows.
5. `best_historical` once a checkpoint exists.
6. A small set of frozen historical champion configs committed under `training/benchmarks/` so the pool is not empty before the first promotion.

### Self-play / evaluation leakage

No confirmed leakage was found in the audited orchestration. Approach candidates are generated into artifacts, then evaluated against a benchmark pool through `evaluate_candidates`. The current issue is not apparent training/evaluation mixing; it is insufficient evaluation volume and noisy rating interpretation. Remaining risk: TD candidates are trained from accumulated trajectory rows, and more provenance should be recorded to prove evaluation run IDs are disjoint from training rows.

### Agent play quality

No obvious move-selection or legal-move bug was changed in this audit. The requested play-quality diagnostics should be added at the arena/game-record layer next:

- average legal moves per turn,
- invalid move count,
- pass frequency,
- final score distribution,
- early-game territory / board occupancy,
- piece usage by size,
- game length distribution.

These are intentionally not faked in this report because they require instrumenting the game engine record schema and validating runtime overhead.

### Rating system

- Elo treats a 4-player game as all pairwise score comparisons. A test now verifies that the top scorer gains Elo and the bottom scorer loses Elo.
- TrueSkill uses a Plackett-Luce multiplayer model ordered by descending score.
- A new test verifies stored per-game champion Elo samples match deterministic replay of the same game history.

No wrong-direction rating update was confirmed.

### State/history corruption

The quick diagnostic currently reports:

- champion params consistent: true,
- latest generation: 131,
- latest run games: 33,
- latest candidate game counts: baseline 2, td 20, mcts_sweep 2, heuristic_tune 9,
- malformed history rows: 0,
- duplicate history keys: 0.

It also flags older rows missing approach-comparison result-like fields. Those are legacy schema rows, not necessarily corruption, but future diagnostics should distinguish legacy vs multi-agent schema versions explicitly.

## Confirmed bugs

1. **Promotion failure explanation bug.** `HOLD td: failed []` was caused by the wrapper not surfacing the conservative gauntlet promotion requirement as a criterion. Fixed.
2. **Workflow game-count comment/config mismatch.** Default `--games 10` was described as 20 total games but could schedule 40 per candidate because there are two arenas and two seeds. Fixed by defaulting to 5 games per arena per seed.
3. **Insufficient nightly evaluation budget.** Defaults were not sufficient for all approaches to satisfy minimum games. Mitigated with longer budget and lower uniform thinking time.

## Suspicious design issues

- Elo is still presented as a champion-strength headline even when no champion promotion occurred; reports should more prominently say "fixed champion measurement drift".
- The benchmark pool has no fixed MCTS anchors before the first promotion.
- The fair per-candidate deadline prevents one candidate from consuming the entire run, but if individual games are extremely long, even fair shares can produce only 1–2 games. A per-game timeout or fixed simulation budget should be considered.
- Promotion requires both conservative gauntlet success and wrapper success. This is safe, but the report must explain both layers.

## Implemented fixes

- Added explicit `conservative_promotes_candidate` criterion to the promotion wrapper.
- Added `python -m training.diagnostics.audit_training_state` with JSON and Markdown output.
- Converted `training.diagnostics` to a package while preserving existing `python -m training.diagnostics` behavior via `__init__.py` content.
- Updated workflow defaults to target the satisfiable 20-game gate for every candidate.
- Added tests for promotion gate behavior and rating replay/direction.

## Tests added

- Candidate with positive results but insufficient games does not promote.
- Candidate with enough games and clear results promotes.
- Inconclusive head-to-head is a no-op promotion.
- Empty conservative failure list is reported with a concrete failed criterion.
- Multiplayer Elo update direction.
- History replay consistency with stored per-game Elo state.

## Quick diagnostic command

```bash
python -m training.diagnostics.audit_training_state
```

Use JSON output for automation:

```bash
python -m training.diagnostics.audit_training_state --json
```

## Recommended next fixes

1. Add frozen MCTS benchmark configs to the benchmark pool before relying on Elo trends.
2. Add per-game/turn play-quality diagnostics to self-play logs.
3. Add a schema version to `history.jsonl` records and validate only comparable rows together.
4. Consider a two-stage promotion policy: cheap 20-game screen, then a separate 60–100 game confirmation for only the leading candidate.
5. Report Elo deltas as measurement deltas unless `last_promoted_generation` changed.

## Follow-up implementation plan

### Phase 1 — make evaluation comparable before the next nightly run

- Add stable non-random MCTS anchors to the benchmark pool so candidates are no longer evaluated only beside `heuristic` and `random` before the first promotion.
- Keep the arena count bounded by pairing weak anchors in one arena and MCTS anchors in the second arena.
- Extend the state-audit diagnostic so it reports whether **all** created candidates, not just one candidate, reached the promotion game floor.

### Phase 2 — improve observability

- Report benchmark-pool health in the quick audit output.
- Distinguish legacy history rows from multi-agent approach-comparison rows when validating `history.jsonl`.
- Add play-quality counters at game-record time: invalid move count, pass frequency, legal-move counts, piece usage, game length, and score distribution.

### Phase 3 — reduce promotion latency safely

- Keep the 20-game screen as the minimum gate.
- Add an optional confirmation stage for only the leading passing candidate when budget remains.
- Promote only after the confirmation stage or after a candidate passes the existing conservative gate with enough games.

## Follow-up fixes implemented after this plan

- Benchmark pool version bumped to `benchmark_v2`.
- Added `baseline_mcts_fast` and `baseline_mcts_strong` fixed MCTS anchors derived from the champion config with heuristic rollouts, no shallow rollout cutoff, and fixed iteration rate.
- Changed candidate arena pairing so the two bounded arenas cover both weak anchors (`heuristic`, `random`) and fixed MCTS anchors (`baseline_mcts_fast`, `baseline_mcts_strong`).
- Expanded the quick audit with benchmark-pool health and all-created-candidates gate-floor checks.
