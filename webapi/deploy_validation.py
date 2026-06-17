"""
Validation and normalization rules for deploy-mode gameplay configuration.
"""

from __future__ import annotations

from typing import Dict

from fastapi import HTTPException

from agents.champion import CHAMPION_PROFILE
from mcts.champion_profile import CHALLENGE_CHAMPION_PROFILE, load_challenge_champion_profile
from schemas.game_state import AgentType, GameConfig, PlayerConfig

DEPLOY_TIME_BUDGET_CAP_MS = 30000
# Default per-move budget for registry-backed champion opponents in the public
# "Play the Champion" demo. Kept modest so the demo stays responsive; callers
# may override up to the deploy cap.
DEPLOY_CHAMPION_DEFAULT_MS = 1000
DEPLOY_DIFFICULTY_TO_MS: Dict[str, int] = {
    "easy": 200,
    "medium": 450,
    "hard": 900,
}
_DEPLOY_REQUIRED_DIFFICULTIES = {"easy", "medium", "hard"}


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def _normalize_difficulty(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value not in DEPLOY_DIFFICULTY_TO_MS:
        valid = ", ".join(sorted(DEPLOY_DIFFICULTY_TO_MS.keys()))
        raise _bad_request(f"Invalid MCTS difficulty '{raw}'. Allowed values: {valid}.")
    return value


def _normalize_time_budget_ms(raw: object) -> int:
    try:
        budget = int(raw)
    except (TypeError, ValueError):
        raise _bad_request("Invalid time budget. 'time_budget_ms' must be an integer.")

    if budget < 1:
        raise _bad_request("Invalid time budget. 'time_budget_ms' must be >= 1.")
    if budget > DEPLOY_TIME_BUDGET_CAP_MS:
        raise _bad_request(
            f"time_budget_ms={budget} exceeds deploy cap ({DEPLOY_TIME_BUDGET_CAP_MS}ms)."
        )
    return budget


def normalize_deploy_game_config(config: GameConfig) -> GameConfig:
    """
    Validate and normalize a create-game payload for APP_PROFILE=deploy.

    Rules:
    - Exactly 4 players
    - Exactly 1 human + 3 mcts
    - MCTS must use either exactly one easy/medium/hard difficulty each, or all
      three MCTS players must use the challenge champion profile
    - Non-deploy agent types are rejected
    - MCTS budgets are normalized from preset or validated against deploy cap
    """
    if len(config.players) != 4:
        raise _bad_request("Deploy mode requires exactly 4 players (1 human + 3 MCTS).")

    human_players = []
    mcts_players = []

    for player_cfg in config.players:
        if player_cfg.agent_type == AgentType.HUMAN:
            human_players.append(player_cfg)
        elif player_cfg.agent_type == AgentType.MCTS:
            mcts_players.append(player_cfg)
        else:
            raise _bad_request(
                "Deploy mode only supports agent_type values: 'human' and 'mcts'."
            )

    if len(human_players) != 1 or len(mcts_players) != 3:
        raise _bad_request(
            "Deploy mode requires exactly 1 human player and exactly 3 MCTS players."
        )

    challenge_players = []
    champion_players = []
    difficulty_players = []
    for player_cfg in mcts_players:
        agent_config = dict(player_cfg.agent_config or {})
        profile = agent_config.get("profile")
        if profile is None:
            difficulty_players.append(player_cfg)
        elif profile == CHALLENGE_CHAMPION_PROFILE:
            challenge_players.append(player_cfg)
        elif profile == CHAMPION_PROFILE:
            champion_players.append(player_cfg)
        else:
            raise _bad_request(f"Invalid MCTS profile '{profile}'.")

    profile_groups = [g for g in (challenge_players, champion_players) if g]
    if profile_groups and difficulty_players:
        raise _bad_request(
            "Deploy mode cannot mix profile players "
            "(challenge champion / champion) with difficulty preset players."
        )
    if len(profile_groups) > 1:
        raise _bad_request(
            "Deploy mode cannot mix challenge champion and champion profile players."
        )

    if champion_players:
        # Registry-backed champion opponents. We validate/normalize the budget
        # here but resolve the actual champion config through the registry at
        # game-creation time (no hardcoded config path).
        for player_cfg in champion_players:
            agent_config = dict(player_cfg.agent_config or {})
            budget_raw = agent_config.get("time_budget_ms", DEPLOY_CHAMPION_DEFAULT_MS)
            budget_ms = _normalize_time_budget_ms(budget_raw)
            agent_config["profile"] = CHAMPION_PROFILE
            agent_config["time_budget_ms"] = budget_ms
            player_cfg.agent_config = agent_config
        human_cfg: PlayerConfig = human_players[0]
        human_cfg.agent_config = dict(human_cfg.agent_config or {})
        return config

    if challenge_players:
        profile = load_challenge_champion_profile()
        default_budget = int(profile["max_budget_ms"])
        for player_cfg in challenge_players:
            agent_config = dict(player_cfg.agent_config or {})
            budget_raw = agent_config.get("time_budget_ms", default_budget)
            budget_ms = _normalize_time_budget_ms(budget_raw)
            agent_config["profile"] = CHALLENGE_CHAMPION_PROFILE
            agent_config["time_budget_ms"] = budget_ms
            player_cfg.agent_config = agent_config
        human_cfg: PlayerConfig = human_players[0]
        human_cfg.agent_config = dict(human_cfg.agent_config or {})
        return config

    seen_difficulties = set()
    for player_cfg in mcts_players:
        agent_config = dict(player_cfg.agent_config or {})
        difficulty_raw = agent_config.get("difficulty")
        budget_raw = agent_config.get("time_budget_ms")

        if budget_raw is not None:
            budget_ms = _normalize_time_budget_ms(budget_raw)
            if difficulty_raw is not None:
                difficulty = _normalize_difficulty(str(difficulty_raw))
            else:
                # Infer nearest deploy difficulty label for consistent telemetry/config.
                difficulty = min(
                    DEPLOY_DIFFICULTY_TO_MS.keys(),
                    key=lambda k: abs(DEPLOY_DIFFICULTY_TO_MS[k] - budget_ms),
                )
        elif difficulty_raw is not None:
            difficulty = _normalize_difficulty(str(difficulty_raw))
            budget_ms = DEPLOY_DIFFICULTY_TO_MS[difficulty]
        else:
            difficulty = "medium"
            budget_ms = DEPLOY_DIFFICULTY_TO_MS[difficulty]

        if budget_ms > DEPLOY_TIME_BUDGET_CAP_MS:
            raise _bad_request(
                f"time_budget_ms={budget_ms} exceeds deploy cap ({DEPLOY_TIME_BUDGET_CAP_MS}ms)."
            )

        seen_difficulties.add(difficulty)
        agent_config["difficulty"] = difficulty
        agent_config["time_budget_ms"] = budget_ms
        player_cfg.agent_config = agent_config

    if seen_difficulties != _DEPLOY_REQUIRED_DIFFICULTIES:
        required = ", ".join(sorted(_DEPLOY_REQUIRED_DIFFICULTIES))
        raise _bad_request(
            f"Deploy mode requires exactly one MCTS player for each difficulty: {required}."
        )

    human_cfg: PlayerConfig = human_players[0]
    human_cfg.agent_config = dict(human_cfg.agent_config or {})

    return config
