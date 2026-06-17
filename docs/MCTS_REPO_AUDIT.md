# MCTS Laboratory — Repo Audit & Recovery Plan (Phase 1)

> **Date:** 2026-06-17
> **Author:** Phase 1 audit (repo audit + recovery plan)
> **Scope:** Assessment only. No code was changed, deleted, or refactored.
> **Goal:** Make the project understandable, measurable, and recoverable —
> establish the shortest path to a benchmarked champion Blokus agent and an
> eventual playable web demo.

---

## 1. Executive Summary

`MCTS_Laboratory` is a **research platform** that asks whether a well-tuned
evaluation function can beat brute-force search in **4-player Blokus**. It
contains a high-performance Python Blokus engine, a heavily layered
configurable MCTS agent (9 "layers" of enhancements), a reproducible arena
tournament harness, a FastAPI backend, and a React + Pyodide frontend.

**Overall health: the project is in better shape than "messy" suggests, but it
is hard to navigate and the single most important question — "which agent is
strongest?" — is currently unanswered by the repo itself.**

Key conclusions:

1. **The game engine is solid and well-tested**, but uses **non-standard
   "house" scoring** (corner/center bonuses). This is documented in code but is
   a correctness/validity risk for a public web app, and means win rates are not
   directly comparable to real Blokus.
2. **The engine is duplicated** into `browser_python/engine/` (for Pyodide).
   The two copies can silently diverge — a known, flagged risk.
3. **There are exactly 3 live agents** (Random, Heuristic, MCTS). Everything
   else is an adapter, an archived dead end (FastMCTS), or an unimplemented RL
   config.
4. **There is no active training loop in the RL sense.** "Training" today means
   self-play data generation → offline regression of evaluation weights. The
   PPO/RL code is archived and disconnected.
5. **Evaluation is the strongest part of the repo**: deterministic, seeded,
   reproducible arena tournaments with TrueSkill, pairwise records, win rates,
   full replayable game logs (`games.jsonl`), and snapshot datasets.
6. **The "champion" story is contradictory.** `data/champion_registry.json`
   declares `champion_v1` the champion with **null metrics**, while
   `docs/CHAMPION_PROGRESSION.md` (which claims to be the single source of
   truth) says **there is no validated champion**, `champion_v1` is a *failed*
   candidate that loses to a same-budget peer, and `champion_minimal` is an
   unvalidated candidate. **This contradiction is the central problem to fix.**
7. **The web stack is surprisingly mature** — a full FastAPI backend with clean
   serializable state/move schemas, MongoDB persistence, and a React frontend
   that can run MCTS in-browser. Web-app readiness is high.

**Strongest-agent classification: B (probably identifiable, needs
verification).** See §7.

**The shortest path to a champion** is *not* more features — it is to run one
clean, multi-seed gauntlet between the existing candidate configs
(`champion_v1`, `champion_minimal`, `pool_peer_500ms`) and the "best config"
from `KEY_FINDINGS.md`, then write the winner (with real metrics) into the
registry. The infrastructure to do this already exists.

---

## 2. Repo Structure Map

