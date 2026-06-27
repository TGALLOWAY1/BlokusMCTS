# Training Workflows — Canonical Reference

This document is the authoritative answer to "which GitHub Actions workflow
trains the agent and emails me, and how do I know the report is fresh?"

## Canonical workflow

There is exactly **one** scheduled training workflow:

| Field | Value |
|---|---|
| File | `.github/workflows/nightly-mcts-training.yml` |
| Workflow name | `nightly-mcts-training` |
| Trigger | `schedule` (cron `0 */6 * * *`, every 6h UTC) + `workflow_dispatch` |
| Branch | runs on the default branch (`main`) — `ref: ${{ github.ref_name }}` |
| Entry point | `python -m training.nightly_run --approaches "td,mcts_sweep,heuristic_tune,baseline" ...` |
| Mode | **multi-agent approach-comparison framework** (NOT the legacy generation loop) |
| Email | `python -m training.email_summary` (always runs — success, failure, or cancellation) |
| Concurrency | group `nightly-mcts-training`, `cancel-in-progress: false` |

A CI guardrail (`tests/test_training_report_guardrails.py::test_exactly_one_scheduled_workflow`)
fails if a second cron-scheduled workflow is ever added, so two workflows can
never both train and email.

> The `browser-core-sync` workflow that appears in the GitHub Actions UI has **no
> file in the repo** — it is a registry remnant of a deleted workflow and never
> runs. It is unrelated to training or email.

## The multi-agent framework (what "agents" means here)

The new framework compares first-class **candidate-generation approaches**
(this is the "multi-agent" approach the migration introduced):

- `baseline` — baseline MCTS seed
- `td` — temporal-difference-trained leaf evaluator
- `heuristic_tune` — tuned heuristic weights
- `mcts_sweep` — MCTS hyper-parameter sweep
- `hybrid` — TD + MCTS hybrid

Each approach produces a `Candidate` (artifact under
`training/artifacts/candidates/`), the created candidates are evaluated against a
**fixed benchmark pool with fixed seeds**, and only a candidate that passes the
statistical promotion gate replaces the champion. See `training/README.md` and
`docs/03-implementation/NIGHTLY_TRAINING.md` for the design.

## How to trigger manually

```bash
# From the GitHub UI: Actions → nightly-mcts-training → Run workflow, or:
gh workflow run nightly-mcts-training.yml \
  -f approaches="td,mcts_sweep,heuristic_tune,baseline" \
  -f games=100 -f time_budget_minutes=45

# Locally (dry run — writes nothing to tracked state):
python -m training.nightly_run --approaches all --dry-run
```

## Artifacts the canonical run generates

| Artifact | Path |
|---|---|
| Per-approach candidate JSON | `training/artifacts/candidates/<approach>_<ts>.json` |
| Durable run state (read by the email) | `training/state/latest.json` |
| Approach-comparison record | `latest.json → last_approach_comparison` |
| Per-generation history | `training/state/history.jsonl` |
| Rating / TrueSkill timeline DB | `training/state/ratings.sqlite` |
| Champion Elo trajectory plot | `training/reports/elo_trend.png` |
| Status report | `training/status.md` |
| Diagnosis | `training/reports/latest_diagnosis.md` |
| Champion registry / snapshots | `data/champion_registry.json`, `data/champion_snapshots.csv` |

## ELO / TrueSkill history

Both live in `training/state/ratings.sqlite` (append-only, recorded once per
real evaluation). The email and the Elo plot read from this DB, not from any
checked-in scalar.

## How to verify a report came from the new pipeline

1. The email **subject** starts with `MCTS Lab Multi-Agent Training Report` and
   carries the date + short commit SHA. An `INCOMPLETE`/`FAILED` subject means the
   run did not produce a fresh multi-agent result.
2. The email **body** has a `## Run Provenance` header showing `Training mode:
   multi-agent-approach-comparison` and an `## Approach Comparison` table.
3. Programmatically: `python -m training.verify_report_freshness` exits `0` only
   when `latest.json` holds a completed approach comparison for the current run.

## Deprecated paths

- **Legacy generation loop** (`nightly_run.run`, used only when `--approaches` is
  omitted) — retained for backward compatibility/tests but NOT used by the
  scheduled workflow. Do not re-wire the workflow to it.
- **FastMCTS** agents — archived (see root `CLAUDE.md`).
