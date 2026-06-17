# Agent Interface

**Status:** Implemented (Phase 3 — Standardize Agent Interface + Web-Ready Champion Contract)

This document defines the **canonical agent contract** for the MCTS Laboratory /
Blokus codebase, explains why several older calling conventions exist, which
adapters remain, and how agents are built for the arena, the backend, and the
registry-backed champion.

---

## 1. The canonical contract

The canonical contract lives in [`agents/interface.py`](../../agents/interface.py).

### `BlokusAgent` (Protocol)

```python
@runtime_checkable
class BlokusAgent(Protocol):
    def select_action(
        self,
        board: Board,
        player: Player,
        legal_moves: list[Move],
    ) -> Move | None:
        ...
```

`select_action` is the **smallest universal contract** — given a board, the
player to move, and the legal moves, return one move (or `None` when there is
nothing to play). Every real gameplay agent already implements it, so
`isinstance(agent, BlokusAgent)` is the canonical conformance check.

### `AgentDecisionContext`

Optional, all-default context for richer call sites:

| Field | Meaning |
|---|---|
| `time_budget_ms` | Soft per-move thinking budget. Forwarded to deploy agents; applied to `agent.time_limit` for native MCTS. |
| `seed` | Per-decision seed, applied via `set_seed` when present. |
| `collect_diagnostics` | When `True`, gather per-move telemetry into the decision. |
| `extra` | Free-form passthrough; never required. |

### `AgentDecision`

```python
@dataclass
class AgentDecision:
    move: Move | None
    stats: dict[str, Any]
```

`move` is `None` when there is no legal move. `stats` is always a dict (possibly
empty): search iterations, visit counts, budget tier, search trace, etc.

### `decide(...)` — the front door

```python
def decide(agent, board, player, legal_moves, context=None) -> AgentDecision
```

`decide` is what new code should call. It:

1. Returns `AgentDecision(None, {})` immediately when `legal_moves` is empty.
2. Applies `context.seed` via `set_seed` when supported.
3. If the agent exposes the **deploy** `choose_move` protocol
   (`is_gameplay_agent(agent)` is `True`), calls it with the requested/default
   budget and returns its `(move, stats)` verbatim.
4. Otherwise calls native `select_action`, pushing `time_budget_ms` onto
   `agent.time_limit` when available and collecting diagnostics on request.

`as_choose_move(...)` is a thin compatibility shim returning the legacy
`(move, stats)` tuple for call sites that still expect that shape.

---

## 2. Why the old conventions existed

The repo grew **three** agent calling conventions. The canonical layer does not
delete them — it unifies them.

| Convention | Signature | Origin / role |
|---|---|---|
| `select_action` | `(board, player, legal_moves) -> Move \| None` | The **native** method on `RandomAgent`, `HeuristicAgent`, `MCTSAgent`. The minimal position→move contract. |
| `choose_move` | `(board, player, legal_moves, time_budget_ms) -> (Move \| None, dict)` | The **deploy/web** protocol (`agents/gameplay_protocol.py`). Adds a per-move time budget and a diagnostics dict needed when serving moves over a websocket. |
| `act` | `(observation, legal_mask, env) -> int \| None` | The **legacy RL-era** protocol (`agents/registry.py`, `league/`). Index-based over a flattened action space; only meaningful inside the gym/PettingZoo training env. |

`select_action` became the de-facto standard because all three production agents
implement it; `choose_move` layered budget + telemetry on top for deployment;
`act` is an RL artifact retained only for the league code.

---

## 3. Which adapters remain

All preserved behind thin adapters — no agent was rewritten.

| Adapter | Location | Bridges |
|---|---|---|
| `_SelectActionAdapter` | `analytics/tournament/arena_runner.py` | native `select_action` → arena `choose_move(board, player, legal_moves, thinking_ms) -> (move, stats)` |
| `_ChooseMoveAdapter` | `analytics/tournament/arena_runner.py` | deploy gameplay agents inside the arena |
| `_MCTSGameplayAdapter` / `_ChallengeChampionGameplayAdapter` | `webapi/gameplay_agent_factory.py` | `MCTSAgent.select_action` → deploy `choose_move` with adaptive budgets |
| `RandomAgentAdapter` / `HeuristicAgentAdapter` / `MCTSAgentAdapter` / `RLPolicyAgent` | `agents/registry.py` | native agents → legacy RL `act(observation, legal_mask, env)` |
| `is_gameplay_agent` / `as_choose_move` | `agents/interface.py` | canonical detection + `(move, stats)` shim |

---

## 4. How arena agents are built

`analytics/tournament/arena_runner.build_agent(AgentConfig, seed)` constructs an
`_ArenaAgentAdapter`:

- `random` / `heuristic` / `mcts` → wrapped in `_SelectActionAdapter`.
- `challenge_champion_gameplay` → wrapped in `_ChooseMoveAdapter`.

The arena run loop drives every agent uniformly via
`agent.choose_move(board, player, legal_moves, thinking_time_ms) -> (move, stats)`,
so the adapters are the unification point. This behaviour is unchanged by Phase 3.

---

## 5. How web/backend agents are built

`webapi/gameplay_agent_factory.build_deploy_gameplay_agent(agent_type, config)`
returns deploy adapters that satisfy `GameplayAgentProtocol.choose_move`. The
FastAPI request path (`webapi/app.py`) calls `choose_move` when the agent is a
gameplay adapter and falls back to `select_action` otherwise — exactly the
routing `decide()` performs. New backend code should prefer
`agents.interface.decide(...)`.

---

## 6. How the champion agent is loaded

The registry-backed champion contract lives in
[`agents/champion.py`](../../agents/champion.py).

```python
from agents.champion import load_champion, NoValidatedChampionError

handle = load_champion()          # raises if no validated champion exists
agent  = handle.agent             # canonical, choose_move-capable
meta   = handle.metadata          # validation metadata
```

`load_champion()`:

1. Reads `data/champion_registry.json` and resolves `current_version`.
2. **Validates** the version is a real, gauntlet-promoted champion: it must carry
   `gate_pass == True`, a resolvable `config_path`, and non-null `avg_win_rate` /
   `avg_trueskill_mu`. The shipped seed `v1` entry (null metrics, no `gate_pass`)
   is therefore **not** loadable — by design.
3. Resolves the config path and builds the agent through the arena's vetted
   `build_agent`, so the served champion is exactly the validated agent.
4. Surfaces `ChampionMetadata`: `validation_date`, `gauntlet_run_path`,
   `win_rate`, `trueskill_mu` / `trueskill_conservative`, `total_games`,
   `config_path`, `params`, `promotion_reason`.

`NoValidatedChampionError` is raised with a clear reason when no validated
champion exists. **The loader never silently falls back to an unvalidated
champion.** Promote one with `scripts/champion_gauntlet.py --promote`.

---

## 7. What future contributors should use

- **Implement** new agents by providing `select_action(board, player, legal_moves)`.
  That alone makes them canonical `BlokusAgent`s.
- **Call** agents through `agents.interface.decide(agent, board, player,
  legal_moves, context)` — never reach for `select_action` / `choose_move` /
  `act` directly in new code.
- **Serve the champion** via `agents.champion.load_champion()`; treat
  `NoValidatedChampionError` as a hard failure, not a reason to fall back.
- **Do not** add a fourth convention. Add an adapter if a foreign interface must
  be bridged.
