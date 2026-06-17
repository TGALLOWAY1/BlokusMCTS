"""Canonical Blokus agent interface.

This module formalises *one* move-selection contract for the whole repo so the
arena, the FastAPI backend, the browser/Pyodide worker, and any future web demo
all speak the same language, while the older calling conventions survive behind
thin adapters.

History — why three conventions exist
-------------------------------------
The codebase grew three different agent calling conventions:

* ``select_action(board, player, legal_moves) -> Move | None``
  The *native* method implemented by every real gameplay agent
  (:class:`agents.random_agent.RandomAgent`,
  :class:`agents.heuristic_agent.HeuristicAgent`,
  :class:`mcts.mcts_agent.MCTSAgent`). It is the smallest possible contract:
  given a position and the legal moves, return one move (or ``None`` when there
  is nothing to play).

* ``choose_move(board, player, legal_moves, time_budget_ms) -> (Move | None, dict)``
  The *deploy/web* protocol (:class:`agents.gameplay_protocol.GameplayAgentProtocol`).
  It adds a per-move time budget and a diagnostics dict (visit counts, search
  trace, budget tier, ...) needed when serving moves over a websocket.

* ``act(observation, legal_mask, env) -> action_index | None``
  The *legacy RL-era* protocol (:class:`agents.registry.AgentProtocol`,
  used by ``league/``). It is index-based over a flattened action space and only
  makes sense inside the gym/PettingZoo training environment.

The canonical contract
----------------------
:class:`BlokusAgent` is the canonical, ``runtime_checkable`` Protocol. Every
gameplay agent already satisfies it because it only requires ``select_action``.
Richer call sites (anything that needs a time budget, a seed, or diagnostics)
should go through :func:`decide`, which returns an :class:`AgentDecision`
(move + stats) and transparently routes to ``choose_move`` when the agent
exposes the deploy protocol, or to ``select_action`` otherwise.

New code should depend on :class:`BlokusAgent` / :func:`decide` rather than
calling ``select_action``/``choose_move``/``act`` directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from engine.board import Board, Player
from engine.move_generator import Move

# Default per-move thinking budget (ms) used when a context does not set one but
# the underlying agent exposes the deploy ``choose_move`` protocol.
DEFAULT_TIME_BUDGET_MS = 1000


@runtime_checkable
class BlokusAgent(Protocol):
    """Canonical move-selection contract for Blokus agents.

    The single required method is :meth:`select_action`. It is intentionally the
    smallest universal contract — every gameplay agent in the repo implements it,
    so ``isinstance(agent, BlokusAgent)`` is the canonical conformance check.

    Agents that also want to advertise a time budget and richer telemetry may
    additionally implement the deploy protocol method
    ``choose_move(board, player, legal_moves, time_budget_ms) -> (Move | None, dict)``;
    :func:`decide` will prefer it automatically when present.
    """

    def select_action(
        self,
        board: Board,
        player: Player,
        legal_moves: List[Move],
    ) -> Optional[Move]:
        """Return one move for ``player`` given ``legal_moves`` (or ``None``)."""
        ...


@dataclass
class AgentDecisionContext:
    """Optional context handed to :func:`decide`.

    All fields are optional so the canonical call works for the simplest agents.

    Attributes
    ----------
    time_budget_ms:
        Soft per-move thinking budget in milliseconds. Forwarded to deploy
        agents via ``choose_move``; for native agents that expose a
        ``time_limit`` attribute (e.g. :class:`mcts.mcts_agent.MCTSAgent`) it is
        applied before selection so the same budget controls search depth.
    seed:
        Per-decision random seed. Applied via the agent's ``set_seed`` method
        when available (no-op for deterministic agents).
    collect_diagnostics:
        When ``True``, :func:`decide` gathers per-move telemetry (via
        ``get_action_info``/``get_search_trace``) into :class:`AgentDecision`.
    extra:
        Free-form passthrough for adapter-specific hints. Never required.
    """

    time_budget_ms: Optional[int] = None
    seed: Optional[int] = None
    collect_diagnostics: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentDecision:
    """Result of a canonical :func:`decide` call.

    ``move`` is ``None`` when the agent has no legal move to play. ``stats``
    holds optional diagnostics (search iterations, visit counts, budget tier,
    search trace, ...); it is always a dict, possibly empty.
    """

    move: Optional[Move]
    stats: Dict[str, Any] = field(default_factory=dict)


def is_gameplay_agent(agent: Any) -> bool:
    """True if ``agent`` exposes the deploy ``choose_move`` protocol.

    Mirrors :func:`webapi.gameplay_agent_factory.is_gameplay_adapter` but is kept
    here so the canonical layer has no dependency on the web package.
    """
    return callable(getattr(agent, "choose_move", None)) and hasattr(
        type(agent), "choose_move"
    )


def conforms(agent: Any) -> bool:
    """True if ``agent`` satisfies the canonical :class:`BlokusAgent` contract."""
    return isinstance(agent, BlokusAgent)


def decide(
    agent: Any,
    board: Board,
    player: Player,
    legal_moves: List[Move],
    context: Optional[AgentDecisionContext] = None,
) -> AgentDecision:
    """Canonical front door for asking any agent to choose a move.

    Routing:

    * If ``agent`` exposes the deploy ``choose_move`` protocol, it is called with
      the requested (or default) time budget and its ``(move, stats)`` tuple is
      returned verbatim.
    * Otherwise the native ``select_action`` is used. The time budget is applied
      to ``agent.time_limit`` when the agent supports it, and diagnostics are
      gathered from ``get_action_info``/``get_search_trace`` when requested.

    Returns ``AgentDecision(move=None, stats={})`` when there are no legal moves.
    """
    context = context or AgentDecisionContext()

    if not legal_moves:
        return AgentDecision(move=None, stats={})

    if context.seed is not None and hasattr(agent, "set_seed"):
        agent.set_seed(int(context.seed))

    if is_gameplay_agent(agent):
        budget = (
            int(context.time_budget_ms)
            if context.time_budget_ms is not None
            else DEFAULT_TIME_BUDGET_MS
        )
        move, stats = agent.choose_move(board, player, legal_moves, budget)
        return AgentDecision(move=move, stats=dict(stats or {}))

    # Native select_action path.
    if context.time_budget_ms is not None and hasattr(agent, "time_limit"):
        agent.time_limit = max(int(context.time_budget_ms), 1) / 1000.0

    move = agent.select_action(board, player, legal_moves)

    stats: Dict[str, Any] = {}
    if context.collect_diagnostics:
        get_info = getattr(agent, "get_action_info", None)
        if callable(get_info):
            info = get_info()
            if isinstance(info, dict) and isinstance(info.get("stats"), dict):
                stats.update(info["stats"])
        get_trace = getattr(agent, "get_search_trace", None)
        if callable(get_trace):
            trace = get_trace()
            if trace:
                stats["searchTrace"] = trace

    return AgentDecision(move=move, stats=stats)


def as_choose_move(
    agent: Any,
    board: Board,
    player: Player,
    legal_moves: List[Move],
    time_budget_ms: Optional[int] = None,
) -> Tuple[Optional[Move], Dict[str, Any]]:
    """Compatibility shim returning the deploy ``(move, stats)`` tuple.

    Lets call sites that still expect the gameplay protocol's tuple shape drive
    *any* canonical agent without caring which native convention it uses.
    """
    decision = decide(
        agent,
        board,
        player,
        legal_moves,
        AgentDecisionContext(time_budget_ms=time_budget_ms, collect_diagnostics=True),
    )
    return decision.move, decision.stats
