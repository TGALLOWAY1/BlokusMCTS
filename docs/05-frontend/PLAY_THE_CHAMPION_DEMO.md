# Play the Champion — Web Demo (Phase 6)

Status: **Implemented** (playable end-to-end once a champion is promoted; degrades
gracefully when none is).

The "Play the Champion" demo is the public, portfolio-facing flow where a human
plays a full game of Blokus against the **validated champion** agent — the agent
that cleared the gauntlet and was promoted into the champion registry.

> Portfolio framing: *"I built a playable web demo where users compete against a
> benchmarked Blokus champion agent, backed by reproducible gauntlet validation,
> registry-based model serving, and explicit scoring modes."*

---

## User flow

1. Open the app → the start modal (`GameConfigModal`) appears.
2. The **Play the Champion** card (top of the modal) shows the champion's
   validation metadata fetched from `GET /api/champion`:
   - champion name + registry version
   - win rate
   - TrueSkill (μ)
   - total validation games
   - validation date
3. Click **Play the Champion**. A 4-player game starts: you (Red) vs three
   registry-backed champion opponents.
4. During play:
   - A **champion banner** (`ChampionBanner`) pins the champion's metadata, the
     active **scoring mode**, a live *"Champion thinking…"* indicator, and
     lightweight search diagnostics (time, simulations, depth, budget tier) for
     the champion's most recent move.
   - Select a piece from the tray, rotate (`R`) / flip (`F`), and click the board
     to place it. Illegal placements are rejected with a clear message.
   - **Pass** when you have no legal moves (the button highlights when you are
     blocked). The pass control stays visible during AI turns (disabled) so the
     layout never shifts.
   - Watch the champion and the other AI seats move; scores update live in the
     turn indicator.
5. On game over, the result banner shows the winner. Start a fresh game with
   **New Game**, or **Save Game** to download the move history JSON for replay.

---

## Architecture (how the champion actually plays)

The public demo runs the **entire game in the browser** via Pyodide
(`browser_python/` → `frontend/public/blokus_core.zip`), so there is no
round-trip to a game server during play. The backend's role is **read-only
metadata + registry-backed config resolution**.

```
GET /api/champion ──► agents.champion.load_champion_metadata()   (registry-backed)
                  └─► agents.champion.champion_browser_config()  (browser-ready spec)
        │
        ▼  { name, winRate, trueSkill, totalGamesPlayed, validationDate,
        │    agentConfig: { type, thinkingTimeMs, mcts: {<MCTSAgent kwargs>} } }
        ▼
frontend  useChampion()  ──►  buildChampionGameConfig(champion)
        │                       (forwards agentConfig verbatim into each AI seat)
        ▼
Pyodide worker  worker_bridge._build_mcts_agent(profile="champion")
        └─► MCTSAgent(**champion.mcts)   ← exact gauntlet-validated agent, in-browser
```

Key property: **the frontend never hardcodes a champion config path.** It plays
whatever `GET /api/champion` resolves from `data/champion_registry.json`. The
champion's MCTS parameters are resolved server-side (including the
deterministic-budget → iteration-count translation that mirrors the arena's
`build_agent`) and forwarded to the worker, which rebuilds the exact validated
agent client-side.

---

## API dependencies

| Endpoint | Purpose | Failure handling |
| --- | --- | --- |
| `GET /api/champion` | Champion validation metadata **and** a browser-ready `agentConfig` spec. | `404` → no validated champion yet (friendly "promote one" message). Network/5xx → "Could not reach the champion service." |

Served by `webapi/app.py::get_champion` (deploy-safe, read-only) and registered
in `webapi/routes_gameplay.py`. Resolution lives in `agents/champion.py`.

The frontend layer:
- `frontend/src/hooks/useChampion.ts` — fetches and classifies the result
  (`available` / `404` / network error).
- `frontend/src/utils/championConfig.ts` — `buildChampionGameConfig()` (pure,
  unit-tested) and `championIsPlayable()`.
