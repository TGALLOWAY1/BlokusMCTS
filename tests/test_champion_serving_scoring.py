"""Phase 5 tests: web API champion serving + scoring-mode support.

Covers:
1. The ``/api/champion`` metadata endpoint (happy path).
2. Backend behavior when no validated champion exists (clear failure).
3. Creating a game / agent against the registry-backed champion.
4. Standard scoring mode (no positional bonuses).
5. House scoring mode (standard + corner/center bonuses).

These tests are self-contained: they build temporary champion registries and a
cheap ``random`` champion so no real gauntlet or MCTS search is needed.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from agents.champion import (
    CHAMPION_PROFILE,
    NoValidatedChampionError,
    REGISTRY_PATH_ENV,
    build_champion_gameplay_agent,
)
from engine.board import Player
from engine.game import BlokusGame
from schemas.game_state import AgentType, GameConfig, Player as SchemaPlayer, PlayerConfig
from webapi.app import create_app
from webapi.deploy_validation import (
    DEPLOY_CHAMPION_DEFAULT_MS,
    normalize_deploy_game_config,
)
from webapi.profile import APP_PROFILE_DEPLOY, APP_PROFILE_RESEARCH


# ---------------------------------------------------------------------------
# Registry fixtures
# ---------------------------------------------------------------------------

def _validated_entry(config_path: str) -> dict:
    return {
        "promoted_at": "2026-06-17T00:00:00+00:00",
        "promoted_from": None,
        "promotion_reason": "phase5 test fixture",
        "champion_name": "test_champion",
        "config_path": config_path,
        "params": {"seed": 0},
        "avg_win_rate": 0.42,
        "win_rate_ci": {"lower": 0.30, "upper": 0.55},
        "avg_trueskill_mu": 27.5,
        "trueskill_sigma": 2.1,
        "trueskill_conservative": 21.2,
        "avg_score": 61.0,
        "total_games_played": 120,
        "seeds": [1, 2, 3],
        "validation_date": "2026-06-17T00:00:00+00:00",
        "gauntlet_run_path": "arena_runs/gauntlets/gauntlet_test",
        "comparison_opponents": ["a", "b", "c"],
        "notes": "fast random champion for tests",
        "gate_pass": True,
    }


def _write_registry(reg_path: Path, entry: dict | None, current: str = "v1") -> None:
    registry = {
        "current_version": current,
        "versions": {current: entry} if entry is not None else {},
        "iterations": [],
        "snapshot_csv_paths": [],
        "total_games_played": int(entry.get("total_games_played", 0)) if entry else 0,
    }
    reg_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


@contextmanager
def _validated_champion_registry():
    """Yield a registry path pointing at a cheap, validated 'random' champion."""
    with TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "champ.json"
        cfg.write_text(
            json.dumps({"type": "random", "thinking_time_ms": 50}), encoding="utf-8"
        )
        reg = Path(tmp) / "registry.json"
        _write_registry(reg, _validated_entry(str(cfg)))
        yield reg


@contextmanager
def _unvalidated_champion_registry():
    """Yield a registry path whose only entry mirrors the shipped null-metric seed."""
    with TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.json"
        _write_registry(
            reg,
            {
                "promoted_at": "2026-04-29T00:00:00+00:00",
                "params": {"rollout_policy": "random"},
                "avg_win_rate": None,
                "avg_trueskill_mu": None,
            },
        )
        yield reg


@contextmanager
def _env(name: str, value: str):
    prev = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = prev


# ---------------------------------------------------------------------------
# 1. Champion metadata endpoint
# ---------------------------------------------------------------------------

def test_champion_endpoint_returns_metadata():
    app = create_app(profile=APP_PROFILE_DEPLOY, include_research_routes=False)
    with _validated_champion_registry() as reg, _env(REGISTRY_PATH_ENV, str(reg)):
        client = TestClient(app)
        resp = client.get("/api/champion")

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "test_champion"
    assert body["winRate"] == 0.42
    assert body["trueSkill"] == 27.5
    assert body["totalGamesPlayed"] == 120
    assert body["validationDate"] == "2026-06-17T00:00:00+00:00"
    assert body["gauntletRunPath"] == "arena_runs/gauntlets/gauntlet_test"
    assert body["notes"] == "fast random champion for tests"
    assert body["configPath"].endswith("champ.json")


# ---------------------------------------------------------------------------
# 2. No validated champion -> clear failure
# ---------------------------------------------------------------------------

def test_champion_endpoint_404_when_no_validated_champion():
    app = create_app(profile=APP_PROFILE_DEPLOY, include_research_routes=False)
    with _unvalidated_champion_registry() as reg, _env(REGISTRY_PATH_ENV, str(reg)):
        client = TestClient(app)
        resp = client.get("/api/champion")

    assert resp.status_code == 404
    # The message must explain *why* there is no champion, not silently 200.
    assert "not a validated champion" in resp.json()["message"]


def test_champion_endpoint_404_when_registry_missing():
    app = create_app(profile=APP_PROFILE_DEPLOY, include_research_routes=False)
    with TemporaryDirectory() as tmp, _env(
        REGISTRY_PATH_ENV, str(Path(tmp) / "does_not_exist.json")
    ):
        client = TestClient(app)
        resp = client.get("/api/champion")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Creating a game / agent against the champion
# ---------------------------------------------------------------------------

def test_build_champion_gameplay_agent_resolves_through_registry():
    with _validated_champion_registry() as reg:
        agent = build_champion_gameplay_agent(registry_path=reg, seed=7)
    # The served champion must speak the deploy gameplay protocol.
    assert callable(getattr(agent, "choose_move", None))

    # And it should actually pick a legal move from a fresh position.
    game = BlokusGame()
    legal = game.get_legal_moves(Player.RED)
    move, stats = agent.choose_move(game.board, Player.RED, legal, 50)
    assert move in legal
    assert isinstance(stats, dict)


def test_champion_serving_fails_clearly_without_validated_champion():
    with _unvalidated_champion_registry() as reg:
        with pytest.raises(NoValidatedChampionError):
            build_champion_gameplay_agent(registry_path=reg)


def test_deploy_validation_accepts_champion_profile():
    cfg = GameConfig(
        players=[
            PlayerConfig(player=SchemaPlayer.RED, agent_type=AgentType.HUMAN, agent_config={}),
            PlayerConfig(player=SchemaPlayer.BLUE, agent_type=AgentType.MCTS, agent_config={"profile": CHAMPION_PROFILE}),
            PlayerConfig(player=SchemaPlayer.GREEN, agent_type=AgentType.MCTS, agent_config={"profile": CHAMPION_PROFILE}),
            PlayerConfig(player=SchemaPlayer.YELLOW, agent_type=AgentType.MCTS, agent_config={"profile": CHAMPION_PROFILE}),
        ],
        auto_start=True,
    )
    normalized = normalize_deploy_game_config(cfg)
    for player_cfg in normalized.players:
        if player_cfg.agent_type == AgentType.MCTS:
            assert player_cfg.agent_config["profile"] == CHAMPION_PROFILE
            assert player_cfg.agent_config["time_budget_ms"] == DEPLOY_CHAMPION_DEFAULT_MS


def test_deploy_validation_rejects_mixed_champion_and_difficulty():
    cfg = GameConfig(
        players=[
            PlayerConfig(player=SchemaPlayer.RED, agent_type=AgentType.HUMAN, agent_config={}),
            PlayerConfig(player=SchemaPlayer.BLUE, agent_type=AgentType.MCTS, agent_config={"profile": CHAMPION_PROFILE}),
            PlayerConfig(player=SchemaPlayer.GREEN, agent_type=AgentType.MCTS, agent_config={"difficulty": "medium"}),
            PlayerConfig(player=SchemaPlayer.YELLOW, agent_type=AgentType.MCTS, agent_config={"difficulty": "hard"}),
        ],
        auto_start=True,
    )
    with pytest.raises(HTTPException) as exc:
        normalize_deploy_game_config(cfg)
    assert exc.value.status_code == 400
    assert "cannot mix" in str(exc.value.detail)


# ---------------------------------------------------------------------------
# 4 & 5. Scoring modes
# ---------------------------------------------------------------------------

def _play_red_corner_move(game: BlokusGame) -> None:
    """Play RED's first legal move (which covers the starting corner)."""
    legal = game.get_legal_moves(Player.RED)
    assert legal, "RED should have legal opening moves"
    assert game.make_move(legal[0], Player.RED)


