# Champion Gauntlet

A one-command, multi-seed evaluation harness that compares the champion
candidates head-to-head, produces real metrics, and (only when the evidence is
clear) promotes a validated champion into `data/champion_registry.json`.

Entry point: **`python scripts/champion_gauntlet.py`**
Library: `analytics/tournament/gauntlet.py`
Tests: `tests/test_champion_gauntlet.py`

---

## 1. Why the gauntlet exists

The repo had a central contradiction (see `docs/MCTS_REPO_AUDIT.md` §7 and
`docs/CHAMPION_PROGRESSION.md`):

- `data/champion_registry.json` declared `champion_v1` the champion with **every
  metric `null`** and `total_games_played: 0` — promoted on description alone.
- `docs/CHAMPION_PROGRESSION.md` (the self-declared single source of truth) said
  **there is no validated champion**, that `champion_v1` is a *failed* candidate
  that loses to a same-budget peer, and that `champion_minimal` is an unvalidated
  candidate.

The evaluation infrastructure to settle this already existed (deterministic
seeded arena tournaments with win rates, pairwise records, and TrueSkill). What
was missing was a single, decisive, multi-seed run whose result is written back
to the registry with real numbers. The gauntlet is that run, plus the promotion
logic that refuses to crown a champion on weak evidence.

The fix is **not new research** — it is one clean tournament between the
existing candidate configs.

---

## 2. Candidates compared

Exactly four candidates fill one Blokus game's four seats. Each is a config of
`MCTSAgent` (not a separate class), loaded from a standalone wrapper in
`config/`:

| Candidate | Config | What it is |
|---|---|---|
| `champion_v1` | `config/champion_arena_params.json` | The bloated incumbent: full Layers 3–7 + 9, phase weights, opponent modeling, adaptive C, sufficiency/loss-avoidance. Promoted prematurely with null metrics. |
| `champion_minimal` | `config/champion_minimal_params.json` | Only the empirically-validated layers (random rollout, cutoff 5, minimax α=0.25, RAVE k=1000, calibrated weights, adaptive rollout depth) **plus** progressive widening and Layer 8 root 2-worker parallelization. |
| `pool_peer_500ms` | `config/pool_peer_500ms_params.json` | Same-budget MCTS peer (no opponent modeling) that has historically out-rated `champion_v1`. The peer to beat. |
| `key_findings_best` | `config/key_findings_best_params.json` | The "Best Configuration" listed literally in `KEY_FINDINGS.md`. Same as `champion_minimal` **minus** progressive widening, so the head-to-head measures whether PW earns its place. |

### Config provenance notes

- `champion_v1` and `champion_minimal` configs already existed.
- `pool_peer_500ms` previously existed only **inline** inside
  `scripts/arena_config_champion_gauntlet*.json`. It was extracted into a
  standalone wrapper (`config/pool_peer_500ms_params.json`) so the gauntlet can
  load it as a first-class candidate. The definition matches
  `scripts/arena_config_champion_gauntlet_v2.json` (the source of the
  documented TrueSkill μ=50.55 anchor).
- The `KEY_FINDINGS.md` best config had **no standalone file**; the smallest
  necessary wrapper was created (`config/key_findings_best_params.json`).

All candidates run at the same 500 ms / `iterations_per_ms=0.5` budget
(≈250 iterations/move) for an apples-to-apples comparison.

---

## 3. How to run it

```bash
# Evaluate only — writes summaries, NEVER touches the registry:
python scripts/champion_gauntlet.py

# Decisive run: 3 seeds x 60 games, promote if (and only if) gates pass:
python scripts/champion_gauntlet.py \
    --seeds 20260617 20260618 20260619 \
    --num-games 60 \
    --promote

# Fast smoke test (cheap; proves the pipeline end-to-end, won't promote):
python scripts/champion_gauntlet.py --num-games 2 --seeds 1 2 --thinking-time-ms 10
```

> **Cost warning.** At the real 500 ms budget a single 4-heavy-agent game takes
> ~3 minutes wall-clock on a typical machine. A 3-seed × 60-game run is ~180
> games ≈ 9 hours. Plan accordingly, or reduce `--num-games`. Use
> `--thinking-time-ms` only for smoke tests — it makes the *results*
> meaningless, but exercises every code path.

### Useful flags

| Flag | Default | Meaning |
|---|---|---|
| `--candidates NAME=PATH ...` | the 4 above | Override the candidate set (must total exactly 4). |
| `--seeds S ...` | `20260617 20260618 20260619` | One deterministic arena run per seed. |
| `--num-games N` | `30` | Games per seed. |
| `--seat-policy` | `round_robin` | Seat assignment (controls/cancels seat bias). |
| `--snapshots` | off | Enable ply snapshots (`se_` dataset rows; slower). |
| `--promote` | off | Update the registry **iff** all gates pass. |
| `--registry PATH` | `data/champion_registry.json` | Registry file to update. |
| `--min-seeds` / `--min-total-games` / `--min-mu-margin` | `2 / 40 / 0.5` | Promotion gate thresholds. |

