# Deployment

This project deploys as a two-part application:

1. **Frontend** — Vite/React SPA built from `frontend/`, served as static assets.
2. **Backend** — FastAPI app exposed through `api-runtime/app.py`, which wraps `webapi/create_app(profile="deploy")` and registers only the gameplay routes.

The canonical Vercel config is [`vercel.json`](../vercel.json).

## Runtime profiles

`webapi/app.py` supports two profiles controlled by `APP_PROFILE`:

| Profile | Routes enabled | Notes |
|---------|---------------|-------|
| `research` (default) | All routes — gameplay, analysis, history, training, DB debug | Used for local development and arena work. |
| `deploy` | Gameplay-only: `/api/games[...]`, `/api/agents`, read-only `/api/champion` + `/api/arena-runs`, `/health`. (`/ws` exists in the app but is not routed by `vercel.json`.) | Used on Vercel. Time budgets capped by `webapi/deploy_validation.py`. The public demo's gameplay runs in-browser, so these routes are optional metadata. |

`api-runtime/app.py` is the entry point that forces `profile="deploy"`.

## Environment variables

### Backend (Vercel project)

| Variable | Required | Purpose |
|----------|----------|---------|
| `APP_PROFILE` | no | `api-runtime/app.py` already forces `profile="deploy"`. Set to `deploy` only for belt-and-suspenders. |
| `ALLOWED_ORIGINS` | no | Comma-separated extra CORS origins (e.g. a custom domain). `*.vercel.app` is already allowed via regex; same-origin rewrites mean CORS is usually never exercised. |
| `MONGODB_URI` | research profile only | MongoDB connection string for analysis/history routes. Unused in deploy. |
| `MONGODB_DB_NAME` | research profile only | Database name. Unused in deploy. |

