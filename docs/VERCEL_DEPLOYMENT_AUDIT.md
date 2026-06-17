# Vercel Deployment Readiness Audit

_Audit date: 2026-06-17 · Branch: `claude/mcts-vercel-audit-uqtf0q` · Status: audit only, no deployment changes applied_

## Executive summary

This project is **unusually well-suited to Vercel** because its defining design
decision — running the Blokus engine and MCTS **entirely in the browser via
Pyodide** — removes the parts that normally make MCTS/AI apps hostile to
serverless hosting (long-running CPU, persistent processes, big memory). The
deployed experience is, for all practical purposes, a **static Vite SPA** with a
**thin, read-only Python serverless function** for two metadata endpoints.

The core functionality (gameplay board, MCTS engine, agent-vs-agent demo,
search-tree visualization) executes client-side in a Web Worker and needs **no
backend at all**. The FastAPI function only serves `/api/champion` and
`/api/arena-runs` (read-only, from committed JSON), and both UI consumers degrade
gracefully if those calls fail.

There is **one genuine blocker**: the current `vercel.json` uses a legacy
`builds` array that builds *only* the Python function and disables Vite framework
detection, so the frontend would never be built or served. This is a small,
well-understood config fix.

### Can this go on Vercel?

**YES — with one required config fix** (rework `vercel.json` so the frontend
actually builds). Everything else is already structured for Vercel: a `deploy`
runtime profile, a slim serverless `requirements.txt` with no native deps, time
budgets capped server-side, MongoDB skipped in deploy mode, and in-browser
gameplay that needs zero backend.

---

## 1. Current architecture

| Aspect | Finding |
|---|---|
| **Frontend framework** | React 18 + TypeScript, built with **Vite 5**. SPA via `react-router-dom`. State via `zustand`. Charts via `recharts`, animation via `framer-motion`. |
| **Package manager** | npm (`frontend/package-lock.json` present). |
| **Backend** | **FastAPI** (`webapi/app.py`, ~78 KB). Two runtime profiles: `research` (full) and `deploy` (gameplay-only). Vercel entry is `api-runtime/app.py` → `create_app(profile="deploy", include_research_routes=False)`. |
| **In-browser engine** | **Pyodide 0.29.3** (WebAssembly CPython) running in a dedicated Web Worker (`frontend/src/store/blokusWorker.ts`). Loads `numpy`, fetches `frontend/public/blokus_core.zip` (105 KB, committed), and imports `browser_python/worker_bridge.py`. |
| **Build system** | `tsc && vite build` for the frontend; `scripts/build_browser_core.sh` regenerates `blokus_core.zip` from `engine/`, `mcts/`, `agents/`, `config/`. |
| **Runtime requirements** | Python ≥ 3.9. Serverless deps are the **slim** `api-runtime/requirements.txt`: `fastapi, uvicorn[standard], pydantic, numpy, orjson, websockets`. (The root `requirements.txt` with `numba/pandas/scikit-learn/matplotlib/motor/...` is for the research/arena tooling, **not** the deploy function.) |
| **Rendering model** | **Static SPA + thin read-only serverless API.** Not SSR. Gameplay is fully client-side; the API is optional metadata. |
| **Runtime data / artifacts** | `frontend/public/blokus_core.zip` (committed, served statically). `arena_runs/**/summary.json` (66 files committed) read by `/api/arena-runs`. `data/champion_registry.json` read by `/api/champion`. Pyodide core + numpy fetched at runtime from `cdn.jsdelivr.net`. |
| **Environment variables** | Frontend (build-time): `VITE_API_URL`, `VITE_APP_PROFILE` (`deploy` hides research UI), optional `VITE_WS_URL`, `VITE_ENABLE_DEBUG_UI`. Backend: `APP_PROFILE=deploy`; `MONGODB_URI`/`MONGODB_DB_NAME` are **research-only** and unused in deploy. |

### Execution-path proof (why "static-friendly" is accurate)

- `frontend/src/store/gameStore.ts`: `createGame`, `connect`, `makeMove`,
  `passTurn`, `advanceTurn`, `loadGame` all `postMessage` to the Pyodide worker.
  No server call is on the gameplay path.