```
MCTS_Laboratory/
├── engine/                  CORE GAME ENGINE (canonical)
│   ├── game.py              BlokusGame: orchestration, scoring, game-over
│   ├── board.py             Board state, rule enforcement, frontier
│   ├── move_generator.py    Legal move generation (frontier + bitboard)
│   ├── pieces.py            21 piece definitions + orientations
│   └── bitboard.py          Bitboard masks for fast legality
│
├── mcts/                    THE MCTS AGENT (the heart of the project)
│   ├── mcts_agent.py        MCTSAgent — Layers 1–9 (2172 lines)
│   ├── mcts.py              Core tree / node primitives
│   ├── champion_profile.py  Loads champion config → MCTS kwargs
│   ├── state_evaluator.py   BlokusStateEvaluator (Layers 4/6)
│   ├── learned_evaluator.py LearnedWinProbabilityEvaluator (loads .pkl)
│   ├── opponent_model.py    Layer 7 opponent modeling
│   ├── parallel.py          Layer 8 root parallelization
│   ├── move_heuristic.py, adaptive_budget.py, search_trace.py,
│   ├── zobrist.py, utils.py
│
├── agents/                  AGENT INTERFACES + simple agents
│   ├── base_agent.py        Base class (partially adopted)
│   ├── random_agent.py      RandomAgent (active)
│   ├── heuristic_agent.py   HeuristicAgent (active, also MCTS rollout policy)
│   ├── gameplay_human.py    Human move adapter (web)
│   ├── gameplay_protocol.py choose_move(...) protocol (web)
│   └── registry.py          Factory + adapters (act()/select_action())
│
├── analytics/               EVALUATION & METRICS
│   ├── tournament/
│   │   ├── arena_runner.py  Runs multi-game tournaments
│   │   ├── arena_stats.py   Win rates, pairwise, seat analysis
│   │   └── trueskill_rating.py
│   ├── metrics/, aggregate/, winprob/, heatmap/, logging/, baseline/
│   └── tests/
│
├── scripts/                 ENTRY POINTS + experiment configs (CLUTTERED)
│   ├── arena.py             ★ arena CLI entry point
│   ├── champion_loop.py     champion self-improvement loop
│   ├── champion_arena.py    champion gauntlet runner
│   ├── generate_training_data.py  self-play snapshot generation
│   ├── train_eval_model.py  trains evaluation .pkl from snapshots
│   ├── validate_eval_model.py, self_improve.py, parameter_sweep.py
│   ├── analyze_layer*.py, collect_layer6_data.py, generate_*.py
│   └── arena_config_*.json  ~38 experiment configs (Layers 1–10)
│
├── config/                  AGENT / CHAMPION CONFIGS
│   ├── challenge_champion_config.json
│   ├── champion_arena_params.json     (champion_v1 params)
│   ├── champion_minimal_params.json   (champion_minimal candidate)
│   └── agents/ppo_agent_v1.yaml       (RL config — no live impl)
│
├── webapi/                  FASTAPI BACKEND
│   ├── app.py               1842 lines — all routes, profiles
│   ├── deploy_validation.py time-budget caps for deploy
│   └── db/models.py         MongoDB game/move records
├── api-runtime/app.py       deploy-profile re-export of webapi.app
├── run_server.py            uvicorn launcher (:8000)
├── schemas/game_state.py    Pydantic GameState + Move schemas
│
├── frontend/                REACT + TS + VITE SPA
│   └── src/ (components, hooks, store, pages) + Pyodide in-browser MCTS
├── browser_python/          PYODIDE MIRROR (engine/, mcts/, agents/ copies)
│   └── worker_bridge.py     wraps engine+MCTS for the browser worker
│
├── league/                  Rating helpers (elo.py, pdl.py)
├── benchmarks/              Perf/throughput benchmarks (not eval)
├── models/eval_from_overnight.pkl   trained evaluator (2.3 MB)
├── data/                    calibrated weights, registry, traces (small)
├── tests/                   38 pytest files (engine + layers + webapi)
├── docs/                    LARGE structured docs system (see §below)
└── archive/                 RL code, old arena runs, layer reports, logs
```

### Structural confusion flags

| Flag | Detail |
|---|---|
| **Engine duplicated** | `engine/` and `browser_python/engine/` are copies; can diverge silently. Same for `agents/` and `mcts/`. |
| **`scripts/` is a dumping ground** | ~38 `arena_config_*.json` + ~50 scripts mixing entry points, one-off experiments, and analysis. No `scripts/experiments/` vs `scripts/` separation. |
| **Two "champion" sources of truth** | `data/champion_registry.json` vs `docs/CHAMPION_PROGRESSION.md` disagree (see §7). |
| **Root markdown sprawl** | `README.md`, `KEY_FINDINGS.md`, `TODO.md`, `FEATURES.md`, `CODE_QUALITY_AUDIT_NOTES.md` at root, plus a full `docs/` tree and an `archive/docs/` tree and `docs/_archived-2026-05/`. |
| **RL residue** | `pyproject.toml` is still named `blokus-rl`; `config/agents/ppo_agent*.yaml`, `archive/rl/` reflect the abandoned RL identity. |
| **Duplicated story images** | `docs/story_images/*.png` and `frontend/public/assets/story/editorial/*.png` are the same large generated images tracked twice (~1.6–2 MB each). |

The repo already has a good docs system under `docs/00-overview` …
`docs/07-ai-context`. Start there (`docs/00-overview/DOCUMENTATION_INDEX.md`).

---

## 3. Game Engine Assessment

**Canonical engine:** `engine/` (Python). A near-identical copy lives in
`browser_python/engine/` for Pyodide.

