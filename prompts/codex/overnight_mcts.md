# Codex Overnight MCTS Prompt

Run this non-interactively from the repo root, e.g.:

```bash
codex exec "$(cat prompts/codex/overnight_mcts.md)"
```

(Requires the Codex CLI to be installed and authenticated, and Python deps
installed — see `TODO.md`. Neither is assumed to be configured.)

---

You are an autonomous agent running an overnight MCTS training/evaluation job
for the Blokus AI lab. Work only inside this repository. Reference
`docs/03-implementation/TRAINING_AND_OVERNIGHT_RUNS.md`.

## Steps

1. **Check repo status:** run `git status`. Do not discard or stash changes.
2. **Confirm dependencies:** `python -c "import numpy, pandas, sklearn, joblib, openskill"`.
   If it fails, run `pip install -r requirements.txt` and re-check.
3. **Run fast tests first** and stop on failure:
   `python -m pytest tests/test_champion_gauntlet.py tests/test_run_overnight_training.py -q`
4. **Validate configs:**
   `python -c "import json,glob; [json.load(open(f)) for f in glob.glob('config/*_params.json')]"`
5. **Dry run, then launch (NO promotion):**
   ```bash
   python scripts/run_overnight_training.py --dry-run --generate-data --train-eval
   python scripts/run_overnight_training.py \
       --generate-data --train-eval \
       --num-games 400 --agent-type mcts \
       --seeds 20260617 20260618 20260619 --games-per-seed 60
   ```
6. **Tail logs** in the created `arena_runs/overnight/<stamp>/` directory
   (`01_generate_data.log`, `02_train_eval.log`, `03_gauntlet.log`) and watch
   for tracebacks or non-zero exits. The wrapper aborts on first failure.
7. **Produce a summary:** write `reports/overnight_<UTCstamp>.md` with the
   manifest stage statuses, the gauntlet leaderboard, the six promotion-gate
   results, and any anomalies.
8. **Append manual follow-ups** to `TODO.md` (verify/commit artifacts, decide
   on promotion).

## Shell commands you MAY run

- The read-only checks above (`git status`, imports, `pytest`, `json.load`).
- `python scripts/run_overnight_training.py ...` **without** `--promote`.
- Reading files under `arena_runs/`, `data/`, `models/`, `config/`.

## You MUST NOT

- Pass `--promote` or otherwise modify `data/champion_registry.json`.
- Overwrite `models/eval_from_overnight.pkl` or any existing dated model.
- Delete or rewrite existing `arena_runs/` directories.
- Start an unbounded training loop.
- Push commits or open PRs unless explicitly instructed.

If a promotion gate is borderline or a stage fails ambiguously, stop and write
the situation into the summary report rather than acting on your own judgement.
