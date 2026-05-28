# Integrations

> External services and runtimes. Last audited: 2026-05-28.

| Integration | Role | Where | Status |
|---|---|---|---|
| **MongoDB** (motor/pymongo) | Persist games, move records, analysis, legacy training runs | `webapi/db/`, env `MONGODB_URI`/`MONGODB_DB_NAME` | Implemented (research profile only) |
| **Pyodide** | Run engine + MCTS in the browser (Python→WASM) | `browser_python/`, `frontend` dep `pyodide`, `frontend/public/blokus_core.zip` | Implemented |
| **Vercel** | Host the deploy-profile backend + frontend | `vercel.json`, `api-runtime/` | Implemented |
| **OpenSkill / TrueSkill / ELO / Plackett-Luce** | Agent rating systems | `analytics/tournament/`, `league/` | Implemented |
| **numba** | JIT acceleration of engine hot paths | `engine/` | Implemented |
| **scikit-learn / pandas** | Regression, Random Forest, SHAP for weight calibration | `scripts/analyze_layer6_features.py` | Implemented |

## Notes

- No third-party generative-AI / LLM API is used by the product (classical MCTS).
- No authentication providers are integrated (no auth — see
  [Risk Register](../04-quality/RISK_REGISTER.md)).
- The browser bundle (`blokus_core.zip`) is a built artifact of
  `browser_python/`; see `scripts/build_browser_core.sh`.