| Concern | Finding | File |
|---|---|---|
| Rules implementation | Clean separation: orchestration / board+rules / move-gen / pieces / bitboard | `engine/game.py`, `board.py`, `move_generator.py`, `pieces.py`, `bitboard.py` |
| Legal move generation | `LegalMoveGenerator.get_legal_moves()`; frontier-based default with naive full-scan fallback; optional bitboard legality | `engine/move_generator.py:131` |
| Turn advancement | `BlokusGame.make_move()` → `Board.place_piece()` → `_update_current_player()` round-robin RED→BLUE→YELLOW→GREEN | `engine/game.py:57`, `board.py:557` |
| Game termination | Ends when **all 4 players** have no legal move; single-player pass does not end game | `engine/game.py:182`, `move_generator.py:962` |
| Result / winner | `get_game_result()` → `GameResult` (scores, winner_ids, tie flag); ties handled | `engine/game.py:216` |
| State format | 20×20 numpy grid (0 empty, 1–4 player); `grid.tolist()` JSON-serializable; bitboard mirror | `engine/board.py` |
| Move format | `Move(piece_id 1–21, orientation, anchor_row, anchor_col)` → `get_positions()` | `engine/move_generator.py:91` |

**Rule completeness:** ✅ 21 pieces per player, 4 players with distinct start
corners, first-move corner rule, diagonal-touch requirement, edge-adjacency
prohibition — all enforced.

### Correctness risks (ordered by importance)

1. **Non-standard scoring (validity risk).** `engine/game.py:287` `get_score()`
   = base (1/square, +15 for all 21 pieces) **plus house bonuses**: +5 per
   controlled corner and +2 per center square (`_calculate_bonus_score`,
   `game.py:303–352`). This is **documented in the docstring** (`game.py:221`,
   "includes house bonuses beyond standard Blokus rules") but it means:
   - Win rates / TrueSkill measure performance at *this variant*, not classic
     Blokus.
   - A public web app would surprise users who expect standard scoring.
   *Recommendation:* keep but make it a config flag (`standard | house`) before
   the web demo. Do **not** change silently — experiments depend on it.
   *Resolved (Phase 5):* `BlokusGame(scoring_mode=...)` now exposes
   `standard | house`. The default remains `house` so every prior arena run and
   experiment is byte-for-byte unchanged (arena_runner constructs `BlokusGame()`
   with no mode). The web API defaults public **deploy** play to `standard` and
   the **research** profile to `house`, and surfaces the active mode in
   `GameState.scoring_mode`. House bonuses (corner/center) are therefore the
   scoring system used in all prior win-rate / TrueSkill experiments —
   `engine/game.py`, `schemas/game_state.py`, `webapi/app.py`.