- `webapi/routes_gameplay.py` is the **only** route group registered in deploy
  profile. Read-only `/api/arena-runs` + `/api/champion` are the only endpoints
  the deploy UI actually fetches (`useChampion.ts`, `useArenaLeaderboard.ts`).
  The `/api/games/{id}` REST call in `GameConfigModal.tsx:129` is a fallback that
  only fires if the worker hasn't populated state.
- `App.tsx` wraps all research routes in `{!IS_DEPLOY_PROFILE && (...)}`, so
  History/Analysis/Train/Benchmark pages — the only callers of research-only
  endpoints — don't render (or fetch) in deploy mode.

---

## 2. Vercel compatibility checklist

| Concern | Present? | Assessment |
|---|---|---|
| Long-running MCTS simulations | **Client-side only** | Runs in the browser Web Worker; never occupies a serverless invocation. Server `create_game` exists but is off the deploy hot path and is capped (`deploy_validation.py`, ≤30 s budgets). |
| Heavy CPU workloads | Browser | Offloaded to the user's machine via Pyodide. No serverless CPU pressure. |
| Python / native deps | Python yes, native **no** | Deploy function is pure Python + numpy. **No `numba`/`njit`/Rust/C++** in `engine/`, `mcts/`, `agents/` (verified). `@vercel/python` handles numpy. |
| Local filesystem writes | No | Deploy API only **reads** committed JSON. MongoDB writes are skipped in deploy profile. |
| SQLite / file DB | No | Persistence is MongoDB, **disabled** in deploy. `arena_runs/` JSON is read-only. |
| WebSockets / persistent processes | Defined, **unused in deploy** | `vercel.json` does not route `/ws`; deploy gameplay uses the worker, not sockets. Serverless can't hold WS anyway — fine because it isn't needed. |
| Background jobs | No | Arena/training are offline scripts, never invoked at runtime. |
| Large memory | No (server) | Serverless function is tiny. Browser carries Pyodide (~tens of MB) on the client. |
| Large static assets | Moderate | `frontend/public/assets/**` (many story PNGs) + `blokus_core.zip` (105 KB). Within Vercel static limits; watch total bundle size. |
| Nonstandard ports | No | Local dev uses 8000/3000; irrelevant on Vercel. |
| Docker-only assumptions | No | No Dockerfile required for deploy path. |
| External runtime fetches | **Yes** | Worker loads Pyodide + numpy from `cdn.jsdelivr.net` at runtime. Works on Vercel, but a strict CSP / locked-down network policy would block it. |

---

## 3. Core functionality risk table

| Feature | Current implementation | Vercel compatibility | Risk | What could break | Recommended mitigation |
|---|---|---|---|---|---|
| **Gameplay board** | React SPA + Pyodide worker (`blokusWorker.ts`, `worker_bridge.py`) | Excellent (static) | **Low** | Worker fails if `blokus_core.zip` isn't served at site root, or jsDelivr CDN blocked | Ensure `frontend/public/` ships to static root; verify `/blokus_core.zip` 200s; allow `cdn.jsdelivr.net` in CSP |
| **MCTS simulation engine** | Pure-Python engine in Pyodide (client) | Excellent | **Low** | Pyodide cold-start (multi-second first load) | Already async with a loading state; consider self-hosting Pyodide assets for reliability |
| **Agent-vs-agent experiments** | In-browser `advance_turn` loop in the worker | Good | **Low–Med** | Heavy multi-game runs are bounded by the user's browser, not the server | Keep `DEPLOY_MCTS_PRESETS` budgets modest; document that arena-scale runs stay offline |
| **Search-tree visualization** | Diagnostics emitted by the worker, rendered with recharts (`mcts-viz/`) | Excellent | **Low** | None server-side | None |
| **Saved experiments / results** | `/api/arena-runs` reads committed `arena_runs/**/summary.json` | Good (read-only) | **Medium** | `arena_runs/` is in `.gitignore`; only currently-committed runs deploy. New runs won't appear without recommit/redeploy | Accept static snapshot, **or** move history to an external store (Supabase/Mongo Atlas) for live updates |
| **Champion banner** | `/api/champion` reads `data/champion_registry.json` | Good | **Low** | 404 if registry missing | `useChampion.ts` degrades gracefully; verify file ships in the function bundle |
| **Replay / analytics (research)** | Research routes + MongoDB | N/A in deploy | **Low** | Pages 404 if exposed | Already gated by `IS_DEPLOY_PROFILE`; keep `VITE_APP_PROFILE=deploy` |