### Frontend (Vercel project / build-time)

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_APP_PROFILE` | no | `deploy` or `research`. Already pinned to `deploy` for production builds via `frontend/.env.production`; set in Vercel only to override. |
| `VITE_API_URL` | no | API base URL. **Leave empty for same-origin** (the default): the frontend then calls `/api/*` relative URLs that Vercel rewrites to the function — no CORS, no origin to hardcode. Set to a full `https://` origin only for a cross-origin/standalone API. |
| `VITE_WS_URL` | no | WebSocket base URL. Unused in deploy (gameplay uses the in-browser worker, not sockets). |

> **Same-origin by default:** production builds default `VITE_API_URL` to empty
> (see `frontend/.env.production`), so `API_BASE` resolves to relative URLs.
> This avoids baking `http://localhost:8000` into the bundle and removes any
> need to know the deployment origin at build time.

Copy `.env.example` to `.env` for local development.

## Local smoke test

Start the deploy-profile backend:

```bash
APP_PROFILE=deploy PYTHONPATH=. python3 api-runtime/app.py
# Serves on http://localhost:8000
```

Create a valid deploy game (1 human vs 3 MCTS):

```bash
curl -sS -X POST http://localhost:8000/api/games \
  -H 'Content-Type: application/json' \
  -d '{
    "players": [
      {"player":"RED","agent_type":"human","agent_config":{}},
      {"player":"BLUE","agent_type":"mcts","agent_config":{"difficulty":"easy"}},
      {"player":"GREEN","agent_type":"mcts","agent_config":{"difficulty":"medium"}},
      {"player":"YELLOW","agent_type":"mcts","agent_config":{"difficulty":"hard"}}
    ],
    "auto_start": true
  }'
```

Verify health and that invalid configs are rejected:

```bash
curl -sS http://localhost:8000/health
curl -sS -X POST http://localhost:8000/api/games \
  -H 'Content-Type: application/json' \
  -d '{"players":[{"player":"RED","agent_type":"human"},{"player":"BLUE","agent_type":"random"}]}'
# Expected: HTTP 400 with validation message
```

## Vercel build & routing

`vercel.json` uses a legacy `builds` array that builds **both** halves of the app:

- `@vercel/static-build` on `frontend/package.json` → runs `npm run build`
  (`tsc && vite build`) and serves `frontend/dist` as static assets.
- `@vercel/python` on `api-runtime/app.py` → the read-only serverless function.
  Its `includeFiles` ships the runtime data the deploy API reads
  (`data/champion_registry.json`, `config/`, `arena_runs/**/summary.json`) and
  the `analytics.tournament` modules lazily imported when `/api/champion`
  resolves the champion's browser agent spec. `@vercel/python` traces Python
  *imports* but not data files, so these must be listed explicitly.

Because legacy `builds` is in use, routing must use `routes` (not `rewrites`):

- `/api/*`, `/health`, `/docs`, `/openapi.json` → `api-runtime/app.py`.
- Cache-Control headers for `/blokus_core.zip` (1 day) and `/assets/*`
  (1 year, immutable) via `continue: true` header routes.
- `{ "handle": "filesystem" }` **before** the SPA fallback so static files
  (`/blokus_core.zip`, `/assets/*`, story PNGs) are served directly.
- `/(.*)` → `/index.html` (SPA fallback) last.

The backend profile is forced to `deploy` in `api-runtime/app.py`, so no env var
is needed to keep research/training routes off.

> **Why the slim function needs `openskill`:** `/api/champion` resolves a
> browser-ready agent spec via `agents.champion` →
> `analytics.tournament.gauntlet` → `arena_stats` → `trueskill_rating`, which
> imports `openskill` at module load. It is in `api-runtime/requirements.txt`
> (pure Python, no native deps). Without it, the champion banner still renders
> but the in-browser "Play the Champion" demo loses its exact validated config.

## Deploying to Vercel (staged rollout)

The Vercel MCP tooling in CI/agent environments only returns instructions; an
actual deploy needs either the **Git integration** (recommended) or the Vercel
CLI with a token. There is no committed `.vercel/` link in this repo, so a
one-time project setup is required.

### One-time project setup

1. In Vercel, **Add New… → Project** and import the GitHub repo
   `TGALLOWAY1/MCTS_Laboratory`.
2. Leave the framework preset as **Other** — `vercel.json` drives the build.
   (Root directory = repo root; do **not** set it to `frontend/`.)
3. (Optional) Set env vars per the tables above. None are strictly required for
   the same-origin deploy; the committed config already pins the deploy profile
   and same-origin API base.
4. Deploy a **preview** (push the working branch or use “Deploy” on a non-prod
   branch). Verify the acceptance checklist below **before** promoting.

### Preview verification checklist

- **Stage 1 — build & serve:** `/` serves the SPA, `/blokus_core.zip` returns
  200, `/health` returns `{"ok": true, "profile": "deploy"}`.
- **Stage 2 — in-browser gameplay:** browser console shows
  `[Worker] Initialization Complete`; `cdn.jsdelivr.net` (Pyodide + numpy) and
  `/blokus_core.zip` load; a full human-vs-MCTS game and an MCTS-vs-MCTS
  (`advance_turn`) game complete with **no backend calls on the move path**;
  the search-tree visualization renders.
- **Stage 3 — read-only API:** `/api/champion` returns champion metadata and
  `/api/arena-runs` returns the committed leaderboard snapshot; the champion
  banner and “Current Best” picker render; the UI still works if either 404s.

Only after the preview passes, **promote to production** (Vercel “Promote”, or
merge to the production branch if auto-deploy is configured).

## Stage 4 — Persistence / experiment history

**Chosen: (a) static snapshot.** `/api/arena-runs` reads the
`arena_runs/**/summary.json` files committed to the repo, and `/api/champion`
reads `data/champion_registry.json`. New arena results appear only after they
are committed and the site is redeployed. `arena_runs/` is git-ignored, so only
already-committed run summaries ship.

This is the zero-effort default and matches the read-only, demo-oriented nature
of the public site. **Option (b) live history** (point `/api/arena-runs` and
champion data at MongoDB Atlas / Supabase and set the connection env vars) is
only warranted if fresh results must surface without a redeploy; it is not
implemented here.

## Stage 5 — Production polish

- **Cache headers** for `blokus_core.zip` and `/assets/*` — done in `vercel.json`.
- **CORS** — `webapi/app.py create_app` allows localhost, any `*.vercel.app`
  origin (regex), and anything in `ALLOWED_ORIGINS`. Same-origin rewrites mean
  CORS is normally not exercised; add a custom production domain to
  `ALLOWED_ORIGINS` if you serve the API cross-origin.
- **CI guard** — `.github/workflows/browser-core-sync.yml` runs
  `scripts/check_browser_core.sh` to fail if `blokus_core.zip` drifts from
  `engine/`+`mcts/`+`agents/`+`config/`.
- **CSP (apply after Stage 2 passes).** A Content-Security-Policy is **not**
  enabled by default so the first preview can verify gameplay without a CSP
  variable masking other issues. Once gameplay is confirmed, add this header
  route to `vercel.json` (before `{ "handle": "filesystem" }`) and re-verify on
  a preview before promoting:

  ```json
  {
    "src": "/(.*)",
    "headers": {
      "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval' 'unsafe-inline' https://cdn.jsdelivr.net; worker-src 'self' blob:; child-src 'self' blob:; connect-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; object-src 'none'; base-uri 'self'"
    },
    "continue": true
  }
  ```

  Pyodide needs `'unsafe-eval'`/`'wasm-unsafe-eval'` (WebAssembly + codegen),
  `blob:` workers, and `cdn.jsdelivr.net` in `script-src`/`connect-src` to fetch
  the Pyodide runtime and numpy. To drop the CDN dependency entirely, self-host
  Pyodide + numpy under `frontend/public/` and point
  `loadPyodide({ indexURL })` at the local path, then tighten the CSP.

## Rollback

The change is config-first and reversible: revert `vercel.json`,
`frontend/.env.production`, the `gameConstants.ts` API-base lines, the
`openskill` requirement, and the `create_app` CORS block to restore the prior
state. No gameplay/MCTS/engine code was changed.

## In-browser gameplay (no backend)

The demo game on the landing page runs entirely in the browser via Pyodide —
`browser_python/` mirrors the engine and MCTS and is loaded in a WebWorker.
This path requires no backend and is the recommended zero-cost demo mode.
Build the browser bundle with `scripts/build_browser_core.sh` before deploying
the frontend.

## Historical notes

Earlier iterations deployed an external `engine-service/` FastAPI microservice
that exposed `POST /think` and was called from the web API via `ENGINE_URL`.
That service has been archived to `archive/engine-service/` because it
depended on the archived `FastMCTSAgent` (see `CLAUDE.md`). The `ENGINE_URL`
fallback path in `webapi/app.py` is left in place but inert when the variable
is unset.
