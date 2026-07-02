---
description: Run a guarded overnight MCTS training/evaluation gauntlet and report results (never promotes).
---

# Run Overnight MCTS

You are running a long, unattended MCTS training/evaluation job for the Blokus
AI lab. Follow this routine exactly. **You must never promote a champion** —
promotion is a human decision (`python -m mcts_lab.promote` without
`--dry-run`) gated behind an explicit re-run.

Reference: `README.md` ("The improvement loop") and `AUDIT_REPORT.md`.

## 1. Pre-flight checks (do not skip)

- `git status` — note uncommitted changes; do not stash or discard anything.
- Confirm dependencies import: `python -c "import numpy, pandas, sklearn, joblib, openskill"`.
  If this fails, run `pip install -r requirements.txt` and re-check.
- Run the fast sanity gate and stop if it fails: `python -m mcts_lab.checks`
- Check free disk (`df -h .`) — abort and tell the user if under ~2 GB free.

## 2. Print the plan, then launch

- Show the plan first with a dry run:
  `python -m training.nightly_run --dry-run --approaches baseline,heuristic_tune`
- If it looks right, run the bounded overnight pipeline (candidate generation,
  self-play, evaluation vs the fixed pool — **no promotion persists in dry-run
  promote**):

```bash
python -m mcts_lab.self_play --games 24
python -m mcts_lab.train
python -m mcts_lab.promote \
    --candidate training/artifacts/candidates/<newest_created_artifact>.json \
    --thinking-ms 100 --budget-minutes 300 --dry-run
```

- Launch long steps as background commands and monitor logs rather than
  blocking.

## 3. Monitor

- Arena outputs stream into `training/state/selfplay_runs/<run_label>/`.
- Watch for tracebacks / non-zero exits. If a stage fails, surface the failing
  log tail and stop — do not retry blindly more than once.

## 4. Summarize afterward

Write a dated markdown report (e.g. `training/reports/overnight_<UTCstamp>.md`)
containing:

- The commands run and their artifacts (candidate path, run dirs).
- The screen/confirm evaluation lines (games, win% + CI, vs-champion record,
  ΔElo, Δμ) and every gate criterion pass/fail.
- Whether the top candidate *would* pass promotion (dry-run verdict).
- Any anomalies (high σ, single-seed wins, budget exhaustion).

## Hard rules

- Never run `mcts_lab.promote` without `--dry-run`. Never edit
  `training/state/champion.json` or `data/champion_registry.json` by hand.
- Never delete `arena_runs/` or `training/state/` contents.
- Never start an unbounded loop; this command runs the bounded pipeline once.
- If anything is ambiguous (e.g. a gate is borderline), report it and ask —
  do not promote on your own judgement.