2. **Engine duplication drift.** `browser_python/engine/` is a manual copy. No
   guard enforces parity → the in-browser game can diverge from the arena
   engine. (Flagged in `PRIORITIZED_TODO` #6.)
3. **Bitboard/grid equivalence is sampled, not exhaustive** (probabilistic
   ~5% check). Covered by `tests/test_legality_bitboard_equivalence.py` and
   `tests/test_move_generation_equivalence.py` but not proven.
4. **Pass handled outside the engine** (API/UI layer), not as an engine action.

**Tests for rule correctness:** Strong. `tests/test_engine.py`,
`test_game_over_logic.py`, `test_game_result.py`, `test_frontier_basic.py`,
`test_move_generation_equivalence.py`, `test_bitboard_basic.py`,
`test_pieces_orientations.py`, `test_piece_shapes_match.py`,
`test_audit_invariants.py`. These are meaningful (invariants, not smoke).

---

## 4. Agent Inventory

There is a partially-adopted base class (`agents/base_agent.py`) and **three
different calling conventions** coexist — a real source of confusion:

- `select_action(board, player, legal_moves)` — Random/Heuristic/MCTS (arena)
- `choose_move(board, player, legal_moves, time_budget_ms)` — gameplay protocol (web)
- `act(observation, legal_mask, env)` — registry adapters (RL-era)

| Agent | File | Type | Description | I/O | Used by | Status |
|---|---|---|---|---|---|---|
| **RandomAgent** | `agents/random_agent.py` | random | Uniform pick from legal moves | `select_action` → `Move` | arena, baselines, MCTS comparisons | **active** |
| **HeuristicAgent** | `agents/heuristic_agent.py` | heuristic | Move scoring (piece size, corner creation, edge avoidance, center) + softmax | `select_action` → `Move` | arena, **MCTS rollout policy**, web | **active** |
| **MCTSAgent** | `mcts/mcts_agent.py` | MCTS | UCB1 + transposition + Layers 3–9 (PW, RAVE, NST, state eval, opponent model, parallel, adaptive meta) | `select_action` → `Move` | arena (primary), web factory | **active (primary)** |
| HumanAgent | `agents/gameplay_human.py` | human | Wraps human-submitted moves for web | `choose_move` | webapi | active (web) |
| Registry adapters | `agents/registry.py` | wrappers | `RandomAgentAdapter`, `HeuristicAgentAdapter`, `MCTSAgentAdapter`, `RLPolicyAgent` (SB3 MaskablePPO wrapper) | `act(...)` | RL-era / league | partial — RLPolicyAgent has no trained model |
| FastMCTSAgent | `browser_python/agents/fast_mcts_agent.py`, `archive/agents/` | invalid MCTS | **NOT a valid tree search** (rollouts score from root). Explicitly rejected by `registry.build_baseline_agent` | — | none | **obsolete (blocked)** |
| GameplayFastMCTSAgent | `browser_python/agents/gameplay_fast_mcts.py`, `archive/agents/` | invalid MCTS | wrapper over FastMCTS | — | none | **obsolete** |
| PPO agent | `config/agents/ppo_agent_v1.yaml` (+ sweeps) | neural (RL) | MaskablePPO config (2×256 MLP) | — | — | **config only — no live implementation** |

**Duplication:** `browser_python/{agents,mcts}/` mirror the root copies for
Pyodide. The mirror was reported as non-divergent at audit time, but nothing
enforces it.

**Champion configs (these are *configs of MCTSAgent*, not separate classes):**
- `config/challenge_champion_config.json` — the playable "challenge champion"
  loaded by `mcts/champion_profile.py` (used by web + browser worker).
- `config/champion_arena_params.json` — `champion_v1` params.
- `config/champion_minimal_params.json` — `champion_minimal` candidate.

---

## 5. Training Flow

**There is no live reinforcement-learning loop.** "Training" today = self-play
data generation → offline regression to produce **evaluation weights** for the
MCTS state evaluator. PPO/SB3 code exists only under `archive/rl/` and is
disconnected from the arena.

```
scripts/generate_training_data.py
  ├─ runs self-play games (MCTS / heuristic / random), deterministic per-seed
  ├─ extracts feature snapshots at fixed plies (8,16,…,64)
  └─ writes snapshots.parquet  (≈40 features × 4 players × plies × games)
        │
        ▼
scripts/train_eval_model.py
  ├─ loads snapshots.parquet
  ├─ builds pairwise (player_i vs player_j) win-label dataset
  ├─ splits by-game (avoids leakage), fits LogisticRegression or per-phase GBT
  └─ writes models/eval_from_overnight.pkl  (joblib)
        │
        ▼
mcts/learned_evaluator.py  (LearnedWinProbabilityEvaluator)
  └─ loads the .pkl; optionally used by MCTSAgent during rollout evaluation
```

A parallel, lighter path produced **calibrated static weights**
(`data/layer6_calibrated_weights.json`, from regression on 13K+ states) which
are what the champion configs actually use.

**Champion self-improvement loop** (`scripts/champion_loop.py`,
`scripts/champion_arena.py`): runs a gauntlet of the champion config vs a tiered
pool, can recalibrate evaluator weights, and is *meant* to update
`data/champion_registry.json`.

**What's brittle / broken:**
- Snapshot **feature columns are matched by name with no schema validation** —
  a rename silently breaks the evaluator.
- `data/champion_registry.json` was written **with null win-rate/TrueSkill/score
  and `total_games_played: 0`** — i.e. the champion was promoted without metrics.
- The RL config files (`config/agents/ppo_agent*.yaml`) imply a training path
  that **does not exist** in the live tree.
- Artifacts (`eval_from_overnight.pkl` vs `archive/rl/models/eval_v1*.pkl`) are
  not clearly versioned against the configs that consume them.

---

## 6. Evaluation Flow

This is the **most mature** part of the repo. Agents can play each other, win
rates and ratings are computed, results are saved, runs are reproducible, and
games are fully replayable.

```
scripts/arena.py  --config scripts/arena_config*.json
  └─ analytics/tournament/arena_runner.py :: run_experiment()
       ├─ builds agents from type strings (mcts | heuristic | random |
       │  learned_evaluator+checkpoint); fast_mcts is rejected
       ├─ deterministic seeding: run_seed → per-game seed
       │  (stable_hash_int(run_seed, game_index)) → per-agent seed
       ├─ seat policy: randomized | round_robin
       ├─ plays full 4-player BlokusGame; optional ply snapshots
       └─ writes arena_runs/<ts>_<hash>/
            ├─ games.jsonl     full replayable game history
            ├─ summary.json    win rates, pairwise, TrueSkill
            ├─ summary.md       human-readable tables
            ├─ snapshots.csv/.parquet   ML dataset (if enabled)
            └─ run_config.json  exact config for reproducibility
  └─ analytics/tournament/arena_stats.py
       ├─ win rate (outright=1.0, shared=0.5), score stats, p25/p75
       ├─ pairwise head-to-head (a_beats_b / b_beats_a / ties)
       ├─ per-seat win rate (seat-bias visibility)
       └─ TrueSkill (analytics/tournament/trueskill_rating.py)
```

| Capability | Status |
|---|---|
| Agents play each other | ✅ arena tournaments |
| Win rates | ✅ with shared-win handling |
| Ratings | ✅ TrueSkill (primary); Elo/OpenSkill helpers in `league/` |
| Results saved | ✅ `summary.json/.md`, `games.jsonl`, snapshots |
| Replay | ✅ from `games.jsonl` (also web replay from MongoDB) |
| Benchmark opponents | ✅ tiered pool (`pool_heuristic`, `pool_l45_100ms`, `pool_peer_500ms`, …) |
| Seeded / reproducible | ✅ deterministic seed → game → agent seeds + saved config |

**Weaknesses:** multi-seat bias is *measured* but not corrected; most published
results use single-seed, ~25–60 game runs (`PRIORITIZED_TODO` #7 asks for
multi-seed 100+ game validation); agent internal RNG state isn't captured (exact
move-replay needs identical agent build).

