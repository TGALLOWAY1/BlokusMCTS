---
description: Run a guarded overnight MCTS training/evaluation gauntlet and report results (never promotes).
---

# Run Overnight MCTS

You are running a long, unattended MCTS training/evaluation job for the Blokus
AI lab. Follow this routine exactly. **You must never promote a champion** —
promotion is a human decision gated behind an explicit re-run.

Reference: `docs/03-implementation/TRAINING_AND_OVERNIGHT_RUNS.md`.

## 1. Pre-flight checks (do not skip)

- `git status` — note uncommitted changes; do not stash or discard anything.
- Confirm dependencies import: `python -c "import numpy, pandas, sklearn, joblib, openskill"`.
  If this fails, run `pip install -r requirements.txt` and re-check.
- Run the fast tests and stop if they fail:
  `python -m pytest tests/test_champion_gauntlet.py tests/test_run_overnight_training.py -q`
- Validate the candidate configs parse:
  `python -c "import json,glob; [json.load(open(f)) for f in glob.glob('config/*_params.json')]"`
- Check free disk (`df -h .`) — abort and tell the user if under ~2 GB free.

## 2. Print the plan, then launch

- First show the command plan with a dry run:
  `python scripts/run_overnight_training.py --dry-run --generate-data --train-eval`
- If it looks right, launch the real run **without `--promote`**:

```bash
python scripts/run_overnight_training.py \
    --generate-data --train-eval \
    --num-games 400 --agent-type mcts \
    --seeds 20260617 20260618 20260619 --games-per-seed 60 \
    --output-dir arena_runs/overnight/$(date -u +%Y%m%d_%H%M%S)
```

- Prefer launching it as a long-running / background command so you can monitor
  logs rather than blocking. (Claude Code hooks can run long shell commands
  asynchronously; use that mechanism if configured.)

## 3. Monitor

- Tail the per-stage logs in the run directory (`01_generate_data.log`,
  `02_train_eval.log`, `03_gauntlet.log`).
- Watch for tracebacks / non-zero exits. The wrapper aborts on the first stage
  failure and records it in `manifest.json`; if that happens, surface the
  failing log tail and stop — do not retry blindly more than once.

## 4. Summarize afterward

Write a dated markdown report (e.g. `reports/overnight_<UTCstamp>.md`)
containing:

- The run directory and `manifest.json` stage statuses.
- The gauntlet leaderboard and the six gate results from
  `arena_runs/overnight/<stamp>/gauntlets/gauntlet_*/gauntlet_summary.md`.
- Whether the top candidate *would* pass all promotion gates.
- Any anomalies (high σ, single-seat wins, failed stages).

## 5. Manual follow-ups

Append concrete checkboxes to `TODO.md` for anything a human must do:
verify/commit artifacts, decide on promotion, etc.

## Hard rules

- Never pass `--promote`. Never edit `data/champion_registry.json`.
- Never overwrite `models/eval_from_overnight.pkl` or existing dated models.
- Never delete old `arena_runs/` directories.
- Never start an unbounded loop; this command runs the bounded pipeline once.
- If anything is ambiguous (e.g. a gate is borderline), report it and ask —
  do not promote on your own judgement.
