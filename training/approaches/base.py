"""Candidate-generation approach contract.

Every nightly "learning" strategy (TD, regression heuristic tuning, MCTS param
sweep, hybrid, stronger baseline) is an :class:`Approach` that, given the current
durable state, returns exactly one :class:`Candidate`. The cardinal rule that fixes
the old "No candidate was learned this cycle" black box:

    **A Candidate ALWAYS carries a specific reason.** When ``created`` is ``False``
    the ``reason`` must say precisely why (e.g. "td: only 140 valid rows in 'late'
    phase (need 200)"), never a vague catch-all.

An approach produces a candidate from *already-collected* data (snapshots,
trajectories) — it does not run the noisy open-ended self-play loop. Evaluation,
promotion, and persistence are handled downstream by :mod:`training.evaluation`.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

ARTIFACT_SCHEMA_VERSION = 1


@dataclass
class ApproachContext:
    """Everything an approach needs to generate a candidate.

    ``state`` is the loaded ``latest.json`` dict (read-only for approaches —
    they clone ``state['champion_params']`` rather than mutate it). ``run_id`` and
    ``now_iso`` are passed in so artifacts are reproducible and time is injected.
    """

    state: Dict[str, Any]
    repo_root: Path
    run_id: str
    now_iso: str
    time_budget_s: float = 600.0
    verbose: bool = False
    # Optional override path for the TD weights artifact (tests / CLI).
    td_weights_path: Optional[str] = None

    def champion_params(self) -> Dict[str, Any]:
        """A deep copy of the champion's agent config (never mutate the original)."""
        return copy.deepcopy(self.state.get("champion_params") or {})


@dataclass
class Candidate:
    """The single output of an approach.

    ``agent_config`` is an arena-loadable ``{type, thinking_time_ms, params, name}``
    dict (``None`` when ``created`` is ``False``). ``metrics`` carries approach
    diagnostics (training rows, loss, swept params, R²) for the report.
    """

    name: str  # short, unique competitor name used in the arena (e.g. "td")
    approach: str  # full approach identifier (e.g. "td_learning")
    created: bool
    reason: str
    agent_config: Optional[Dict[str, Any]] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifact_path: Optional[str] = None

    def to_artifact(self, run_id: str, now_iso: str) -> Dict[str, Any]:
        return {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "approach": self.approach,
            "name": self.name,
            "run_id": run_id,
            "created_at": now_iso,
            "created": bool(self.created),
            "reason": self.reason,
            "agent_config": self.agent_config,
            "metrics": self.metrics,
        }


class Approach(Protocol):
    """Protocol every approach module satisfies."""

    name: str

    def generate(self, ctx: ApproachContext) -> Candidate:  # pragma: no cover - protocol
        ...


# ---------------------------------------------------------------------------
# Artifact persistence + validation
# ---------------------------------------------------------------------------


def candidates_dir(repo_root: Path | str) -> Path:
    """Directory where candidate artifacts live (committed for inspection)."""
    return Path(repo_root) / "training" / "artifacts" / "candidates"


def artifact_path_for(repo_root: Path | str, approach: str, run_id: str) -> Path:
    return candidates_dir(repo_root) / f"{approach}_{run_id}.json"


def write_candidate_artifact(
    candidate: Candidate,
    *,
    repo_root: Path | str,
    run_id: str,
    now_iso: str,
) -> Path:
    """Persist a candidate (created or not) as JSON and return its path."""
    out = artifact_path_for(repo_root, candidate.approach, run_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(candidate.to_artifact(run_id, now_iso), indent=2), encoding="utf-8")
    candidate.artifact_path = str(out)
    return out


def validate_candidate_artifact(artifact: Dict[str, Any]) -> tuple[bool, str]:
    """Validate a candidate artifact dict. Returns ``(ok, reason)``.

    A *created* candidate must carry a usable arena agent config; a *not-created*
    candidate must carry a non-empty reason. This is the gate that stops a
    malformed candidate from ever reaching the arena.
    """
    required = {"schema_version", "approach", "name", "created", "reason"}
    missing = required - set(artifact)
    if missing:
        return False, f"missing keys: {sorted(missing)}"
    if not str(artifact.get("reason", "")).strip():
        return False, "empty reason"
    if not artifact.get("created"):
        # A failed candidate is valid as long as it explains itself.
        return True, "not created (reason recorded)"
    cfg = artifact.get("agent_config")
    if not isinstance(cfg, dict):
        return False, "created candidate has no agent_config dict"
    if not cfg.get("type"):
        return False, "agent_config missing 'type'"
    if cfg.get("type") == "mcts" and not isinstance(cfg.get("params"), dict):
        return False, "mcts agent_config missing 'params' dict"
    return True, "ok"


def load_candidate_artifacts(repo_root: Path | str) -> List[Dict[str, Any]]:
    """Load all candidate artifacts (for the report / re-evaluation)."""
    out: List[Dict[str, Any]] = []
    d = candidates_dir(repo_root)
    if not d.exists():
        return out
    for p in sorted(d.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out
