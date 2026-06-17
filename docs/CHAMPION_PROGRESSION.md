# Champion Progression

**Status as of 2026-05-15.** Single source of truth for the agent storyline.
If a doc disagrees with this page, this page is right.

## Current Status

- **There is no validated champion.** No agent currently in the registry has
  passed the promotion gates defined below.
- `champion_v1` is a **failed integrated candidate** kept as a regression
  baseline. It loses head-to-head to a same-budget peer (see "v1 failure"
  below), so it cannot be used as the headline agent.
- `champion_minimal` is the **current candidate**, not the champion. It
  isolates only the empirically validated layers and adds the Layer 8
  parallelization that v1 missed. It still has to clear the promotion gate
  on the Night-1 reset run.
- The project has **not** demonstrated human-level play. The closest
  evidence — 65.0% WR vs `pool_heuristic` over 60 games — has a Wilson-95
  lower bound of 52.4%, below the ≥65% bar the roadmap requires before
  the headline can be claimed.

## Agent Lineage

| Stage | Agent | Role | Status | Source |
|---|---|---|---|---|
| 0 | `random` | Pure-random baseline | Reference | `agents/random_agent.py` |
| 0 | `pool_heuristic` | Heuristic / human proxy (no lookahead) | Reference | `agents/heuristic_agent.py` |
| 3 | `pool_l45_100ms` | Layer 4 + Layer 5 MCTS at 100 ms / 50 iter | Reference (low tier) | arena pool |
| 5 | `pool_peer_500ms` | MCTS same time budget as champion candidates, no opponent modeling | **Active peer to beat** — currently outperforms `champion_v1` | arena pool |
| – | `champion_v1` | Full-stack MCTS w/ phase weights, opponent modeling, adaptive C, sufficiency/loss-avoidance | **Failed full-stack candidate** — promoted prematurely with null metrics, lost to `pool_peer_500ms` | `config/champion_arena_params.json`, `data/champion_registry.json` |
| – | `champion_minimal` | Validated-only layers + L8 root parallelization | **Current candidate** — awaiting Night-1 reset gate | `config/champion_minimal_params.json` |
| – | `champion_v2` | _placeholder_ | Reserved for the Night-1 winner if the gate passes | TBD |
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

Writing this into `data/champion_registry.json` is **no longer a manual
TODO**: `scripts/champion_gauntlet.py` (see `docs/CHAMPION_GAUNTLET.md`)
runs the multi-seed gauntlet, enforces these gates, and — only with
`--promote` and only when every gate passes — writes a fully-populated
registry entry (with non-null metrics, CIs, seeds, and the gauntlet run
path), preserving the historical `v1` entry and backing up the previous
file. Without `--promote` it evaluates and reports but never touches the
registry.

## Champion gauntlet harness (Phase 2)

The decision run is now a one-command harness rather than a hand-assembled
arena config. `scripts/champion_gauntlet.py` runs a multi-seed, four-way
tournament between the candidate configs — `champion_v1`,
`champion_minimal`, `pool_peer_500ms`, and the `KEY_FINDINGS.md`
"best config" (`key_findings_best`) — pools the games across seeds,
ranks by TrueSkill conservative with Wilson-95 win-rate CIs, reports
pairwise and seat-position records, and applies the promotion gates above.
It refuses to promote on inconclusive evidence and only edits the registry
under `--promote`. Full details: `docs/CHAMPION_GAUNTLET.md`.

**Status:** the harness is built, unit-tested, and smoke-validated
end-to-end, but the full decision run has **not** yet been executed at the
real 500 ms budget (≈9 h for 3 seeds × 60 games). Until it is, the
registry intentionally remains unpromoted and this page's "no validated
champion" status stands.

## Next experiment

The Night-1 reset run is the immediate gate (now runnable as the gauntlet
above). It is configured in
`scripts/arena_config_night1_champion_reset.json` and pits four agents
at the same 500 ms budget: `champion_minimal`, `champion_v1`,
`pool_peer_500ms`, `pool_heuristic`.

1. **Smoke test the config first.** Run the same arena CLI with
   `--num-games 4` to confirm all four agents parse, construct, and
   produce distinct telemetry. Specifically verify `champion_minimal`
   is actually using `num_workers=2, parallel_strategy="root"` and that
   `champion_v1` still loads its phase weights — a silent fallback to
   identical configs is the most likely way this run goes wrong.
2. **Verify agent distinctness.** Inspect `run_config.json` and the
   per-move telemetry in `games.jsonl` to confirm the four agents are
   not collapsing into duplicate parameter sets.
3. **Run the full 60-game reset gauntlet.**
   `python scripts/arena.py --config scripts/arena_config_night1_champion_reset.json`.
   Expect ≤3 h wall clock if `champion_minimal` is materially faster than
   v1 (it should be — no opponent-modeling overhead, plus parallelization).
4. **Promote only on gate pass.** `champion_minimal → champion_v2` only
   if it beats `champion_v1` by Δμ ≥ 0.5 TrueSkill **and** has a positive
   pairwise record, with the registry entry populated per the promotion
   rule above. Otherwise, the registry stays as-is and the failure is
   recorded in `docs/arena_run_registry.md`.
5. **Label the outcome honestly.** If `champion_minimal` beats v1 but
   still loses badly to `pool_peer_500ms`, the correct framing is
   **"v1 cleanup successful, peer gap remains"** — not a champion
   promotion, and not a human-play claim. The headline run is Night 4
   (multi-seed vs `pool_heuristic`), not Night 1.

## Reusable assets from the v1 era

Catalogued in `docs/arena_run_registry.md`. The short list:

- 3 v1-config gauntlet runs (40 games each) and 3 v2-config gauntlet runs
  (60 games each), all preserved under `arena_runs/`.
- ~3,200 `se_*`-enriched snapshot rows for evaluator refit (Night 3).
- TrueSkill anchors for the standard pool (`pool_peer_500ms`,
  `pool_heuristic`, `pool_l45_100ms`).
- Failed-validation evidence that motivates the reset.

## Related docs

- `docs/CHAMPION_GAUNTLET.md` — the one-command, multi-seed evaluation +
  promotion harness that decides this page's status.
- `KEY_FINDINGS.md` — layer-by-layer experimental verdicts that
  `champion_minimal` is built from.
- `docs/arena_run_registry.md` — per-run status, what each run is
  reusable for, what it cannot prove.
- `docs/overnight_training_roadmap_2026-05-14.md` — the operational plan
  (Nights 1–7) of which Night 1 is the champion reset gate.
- `data/champion_registry.json` — the live registry. Treat any entry
  with null validation metrics as **not promoted**, regardless of what
  the `current_version` field says.
