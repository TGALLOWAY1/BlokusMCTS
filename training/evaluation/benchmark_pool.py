"""Fixed, versioned benchmark pool for candidate evaluation.

The old nightly evaluated candidates against a *rotating* opponent set, so Elo deltas
were never comparable run-to-run. This module assembles a **stable** roster so that a
candidate's measured strength is attributable to the candidate, not the luck of the
draw. Opponents (always 4-agent-arena ready):

* ``heuristic`` and ``random`` — fixed, reproducible skill anchors,
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

POOL_VERSION = "benchmark_v1"


def _baseline_agent(agent_type: str) -> Dict[str, Any]:
    return {"name": agent_type, "type": agent_type, "thinking_time_ms": None, "params": {}}


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

    Always includes the heuristic and random anchors; adds the best historical
    champion when one has been promoted. The current champion is NOT included here —
    the evaluator always pairs ``[champion, candidate, *pool]`` so the head-to-head
    gate is well-defined.
    """
    opponents: List[Dict[str, Any]] = [_baseline_agent("heuristic"), _baseline_agent("random")]
    if include_historical:
        hist = _best_historical(state)
        if hist is not None:
            opponents.append(hist)
    return BenchmarkPool(
        version=POOL_VERSION,
        seeds=list(seeds) if seeds else list(DEFAULT_BENCHMARK_SEEDS),
        opponents=opponents,
    )
