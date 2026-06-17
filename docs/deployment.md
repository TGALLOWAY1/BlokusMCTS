# Deployment (Vercel)

This project deploys as a **Vite static SPA with in-browser Pyodide gameplay/MCTS**,
plus a **thin Python serverless API** for read-only metadata. Gameplay, the MCTS
engine, agent-vs-agent, and the search-tree visualization all run **client-side**
in a Web Worker (Pyodide), so the backend is only needed for read-only metadata.

## Recommended architecture

```
                ┌────────────────────────── Vercel project ──────────────────────────┐
  Browser  ──▶  │  Static SPA (frontend/dist)        Python function (api/index.py)   │
               │   • React + Vite                     • FastAPI, deploy profile        │
               │   • Pyodide Web Worker (MCTS)        • /api/champion  (read-only)     │
               │   • /blokus_core.zip (engine)        • /api/arena-runs (read-only)    │
               │                                      • /api/games... (gameplay)       │
               │                                      • /health                        │
               └─────────────────────────────────────────────────────────────────────┘
```

* **Frontend** — built from `frontend/`, served as static assets from `frontend/dist`.
* **Backend** — `api/index.py` is the Vercel serverless entry. It wraps
  `webapi.create_app(profile="deploy", include_research_routes=False)` — gameplay
  routes plus read-only `/api/champion`, `/api/arena-runs`, and `/health`. No
  research routes, no MongoDB. (`api-runtime/app.py` is the equivalent entry used
  for local `uvicorn` runs.)

The canonical config is [`vercel.json`](../vercel.json).

### Why this config works on Vercel

The previous `vercel.json` used a legacy `builds: [@vercel/python]` array. A
`builds` array **disables Vite framework detection** and builds *only* the Python
function, so `npm run build` never ran and there was no `index.html` to serve. The
new config fixes this:

* **`buildCommand` + `outputDirectory`** (not `builds`) — Vercel builds the Vite
  app from the `frontend/` subdirectory and serves `frontend/dist` as the static
  SPA. No legacy `builds` array, so static asset serving is not disabled.
* **`/api` directory auto-detection** — `api/index.py` lives in the conventional
  `/api` directory, so Vercel's Python runtime detects and builds it as a
  serverless function automatically (no `builds` entry needed). Its slim
  `api/requirements.txt` (adjacent to the entrypoint) is installed instead of the
  heavy research-only root `requirements.txt`/`pyproject.toml`.
* **`functions.includeFiles`** — ships the read-only data the function reads at
  runtime (`data/champion_registry.json`, `arena_runs/**/summary.json`, and the
  champion `config/*.json`), which Python import tracing alone would not include.