**The evaluation harness is good enough to identify a champion today** — it just
hasn't been run as one clean, decisive, multi-seed gauntlet whose result is
written back to the registry.

---

## 7. Current Strongest Agent Assessment

**Classification: B — probably identifiable, but needs verification.**

Why not A: the repo's two "champion" sources of truth **disagree**, and the one
machine-readable champion record has **no metrics**:

- `data/champion_registry.json` → `current_version: "v1"`, but every metric
  (`avg_win_rate`, `avg_trueskill_mu`, `avg_score`) is **null** and
  `total_games_played: 0`. It promotes `champion_v1` on description alone.
- `docs/CHAMPION_PROGRESSION.md` (declares itself the single source of truth,
  *"if a doc disagrees with this page, this page is right"*) states:
  - **"There is no validated champion."**
  - `champion_v1` is a **failed** full-stack candidate that **loses
    head-to-head to `pool_peer_500ms`** (a same-budget MCTS without opponent
    modeling), kept only as a regression baseline.
  - `champion_minimal` (validated layers + Layer 8 parallelization) is the
    **current candidate**, awaiting a "Night-1 reset" gate.
  - No human-level play demonstrated (best evidence 65% WR vs `pool_heuristic`,
    Wilson-95 lower bound 52.4%, below the ≥65% bar).

Why not C: we *do* have strong directional evidence. `KEY_FINDINGS.md` documents
a coherent "best configuration" (random rollout, cutoff depth 5, minimax
α=0.25, calibrated weights, RAVE k=1000, root 2-worker parallel, adaptive
rollout depth) and the arena harness can settle it.

**Practical reading:** the empirically strongest *validated* agent right now is
most likely **`pool_peer_500ms`** (it beats the registered champion), with
**`champion_minimal`** the leading candidate to surpass it — but neither has a
recorded, multi-seed, registry-backed win-rate. **The fix is one decisive
gauntlet, not new research.**

---

## 8. Technical Debt / Cleanup

> Nothing below has been deleted. These are *candidates* with justification.