### Output

Each run writes a timestamped directory under `arena_runs/gauntlets/`:

```
arena_runs/gauntlets/gauntlet_<ts>/
├── seed_<S>/<run_id>/        # one full arena run per seed (games.jsonl, summary.json/md, run_config.json)
├── gauntlet_summary.json     # machine-readable: ranked leaderboard, pairwise, pooled summary, promotion decision
└── gauntlet_summary.md       # human-readable ranked table + promotion gate breakdown
```

Reproducibility: the seeds, per-candidate config paths + hashes, and full
per-seed `run_config.json` are all saved. Re-running with the same seeds and
configs reproduces the games (the arena derives per-game and per-agent seeds
deterministically from the run seed).

---

## 4. Metrics reported

All metrics are computed by the existing arena code
(`analytics/tournament/arena_stats.py`) over the **pooled** games from every
seed — no new metric definitions are invented.

Per candidate:

- **Win rate** — shared-win aware (`win_points / games_played`).
- **Wilson-95 confidence interval** on the win rate
  (`analytics/tournament/statistics.py::wilson_score_interval`).
- **TrueSkill rating** — μ, σ, and conservative estimate (μ − 3σ), the ranking
  metric (`analytics/tournament/trueskill_rating.py`).
- **Average score** (mean, plus median/std/quartiles in the pooled summary).
- **Games played**, **seeds used**, **config path + config hash**.

Cross-candidate:

- **Pairwise records** — outright score wins for every pair (a-beats-b /
  b-beats-a / ties).
- **Seat-position analysis** — per-seat win rate and per-seat score
  (`wins_by_seat`, `score_by_seat_position`) to disentangle strength from
  first-player advantage.

Candidates are **ranked by TrueSkill conservative (μ − 3σ)**, the repo's
established leaderboard metric, with win rate as the tie-breaker.

---

## 5. Champion promotion criteria

A candidate is promoted to champion **only if it clears every gate**. The
defaults encode the promotion rule from `docs/CHAMPION_PROGRESSION.md`:

| Gate | Default | Rationale |
|---|---|---|
| `highest_ranking` | rank #1 by μ − 3σ | Must be the strongest by the leaderboard metric. |
| `beats_runner_up_h2h` | outright record vs #2 is positive | Must actually beat the strongest peer, not just out-average the field. |
| `trueskill_margin` | Δμ over #2 ≥ 0.5 | The repo's TrueSkill promotion gate; guards against ties. |
| `win_rate_ci_conclusive` | Wilson-95 lower bound > 1/N (0.25 for 4 agents) | Win rate must be better than random *with confidence*, not just on the point estimate. |
| `multiple_seeds` | ≥ 2 seeds | No single-seed promotions. |
| `enough_games` | ≥ 40 total games | Enough evidence for the CIs to mean something. |

If **all** gates pass *and* `--promote` is set, the gauntlet writes a fully
populated registry entry (champion name, config path, win rate + CI, TrueSkill
μ/σ/conservative, average score, total games, seeds, validation date, gauntlet
run path, comparison opponents, notes, `gate_pass: true`). It bumps
`current_version` to a fresh `vN`, **preserves all historical versions**,
accumulates `total_games_played`, appends an iteration record, and writes a
`.bak` of the previous registry first.

Without `--promote`, the gauntlet runs the full evaluation and writes the
summaries but **never modifies the registry** — even if the candidate would
have passed.

---

## 6. How to interpret inconclusive results

If the top candidate fails any gate, the gauntlet prints:

```
No validated champion promoted.
```

…followed by the list of failed gates, and leaves the registry untouched. This
is the **correct** outcome, not a failure of the harness — a falsely promoted
champion is worse than an honestly unresolved one.

Common inconclusive patterns and what they mean:

- **`trueskill_margin` / `beats_runner_up_h2h` fail** → the top two candidates
  are too close to separate at this sample size. Either run more games/seeds, or
  accept that they are effectively tied at this budget.
- **`win_rate_ci_conclusive` fails** → the win-rate point estimate looks good
  but the Wilson lower bound is below random. More games will tighten the CI.
- **`enough_games` / `multiple_seeds` fail** → you ran a smoke/pilot, not a
  decision run. Re-run at full size.

When a result is inconclusive, prefer reporting the honest framing (e.g.
"v1 cleanup successful, peer gap remains") over a champion claim. The
human-play headline (≥65% WR vs `pool_heuristic` with a defensible Wilson lower
bound) is a separate, later bar — the gauntlet measures relative candidate
strength, not human-level play.

---

## 7. Related

- `docs/CHAMPION_PROGRESSION.md` — the champion storyline and promotion rule.
- `docs/MCTS_REPO_AUDIT.md` — Phase 1 audit that motivated this harness.
- `KEY_FINDINGS.md` — the layer-by-layer verdicts the candidates are built from.
- `scripts/arena.py` / `analytics/tournament/arena_runner.py` — the underlying
  arena harness the gauntlet drives.