* **Rewrites** — `/api/*` and `/health` route to the function (Vercel preserves
  the original request path, so FastAPI's own routing resolves the endpoint);
  everything else falls back to `/index.html` for the SPA router.
* **Same-origin** — because the SPA and the function share one origin, the
  frontend calls the API via relative `/api/...` paths (no CORS, no `localhost`,
  no cross-origin `VITE_API_URL` required).

## Environment variables

### Backend (Vercel project)

| Variable | Required | Purpose |
|----------|----------|---------|
| `APP_PROFILE` | **yes** | Set to `deploy`. Registers gameplay + read-only metadata only; skips MongoDB and research routes. (`api/index.py` also defaults it to `deploy`.) |
| `CORS_ALLOW_ORIGINS` | no | Comma-separated extra origins (only needed if the API is ever served cross-origin). |
| `CORS_ALLOW_ORIGIN_REGEX` | no | Origin regex; defaults to `https://.*\.vercel\.app` so preview deployments work. |
| `MONGODB_URI` / `MONGODB_DB_NAME` | research only | Unused in deploy profile. |

### Frontend (build-time)

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_APP_PROFILE` | **yes** | Set to `deploy` to hide research-only routes (Train/History/Analysis/Benchmark/MCTS-analysis). |
| `VITE_API_URL` | **no** | Leave **unset** for same-origin (`/api`). Set only for a cross-origin backend. An unset value no longer leaks `http://localhost:8000` into production builds. |
| `VITE_WS_URL` | no | WebSocket base; derived from `VITE_API_URL` if set. Not used by the in-browser demo. |
| `VITE_ENABLE_DEBUG_UI` | no | `true` to show the in-game Debug/Logs tab. |

## Build & output

| Setting | Value |
|---------|-------|
| Build command | `npm --prefix frontend install && npm --prefix frontend run build` (from `vercel.json`) |
| Output directory | `frontend/dist` |
| Function | `api/index.py` (Python, deploy profile) |
| Function deps | `api/requirements.txt` (slim: fastapi, uvicorn, pydantic, numpy, orjson, websockets) |

## Refreshing the in-browser engine bundle

The Pyodide worker fetches `frontend/public/blokus_core.zip` (committed, served
statically at `/blokus_core.zip`). Rebuild it whenever `engine/`, `mcts/`,
`agents/`, `config/`, or `browser_python/worker_bridge.py` change:

```bash
bash scripts/build_browser_core.sh        # rebuild the bundle
bash scripts/check_browser_core.sh        # CI-friendly staleness guard (exit != 0 if stale)
```

`check_browser_core.sh` extracts the committed zip and diffs it against the live
sources, so a stale bundle fails the check (wire it into CI before deploy).

## Local smoke test

Run the deploy-profile backend (uses `api-runtime/app.py`, equivalent to the
Vercel function):

```bash
APP_PROFILE=deploy PYTHONPATH=. python3 api-runtime/app.py   # http://localhost:8000
```

Run the frontend against it (same-origin via the Vite proxy):

```bash
cd frontend && npm ci && VITE_APP_PROFILE=deploy npm run dev   # http://localhost:3000
```

Quick endpoint checks:

```bash
curl -sS http://localhost:8000/health           # {"ok": true, "profile": "deploy"}
curl -sS http://localhost:8000/api/champion      # validated-champion metadata JSON
curl -sS http://localhost:8000/api/arena-runs    # {"runs": [...]}
```

## Vercel preview verification checklist

After deploying a preview, confirm:

- [ ] `/` loads (SPA renders)
- [ ] `/blokus_core.zip` returns `200`
- [ ] Pyodide worker reaches the `ready` state (console: "Initialization Complete")
- [ ] A new game can be created
- [ ] A piece can be placed
- [ ] An MCTS / AI move can run
- [ ] Search-tree visualization renders
- [ ] `/api/champion` returns JSON (and "Play the Champion" is enabled)
- [ ] `/api/arena-runs` returns JSON
- [ ] `/health` returns `{"ok": true}`
- [ ] Browser console shows **no** production calls to `localhost`

## Known limitations

* **CDN dependency** — Pyodide + numpy load from `cdn.jsdelivr.net` at runtime. A
  strict CSP or locked-down network policy would block the worker; self-host these
  under `frontend/public/` to remove the dependency.
* **Static arena history** — `arena_runs/` is git-ignored; only the currently
  committed `summary.json` snapshots are served by `/api/arena-runs`. New runs
  require recommit/redeploy, or moving history to external storage.
* **Research routes hidden** — Train/History/Analysis/Benchmark and the
  MongoDB-backed analytics are not registered in the deploy profile and not routed
  in the SPA. Use the research profile (local) for those.
* **No server-side MCTS** — heavy simulation stays in the browser; the serverless
  function is read-only metadata + lightweight gameplay bookkeeping (budgets are
  capped by `webapi/deploy_validation.py`).

## Historical notes

Earlier iterations deployed an external `engine-service/` FastAPI microservice
(`POST /think`, called via `ENGINE_URL`). It has been archived to
`archive/engine-service/` because it depended on the archived `FastMCTSAgent`
(see `CLAUDE.md`). The `ENGINE_URL` fallback in `webapi/app.py` is left in place
but inert when the variable is unset.