- `frontend/src/components/ChampionCard.tsx` — start-modal entry point.
- `frontend/src/components/ChampionBanner.tsx` — in-game metadata + diagnostics.

---

## Champion metadata display

| Field | Source (`/api/champion`) | Shown in |
| --- | --- | --- |
| Champion name + version | `name`, `version` | Card, Banner |
| Win rate | `winRate` | Card, Banner |
| TrueSkill (μ) | `trueSkill` | Card, Banner |
| Total validation games | `totalGamesPlayed` | Card, Banner |
| Validation date | `validationDate` | Card, Banner |
| Browser agent spec | `agentConfig` | (used to instantiate the agent) |

---

## Scoring mode

Public play defaults to **standard Blokus scoring** (covered squares + all-pieces
bonus, no house corner/center bonuses). `buildChampionGameConfig()` sets
`scoring_mode: "standard"`, the Pyodide worker plumbs it into the in-browser
`BlokusGame`, and the mode is surfaced as a badge in both the turn indicator and
the champion banner. If a game runs under **house scoring**, the badge says so —
the mode is always labelled, never hidden.

---

## MCTS diagnostics (lightweight)

The champion banner surfaces, for the champion's most recent move:

- search time (s)
- simulations run
- max tree depth
- adaptive budget tier (when present)

Deeper visualizations (top candidate moves, UCT breakdown, exploration timelines)
remain available via the right-panel **MCTS** / **Analysis** tabs when *Enable
MCTS Diagnostics* is toggled on. This phase intentionally keeps the always-on
diagnostics minimal — enough for portfolio storytelling without overbuilding.

---

## Mobile + desktop

- The banner and start card use wrapping flex layouts so metadata reflows on
  narrow screens.
- Critical controls (hint, pass, save) stay visible across AI turns (disabled
  when it is not your turn) so nothing important is hidden and the layout does
  not jump — verified by `frontend/src/__tests__/HeaderPersistence.test.tsx`.

---

## Known limitations

- **Requires a promoted champion.** When the registry has no validated champion
  (the shipped seed `v1` has null metrics and does not pass the gauntlet gates),
  `GET /api/champion` returns `404` and the demo shows a friendly "no validated
  champion yet" state instead of a Play button. Promote one with
  `scripts/champion_gauntlet.py --promote`.
- **Champion runs in-browser.** Per-move budgets are kept small
  (`CHAMPION_*_BUDGET_MS` in `frontend/src/constants/gameConstants.ts`) so the
  demo stays responsive in Pyodide; the in-browser champion is therefore weaker
  than the same agent run server-side at full budget.
- **Single human seat.** The demo is fixed at 1 human (Red) vs 3 champion seats.
- Non-MCTS champion types (e.g. a `random`/`heuristic` champion) return metadata
  and an `agentConfig.type`, but the in-browser builder currently specialises the
  MCTS case; a non-MCTS champion falls back to a plain search in-browser.

---

## Future improvements

- Promote a real champion and capture a recorded demo game for the portfolio.
- Difficulty slider for the champion's per-move budget.
- "Replay vs champion" from saved move history with per-move diagnostics.
- Server-driven champion play (full budget) as an opt-in "hard mode" when a game
  backend is available.
- Surface top candidate moves inline in the banner (already computed in
  `mcts_stats.topMoves`).

---

## Tests

- Backend: `tests/test_champion_serving_scoring.py`
  - `/api/champion` returns metadata + browser `agentConfig`.
  - `champion_browser_config()` translates deterministic-budget MCTS params.
  - `404` path when no validated champion exists.
- Frontend: `frontend/src/utils/__tests__/championConfig.test.ts`
  - `buildChampionGameConfig()` seat layout, budget clamping, standard scoring.
- Worker path verified manually against `browser_python/worker_bridge.py`
  (`profile="champion"` builds the exact MCTS agent and makes a legal move).
