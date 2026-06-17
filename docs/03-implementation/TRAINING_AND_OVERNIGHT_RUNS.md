# Training & Overnight Runs

> Status of this document: **Implemented pipeline + proposed automation.**
> Sections marked **(Implemented)** describe scripts and artifacts that exist
> today. Sections marked **(Proposed)** describe wrappers / automation added by
> this phase or still to be wired up. Manual setup steps live in the repo-root
> [`TODO.md`](../../TODO.md) under *Manual Setup Required for Overnight MCTS Runs*.

---

## 1. Current Training Reality

**This is not reinforcement learning.** There is no PPO, no policy-gradient
loop, no live self-play-and-update cycle, and no neural network being trained
online. The RL-era code has been archived (see `docs/_archived-2026-05/` and
`archive/`). What the repo calls "training" is an **offline, supervised +
search-tuning pipeline**:

```
   self-play snapshots          (scripts/generate_training_data.py)
          │  parquet of per-player feature rows + final scores
          ▼
   evaluator fitting            (scripts/train_eval_model.py            -> .pkl
          │                      OR  champion_loop.py per-phase regression -> weights JSON)
          ▼
   candidate config             (config/*_params.json — search params + eval weights/model)
          ▼
   gauntlet validation          (scripts/champion_gauntlet.py — multi-seed, 6 promotion gates)
          ▼
   champion registry promotion  (data/champion_registry.json — ONLY with --promote + gates pass)
```

Two distinct "learned" artifacts exist, and they connect to the search in
**different** ways:

| Artifact | Produced by | Connects to MCTS via | Notes |
|----------|-------------|----------------------|-------|
| `models/*.pkl` (learned win-prob model) | `train_eval_model.py` | `learned_model_path` + `leaf_evaluation_enabled` / `progressive_bias_enabled` / `potential_shaping_enabled` | Layer 2 finding: ~26 ms/call, **no measured benefit** at competitive budgets. Treat as research, not the default. |
| `data/layer6_calibrated_weights.json` (linear feature weights) | `analyze_layer6_features.py`, refit inside `champion_loop.py` | injected as `state_eval_weights` / `state_eval_phase_weights` in a candidate config | The lightweight `BlokusStateEvaluator` (sub-0.5 ms). This is what the current champion config actually uses. |

> **Bottom line:** the *practical* improvement path today is **search-parameter
> + evaluation-weight tuning, validated by gauntlet**, not learned-model
> training. The learned `.pkl` path exists and is wired, but Layer 2 results say
> it does not earn its inference cost. Document/experiment with it, don't ship it
> by default.

### What's active vs obsolete

**(Implemented) Active scripts**

- `scripts/generate_training_data.py` — self-play → `snapshots.parquet`.
  ⚠️ Its `--agent-type` **defaults to `fast_mcts`, which is archived and will
  fail to import** (`agents.fast_mcts_agent` no longer exists). **Always pass
  `--agent-type mcts`.** See TODO for the proposed default fix.
- `scripts/train_eval_model.py` — fit `pairwise_logreg` or `pairwise_gbt_phase`
  evaluator `.pkl` from snapshots.
- `scripts/validate_eval_model.py` — inference-speed check + small head-to-head
  arena for a learned `.pkl`.
- `scripts/champion_gauntlet.py` — **the canonical validation + guarded
  promotion entry point.** Multi-seed, 6 conservative gates, `--promote` opt-in.
- `scripts/champion_loop.py` — long-running self-improvement loop: arena vs a
  challenger pool, persistent TrueSkill, periodic per-phase weight refit,
  markdown progress report.
- `scripts/self_improve.py` — runs one arena and appends metrics to a tracking
  log (`--show` to print history).
- `scripts/run_overnight.sh` — tmux/nohup wrapper that runs a fixed
  `arena_config_overnight_10hr.json` for up to 10 h / 300 games.
- `scripts/run_overnight_training.py` — **(Proposed, added this phase)** thin
  orchestrator chaining generate → train → gauntlet with `--dry-run`,
  `--resume`, and **no-promote-by-default**.

**Unclear / overlapping (use with care)**

- `champion_arena.py` (30 KB) and `champion_loop.py` (29 KB) overlap with the
  newer `champion_gauntlet.py`. The gauntlet is the recommended, conservative
  path; the older two predate it and have looser promotion semantics. Prefer
  the gauntlet for any promotion decision.
- `run_overnight_learned.sh` is the learned-`.pkl` variant of the overnight
  arena and inherits the Layer 2 "no benefit" caveat.

### Artifacts produced

| Path | What | When |
|------|------|------|
| `data/snapshots.parquet` (or chosen `--output`) | per-player feature rows + final scores | data generation |
| `models/*.pkl` | learned win-prob evaluator | `train_eval_model.py` |
| `data/layer6_calibrated_weights.json` | single/phase/default eval weights | feature analysis / `champion_loop.py` refit |
| `config/*_params.json` | candidate search+eval configs | hand-authored / derived |
| `arena_runs/**/games.jsonl` | per-game records | every arena run |
| `arena_runs/gauntlets/gauntlet_*/gauntlet_summary.{json,md}` | ranked leaderboard + promotion decision | `champion_gauntlet.py` |
| `data/champion_registry.json` | versioned champion params + provenance | gauntlet `--promote` only |
| `data/champion_state.json`, `champion_snapshots.csv`, `champion_progress.md` | loop state / accumulated data / report | `champion_loop.py` |

