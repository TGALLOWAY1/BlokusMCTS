# Security & Privacy Notes

> Last audited: 2026-05-28. This is a single-user research tool, not a
> multi-tenant product; notes below are scoped accordingly.

## Secrets
- Only secret is `MONGODB_URI` (`.env.example` → `.env`). Keep `.env` out of git.
- No API keys or third-party credentials are required by the product.

## Authentication / authorization
- **None.** No login, no route guards, no per-game ownership checks
  (`webapi/routes_*.py`). Anyone who can reach the API can read/write any game.
- Safe only when the research profile runs locally / on a trusted network. The
  Vercel deploy profile is gameplay-only (`webapi/profile.py`).

## Data exposure
- `/debug/mongo` and `/api/health/db` expose DB connectivity/internals — research
  profile only; do not expose publicly.
- Move-execution errors return a **generic** message; raw exception text is
  logged server-side, not returned to clients (`webapi/game_manager.py`).
- No PII is collected; game data is anonymous gameplay records.

## Input validation
- Request bodies are validated by Pydantic schemas (`schemas/`).
- Move legality is enforced by the engine; invalid moves are rejected.
- Ownership/identity of `game_id` is **not** validated (no auth) — acceptable
  for local use, a risk if exposed.

## Recommendations (if ever deployed beyond local)
1. Add authentication and per-resource authorization.
2. Remove or gate `/debug/mongo` and `/api/health/db`.
3. Add rate limiting on game-creation and move endpoints.
4. Keep the deploy (gameplay-only) profile as the public surface.

See [Risk Register](RISK_REGISTER.md) for severities.
