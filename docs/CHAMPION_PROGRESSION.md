# Champion Progression

**Status as of 2026-06-14.** Single source of truth for the agent storyline.
If a doc disagrees with this page, this page is right.

## Current Status

- **`champion_v2` is the current validated champion.** Promoted 2026-06-14
  after Night-1 reset run (`20260614_135743_ca1ba49d`). Gate: Δμ=7.39 ≥ 0.5
  AND pairwise 38-22 vs `champion_v1`. TrueSkill μ=39.38 (conservative 18.72).
- `champion_v1` is a **failed integrated candidate** kept as a regression
  baseline. Night-1 data confirms it loses 22-38 to `champion_minimal` and
  scores μ=32.00 vs μ=39.38.
- **`champion_v2` ties `pool_peer_500ms` 30-30** — this is the peer gap that
  Night 2 (L8 sweep) aims to close. The tie means the correct headline framing
  is "v1 cleanup complete, peer gap narrowed but not closed."
- **Headline "beats humans" claim is NOT YET valid.** Wilson-95 LB vs
  `pool_heuristic` is 0.819 at 60 games (1 seed), which looks promising but
  the roadmap requires ≥240 games across ≥4 seeds with LB ≥ 0.65 before the
  headline can be made. That is Night 4.

## Agent Lineage

| Stage | Agent | Role | Status | Source |
|---|---|---|---|---|
| 0 | `random` | Pure-random baseline | Reference | `agents/random_agent.py` |
| 0 | `pool_heuristic` | Heuristic / human proxy (no lookahead) | Reference | `agents/heuristic_agent.py` |
| 3 | `pool_l45_100ms` | Layer 4 + Layer 5 MCTS at 100 ms / 50 iter | Reference (low tier) | arena pool |
| 5 | `pool_peer_500ms` | MCTS same time budget as champion candidates, no opponent modeling | **Active peer to beat** — currently outperforms `champion_v1` | arena pool |
| – | `champion_v1` | Full-stack MCTS w/ phase weights, opponent modeling, adaptive C, sufficiency/loss-avoidance | **Failed full-stack candidate** — promoted prematurely with null metrics, lost to `pool_peer_500ms` | `config/champion_arena_params.json`, `data/champion_registry.json` |
| – | `champion_minimal` | Validated-only layers + L8 root parallelization | **Promoted to v2 on 2026-06-14** — Night-1 gate PASS (Δμ=7.39, pairwise 38-22 vs v1) | `config/champion_minimal_params.json` |
| – | `champion_v2` | Same config as champion_minimal | **Current champion** — promoted 2026-06-14 after Night-1 reset, μ=39.38 | `data/champion_registry.json` v2 entry |
| – | `champion_v3` | _placeholder_ | Reserved for Night-3 refit-weight candidate | TBD |

## Why `champion_v1` is the failed candidate

`champion_v1` was registered on 2026-04-29 with every win-rate, TrueSkill,
and score field set to `null` (see `data/champion_registry.json`). It was
not validated before being declared the champion. The arena evidence from
PRs #146–#148 then made the gap visible:

| Run | Games | `champion_v1` WR | `pool_peer_500ms` WR | Pairwise (champ-vs-peer) |
|---|---|---|---|---|
| v1 gauntlet, seed 20260503 | 40 | 0.375 | 0.525 | 16–24 (champ loses) |
| v2 gauntlet, seed 20260601 (May 14) | 60 | 0.383 | 0.492 | 26–34 (champ loses) |

TrueSkill on the May 14 run: `pool_peer_500ms` μ−3σ = **29.45** vs
`champion` μ−3σ = **19.65** — a Δμ ≈ 10 in favor of the simpler peer at
the same 500 ms budget.

`champion_v1` packs several features that the layer experiments had
already flagged as harmful or expensive:

| Feature in `champion_v1` | Layer verdict (from `KEY_FINDINGS.md`) |
|---|---|
| `state_eval_phase_weights` (early/mid/late) | L6: **0% WR** in 25-game eval. Phase transitions have inverted signs at low R². |
| `adaptive_exploration_enabled` | L9: **8% WR**. Double-counts exploration when RAVE is already on. |
| `opponent_modeling_enabled` + `alliance_detection_enabled` + `kingmaker_detection_enabled` | L7: "no reliable competitive advantage", **2.4× slower** at low iteration budgets. |
| `sufficiency_threshold_enabled` + `loss_avoidance_enabled` | L9: inconclusive, confounded by adaptive C. |
| _missing_ `num_workers: 2, parallel_strategy: "root"` | L8: root-2w was **46% WR / TrueSkill #1**, the single largest measured win. v1 deploys none of it. |