---

## 4. Deployment options

| Option | Pros | Cons | Complexity | Preserves core? |
|---|---|---|---|---|
| **Vercel only** (static SPA + `@vercel/python` read-only function) — _recommended_ | Single platform; in-browser MCTS = zero backend cost; matches existing `deploy` profile & docs | Requires the `vercel.json` build fix; live experiment history needs an external store | **Low** | **Yes** — gameplay/MCTS/viz fully preserved |
| **Vercel frontend + separate backend** (Render/Fly for FastAPI) | Lets server-side MCTS / Mongo / research routes run unconstrained | Two deploys, CORS, more ops; unnecessary since deploy API is read-only | Medium | Yes, with overkill |
| **Static-only** (no function) | Simplest; pure CDN | Loses `/api/champion` + `/api/arena-runs` (banners/leaderboard) unless inlined as static JSON | Lowest | Mostly — gameplay yes, metadata degraded |
| **Docker VPS** | Full control; long-running server; native deps OK | Manual scaling, patching, TLS; loses Vercel CDN/preview ergonomics | Medium–High | Yes |
| **Serverless functions** (current plan) | Cheap, scalable, read-only fits the 10 s/60 s window | Cold starts; not for long MCTS (not needed here) | Low | Yes |
| **Edge functions** | Lowest latency | Python isn't supported on Edge; numpy/Pyodide won't run there | — | No (incompatible) |
| **Background-worker architecture** | Needed for server-side arena/training at scale | Vercel has no durable workers; would need a queue + external worker | High | Overkill for the public demo |

---

## 5. Suggested staged implementation plan (Vercel)

**Stage 1 — Get the frontend deployed (the required fix).**
Rework `vercel.json` so Vite is detected and built, while keeping the Python
function under `/api`. Set `VITE_APP_PROFILE=deploy`, `VITE_API_URL` (same origin),
`APP_PROFILE=deploy`. Run `scripts/build_browser_core.sh` so `blokus_core.zip` is
current before building. Verify `/`, `/blokus_core.zip`, and assets serve.

**Stage 2 — Preserve gameplay in-browser.**
No code change required: gameplay already runs in the Pyodide worker. Confirm the
worker boots in production (CDN reachable, `blokus_core.zip` 200, numpy loads).
Optionally self-host Pyodide + numpy under `frontend/public/` to remove the
jsDelivr runtime dependency.

**Stage 3 — Handle simulations / API calls.**
Confirm the deploy function answers `/api/champion` and `/api/arena-runs` and that
same-origin rewrites avoid CORS. Heavy simulation stays client-side; no server
MCTS is required for the public demo.

**Stage 4 — Persistence & experiment history.**
Decide between (a) **static snapshot** — keep committing selected `arena_runs/`
summaries (current behavior), or (b) **live history** — point `/api/arena-runs`
and champion data at MongoDB Atlas / Supabase and set the connection env vars.
(a) is zero-effort; (b) enables fresh results without redeploys.

**Stage 5 — Production polish.**
Lock CORS to the production origin (currently hardcoded to `localhost:3000`),
add a CSP that allows `cdn.jsdelivr.net` (or self-hosted Pyodide), set cache
headers for `blokus_core.zip` and assets, and add a tiny CI check that rebuilds
the browser bundle so it can't drift from `engine/`/`mcts/`.

---

## 6. Alternatives if Vercel is not ideal

Vercel **is** ideal here, but if requirements change (e.g., live server-side
arena runs, durable history, or no external-CDN dependency):

- **Supabase + Vercel** — best upgrade: Vercel keeps the SPA + read API; Supabase
  (Postgres) stores experiment history/champion data for live updates. Low effort.
- **Render / Railway** — run the full FastAPI server (research profile, Mongo,
  server-side MCTS) as a persistent service if you ever want WebSockets or
  unbounded server simulations. Pair with Vercel/static frontend.
- **Fly.io** — same as above with global regions; good if you want the engine
  near users without Pyodide.
- **Cloudflare Pages + Workers** — great static host, but Workers don't run
  Python/numpy/Pyodide server-side; you'd keep MCTS in-browser (works) and lose
  the Python function (move metadata to static JSON or Workers KV).
