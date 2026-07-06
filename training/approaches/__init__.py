"""Candidate-generation approaches for the nightly approach-comparison framework.

Each approach turns the current durable state into exactly one :class:`Candidate`
with an explicit ``created``/``reason``. Resolve approaches by short name via
:func:`get_approach` / :func:`build_approaches`.
"""

from __future__ import annotations

from typing import Callable, Dict, List

from training.approaches.base import (
    Approach,
    ApproachContext,
    Candidate,
    artifact_path_for,
    candidates_dir,
    load_candidate_artifacts,
    validate_candidate_artifact,
    write_candidate_artifact,
)

# Short-name -> factory. Keep names stable: they appear in artifacts, reports, and CLI.
_FACTORIES: Dict[str, Callable[[], Approach]] = {}


def _register() -> None:
    from training.approaches import (
        baseline_mcts,
        heuristic_tuning,
        hybrid_td_mcts,
        mcts_param_sweep,
        policy_prior,
        progressive_widening,
        td_learning,
    )

    _FACTORIES.update({
        baseline_mcts.NAME: baseline_mcts.make,
        heuristic_tuning.NAME: heuristic_tuning.make,
        mcts_param_sweep.NAME: mcts_param_sweep.make,
        td_learning.NAME: td_learning.make,
        hybrid_td_mcts.NAME: hybrid_td_mcts.make,
        policy_prior.NAME: policy_prior.make,
        progressive_widening.NAME: progressive_widening.make,
    })


_register()

# Default roster for a nightly run (order = report order). Leads with candidates that
# are genuinely DIFFERENT from the champion — the plateau came from a roster that had
# collapsed onto the incumbent (`baseline` reproduced it exactly; `policy` self-distilled
# back into the fixed heuristic). `mcts_sweep` (tuned exploration constant) and
# `progressive_widening` (focus search on top moves) explore new search behaviour;
# `heuristic_tune` re-fits the evaluator. `baseline` self-retires when identical to the
# champion, so it only competes if a future champion drifts from the strong-search seed.
DEFAULT_APPROACHES: List[str] = [
    "mcts_sweep", "progressive_widening", "heuristic_tune", "policy", "baseline",
]

ALL_APPROACHES: List[str] = list(_FACTORIES.keys())


def get_approach(name: str) -> Approach:
    """Resolve a single approach by short name (raises ``KeyError`` if unknown)."""
    if name not in _FACTORIES:
        raise KeyError(f"unknown approach '{name}'; known: {sorted(_FACTORIES)}")
    return _FACTORIES[name]()


def build_approaches(names: List[str]) -> List[Approach]:
    """Resolve a list of approach short names into approach instances."""
    return [get_approach(n) for n in names]


__all__ = [
    "Approach",
    "ApproachContext",
    "Candidate",
    "DEFAULT_APPROACHES",
    "ALL_APPROACHES",
    "get_approach",
    "build_approaches",
    "artifact_path_for",
    "candidates_dir",
    "load_candidate_artifacts",
    "validate_candidate_artifact",
    "write_candidate_artifact",
]
