"""Experiment manifests — the reproducibility contract.

Every comparison run writes a manifest capturing exactly what was run: the agents
(by config hash), seeds, game counts, learning modes, and the artifacts consumed
(TD weights file, snapshot CSV). Re-running with the same manifest reproduces the
same games, because the harness derives every per-game seed deterministically from
the manifest's ``seeds`` and arena index.

Manifests are plain JSON so they diff cleanly and can be committed alongside a
report.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _stable_hash(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


@dataclass
class ExperimentManifest:
    experiment_id: str
    date: str
    description: str
    games_per_arena: int
    seeds: List[int]
    thinking_time_ms: Optional[int]
    max_turns: int
    competitors: Dict[str, str]  # name -> config hash
    competitor_configs: Dict[str, Any] = field(default_factory=dict)
    learning_modes: Dict[str, str] = field(default_factory=dict)  # name -> mode
    artifacts: Dict[str, Any] = field(default_factory=dict)
    code_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "date": self.date,
            "description": self.description,
            "games_per_arena": self.games_per_arena,
            "seeds": list(self.seeds),
            "thinking_time_ms": self.thinking_time_ms,
            "max_turns": self.max_turns,
            "competitors": self.competitors,
            "competitor_configs": self.competitor_configs,
            "learning_modes": self.learning_modes,
            "artifacts": self.artifacts,
            "code_version": self.code_version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExperimentManifest":
        return cls(
            experiment_id=d["experiment_id"],
            date=d["date"],
            description=d.get("description", ""),
            games_per_arena=int(d["games_per_arena"]),
            seeds=list(d["seeds"]),
            thinking_time_ms=d.get("thinking_time_ms"),
            max_turns=int(d.get("max_turns", 2500)),
            competitors=dict(d.get("competitors", {})),
            competitor_configs=dict(d.get("competitor_configs", {})),
            learning_modes=dict(d.get("learning_modes", {})),
            artifacts=dict(d.get("artifacts", {})),
            code_version=d.get("code_version"),
        )


def build_manifest(
    *,
    description: str,
    competitor_configs: Dict[str, Any],
    seeds: List[int],
    games_per_arena: int,
    thinking_time_ms: Optional[int],
    max_turns: int = 2500,
    learning_modes: Optional[Dict[str, str]] = None,
    artifacts: Optional[Dict[str, Any]] = None,
    code_version: Optional[str] = None,
    now: Optional[str] = None,
) -> ExperimentManifest:
    """Construct a manifest (and a deterministic experiment_id) from inputs."""
    competitors = {name: _stable_hash(cfg) for name, cfg in competitor_configs.items()}
    date = now or datetime.now(timezone.utc).isoformat()
    seed_part = _stable_hash({
        "competitors": competitors, "seeds": seeds,
        "games_per_arena": games_per_arena, "thinking_time_ms": thinking_time_ms,
    })
    experiment_id = f"exp_{seed_part}"
    return ExperimentManifest(
        experiment_id=experiment_id,
        date=date,
        description=description,
        games_per_arena=games_per_arena,
        seeds=list(seeds),
        thinking_time_ms=thinking_time_ms,
        max_turns=max_turns,
        competitors=competitors,
        competitor_configs=competitor_configs,
        learning_modes=learning_modes or {},
        artifacts=artifacts or {},
        code_version=code_version,
    )


def save_manifest(manifest: ExperimentManifest, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    return path


def load_manifest(path: Path | str) -> ExperimentManifest:
    return ExperimentManifest.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