### How a candidate becomes a champion (Implemented)

`champion_gauntlet.py` runs the 4 candidates across multiple seeds, pools the
games, ranks by conservative TrueSkill (μ − 3σ), and evaluates **six gates**
(`analytics/tournament/gauntlet.py::evaluate_promotion`):

1. `highest_ranking` — #1 by conservative TrueSkill.
2. `beats_runner_up_h2h` — positive head-to-head vs runner-up.
3. `trueskill_margin` — Δμ over runner-up ≥ `--min-mu-margin` (default 0.5).
4. `win_rate_ci_conclusive` — Wilson-95 lower bound > random baseline (1/N).
5. `multiple_seeds` — seeds ≥ `--min-seeds` (default 2).
6. `enough_games` — total games ≥ `--min-total-games` (default 40).

The registry is written **only if every gate passes AND `--promote` is set.**
Otherwise it prints `No validated champion promoted.` and leaves the registry
untouched. (Today `data/champion_registry.json` still holds a `v1` entry with
`null` metrics — i.e. no validated champion has been promoted yet.)

### Manual steps currently required

- Choosing/authoring the candidate `config/*_params.json` files.
- Passing `--agent-type mcts` to data generation (bad default).
- Reading the gauntlet summary and deciding whether to re-run with `--promote`.
- Committing any artifacts worth keeping (the remote container is ephemeral).

---

## 2. One-Command Training Path (Implemented)

All commands are runnable from the repo root. Replace seeds/counts to taste.

```bash
# 0. Install deps once (see TODO for environment specifics)
pip install -r requirements.txt

# 1. Generate self-play data  (NOTE: --agent-type mcts, NOT the fast_mcts default)
python scripts/generate_training_data.py \
    --num-games 400 \
    --agent-type mcts \
    --thinking-time-ms 100 \
    --checkpoint-interval 4 \
    --workers 4 \
    --seed 20260617 \
    --output data/snapshots_20260617.parquet

# 2. (Optional, research) Fit a learned evaluator from those snapshots
python scripts/train_eval_model.py \
    --data data/snapshots_20260617.parquet \
    --model-type pairwise_gbt_phase \
    --output models/eval_20260617.pkl \
    --seed 20260617

# 2b. (Optional) Validate the learned model in isolation
python scripts/validate_eval_model.py \
    --model models/eval_20260617.pkl \
    --num-games 60 --thinking-time-ms 100

# 3. Validate candidate configs against each other (NO promotion)
python scripts/champion_gauntlet.py \
    --seeds 20260617 20260618 20260619 \
    --num-games 60

# 4. Promote ONLY after reviewing step 3's summary and confirming gates pass
python scripts/champion_gauntlet.py \
    --seeds 20260617 20260618 20260619 \
    --num-games 60 \
    --promote
```

Or use the proposed single entry point that chains 1→2→3 with logging and a
manifest (still no-promote by default):

```bash
# Dry run first — prints the exact command plan, writes nothing
python scripts/run_overnight_training.py --dry-run --generate-data --train-eval

# Real run, validation only, no promotion
python scripts/run_overnight_training.py \
    --generate-data --train-eval \
    --num-games 400 --agent-type mcts \
    --seeds 20260617 20260618 20260619 --games-per-seed 60
```

Fast smoke test (proves the pipeline end-to-end in minutes):

```bash
python scripts/champion_gauntlet.py --num-games 2 --seeds 1 2 --thinking-time-ms 10
# or
python scripts/run_overnight_training.py \
    --seeds 1 2 --games-per-seed 2 --thinking-time-ms-gauntlet 10 \
    --output-dir /tmp/overnight_smoke
```

---

## 3. Artifact Versioning

Prefer **timestamped run directories** and **config hashes** over overwriting
shared files. `champion_gauntlet.py` already records `config_hash` per candidate
in its summary; `run_overnight_training.py` already writes a per-run
`manifest.json`.

Recommended conventions:

| Artifact | Naming | Storage |
|----------|--------|---------|
| Snapshots | `data/snapshots_<YYYYMMDD>_<seed>.parquet` | committed only if small / canonical; else keep in run dir |
| Learned models | `models/eval_<YYYYMMDD>[_<tag>].pkl` | **never overwrite** `eval_from_overnight.pkl`; add new dated files |
| Calibrated weights | `data/layer6_calibrated_weights.json` is the canonical; archive prior copies as `data/archive/layer6_weights_<date>.json` before refit | |
| Candidate configs | `config/<name>_params.json`; include a `description` + `champion_version` field | committed |
| Gauntlet outputs | `arena_runs/gauntlets/gauntlet_<UTCstamp>/` (auto) | keep; never delete old runs |
| Overnight runs | `arena_runs/overnight/<UTCstamp>/` with `manifest.json` + per-stage logs (auto) | keep |
| Champion registry | versioned in-file (`v1`, `v2`, …) with `promoted_from`, `promotion_reason`, `config_hash` | committed, change reviewed |

