# MCTS Laboratory — 4-player Blokus AI

A lab for building, training, and evaluating strong Monte-Carlo-Tree-Search
agents for 4-player Blokus, with a web demo you can play against.

**Read this first:** [AUDIT_REPORT.md](AUDIT_REPORT.md) — the July 2026 audit
that simplified this repo, fixed a structural MCTS bug (opponents in the tree
were modeled as *cooperating* with the root player), and replaced the training
workflow. Everything below reflects the post-audit state.

## What this repo does

- **Game engine** (`engine/`) — complete Blokus rules: legal move generation,
  corner-contact adjacency, scoring with all-pieces/monomino bonuses, pass and
  endgame handling. Numpy grid + bitboard acceleration.
- **Agents** (`agents/`, `mcts/`) — `random`, `heuristic` (no search), and the
  canonical `MCTSAgent`: UCT with **maxⁿ per-player backups** (each player in
  the tree optimizes its own reward), heuristic move ordering, configurable
  rollout policies, and optional experimental layers (RAVE, progressive
  widening, opponent modeling — off by default).
- **Arena** (`analytics/tournament/`) — seeded, seat-randomized 4-player
  tournaments with TrueSkill/Elo tracking and Wilson confidence intervals.
- **Training pipeline** (`training/`, driven by `mcts_lab` CLIs) — self-play
  data generation, evaluation-weight fitting (regression + TD), a fixed
  benchmark pool, and a two-stage statistically-gated champion promotion.
  Runs nightly via GitHub Actions (`.github/workflows/nightly-mcts-training.yml`).
- **Web demo** (`frontend/` + `webapi/`) — React UI playing against the
  champion in-browser via Pyodide (`scripts/build_browser_core.sh` bundles the
  Python core), plus a FastAPI backend for research/analysis views.

## Quick start

```bash
pip install -r requirements.txt

# 1. Sanity check the lab (~1 min)
python -m mcts_lab.checks

# 2. Run a benchmark arena (leaderboard with confidence intervals)
python -m mcts_lab.eval --agents champion,baseline --games 10 --seeds 20260620,20260621

# 3. Generate self-play data (snapshot corpus for weight fitting)
python -m mcts_lab.self_play --games 24

# 4. Train: produce candidate agent configs from the data
python -m mcts_lab.train

# 5. Promote: screen + confirm a candidate against the champion, gated
python -m mcts_lab.promote --candidate training/artifacts/candidates/<artifact>.json
```

`--thinking-ms 50` on `eval`/`promote` gives fast smoke runs; drop the flag
for full-strength (500 ms/move) evaluation.

### Run the web demo

```bash
bash scripts/build_browser_core.sh   # bundle engine+mcts+agents for Pyodide
python run_server.py                 # FastAPI backend on :8000
cd frontend && npm install && npm run dev
```

## The improvement loop

```
current champion ──(mcts_lab.self_play)──> snapshot corpus
        │                                        │
        │                              (mcts_lab.train)
        │                                        ▼
        │                              candidate artifact
        │                                        │
        └───(mcts_lab.promote: screen ≥20 games → confirm ≥60 games,
             fixed seeds, fixed benchmark pool, Wilson-CI + TrueSkill gates)
                                                 │
                                    pass ──> new champion
                                    (training/state/champion.json,
                                     old champion checkpointed as a
                                     future benchmark opponent)
```

- **Champion registry:** `training/state/champion.json` is the single source
  of truth (version, params, rating, full lineage). Promoted champions are
  checkpointed under `training/state/checkpoints/` and join the evaluation
  pool, so strength ratchets and can't silently cycle.
- **Statistical guardrails:** promotion requires beating the champion
  head-to-head, positive Elo *and* TrueSkill deltas, rank #1 vs the fixed pool
  (heuristic, random, two fixed MCTS anchors), ≥2 fixed seeds, and holding all
  of that over a 60+ game confirmation run. Elo movement without a promotion
  is measurement noise, and the reports label it as such.
- **Nightly automation:** the GitHub Actions workflow resumes from committed
  state every 6 hours, runs the same loop (`training.nightly_run`), commits
  results, and emails a summary. Reports land in `training/status.md` and
  `training/reports/`.

## Reproducing benchmark results

All evaluation is seed-deterministic. To reproduce a leaderboard:

```bash
python -m mcts_lab.eval --agents champion,baseline --games 20 \
    --seeds 20260620,20260621 --out results.json
```

Same seeds + same agent configs ⇒ identical games. Arena outputs (per-game
JSONL + pooled summary) are written under `training/state/selfplay_runs/` and
historical gauntlet runs live in `arena_runs/`.

## Current best agent status

- The long-standing `gen0` champion (random rollouts, depth-5 cutoff, RAVE on
  a broken reward scheme) was diagnosed as *weaker than the no-search
  heuristic agent* — see AUDIT_REPORT.md §1. The corrected strong baseline —
  **greedy-sample rollouts (sample 12 moves/step, pick best by fast
  heuristic), rollout cutoff 12, heuristic move ordering, plain UCT with maxⁿ
  backups** — is the promotion candidate expected to replace it through the
  gate (`python -m mcts_lab.promote`).
- Absolute Elo numbers before this fix (~1200 plateau) are measurement noise
  around an unchanging agent and are not comparable to post-fix ratings.
- Next strength milestones, in order: retune evaluation weights on fresh
  self-play from the fixed search; retest RAVE/minimax/progressive-widening on
  top of maxⁿ; learn a rollout/move-ordering policy from MCTS visit counts.

## What files matter

| Path | What it is |
|---|---|
| `engine/` | Blokus rules engine (board, move generator, pieces, scoring) |
| `mcts/mcts_agent.py` | The canonical MCTS agent (maxⁿ UCT + options) |
| `mcts/state_evaluator.py` | Fast state evaluation (phase-dependent weights) |
| `agents/` | Random/heuristic agents + champion loading |
| `analytics/tournament/arena_runner.py` | Arena harness (seeded, seat-randomized) |
| `analytics/tournament/gauntlet.py` | Pooled stats + conservative promotion decision |
| `mcts_lab/` | **The canonical CLI workflow** (checks/eval/self_play/train/promote) |
| `training/` | Durable pipeline internals + state (`training/state/`) |
| `training/state/champion.json` | Champion registry (version, params, lineage) |
| `.github/workflows/nightly-mcts-training.yml` | Nightly training automation |
| `webapi/`, `frontend/`, `browser_python/worker_bridge.py` | Web demo |
| `scripts/` | Arena CLI, champion gauntlet, Pyodide bundle build |
| `tests/` | Engine/agent/pipeline tests (`python -m pytest tests/ -q`) |

Docs index: [docs/README.md](docs/README.md). Historical layer-by-layer
experiment narratives predate the maxⁿ fix — their strength conclusions are
obsolete (see AUDIT_REPORT.md §6).
