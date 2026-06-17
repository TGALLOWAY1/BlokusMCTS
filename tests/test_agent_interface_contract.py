"""Tests for the canonical agent interface and the champion contract.

These are deliberately lightweight and deterministic — no tournaments are run.
They verify:

1. RandomAgent / HeuristicAgent / MCTSAgent conform to ``BlokusAgent``.
2. :func:`agents.interface.decide` returns canonical decisions, including the
   ``None`` move on empty legal moves.
3. The arena adapter preserves existing ``choose_move`` behaviour.
4. The champion loader fails clearly when the registry has no validated champion.
5. The champion loader works when the registry has valid metadata + config.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from engine.board import Board, Player
from engine.game import BlokusGame

from agents.random_agent import RandomAgent
from agents.heuristic_agent import HeuristicAgent
from mcts.mcts_agent import MCTSAgent

from agents.interface import (
    AgentDecision,
    AgentDecisionContext,
    BlokusAgent,
    conforms,
    decide,
    is_gameplay_agent,
)
from agents.champion import (
    ChampionHandle,
    ChampionMetadata,
    NoValidatedChampionError,
    load_champion,
    load_champion_metadata,
)


def _fresh_position():
    game = BlokusGame()
    player = game.get_current_player()
    legal_moves = game.get_legal_moves(player)
    return game.board, player, legal_moves


def _move_key(move):
    return (move.piece_id, move.orientation, move.anchor_row, move.anchor_col)


def _legal_keys(legal_moves):
    # Move has no value equality; compare by identifying tuple like the rest of
    # the test-suite does.
    return {_move_key(m) for m in legal_moves}


class TestCanonicalConformance(unittest.TestCase):
    """All real gameplay agents satisfy the canonical BlokusAgent contract."""

    def test_random_agent_conforms(self):
        agent = RandomAgent(seed=1)
        self.assertIsInstance(agent, BlokusAgent)
        self.assertTrue(conforms(agent))

    def test_heuristic_agent_conforms(self):
        agent = HeuristicAgent(seed=1)
        self.assertIsInstance(agent, BlokusAgent)
        self.assertTrue(conforms(agent))

    def test_mcts_agent_conforms(self):
        agent = MCTSAgent(iterations=5, seed=1)
        self.assertIsInstance(agent, BlokusAgent)
        self.assertTrue(conforms(agent))


class TestDecide(unittest.TestCase):
    """The decide() front door behaves canonically for every agent."""

    def test_decide_returns_legal_move_random(self):
        board, player, legal_moves = _fresh_position()
        decision = decide(RandomAgent(seed=7), board, player, legal_moves)
        self.assertIsInstance(decision, AgentDecision)
        self.assertIn(_move_key(decision.move), _legal_keys(legal_moves))

    def test_decide_returns_legal_move_heuristic(self):
        board, player, legal_moves = _fresh_position()
        decision = decide(HeuristicAgent(seed=7), board, player, legal_moves)
        self.assertIn(_move_key(decision.move), _legal_keys(legal_moves))

    def test_decide_returns_legal_move_mcts(self):
        board, player, legal_moves = _fresh_position()
        decision = decide(MCTSAgent(iterations=10, seed=7), board, player, legal_moves)
        self.assertIn(_move_key(decision.move), _legal_keys(legal_moves))

    def test_decide_none_on_empty_legal_moves(self):
        board, player, _ = _fresh_position()
        decision = decide(RandomAgent(seed=7), board, player, [])
        self.assertIsNone(decision.move)
        self.assertEqual(decision.stats, {})

    def test_decide_collects_mcts_diagnostics(self):
        board, player, legal_moves = _fresh_position()
        context = AgentDecisionContext(collect_diagnostics=True)
        decision = decide(MCTSAgent(iterations=10, seed=7), board, player, legal_moves, context)
        # MCTSAgent.get_action_info exposes a stats dict.
        self.assertIsInstance(decision.stats, dict)
        self.assertIn("iterations_run", decision.stats)

    def test_decide_applies_time_budget_to_mcts(self):
        board, player, legal_moves = _fresh_position()
        agent = MCTSAgent(iterations=10000, seed=7)
        context = AgentDecisionContext(time_budget_ms=50)
        decide(agent, board, player, legal_moves, context)
        # The budget was pushed onto the agent's time_limit (seconds).
        self.assertAlmostEqual(agent.time_limit, 0.05, places=6)

    def test_native_agents_are_not_gameplay_agents(self):
        self.assertFalse(is_gameplay_agent(RandomAgent(seed=1)))
        self.assertFalse(is_gameplay_agent(MCTSAgent(iterations=5, seed=1)))


class TestArenaAdapterPreserved(unittest.TestCase):
    """The arena adapter still wraps select_action into (move, stats)."""

    def test_select_action_adapter_choose_move(self):
        from analytics.tournament.arena_runner import _SelectActionAdapter

        board, player, legal_moves = _fresh_position()
        adapter = _SelectActionAdapter(RandomAgent(seed=3))
        self.assertTrue(is_gameplay_agent(adapter))
        move, stats = adapter.choose_move(board, player, legal_moves, 1000)
        self.assertIn(move, legal_moves)
        self.assertIn("timeSpentMs", stats)

    def test_decide_routes_through_gameplay_adapter(self):
        from analytics.tournament.arena_runner import _SelectActionAdapter

        board, player, legal_moves = _fresh_position()
        adapter = _SelectActionAdapter(RandomAgent(seed=3))
        decision = decide(
            adapter, board, player, legal_moves,
            AgentDecisionContext(time_budget_ms=500),
        )
        self.assertIn(_move_key(decision.move), _legal_keys(legal_moves))
        self.assertIn("timeSpentMs", decision.stats)


def _write_registry(path: Path, entry: dict, current: str = "v1") -> None:
    registry = {
        "current_version": current,
        "versions": {current: entry} if entry is not None else {},
        "iterations": [],
        "snapshot_csv_paths": [],
        "total_games_played": int(entry.get("total_games_played", 0)) if entry else 0,
    }
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


class TestChampionLoaderFailsClearly(unittest.TestCase):
    """The loader refuses to serve an unvalidated champion."""

    def test_seed_registry_with_null_metrics_is_rejected(self):
        with TemporaryDirectory() as tmp:
            reg = Path(tmp) / "registry.json"
            # Mirrors the shipped seed entry: null metrics, no gate_pass/config.
            _write_registry(reg, {
                "promoted_at": "2026-04-29T00:00:00+00:00",
                "params": {"rollout_policy": "random"},
                "avg_win_rate": None,
                "avg_trueskill_mu": None,
            })
            with self.assertRaises(NoValidatedChampionError):
                load_champion_metadata(reg)

    def test_missing_registry_raises(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(NoValidatedChampionError):
                load_champion_metadata(Path(tmp) / "does_not_exist.json")

    def test_no_current_version_raises(self):
        with TemporaryDirectory() as tmp:
            reg = Path(tmp) / "registry.json"
            reg.write_text(json.dumps({"current_version": None, "versions": {}}), encoding="utf-8")
            with self.assertRaises(NoValidatedChampionError):
                load_champion_metadata(reg)


class TestChampionLoaderHappyPath(unittest.TestCase):
    """The loader resolves metadata + builds an agent for a validated champion."""

    def _validated_entry(self, config_path: str) -> dict:
        return {
            "promoted_at": "2026-06-17T00:00:00+00:00",
            "promoted_from": None,
            "promotion_reason": "test fixture",
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
            "gauntlet_run_path": "analytics/tournament/runs/gauntlet_test",
            "comparison_opponents": ["a", "b", "c"],
            "gate_pass": True,
        }

    def test_metadata_resolves(self):
        with TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "champ.json"
            cfg.write_text(json.dumps({"type": "random", "thinking_time_ms": 100}), encoding="utf-8")
            reg = Path(tmp) / "registry.json"
            _write_registry(reg, self._validated_entry(str(cfg)))

            meta = load_champion_metadata(reg)
            self.assertIsInstance(meta, ChampionMetadata)
            self.assertEqual(meta.champion_name, "test_champion")
            self.assertEqual(meta.win_rate, 0.42)
            self.assertEqual(meta.trueskill_mu, 27.5)
            self.assertEqual(meta.total_games, 120)
            self.assertEqual(meta.gauntlet_run_path, "analytics/tournament/runs/gauntlet_test")
            self.assertIn("test_champion", meta.summary())

    def test_loads_and_builds_agent(self):
        # Use a cheap 'random' champion so the test stays fast & deterministic.
        with TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "champ.json"
            cfg.write_text(json.dumps({"type": "random", "thinking_time_ms": 100}), encoding="utf-8")
            reg = Path(tmp) / "registry.json"
            _write_registry(reg, self._validated_entry(str(cfg)))

            handle = load_champion(reg, seed=5)
            self.assertIsInstance(handle, ChampionHandle)
            # The built agent is canonical-drivable.
            self.assertTrue(is_gameplay_agent(handle.agent))
            board, player, legal_moves = _fresh_position()
            decision = decide(handle.agent, board, player, legal_moves)
            self.assertIn(_move_key(decision.move), _legal_keys(legal_moves))


if __name__ == "__main__":
    unittest.main()