def test_standard_scoring_excludes_positional_bonuses():
    game = BlokusGame(scoring_mode="standard")
    _play_red_corner_move(game)

    base = int(game.board.get_score(Player.RED))
    # RED's opening covers a board corner, so the house corner bonus would apply.
    assert game._calculate_corner_bonus(Player.RED) > 0
    # ...but standard scoring must ignore it.
    assert game.get_score(Player.RED) == base


def test_house_scoring_includes_positional_bonuses():
    game = BlokusGame(scoring_mode="house")
    _play_red_corner_move(game)

    base = int(game.board.get_score(Player.RED))
    bonus = game._calculate_corner_bonus(Player.RED) + game._calculate_center_bonus(Player.RED)
    assert bonus > 0
    assert game.get_score(Player.RED) == base + bonus


def test_house_scoring_is_default():
    # Existing arena runs / experiments construct BlokusGame() with no mode and
    # must keep the historical house behavior.
    assert BlokusGame().scoring_mode == "house"


def test_standard_and_house_diverge_on_same_position():
    standard = BlokusGame(scoring_mode="standard")
    house = BlokusGame(scoring_mode="house")
    for game in (standard, house):
        _play_red_corner_move(game)
    assert house.get_score(Player.RED) > standard.get_score(Player.RED)


# ---------------------------------------------------------------------------
# Scoring mode surfaced in API game state
# ---------------------------------------------------------------------------

def _two_player_config(scoring_mode=None) -> dict:
    payload = {
        "players": [
            {"player": "RED", "agent_type": "human", "agent_config": {}},
            {"player": "BLUE", "agent_type": "human", "agent_config": {}},
        ],
        "auto_start": True,
    }
    if scoring_mode is not None:
        payload["scoring_mode"] = scoring_mode
    return payload


def test_game_state_reports_scoring_mode_research_default_house():
    app = create_app(profile=APP_PROFILE_RESEARCH, include_research_routes=False)
    client = TestClient(app)
    resp = client.post("/api/games", json=_two_player_config())
    assert resp.status_code == 200
    assert resp.json()["game_state"]["scoring_mode"] == "house"


def test_game_state_reports_explicit_standard_scoring_mode():
    app = create_app(profile=APP_PROFILE_RESEARCH, include_research_routes=False)
    client = TestClient(app)
    resp = client.post("/api/games", json=_two_player_config(scoring_mode="standard"))
    assert resp.status_code == 200
    assert resp.json()["game_state"]["scoring_mode"] == "standard"
