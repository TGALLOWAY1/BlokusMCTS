# Durable MCTS Training Pipeline

Status: **Implemented**

A continuously-improving, AlphaZero-spirit self-play training system that runs
**every 6 hours** (00/06/12/18 UTC), **resumes from durable on-disk state**,
generates improved candidate agents, promotes them when statistically justified,
tracks Elo + TrueSkill over time, estimates progress toward human-level play,
and emails a concise summary. The pipeline was originally daily; running four
times a day takes advantage of GitHub Actions' unlimited free minutes on public
repos (the file/dir names still say "nightly" for historical compatibility).

The cardinal rule — and the reason previous nightly attempts failed — is that
**all training memory lives on disk under `training/state/`**. Every run loads it,
updates it, and writes it back, so the next run (or a freshly recreated CI runner)
continues seamlessly. Nothing of value lives only in process memory, CI logs, or
workflow state.

## What it reuses (it does not reinvent the engine)

The "learning" is **re-fitting the Layer-6 state evaluator** on accumulated
self-play snapshots (there is no neural net). Almost everything heavy is imported
from existing, tested code:

| Concern | Reused from |
|---|---|
| Self-improvement helpers, challenger pool, snapshot accumulation, **evaluator weight re-fit** (candidate generation), TrueSkill build/persist | `scripts/champion_loop.py` |
| In-process 4-agent arena | `analytics/tournament/arena_runner.py` (`run_experiment`) |
| TrueSkill / Elo | `analytics/tournament/trueskill_rating.py`, `analytics/tournament/elo.py` |
| Pooled aggregation + conservative 6-gate promotion | `analytics/tournament/gauntlet.py` |
| Cold-start champion seed | `config/key_findings_best_params.json`, `agents/champion.py` |

## Durable state layout (`training/state/`)

| File / dir | Role | Committed? |
|---|---|---|
| `latest.json` | Full resumable run state (generation, totals, champion, ratings, human estimate, last error) | yes |
| `champion.json` | Current champion: params, rating, promotion date, lineage | yes |
| `ratings.sqlite` | **Append-only** Elo + TrueSkill timeline (graph it months later) | yes |
| `history.jsonl` | Append-only per-generation record | yes |
| `checkpoints/` | Immutable champion checkpoint per promotion (also the "historical champions" eval pool) | yes |
| `reports/` | Timestamped `status.md` snapshots | yes |
| `selfplay_runs/` | Per-game arena outputs (bulky, reproducible) | **no** (git-ignored — see Storage) |

Reports also live at `training/status.md` and `training/reports/latest_diagnosis.md`.

## How a nightly run works (`training/nightly_run.py`)

1. Load `latest.json` + `champion.json` + `ratings.sqlite` (cold start seeds the
   champion from `config/key_findings_best_params.json`).
2. Seed the Elo + TrueSkill trackers from the SQLite timeline (Elo has no
   serializer of its own — this is how it persists across runs).
3. **Time-budgeted generation loop:** run champion-vs-challenger self-play
   generations until the wall-clock budget (`--hours × 0.7`) is spent, writing
   state atomically and appending to `history.jsonl` **after each generation**
   (so a crash never loses completed generations). Each generation grows the
   shared snapshot corpus `data/champion_snapshots.csv`. Each generation's
   3-challenger lineup is Elo-improvement oriented (see :func:`select_challengers`
   in `scripts/champion_loop.py`): slot 0 is always `heuristic`; slot 1 is a
   recent learned checkpoint; slot 2 is an MCTS variant, with a small
   `WEAK_OPPONENT_PROB` (default 0.2) chance of being swapped for `random` —
   the explicit "occasional weak agent" that anchors the bottom of the rating
   ladder and broadens the snapshot corpus.
4. **Candidate:** re-fit evaluator weights on the corpus → candidate = champion +
   new per-phase weights. (No candidate until ≥200 snapshot rows exist.)
5. **Evaluate:** a battery of 4-agent arenas — `[champion, candidate, opp_A, opp_B]`
   — rotates opponents (baselines, previous champion, historical champions) across
   ≥2 seeds, pools every game, and applies the conservative 6 promotion gates.
6. **Promote (internal):** on a pass, write a checkpoint, update `champion.json`
   (+ lineage), and reset champion σ. The deployed `data/champion_registry.json`
   is **not** touched unless `--promote-registry` is passed.
