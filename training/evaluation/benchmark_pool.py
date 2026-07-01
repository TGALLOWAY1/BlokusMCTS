"""Fixed, versioned benchmark pool for candidate evaluation.

The old nightly evaluated candidates against a *rotating* opponent set, so Elo deltas
were never comparable run-to-run. This module assembles a **stable** roster so that a
candidate's measured strength is attributable to the candidate, not the luck of the
draw. Opponents (always 4-agent-arena ready):

* ``heuristic`` and ``random`` — fixed, reproducible skill anchors,
* ``baseline_mcts_fast`` and ``baseline_mcts_strong`` — fixed-parameter MCTS
  anchors that prevent the pool from being only weak opponents before the first
  promotion,
* ``best_historical`` — the strongest promoted checkpoint (if any),

plus the current ``champion`` (added by the evaluator, always co-present with the
candidate so the head-to-head gate has data). Evaluation seeds are fixed here too.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Fixed evaluation seeds — reproducible across runs so deltas are comparable.
DEFAULT_BENCHMARK_SEEDS: List[int] = [20260101, 20260202]

POOL_VERSION = "benchmark_v2"


def _baseline_agent(agent_type: str) -> Dict[str, Any]:
    return {"name": agent_type, "type": agent_type, "thinking_time_ms": None, "params": {}}


def _mcts_anchor(
    state: Dict[str, Any],
    *,
    name: str,
    thinking_time_ms: int,
    iterations_per_ms: float,
) -> Optional[Dict[str, Any]]:
    """Build a deterministic MCTS benchmark anchor from the champion's base config.

    The anchor keeps the champion's evaluator/search feature set but fixes the most
    important budget/search knobs. This gives every run stable non-random MCTS
    opponents even before the first promoted historical checkpoint exists.
    """
    base = copy.deepcopy(state.get("champion_params") or {})
    if not base:
        return None
    base["name"] = name
    base["type"] = base.get("type", "mcts")
    base["thinking_time_ms"] = thinking_time_ms
    params = base.setdefault("params", {})
    params.update({
        # greedy_sample + cutoff keeps a single anchor move at ~1s. The old
        # "heuristic + no cutoff" setting cost ~2s PER ROLLOUT (it scores every
        # legal move at every rollout step), i.e. minutes per move — anchor
        # games alone could eat the entire evaluation budget.
        "rollout_policy": "greedy_sample",
        "rollout_cutoff_depth": 12,
        "adaptive_rollout_depth_enabled": False,
        "iterations_per_ms": iterations_per_ms,
        "num_workers": 1,
    })
    return base


def _best_historical(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Strongest promoted checkpoint as an opponent agent, or ``None`` if none exist."""
    checkpoints = list(state.get("checkpoints", []) or [])
    if not checkpoints:
        return None
    def _mu(ck: Dict[str, Any]) -> float:
        return float((ck.get("rating") or {}).get("mu", 0.0))
    best = max(checkpoints, key=_mu)
    cfg = copy.deepcopy(best.get("params") or {})
    if not cfg:
        return None
    cfg["name"] = "best_historical"
    return cfg


@dataclass
class BenchmarkPool:
    """A fixed opponent roster + fixed seeds for candidate evaluation."""

    version: str
    seeds: List[int]
    opponents: List[Dict[str, Any]] = field(default_factory=list)

    def opponent_names(self) -> List[str]:
        return [o["name"] for o in self.opponents]

    def describe(self) -> Dict[str, Any]:
        return {"version": self.version, "seeds": list(self.seeds),
                "opponents": self.opponent_names()}


def build_benchmark_pool(
    state: Dict[str, Any],
    *,
    seeds: Optional[List[int]] = None,
    include_historical: bool = True,
) -> BenchmarkPool:
    """Assemble the stable benchmark pool from durable state.

    Always includes heuristic/random plus fixed MCTS anchors; adds the best
    historical champion when one has been promoted. The current champion is NOT
    included here — the evaluator always pairs ``[champion, candidate, *pool]`` so
    the head-to-head gate is well-defined.
    """
    opponents: List[Dict[str, Any]] = [_baseline_agent("heuristic"), _baseline_agent("random")]
    for anchor in (
        _mcts_anchor(state, name="baseline_mcts_fast", thinking_time_ms=100, iterations_per_ms=1.0),
        _mcts_anchor(state, name="baseline_mcts_strong", thinking_time_ms=500, iterations_per_ms=1.0),
    ):
        if anchor is not None:
            opponents.append(anchor)
    if include_historical:
        hist = _best_historical(state)
        if hist is not None:
            opponents.append(hist)
    return BenchmarkPool(
        version=POOL_VERSION,
        seeds=list(seeds) if seeds else list(DEFAULT_BENCHMARK_SEEDS),
        opponents=opponents,
    )
