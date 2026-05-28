# API Inventory

> Backend endpoints. The full per-route table with handlers and profiles lives
> in [Route Inventory](../03-implementation/ROUTE_INVENTORY.md); narrative
> reference is [`docs/webapi/README.md`](../webapi/README.md). Last audited: 2026-05-28.

Routes are registered (not decorator-style) via `app.add_api_route(...)` in
`webapi/routes_gameplay.py` (`register_gameplay_routes`) and
`webapi/routes_research.py` (`register_research_routes`); the profile
(`webapi/profile.py`) decides which set is mounted.

## Gameplay profile (deploy-safe)

| Endpoint | Purpose | Auth | Status |
|---|---|---|---|
| `GET /health`, `GET /` | liveness / root | none | Implemented |
| `POST /api/games` | create game | none | Implemented |
| `GET /api/games`, `GET /api/games/{id}` | list / fetch game | none | Implemented |
| `POST /api/games/{id}/move` | submit a move | none | Implemented |
| `POST /api/games/{id}/pass` | pass turn | none | Implemented |
| `POST /api/games/{id}/advance_turn` | trigger AI move | none | Implemented |
| `POST /api/games/{id}/finish` | finalize game | none | Implemented |
| `GET /api/agents` | available agents | none | Implemented |
| `GET /api/arena-runs`, `GET /api/arena-runs/{id}` | tournament results | none | Implemented |
| `WS /ws/games/{id}` | realtime game stream | none | Implemented |

## Research profile (adds)

| Endpoint | Purpose | Auth | Status |
|---|---|---|---|
| `GET /api/health/db`, `GET /debug/mongo` | DB health / debug | none | Implemented |
| `GET /api/analysis/{id}` (+ `/replay`, `/steps`, `/summary`) | game analysis | none | Implemented |
| `GET /api/history` | game history | none | Implemented |
| `GET /api/trends` | aggregate trends | none | Implemented |
| `GET /api/training-runs*` | legacy RL training data | none | Deprecated (RL-era) |

## Cross-cutting notes

- **Auth:** no authentication/authorization on any route (single-user research
  tool). See [Risk Register](../04-quality/RISK_REGISTER.md).
- **Errors:** move failures return a stable generic message; raw exception text
  is logged server-side, not returned (`webapi/game_manager.py`). Structured
  error codes (`NOT_YOUR_TURN`, `INVALID_MOVE`) are an open question.
- **Validation:** request bodies validated by Pydantic schemas (`schemas/`);
  ownership of `projectId`/game is **not** enforced.
- **OpenAPI:** auto-docs at `/docs` when the server runs.
