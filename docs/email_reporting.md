# Email Reporting — How the Morning Email Works

## The one code path

The morning email is produced by **`training/email_summary.py`** and nothing
else. The canonical workflow's "Email summary" step runs:

```bash
python -m training.email_summary            # normal
python -m training.email_summary --failed   # when the training step crashed
```

`compose()` builds the email purely from **durable on-disk state**:

- `training/state/latest.json` (via `state_store.load_latest`) — champion,
  generation, counters, and crucially `last_approach_comparison` /
  `last_eval`.
- `training/state/ratings.sqlite` (via `ratings_db.recent_window`) — the Elo /
  TrueSkill timeline that drives the headline Elo, deltas, and the plot.

SMTP credentials come **only** from repo secrets (`SMTP_*`,
`TRAINING_EMAIL_TO/FROM`); if any are missing the body is printed and the send is
skipped, never crashing the workflow.

## What makes a report "multi-agent" (fresh) vs "legacy/incomplete"

The single source of truth is `latest.json → last_approach_comparison`. The
approach-comparison framework writes it (with the run's `run_id`) only after a
real evaluation completes (`run_approaches → save_latest`).

- **Present** → the email is branded `MCTS Lab Multi-Agent Training Report` and
  renders the `## Approach Comparison` table.
- **Absent** → the email is flagged `INCOMPLETE` in the subject and carries a
  prominent `LEGACY / INCOMPLETE REPORT` banner. Every figure below it is stale.

## Root cause of the "old-style email" regression (2026-06)

After the approach-comparison PR merged, emails still looked like the old
progress reports. Root cause chain (all proven against run `28283818000`):

1. The eval battery only checked the wall-clock deadline **between candidates**,
   not between the `(arena, seed)` sub-batteries. With `--games 100` a single
   candidate's battery blew the 45-minute budget.
2. The job therefore ran to the `timeout-minutes: 350` cap and was **cancelled**
   mid-evaluation, so `run_approaches` never reached `save_latest()` —
   `last_approach_comparison` was never written to `latest.json`. (Candidate
   artifacts, written earlier, still got committed, which is why the commits
   looked busy.)
3. The `always()` email step then read the **stale pre-migration `latest.json`**
   (legacy generation-loop state, gen 123, champion gen0) and rendered an
   old-style report with an old-style subject. The freshness check did not trip
   because the stale state and stale DB row agreed with each other.

### Fixes

- `training/evaluation/head_to_head.py` — the deadline is threaded into
  `evaluate_candidate_vs_pool` and checked before each `(arena, seed)`, so a run
  completes within budget and persists its result.
- `training/email_summary.py` — multi-agent subject branding, a `## Run
  Provenance` header (workflow file, run id, commit SHA, branch, state timestamp,
  mode), and the LEGACY/INCOMPLETE guardrail above.
- `.github/workflows/nightly-mcts-training.yml` — a "Verify report freshness"
  guardrail step (`training.verify_report_freshness`), explicit handling of a
  cancelled training step, and the job now fails on **any** non-success outcome
  (so a cancelled run no longer shows green).

## Email anatomy

| Section | Source |
|---|---|
| Subject | `build_subject` — branding + date + short SHA + Elo/delta or INCOMPLETE/FAILED |
| `## Run Provenance` | `build_provenance` (GitHub env + state) |
| LEGACY/INCOMPLETE banner | shown iff `last_approach_comparison` absent |
| `## Summary` / `## ELO Trend` | `latest.json` + `ratings.sqlite` + `elo_trend.png` |
| `## Approach Comparison` | `latest.json → last_approach_comparison` |
| `## Learning Method` / `## Match Breakdown` | `latest.json → last_eval` (legacy path) |
| `## Diagnostics` | `diagnostics.collect_findings` |

## Verifying locally

```bash
# Render the exact email without sending (uses the live state):
python -m training.email_summary --dry-run

# Assert the durable state holds a fresh multi-agent result (exit 0):
python -m training.verify_report_freshness
```

## ELO / TrueSkill history

Stored in `training/state/ratings.sqlite`. See `docs/training_workflows.md`.
