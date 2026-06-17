"""Registry-backed champion contract.

The backend and the future web demo should be able to ask for *"the champion"*
by name and receive the **validated** champion — never an ambiguous or stale
config, and never a silent fall-back to an unvalidated candidate.

This module is the single resolution point. It:

1. Loads champion metadata from ``data/champion_registry.json``.
2. Resolves the champion's config path.
3. Builds the champion agent through the canonical agent layer
   (:mod:`agents.interface`), reusing the arena's vetted ``build_agent`` so the
   served champion is byte-for-byte the agent the gauntlet validated.
4. Surfaces validation metadata (validation date, gauntlet run path, win rate,
   TrueSkill, total games) alongside the agent.
5. Fails *clearly* — :class:`NoValidatedChampionError` — when no validated
   champion exists, instead of returning a half-configured agent.

A registry version counts as a *validated champion* only when it was written by
the gauntlet promotion path (:func:`analytics.tournament.gauntlet.build_registry_entry`),
i.e. it carries ``gate_pass == True``, a resolvable ``config_path``, and real
(non-null) ``avg_win_rate``/``avg_trueskill_mu`` metrics. The seed ``v1`` entry
that ships with null metrics is therefore *not* loadable — by design.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = _REPO_ROOT / "data" / "champion_registry.json"


class NoValidatedChampionError(RuntimeError):
    """Raised when the registry contains no validated champion to serve."""


@dataclass(frozen=True)
class ChampionMetadata:
    """Validation metadata for a registry champion version."""

    version: str
    champion_name: str
    config_path: str
    params: Dict[str, Any]
    thinking_time_ms: Optional[int]
    validation_date: Optional[str]
    gauntlet_run_path: Optional[str]
    win_rate: Optional[float]
    trueskill_mu: Optional[float]
    trueskill_conservative: Optional[float]
    total_games: Optional[int]
    promoted_at: Optional[str]
    promotion_reason: Optional[str]

    def summary(self) -> str:
        """One-line human summary for logs / API responses."""
        wr = f"{self.win_rate * 100:.1f}%" if self.win_rate is not None else "n/a"
        mu = (
            f"{self.trueskill_mu:.2f}"
            if self.trueskill_mu is not None
            else "n/a"
        )
        return (
            f"champion {self.version} '{self.champion_name}' "
            f"(win_rate={wr}, TrueSkill mu={mu}, "
            f"games={self.total_games}, validated={self.validation_date})"
        )


@dataclass
class ChampionHandle:
    """A loaded champion: its validation metadata plus a ready-to-play agent.

    ``agent`` conforms to the canonical agent layer — it exposes the deploy
    ``choose_move(board, player, legal_moves, budget_ms) -> (move, stats)``
    protocol, so it is directly usable by the backend and drivable through
    :func:`agents.interface.decide`.
    """

    metadata: ChampionMetadata
    agent: Any


def _load_registry(registry_path: Path) -> Mapping[str, Any]:
    if not registry_path.exists():
        raise NoValidatedChampionError(
            f"Champion registry not found at {registry_path}. "
            "Run scripts/champion_gauntlet.py --promote to create one."
        )
    with registry_path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    if not isinstance(registry, Mapping):
        raise NoValidatedChampionError(
            f"Champion registry at {registry_path} is not a JSON object."
        )
    return registry


def _missing_validation_fields(entry: Mapping[str, Any]) -> list[str]:
    """Return the reasons ``entry`` is not a validated champion (empty == valid)."""
    reasons: list[str] = []
    if entry.get("gate_pass") is not True:
        reasons.append("gate_pass is not True (was not promoted through the gauntlet)")
    if not entry.get("config_path"):
        reasons.append("missing config_path")
    if entry.get("avg_win_rate") is None:
        reasons.append("avg_win_rate is null")
    if entry.get("avg_trueskill_mu") is None:
        reasons.append("avg_trueskill_mu is null")
    return reasons


def load_champion_metadata(
    registry_path: Optional[Path | str] = None,
) -> ChampionMetadata:
    """Resolve and validate the current champion's metadata.

    Raises :class:`NoValidatedChampionError` (with a clear reason) when the
    registry has no current version, the version is missing, or the entry has not
    cleared the gauntlet's promotion gates.
    """
    registry_path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
    registry = _load_registry(registry_path)

    current = registry.get("current_version")
    if not current:
        raise NoValidatedChampionError(
            f"Registry {registry_path} has no current_version set; "
            "no validated champion exists."
        )

    versions = registry.get("versions") or {}
    entry = versions.get(current)
    if not isinstance(entry, Mapping):
        raise NoValidatedChampionError(
            f"Registry {registry_path} current_version '{current}' "
            "has no matching versions entry."
        )

    reasons = _missing_validation_fields(entry)
    if reasons:
        raise NoValidatedChampionError(
            f"Registry {registry_path} champion '{current}' is not a validated "
            f"champion: {'; '.join(reasons)}. "
            "Promote one with scripts/champion_gauntlet.py --promote; "
            "refusing to fall back to an unvalidated champion."
        )

    config_path = str(entry["config_path"])
    if not Path(config_path).is_absolute():
        resolved = (_REPO_ROOT / config_path)
        if resolved.exists():
            config_path = str(resolved)

    ci = entry.get("win_rate_ci") or {}
    return ChampionMetadata(
        version=str(current),
        champion_name=str(entry.get("champion_name", current)),
        config_path=config_path,
        params=dict(entry.get("params") or {}),
        thinking_time_ms=entry.get("thinking_time_ms"),
        validation_date=entry.get("validation_date"),
        gauntlet_run_path=entry.get("gauntlet_run_path"),
        win_rate=entry.get("avg_win_rate"),
        trueskill_mu=entry.get("avg_trueskill_mu"),
        trueskill_conservative=entry.get("trueskill_conservative"),
        total_games=entry.get("total_games_played"),
        promoted_at=entry.get("promoted_at"),
        promotion_reason=entry.get("promotion_reason"),
    )


def build_champion_agent(metadata: ChampionMetadata, seed: Optional[int] = None) -> Any:
    """Build the champion's gameplay agent from its validated config.

    Reuses the gauntlet's config loader and the arena's ``build_agent`` so the
    served champion is exactly the agent that was validated. The returned adapter
    conforms to the canonical agent layer (exposes ``choose_move``).
    """
    # Lazy imports: keep this module importable without pulling in the heavy
    # arena/analytics stack unless a champion is actually being built.
    from analytics.tournament.arena_runner import AgentConfig, build_agent
    from analytics.tournament.gauntlet import load_candidate_config

    agent_dict = load_candidate_config(metadata.champion_name, metadata.config_path)
    config = AgentConfig.from_dict(agent_dict)
    return build_agent(config, seed=seed if seed is not None else 0)


def load_champion(
    registry_path: Optional[Path | str] = None,
    seed: Optional[int] = None,
) -> ChampionHandle:
    """Load the validated champion (metadata + ready-to-play agent).

    This is the single entry point the backend / web demo should call to request
    *"champion"*. Raises :class:`NoValidatedChampionError` when no validated
    champion exists — it never silently serves an unvalidated agent.
    """
    metadata = load_champion_metadata(registry_path)
    agent = build_champion_agent(metadata, seed=seed)
    return ChampionHandle(metadata=metadata, agent=agent)