| Item | Location | Action (later phase) | Safety |
|---|---|---|---|
| **Champion source-of-truth conflict** | `data/champion_registry.json` vs `docs/CHAMPION_PROGRESSION.md` | Reconcile; registry must carry real metrics | High value |
| Engine/agent duplication | `browser_python/{engine,mcts,agents}/` | Add a parity/sync guard or build step (`scripts/build_browser_core.sh` exists) | Don't merge yet |
| `scripts/` clutter | ~38 `arena_config_*.json`, ~50 scripts | Move per-layer experiment configs to `scripts/experiments/` | Safe (paths in docs) |
| RL residue | `pyproject.toml` name `blokus-rl`; `config/agents/ppo_agent*.yaml`; `archive/rl/` | Rename package; clearly mark RL configs archived | Low risk |
| Obsolete agents | FastMCTS in `browser_python/agents/` + `archive/agents/` | Already blocked; consider removing browser copy | Verify no import |
| Duplicated story images | `docs/story_images/` ↔ `frontend/public/assets/story/editorial/` | De-dupe (~20 MB of PNGs tracked twice) | Confirm references first |
| **No MCTS-core unit test** | `mcts/mcts_agent.py` (2172 lines) untested at the search level | Add `tests/test_mcts_core.py` (selection/expansion/backprop) | High value (`PRIORITIZED_TODO` #1) |
| **No CI** | `.github/workflows/` absent | Add pytest+ruff+mypy CI | High value (#3) |
| Broken editable install | `pyproject.toml` packaging | Fix `pip install -e .` (README quickstart) | High value (#2) |
| Generated artifacts on disk | `arena_runs/` (6.3 MB), `archive/arena_runs/` (15 MB) | Correctly **gitignored** already; large on disk only | OK |
| Inconsistent agent interfaces | `select_action` / `choose_move` / `act` | Standardize (Phase 2) | Medium |
| Doc sprawl | root `*.md` + `docs/` + `archive/docs/` + `docs/_archived-2026-05/` | Already partly organized; keep consolidating | Low risk |

**Models/data (small, fine to keep):** `models/eval_from_overnight.pkl`
(2.3 MB), `archive/rl/models/eval_v1*.pkl`, `data/*.json` (calibrated weights,
champion registry, throughput calibration, sample trace). **No neural-network
checkpoints exist** (no `.pth/.safetensors/.h5`) — evaluators are scikit-learn /
joblib artifacts.

---

## 9. Web App Readiness

**Readiness is HIGH.** A working backend and frontend already exist.

| Question | Answer | Evidence |
|---|---|---|
| Engine usable from a backend/API? | ✅ Yes — FastAPI app fully wraps the engine | `webapi/app.py` (1842 lines), `run_server.py`, `api-runtime/app.py` |
| Agent move from serialized state? | ✅ Yes — POST move / advance_turn drives MCTSAgent from board state | `webapi/app.py` routes; `webapi/gameplay_agent_factory` |
| Clean state format? | ✅ Pydantic `GameState` (board `List[List[int]]`, scores, legal moves, mobility, heatmap, MCTS diagnostics) | `schemas/game_state.py` |
| Clean move format? | ✅ `Move{piece_id 1–21, orientation, anchor_row 0–19, anchor_col 0–19}` validated | `schemas/game_state.py` |
| Games resumable / history saved? | ✅ MongoDB `game_records` + `move_records`; replay/analysis endpoints | `webapi/db/models.py` |
| Frontend exists? | ✅ React 18 + TS + Vite + Zustand; can also run **MCTS in-browser via Pyodide** | `frontend/`, `browser_python/worker_bridge.py` |
| Deploy target? | ✅ `vercel.json` (Python runtime → `api-runtime/app.py`, SPA rewrites) | `vercel.json` |

**Existing endpoints (abridged):** `POST /api/games`, `GET /api/games/{id}`,
`POST /api/games/{id}/move`, `/pass`, `/advance_turn`, `/finish`,
`GET /api/agents`, `GET /api/arena-runs[/{id}]`, `GET /health`. Deploy profile
caps MCTS time budget at 9000 ms (`webapi/deploy_validation.py`).

**What still needs attention before a public "play the champion" demo:**
1. **Pin the champion** the web app serves (today it loads
   `challenge_champion_config.json`, an *unvalidated* config — see §7).
2. **Scoring mode**: decide standard vs house scoring for public users (§3).
3. WebSocket endpoints are defined but not fully wired (polling via
   `advance_turn` works).
4. Browser/arena engine parity guard (§8) so the in-browser game matches the
   benchmarked agent.

---

## 10. Recommended Recovery Plan

Guiding principle: **the next win is settling the champion question with the
tools that already exist, not adding features.**

### Phase 2 — Standardize Agent Interface
- **Goal:** One canonical agent contract so arena, web, and browser share code.
- **Tasks:** Adopt `agents/base_agent.py` everywhere; converge
  `select_action` / `choose_move` / `act` into one interface (keep thin
  adapters); document it in `docs/02-architecture/`.
- **Output:** A single `Agent` protocol + adapter shims; all 3 live agents
  conform.
- **Risk:** Medium (touches arena + web call sites).
- **Effort:** 2–3 days.
- **Portfolio value:** Medium — shows API design discipline.

### Phase 3 — Build / Harden Evaluation Harness
- **Goal:** A one-command, multi-seed, decisive gauntlet with confidence
  intervals.
- **Tasks:** The harness already exists (`scripts/arena.py`); add a
  `scripts/gauntlet.py` (or extend `champion_arena.py`) that runs ≥3 seeds ×
  100+ games, aggregates with Wilson CIs, and emits one ranked table; add
  `tests/test_mcts_core.py`; add CI (pytest+ruff+mypy); fix editable install.
- **Output:** Reproducible ranked leaderboard with CIs; green CI.
- **Risk:** Low.
- **Effort:** 2–4 days.
- **Portfolio value:** High — "I can measure agent strength rigorously."

### Phase 4 — Identify the Champion
- **Goal:** Resolve §7 — name the strongest agent with real numbers.
- **Tasks:** Run the Phase-3 gauntlet over `champion_v1`, `champion_minimal`,
  `pool_peer_500ms`, and the `KEY_FINDINGS` "best config"; write the winner +
  metrics into `data/champion_registry.json`; make
  `docs/CHAMPION_PROGRESSION.md` and the registry agree.
- **Output:** A single, validated, registry-backed champion config.
- **Risk:** Low (compute-bound).
- **Effort:** 1–2 days + tournament compute.
- **Portfolio value:** **Highest** — turns a research pile into "here is the
  champion and here's the evidence."

### Phase 5 — Clean Training + Checkpoint Flow
- **Goal:** A trustworthy, versioned path from data → evaluator → champion.
- **Tasks:** Add snapshot **schema validation**; version artifacts against the
  configs that consume them; document `generate_training_data → train_eval_model
  → champion_loop`; clearly archive/retire the dead RL config + `blokus-rl`
  name.
- **Output:** `docs/03-implementation/TRAINING_FLOW.md` + validated pipeline.
- **Risk:** Medium.
- **Effort:** 3–5 days.
- **Portfolio value:** Medium-High.

### Phase 6 — Prepare Web API for the Champion
- **Goal:** Serve the *validated* champion safely and with standard rules.
- **Tasks:** Point the web factory at the Phase-4 champion config; add a
  scoring-mode flag (standard | house); add the engine parity guard; finish or
  formally drop WebSocket; structured API error codes.
- **Output:** A backend that serves the benchmarked champion under standard
  Blokus rules.
- **Risk:** Medium.
- **Effort:** 3–5 days.
- **Portfolio value:** High.

### Phase 7 — Build the Playable Web Interface
- **Goal:** A polished "play the champion" demo (likely on Vercel).
- **Tasks:** Wire the existing React frontend to the Phase-6 API (or the
  Pyodide path); human vs champion flow; show MCTS diagnostics/heatmap; game
  history/replay; deploy.
- **Output:** A public, playable Blokus-vs-champion demo.
- **Risk:** Medium.
- **Effort:** 1–2 weeks (polish-bound).
- **Portfolio value:** **Highest** — the visible, shareable deliverable.

---

## Appendix — Unknowns / Things to Verify

- Exact head-to-head numbers behind "`champion_v1` loses to `pool_peer_500ms`"
  live in PRs #146–#148 / `archive/arena_runs/`; not re-derived here.
- Whether `browser_python/` copies are byte-identical to the canonical modules
  *today* (no parity check exists; reported equal at audit time).
- Whether `models/eval_from_overnight.pkl` is the artifact any current champion
  config actually loads (configs mostly use static calibrated weights).
- Frontend↔backend wiring was assessed from route/hook reads, not a live run.
