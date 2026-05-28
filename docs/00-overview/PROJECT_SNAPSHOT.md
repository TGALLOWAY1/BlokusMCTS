# Project Snapshot

> One-page orientation. Last audited: 2026-05-28. Status labels:
> `Implemented | Partial | Stubbed | Broken | Designed only | Deprecated | Unknown`.

## What this is

`MCTS_Laboratory` is a research platform that asks: **can a well-tuned
evaluation function beat brute-force search in 4-player Blokus?** It pairs a
high-performance Python Blokus engine with a configurable Monte Carlo Tree
Search agent (Layers 1–10 of iterative enhancements), a reproducible arena
tournament harness, and a React frontend that runs MCTS in-browser via Pyodide.

The headline finding: an agent with ML-calibrated evaluation weights and
shallow rollouts (depth 5, 25 iterations) beats one running 1,000 iterations of
default static evaluation. See [`KEY_FINDINGS.md`](../../KEY_FINDINGS.md).

> Note: this began as a reinforcement-learning environment (v1) and pivoted to
> MCTS in March 2026. RL code is archived under `archive/rl/`. Some metadata
> still reflects the old identity (e.g. `pyproject.toml` name `blokus-rl`) —
> see [Known Issues](../04-quality/KNOWN_ISSUES.md).

## Stack

| Layer | Technology | Evidence |
|---|---|---|
| Game engine + search | Python 3.9+ (numpy, numba) | `pyproject.toml`, `engine/`, `mcts/` |
| Backend API | FastAPI + Uvicorn, MongoDB (motor) | `webapi/`, `run_server.py` |
| Frontend | React 18 + TypeScript + Vite + Zustand | `frontend/package.json` |
| In-browser engine | Pyodide (Python→WASM) WebWorker | `browser_python/`, `frontend` (pyodide dep) |
| Ratings | TrueSkill, ELO, OpenSkill, Plackett-Luce | `analytics/tournament/`, `league/` |
| Data/ML | pandas, scikit-learn (regression, SHAP) | `scripts/analyze_layer6_features.py` |

CI: **none** (`.github/workflows/` absent) — a documented risk.

## Entry points

| Command | What it does | Status |
|---|---|---|
| `python run_server.py` | FastAPI backend on `:8000` (research profile) | Implemented |
| `python scripts/arena.py --config <cfg>` | Reproducible arena tournament | Implemented |
| `cd frontend && npm run dev` | Vite dev server on `:5173` | Implemented |
| `webapi/app.py` | FastAPI app module (research + deploy profiles) | Implemented |

## Build / test / lint

```bash
# Python
pip install -e .[dev]          # numpy, numba, fastapi, pytest, ruff, mypy, ...
pytest                          # testpaths=tests/; asyncio_mode=auto
ruff check .                    # line-length 88; E,W,F,I,B,C4,UP
mypy .                          # strict-ish (disallow_untyped_defs)

# Frontend (from frontend/)
npm install
npm run dev                     # vite
npm run build                   # tsc && vite build
npm run lint                    # eslint, --max-warnings 0
npm test                        # vitest run
```

## Current status at a glance

| Area | Status | Notes |
|---|---|---|
| Blokus engine (bitboard, frontier move-gen) | Implemented | `engine/`; optimized, benchmarked |
| MCTS agent (Layers 3–9) | Implemented | `mcts/mcts_agent.py`; best settings in KEY_FINDINGS |
| Arena/tournament harness | Implemented | `scripts/arena.py`, `analytics/tournament/` |
| Opponent modeling (Layer 7) | Implemented but **not recommended** | works after bugfix, no reliable advantage |
| Learned evaluator (Layer 2, GBT) | Implemented but **not recommended** | ~26ms inference eats the time budget |
| Frontend SPA (board, MCTS viz, scoreboard) | Implemented | `frontend/src/` |
| In-browser MCTS (Pyodide) | Implemented | `browser_python/`, `frontend/public/blokus_core.zip` |
| FastAPI backend | Implemented | research + deploy profiles |
| Champion self-improvement loop | Partial | infra exists; no agent is a *validated* champion yet (see `docs/CHAMPION_PROGRESSION.md`) |
| MCTS-core unit tests | Partial | per-layer tests strong; core UCB/selection/backup lacks dedicated tests |
| CI | Designed only | no workflow committed |

## Where to start

- New contributor / recruiter: root [`README.md`](../../README.md) → [`KEY_FINDINGS.md`](../../KEY_FINDINGS.md).
- AI agent: [`DOCUMENTATION_INDEX.md`](DOCUMENTATION_INDEX.md) → [Context Loading Protocol](../07-ai-context/CONTEXT_LOADING_PROTOCOL.md).
- Running experiments: [`docs/arena.md`](../arena.md), [`docs/config/agents/QUICK_START.md`](../config/agents/QUICK_START.md).
- Architecture: [`docs/02-architecture/ARCHITECTURE.md`](../02-architecture/ARCHITECTURE.md).
