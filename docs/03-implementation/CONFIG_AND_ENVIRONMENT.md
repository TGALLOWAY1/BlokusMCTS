# Configuration & Environment

> How the project is configured. Last audited: 2026-05-28.

## Environment variables

Only MongoDB is configured via env (`.env.example`):

| Variable | Purpose | Required for |
|---|---|---|
| `MONGODB_URI` | MongoDB connection string | Research-profile backend only |
| `MONGODB_DB_NAME` | Database name (default `blokusdb`) | Research-profile backend only |

The deploy/gameplay profile and the arena CLI do **not** require MongoDB.
Copy `.env.example` → `.env` for local research-profile work. The URI is a
secret — never commit a populated `.env` (see
[Security & Privacy Notes](../04-quality/SECURITY_AND_PRIVACY_NOTES.md)).

## Python packaging (`pyproject.toml`)

- Runtime deps: `numpy`, `numba`, `fastapi`, `uvicorn[standard]`, `pydantic`,
  `orjson`, `websockets`, `openskill`.
- Dev extra (`pip install -e .[dev]`): `pytest`, `pytest-asyncio`, `ruff`, `mypy`.
- Tooling: `ruff` (line-length 88; `E,W,F,I,B,C4,UP`), `mypy` (strict-ish:
  `disallow_untyped_defs`, `warn_unreachable`, …), `pytest`
  (`testpaths=["tests"]`, `asyncio_mode="auto"`, `pythonpath=[".", "browser_python"]`).
- **Known inconsistency:** `[project].name` is still `blokus-rl` with description
  "Blokus Reinforcement Learning Environment" and a placeholder author — leftover
  from the v1 RL identity. Logged in [Known Issues](../04-quality/KNOWN_ISSUES.md);
  not changed by the docs pass.

## Backend profiles (`webapi/profile.py`)

- **research** — full route surface (gameplay + research/analysis/history/arena);
  used by `run_server.py` locally; needs MongoDB.
- **deploy** — gameplay-only, used on Vercel (`api-runtime/`, `vercel.json`).

See [`docs/webapi/README.md`](../webapi/README.md) and
[`docs/deployment.md`](../deployment.md).

## Agent configs (`config/`)

| File | Purpose |
|---|---|
| `config/challenge_champion_config.json` | Challenge Champion gameplay profile (tiers, budget caps) |
| `config/champion_arena_params.json` | Champion gauntlet arena parameters |
| `config/champion_minimal_params.json` | Minimal validated stack (best-of-layers, root parallelism) |
| `config/agents/QUICK_START.md` | How to write agent configs and run sweeps |

## Arena configs (`scripts/arena_config*.json`)

~35 JSON presets drive `scripts/arena.py`. They are organized by experiment
family; representative members:

| Family | Examples | Purpose |
|---|---|---|
| Default / fast | `arena_config.json`, `arena_config_fastest.json`, `arena_config_fair_time.json` | Standard + smoke runs |
| Layer 3–10 sweeps | `arena_config_layer4_cutoff.json`, `arena_config_layer5_rave_k_sweep.json`, `arena_config_layer6_phase.json`, `arena_config_layer8_strength.json`, `arena_config_layer9_adaptive.json`, `arena_config_layer10_*.json` | Per-layer ablations |
| Champion | `arena_config_champion_gauntlet*.json`, `arena_config_night1_champion_reset.json` | Champion progression runs |
| Overnight | `arena_config_overnight_*.json` | Long multi-hour runs |
| Heatmap | `arena_config_heatmap_*.json` | Visit-count heatmap captures |

Config schema and output artifacts: [`docs/arena.md`](../arena.md). Key MCTS
parameters (Layers 4–9) are documented in the root
[`CLAUDE.md`](../../CLAUDE.md).

## Calibration & data inputs (`data/`)

| File | Used by |
|---|---|
| `layer6_calibrated_weights.json` | `BlokusStateEvaluator` weight presets (`single`/`phase`/`default`) |
| `champion_registry.json` | Champion versioning + promotion records |
| `throughput_calibration.json` | iter/ms by rollout cutoff depth (Layer 10) |
| `sample_search_trace.json` | Example trace for diagnostics UI |

See the [Data Model](../02-architecture/DATA_MODEL.md) for shapes.