Rules of thumb:

- **Append, don't overwrite.** New dated artifacts beside old ones.
- The `manifest.json` (run dir) is the source of truth for *what produced what*.
- Commit the registry change in its own small, reviewable commit.

---

## 4. Overnight Experiment Strategy

**Machine setup**

- 4+ physical cores (root parallelization scales near-linearly to core count;
  Layer 8 found 8 workers on 4 cores is *slower*). Match `--workers` (data gen)
  and candidate `num_workers` to physical cores.
- Disable system sleep / display sleep (see TODO). On the ephemeral remote
  container the job dies when the container is reclaimed — keep runs bounded and
  commit artifacts as you go.
- Confirm free disk: snapshots + many `games.jsonl` add up. Budget a few GB.

**Seeds & game counts**

- Use **≥ 3 seeds**; the gauntlet's `multiple_seeds` gate needs ≥ 2 and total
  games ≥ 40. For a decisive overnight verdict: `--seeds 3` × `--num-games 60`
  = 180 games.
- TrueSkill σ stays high (~7) until ~50+ games/agent; do not read a 25-game
  result as converged.

**Timing** (from TODO calibration): with `rollout_cutoff_depth` configs, games
run ~4–5 min each; a ~180-game gauntlet is a few hours. Full uncut rollouts took
2+ h/game — never use them overnight.

**Logging / checkpointing / recovery**

- Every arena run writes `games.jsonl` **incrementally** — a killed run still
  yields usable partial data.
- `run_overnight_training.py` logs each stage to its own file and records status
  in `manifest.json`; on failure it aborts and tells you to re-run with
  `--resume` (which skips stages whose output artifact already exists).
- `champion_loop.py` persists TrueSkill + accumulated snapshots between
  generations, so it resumes naturally on re-invocation.

**Morning review**

```bash
# The headline verdict:
cat arena_runs/gauntlets/gauntlet_*/gauntlet_summary.md | tail -n 40
# Per-run status + which stage (if any) failed:
cat arena_runs/overnight/<stamp>/manifest.json
# Loop progress over generations:
cat data/champion_progress.md
```

**When NOT to promote**

- Any gate failed (the summary says `No validated champion promoted.`).
- σ still large / fewer than 2 seeds / < 40 games.
- The "winner" only wins on one seat policy or one seed (check pairwise lines).
- The win comes from a config you can't reproduce (no `config_hash` recorded).
- You haven't read the summary yet. Promotion is a **human decision**; the
  `--promote` flag is the deliberate gate.

---

## 5. Agent-Assisted Overnight Runs

> Neither Claude Code hooks, the Codex CLI, nor GitHub Actions are assumed to be
> configured in this repo. Setup steps are in [`TODO.md`](../../TODO.md).

### Option A: Claude Code Routine / Command (Proposed)

Claude Code supports repo-local **slash commands** (markdown files under
`.claude/commands/`) for running scripted workflows, and **hooks** that can run
long shell commands asynchronously (useful for kicking off a multi-hour job and
being notified on completion).

- **Where:** `.claude/commands/run-overnight-mcts.md` (added this phase).
- **What it does:** drives `run_overnight_training.py` end-to-end.
- **Pre-flight checks:** clean-ish git status, deps installed, fast tests green,
  candidate configs valid, disk space OK.
- **Monitoring:** tail the per-stage logs under the run dir; surface the gauntlet
  summary when it lands.
- **Afterward:** write a markdown report and append manual follow-ups to
  `TODO.md`.
- **Manual confirmation before promotion:** the command must **never** pass
  `--promote`; a human re-runs the gauntlet with `--promote` after reading the
  summary.

### Option B: Codex CLI Non-Interactive Run (Proposed)

Codex CLI's `codex exec` runs a prompt non-interactively (scripts / CI-style).

- **Where:** `prompts/codex/overnight_mcts.md` (added this phase).
- **Invoke:** `codex exec "$(cat prompts/codex/overnight_mcts.md)"` (or pipe the
  file in), from the repo root in an environment with deps installed.
- **Shell commands it may run:** the read-only checks + `run_overnight_training.py`
  **without** `--promote`. It must not modify the registry.
- **Files it inspects:** `manifest.json`, per-stage logs, `gauntlet_summary.md`.
- **Summary it produces:** a dated markdown report of rankings + gate results.
- **Must not do automatically:** promote a champion, overwrite model artifacts,
  delete arena runs, or start an unbounded loop.

---

## 6. References

- Claude Code **commands** can run repo workflows; Claude Code **hooks** can run
  long-running shell commands asynchronously.
- Codex CLI provides a **non-interactive `codex exec`** mode for scripts/CI.
- Promotion gate logic: `analytics/tournament/gauntlet.py`.
- Search-side wiring of learned/calibrated evaluation: `mcts/mcts_agent.py`,
  `mcts/learned_evaluator.py`, `mcts/state_evaluator.py`.