7. Append the run to the rating timeline, compute the human-strength estimate, and
   write `status.md` + `latest_diagnosis.md`.

### CLI

```bash
# Standard nightly (what CI runs)
python -m training.nightly_run --hours 5 --resume training/state/latest.json

# Fast local smoke (tiny budget + thinking time)
python -m training.nightly_run --hours 0.05 --seeds 1 2 --games-per-arena 2 --thinking-time-ms 10

# Also push a promoted champion to the live web demo (opt-in)
python -m training.nightly_run --hours 5 --promote-registry

# Email digest (used by CI; prints body, sends only if SMTP env present)
python -m training.email_summary            # success
python -m training.email_summary --failed   # failure
```

## GitHub Actions (`.github/workflows/nightly-mcts-training.yml`)

- `schedule: cron "0 */6 * * *"` (every 6 hours at :00 UTC — 4 runs/day) +
  `workflow_dispatch` (manual, with `hours`/`games_per_arena` inputs).
- `concurrency: nightly-mcts-training`, `cancel-in-progress: false` — never two at
  once, never kill an in-flight run. With the 5-hour default budget and a
  6-hour cadence there is a ~1h buffer between runs; if one runs long the next
  scheduled tick queues rather than starting concurrently.
- **Counter semantics under multi-run cadence:** `state["days_trained"]`
  increments once per *run*, not once per calendar day. With 4 runs/day it now
  reads as "training cycles completed" rather than literal days; the
  human-strength projection's per-day rate is similarly a per-run rate. Both
  numbers are still monotonic and useful for trend visualisation; only the
  unit label is loose.
- Steps: checkout → install → **train** (`continue-on-error`) → reports
  (`if: always()`) → optional Claude augmentation → **commit state back** →
  **email** (`if: always()`, `--failed` when training failed) → mark job failed.
- The email step always runs, so you get a summary on success *and* failure.

### Required repository secrets

`SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
`TRAINING_EMAIL_TO`, `TRAINING_EMAIL_FROM`. If any are missing the run still
completes; the email is skipped gracefully and the body is printed to the CI log.

### Runtime budget & self-hosted fallback

GitHub-hosted runners hard-cap a job at 360 minutes. The default `--hours 5` with
`timeout-minutes: 350` stays safely under it (reserving time for eval, reports,
commit, email). For longer budgets (e.g. `--hours 8`), use a **self-hosted
runner**: change `runs-on: ubuntu-latest` to `runs-on: [self-hosted]`, raise
`timeout-minutes`, and dispatch with a larger `hours` input. The pipeline logic is
identical — only the runner and cap change.

## Failure handling

A crash mid-run writes a truncated traceback + the failing generation into
`latest.json["last_error"]` (atomically), still writes the reports, and the
workflow's always-run email step sends a failure digest. Because state is written
atomically after every generation, the next night **resumes from the last valid
generation** — no single failed run destroys progress.

## Storage growth (deferred decisions — not implemented automatically)

The committed footprint is bounded: `ratings.sqlite`, `history.jsonl`,
`champion.json`, `latest.json`, checkpoints, and reports. The bulky per-game arena
outputs under `training/state/selfplay_runs/` are **git-ignored** by default
(`training/.gitignore`) because committing every game nightly would explode the
repo; they are reproducible intermediate artifacts and the durable signal is fully
captured elsewhere.

If/when even the committed footprint grows large, options (to be chosen by a human,
**not** automated):
- Migrate `ratings.sqlite` / checkpoints to **Git LFS**.
- Offload `selfplay_runs/` (if retention is desired) to **S3 / Cloudflare R2**.

Per project policy, historical rating data, reports, champions, and training
summaries are **never deleted** — the repo is a permanent record of progress.

## Tests

`tests/test_training_*.py` cover: path resolution + atomic writes, append-only
ratings DB, human-estimate math (including the no-fabricated-confidence rule),
status rendering, diagnostics detectors, email subject/body (success + failure,
fake transport, missing-env skip), `selfplay_core` eval-battery construction, and
an end-to-end **resume proof** + failure-preservation test (arena mocked).

```bash
python -m pytest tests/test_training_*.py -q
```