The cleanest reading: v1 added bloat that didn't pay rent and dropped the
one layer that did. The arena loss is a configuration / integration
failure, not evidence that MCTS improvements don't work.

## What the v1 arena data IS useful for

Treat PRs #146–#148 as diagnostic, not promotional. The recorded
artifacts remain useful for:

- **Regression evidence** that the v1 config is worse than a same-budget
  peer (the case for resetting the champion).
- **TrueSkill anchors** for the shared pool: `pool_peer_500ms` μ=50.55,
  `pool_heuristic` μ=12.58, `pool_l45_100ms` μ=−2.51 (May 14 run).
- **~3,200 `se_*`-enriched snapshot rows** for evaluator refit input
  (Night 3 of the roadmap).
- **Pairwise pool-vs-pool baselines** that future candidate runs can be
  scored against without re-running the entire pool.

They are explicitly **not** useful as proof that the champion is strong,
beats heuristic baselines by a defensible margin, or is ready for a
human-play headline.

## Promotion rule

> No agent may be called "champion" in docs, in `data/champion_registry.json`,
> on the frontend, or in any report unless it has passed the gates below.

The promoted entry must record non-null values for every metric in the
checklist:

- `promotion_run_id` — the arena run that produced the decision
- `games_played` — at least 60 head-to-head games at the deciding budget
- `pairwise_vs_previous` — outright-win count vs the previous champion or
  incumbent candidate; must be ≥ losses by a margin consistent with
  Δμ ≥ 0.5 TrueSkill **and** a positive pairwise record
- `pairwise_vs_pool_peer_500ms` — outright-win record at the same time
  budget. A loss here is not automatically disqualifying, but must be
  documented; a candidate that loses to the peer cannot be called the
  headline champion.
- `pairwise_vs_pool_heuristic` — outright-win record. Wilson-95 lower
  bound on WR must be reported; ≥0.65 is required before any
  "beats humans" framing.
- `trueskill_mu`, `trueskill_sigma`, `trueskill_conservative` (μ−3σ) on
  the promotion run, with `converged: true` ideally, otherwise flagged
- `gate_pass: bool` — whether all the above met the thresholds in the
  roadmap. If false, the registry entry must include the
  `failure_reason`.
- `known_limitations` — free-text list of caveats the next iteration
  needs to address

If the current code does not make this straightforward to write into
`data/champion_registry.json`, the registry change is a **TODO** rather
than a blocker for the doc.

## Next experiment (Night 2)

Night-1 reset is **complete** (`20260614_135743_ca1ba49d`, gate PASS, v2 promoted).

Night 2 is the Layer 8 parallelization sweep: `num_workers ∈ {1,4,8}` ×
`thinking_time_ms ∈ {500,2000,5000}`, 24 games each, opponents =
`pool_heuristic` + `pool_l9_partial_200ms`. Goal: find the wall-clock-efficient
parallelization point, then carry the winning cell into Night 3 refit.

Key constraint carried into Night 2: champion_v2 ties `pool_peer_500ms` 30-30
at 500 ms / 2 workers. Any cell that beats the peer decisively at the same or
lower budget is a candidate for the headline run (Night 4).

## Reusable assets from the v1 era

Catalogued in `docs/arena_run_registry.md`. The short list:

- 3 v1-config gauntlet runs (40 games each) and 3 v2-config gauntlet runs
  (60 games each), all preserved under `arena_runs/`.
- ~3,200 `se_*`-enriched snapshot rows for evaluator refit (Night 3).
- TrueSkill anchors for the standard pool (`pool_peer_500ms`,
  `pool_heuristic`, `pool_l45_100ms`).
- Failed-validation evidence that motivates the reset.

## Related docs

- `KEY_FINDINGS.md` — layer-by-layer experimental verdicts that
  `champion_minimal` is built from.
- `docs/arena_run_registry.md` — per-run status, what each run is
  reusable for, what it cannot prove.
- `docs/overnight_training_roadmap_2026-05-14.md` — the operational plan
  (Nights 1–7) of which Night 1 is the champion reset gate.
- `data/champion_registry.json` — the live registry. Treat any entry
  with null validation metrics as **not promoted**, regardless of what
  the `current_version` field says.
