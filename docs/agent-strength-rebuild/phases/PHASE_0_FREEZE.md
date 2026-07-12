# Phase 0 — Freeze and Preserve the Current System

- **Purpose:** stop uncontrolled training from generating further misleading/era-mixed data;
  preserve current champions, datasets, and performance records for comparison and forensics.

- **Work completed:**
  - Removed the `schedule:` cron trigger (`0 */6 * * *`) from
    `.github/workflows/nightly-mcts-training.yml`; kept `workflow_dispatch` with its full input
    surface for deliberate, attended runs (decision D-003).
  - Inventoried and sha256-pinned all durable assets at baseline commit `cabe2dd`
    (`../DATA_LINEAGE.md`): 3 data corpora, serving registry, champion/latest state,
    gen140 checkpoint, ratings DB, 3 learned-weight files, pre-fix archive.
  - Labeled legacy-data compatibility (Verified / Suspect / Incompatible / Unknown) and set the
    rule that the new Phase 6–8 loop never loads legacy corpora by default.
  - Recorded current known performance as EXP-000 (`../EXPERIMENT_LOG.md`).
  - Audited other automation: `.claude/commands/run-overnight-mcts.md` is manual-only and
    already promotion-guarded (always `--dry-run` promote) — no change needed. No other
    workflows, crontabs, or unattended runners exist.

- **Components changed:** `.github/workflows/nightly-mcts-training.yml` (triggers only — job
  steps untouched).

- **Tests added:** none required (no behavioral code changed). Regression evidence:
  `python -m mcts_lab.checks` passes; workflow YAML parses; `workflow_dispatch` retained.

- **Experiments run:** EXP-000 (baseline snapshot, no new games).

- **Results:**
  - Disabled automation inventory: nightly cron (was every 6 h, ~4 runs/day, `contents: write`,
    committing `data/*.csv`, `training/state/`, reports back to `main`). This was the only
    scheduled job.
  - Checkpoint inventory: champion gen140 (`training/state/champion.json`,
    `training/state/checkpoints/champion_gen140.json`) + serving registry v2
    (`data/champion_registry.json`) — all git-committed and hash-pinned; no copying needed,
    git history is the immutable archive.
  - Current benchmark snapshot: champion gen140 Elo 1388.55, TrueSkill μ 54.39 σ 5.02,
    generation 179, 6 290 games, last promotion 2026-07-02 (details in EXP-000).
  - Legacy compatibility table: see `../DATA_LINEAGE.md`.

- **Unexpected findings:** none in this phase (audit findings are Phase 1's report).

- **Gate criteria:**
  1. No uncontrolled training process remains active.
  2. Existing assets preserved/pinned.
  3. New experiments cannot silently consume legacy data.

- **Gate result:** **PARTIAL — BLOCKED.**
  Criteria 2 and 3 are met (hash-pinned assets; lineage rules in force for all rescue work).
  Criterion 1 is met in this branch but **GitHub evaluates cron schedules from the default
  branch**, so scheduled runs continue until this change merges to `main`. The gate flips to
  PASS on merge with no further action; any corpus/ratings drift on `main` between the baseline
  commit and the merge is detectable against the `DATA_LINEAGE.md` hashes and must be noted
  there after merge.

- **Remaining risks:** delayed merge extends the drift window; a manually dispatched run would
  also append to corpora (acceptable — dispatch is deliberate and attended by definition).

- **Decision:** D-003 (freeze method) in `../DECISIONS.md`.

- **Next phase:** Phase 1 (forensic audit) — completed in the same session; see
  `PHASE_1_FORENSIC_AUDIT.md`.

- **Reproduction commands:**
  ```bash
  git show 166c33b --stat                 # docs-only checkpoint
  python -c "import yaml; wf = yaml.safe_load(open('.github/workflows/nightly-mcts-training.yml')); print(list(wf[True].keys()) if True in wf else list(wf['on'].keys()))"
  sha256sum data/*.csv training/state/champion.json   # vs ../DATA_LINEAGE.md
  python -m mcts_lab.checks
  ```

- **Artifacts:** `../DATA_LINEAGE.md` (frozen-asset inventory), `../EXPERIMENT_LOG.md`
  (EXP-000), the workflow diff in this commit.