- **Docker VPS** — maximum control; most ops burden. Only if you outgrow
  serverless limits.
- **GitHub Pages (static only)** — viable for a pure in-browser demo if you drop
  the two metadata endpoints (inline champion/leaderboard as static JSON). No
  Python function support.

---

## 7. Output summary

### Blocking issues

1. **`vercel.json` does not build the frontend.** The legacy `builds: [python]`
   array disables Vite framework detection, so `npm run build` never runs and the
   `/(.*) → /index.html` rewrite has no `index.html` to serve. **Must be
   reworked** before any successful deploy. _(File: `vercel.json`.)_

### Non-blocking issues (fix during polish)

- **CORS hardcoded to `localhost:3000`** (`webapi/app.py` `create_app`). Harmless
  with same-origin rewrites, but should include the production origin if the API
  is ever cross-origin.
- **Runtime CDN dependency.** Pyodide + numpy load from `cdn.jsdelivr.net`; a
  strict CSP or locked network policy would break the worker. Consider
  self-hosting these assets.
- **`arena_runs/` is git-ignored.** Only the 66 currently-committed files deploy;
  new arena results won't surface without recommit/redeploy or an external store.
- **Bundle hygiene.** Confirm `data/champion_registry.json` (and any files
  `agents/champion.py` reads) are included in the serverless function bundle.
- **Stale-bundle risk.** `blokus_core.zip` can drift from `engine/`/`mcts/` if
  `build_browser_core.sh` isn't run before deploy; add a CI guard.

### Recommended deployment architecture

**Single Vercel project:** Vite SPA served statically (in-browser Pyodide MCTS) +
one `@vercel/python` serverless function (`api-runtime/app.py`, deploy profile)
serving read-only `/api/champion` and `/api/arena-runs`. Same-origin rewrites
route `/api/*` to the function and everything else to the SPA.

### Step-by-step (minimal path to a working deploy)

1. Run `bash scripts/build_browser_core.sh` to refresh `frontend/public/blokus_core.zip`.
2. Rework `vercel.json` to build the Vite app **and** the Python function (see
   "Specific files" below).
3. In Vercel project settings, set env vars: `APP_PROFILE=deploy`,
   `VITE_APP_PROFILE=deploy`, `VITE_API_URL=<deployment origin>`.
4. Deploy a preview; verify: SPA loads at `/`, `/blokus_core.zip` returns 200,
   the worker reaches `ready`, a game plays through, `/api/champion` and
   `/api/arena-runs` return JSON, `/health` returns `{"ok": true}`.
5. Promote to production; apply Stage 5 polish (CORS origin, CSP, cache headers).

### Specific files that need changes

| File | Change | Risk of change |
|---|---|---|
| `vercel.json` | Replace legacy `builds` with frontend build (Vite) + Python function; keep `/api/*` and SPA-fallback rewrites | **The one required change**; test on a preview deploy first |
| Vercel project env (not a file) | `APP_PROFILE`, `VITE_APP_PROFILE`, `VITE_API_URL` | None |
| `webapi/app.py` (polish) | Add production origin to CORS `allow_origins` | Low |
| `frontend/public/` (optional) | Self-host Pyodide + numpy to drop the CDN dependency | Low–Med (size) |
| CI (optional) | Guard that `blokus_core.zip` matches `engine/`+`mcts/`+`agents/` | Low |

### Specific risks to test before production

1. **Frontend actually builds & serves** on Vercel (the blocker) — confirm on a preview URL.
2. **Pyodide worker boots in prod** — `blokus_core.zip` 200, jsDelivr reachable, `numpy` loads, `ready` fires.
3. **Full game playthrough** in the browser, including `advance_turn` agent-vs-agent.
4. **`/api/champion` + `/api/arena-runs`** return data and the UI degrades gracefully if they don't.
5. **Same-origin rewrites** avoid CORS; no `localhost` leakage in `VITE_API_URL`.
6. **Cold-start latency** of the Python function and Pyodide first-load are acceptable.
7. **Static payload size** (story PNGs + zip) within limits and reasonably cached.

---

_No functionality is recommended for removal. The only required change is a
deployment-config fix; all gameplay, MCTS, agent-vs-agent, and visualization
capabilities are preserved by deploying the in-browser engine as static assets._
