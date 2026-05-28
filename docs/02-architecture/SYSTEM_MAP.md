# System Map

> Module relationships at a glance. Last audited: 2026-05-28.
> Narrative: [Architecture](ARCHITECTURE.md). More diagrams: [Flow Diagrams](../08-visuals/FLOW_DIAGRAMS.md).

```mermaid
flowchart TB
    subgraph Core["Core (Python, no I/O)"]
        ENG["engine/<br/>Board, Pieces, MoveGen, Game"]
        MCTS["mcts/<br/>MCTSAgent, StateEvaluator,<br/>OpponentModel, parallel, Zobrist"]
        AG["agents/<br/>Random, Heuristic, registry"]
        MCTS --> ENG
        AG --> ENG
    end

    subgraph Research["Research / Offline (Python)"]
        ARENA["scripts/arena.py"]
        RUNNER["analytics/tournament/<br/>arena_runner, ratings, stats"]
        ANALYTICS["analytics/<br/>metrics, winprob, heatmap"]
        CALIB["scripts/analyze_layer6_features.py"]
        ARENA --> RUNNER --> MCTS
        RUNNER --> ANALYTICS
    end

    subgraph App["Application (Web)"]
        API["webapi/<br/>FastAPI, GameManager, profiles"]
        FE["frontend/<br/>React SPA"]
        BP["browser_python/<br/>Pyodide mirror of engine+mcts"]
        FE -->|WebWorker| BP --> MCTS
        FE -->|REST + WS| API --> MCTS
    end

    MONGO[("MongoDB<br/>blokusdb")]
    FSRUN[["arena_runs/*<br/>summary, games.jsonl, snapshots"]]
    WEIGHTS[["data/layer6_calibrated_weights.json"]]

    API --> MONGO
    RUNNER --> FSRUN
    ANALYTICS --> CALIB --> WEIGHTS
    WEIGHTS -.calibrated weights.-> MCTS
    FSRUN -.read by.-> API
```

## Reading the map

- **Core** has no I/O and no web dependencies; everything depends on `engine/`.
- **Research/Offline** runs tournaments and the calibration feedback loop that
  produces `data/layer6_calibrated_weights.json`, which feeds back into the
  evaluator (dashed arrow).
- **Application** exposes the same core two ways: in-browser via the Pyodide
  mirror (`browser_python/`) and server-side via FastAPI.
- **MongoDB** persists games/analysis (research profile only); arena artifacts
  live on the filesystem and are read back by the API for the dashboards.

## Dependency direction (who imports whom)

```
engine  ←  mcts  ←  agents
   ↑         ↑         ↑
   └──── analytics, webapi, browser_python, scripts
```

No module in `Core` imports from `webapi/`, `frontend/`, or `analytics/`.
