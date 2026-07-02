"""Shared helpers for the mcts_lab CLIs."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from training import TrainingPaths
from training import state_store

# Well-known agent specs accepted by --agents. Anything else is treated as a
# path to a JSON agent config ({name?, type, thinking_time_ms, params}).
BUILTIN_AGENTS = ("champion", "baseline", "heuristic", "random")


def load_state(paths: Optional[TrainingPaths] = None) -> Dict[str, Any]:
    """Load ``training/state/latest.json`` (cold-start default if missing)."""
    paths = paths or TrainingPaths.default()
    state = state_store.load_latest(paths)
    if not state.get("champion_params"):
        # Cold start: seed champion params the same way the nightly run does.
        from training.nightly_run import _ensure_cold_start

        champion = state_store.load_champion(paths)
        _ensure_cold_start(state, champion)
    return state


def resolve_agent(spec: str, state: Dict[str, Any], name: Optional[str] = None) -> Dict[str, Any]:
    """Resolve an ``--agents`` entry to an arena agent config.

    * ``champion``  — the current champion (training/state/champion.json params)
    * ``baseline``  — the strong-search baseline derived from the champion
    * ``heuristic`` / ``random`` — the fixed anchor agents
    * anything else — path to a JSON agent config file
    """
    spec = spec.strip()
    if spec == "champion":
        cfg = copy.deepcopy(state["champion_params"])
    elif spec == "baseline":
        from training.approaches.baseline_mcts import strong_baseline_params

        cfg = strong_baseline_params(state["champion_params"])
    elif spec in ("heuristic", "random"):
        cfg = {"type": spec, "thinking_time_ms": None, "params": {}}
    else:
        path = Path(spec)
        if not path.exists():
            raise SystemExit(f"unknown agent spec {spec!r} (not a builtin "
                             f"{BUILTIN_AGENTS} and no such file)")
        data = json.loads(path.read_text(encoding="utf-8"))
        # Accept either a bare agent config or a candidate artifact.
        cfg = data.get("agent_config", data)
    cfg["name"] = name or spec.replace("/", "_").replace(".json", "")
    return cfg


def parse_seeds(text: str) -> List[int]:
    return [int(s) for s in text.split(",") if s.strip()]


def wilson_interval(wins: float, games: int, z: float = 1.96) -> tuple:
    """95% Wilson score interval for a win proportion."""
    if games <= 0:
        return (0.0, 0.0)
    p = wins / games
    denom = 1.0 + z * z / games
    centre = (p + z * z / (2 * games)) / denom
    margin = z * ((p * (1 - p) / games + z * z / (4 * games * games)) ** 0.5) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))
