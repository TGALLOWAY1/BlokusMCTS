"""Regression tests for the maxⁿ per-player reward backpropagation.

The pre-July-2026 bug: rollout rewards were computed only from the root
player's perspective and every node — including opponent nodes — selected
children by maximizing that value, so the tree modeled opponents as
cooperating with the root player. These tests pin the fixed semantics:

* rollouts return a reward for every player;
* each node accumulates the reward of the player who moved into it;
* selection at an opponent node prefers the move that is good for the
  opponent, not the move that is good for the root player.
"""

import unittest

from engine.board import Board, Player
from engine.game import BlokusGame
from mcts.mcts_agent import MCTSAgent, MCTSNode, _PLAYERS


class TestRolloutRewardVector(unittest.TestCase):
    def test_rollout_returns_reward_for_every_player(self):
        agent = MCTSAgent(iterations=2, seed=3, rollout_policy="random",
                          use_transposition_table=False)
        agent._root_player = Player.RED
        rewards, _ = agent._rollout(Board(), Player.RED)
        self.assertEqual(set(rewards), set(_PLAYERS))
        for value in rewards.values():
            self.assertIsInstance(value, float)

    def test_win_bonus_goes_to_the_winner_not_the_root(self):
        """Play a full rollout to completion; whoever scored highest gets the
        outright-win bonus in their OWN entry."""
        agent = MCTSAgent(iterations=2, seed=11, rollout_policy="random",
                          use_transposition_table=False, max_rollout_moves=500)
        agent._root_player = Player.RED
        rewards, _ = agent._rollout(Board(), Player.RED)
        # With max_rollout_moves=500 the game always reaches all-pass, so the
        # winner carries the +100 outright / +10 tie bonus, lifting them
        # clearly above pure score deltas.
        self.assertTrue(any(v >= 100.0 for v in rewards.values()),
                        f"no winner bonus found in {rewards}")


class TestBackpropagationPerspective(unittest.TestCase):
    def _tree(self):
        """root(RED) -> child(BLUE) -> grandchild(YELLOW)."""
        board = Board()
        root = MCTSNode(board, Player.RED)
        child = MCTSNode(board, Player.BLUE, move=None, parent=root)
        grand = MCTSNode(board, Player.YELLOW, move=None, parent=child)
        return root, child, grand

    def test_each_node_gets_movers_reward(self):
        root, child, grand = self._tree()
        agent = MCTSAgent(iterations=1, seed=1, use_transposition_table=False)
        agent._root_player = Player.RED
        rewards = {Player.RED: 10.0, Player.BLUE: -4.0,
                   Player.YELLOW: 7.0, Player.GREEN: 0.0}
        agent._backpropagation(grand, rewards)
        # grand was reached by BLUE's move (child.player == BLUE) -> BLUE's reward
        self.assertEqual(grand.total_reward, -4.0)
        # child was reached by RED's move (root.player == RED) -> RED's reward
        self.assertEqual(child.total_reward, 10.0)
        # root accumulates the root player's reward
        self.assertEqual(root.total_reward, 10.0)

    def test_opponent_node_selects_own_best_move(self):
        """At a BLUE node, UCB must prefer the child that is good for BLUE,
        even when that child is bad for the root player (RED)."""
        board = Board()
        blue_node = MCTSNode(board, Player.BLUE)
        blue_node.visits = 20
        good_for_blue = MCTSNode(board, Player.YELLOW, move=None, parent=blue_node)
        good_for_red = MCTSNode(board, Player.YELLOW, move=None, parent=blue_node)
        blue_node.children = [good_for_blue, good_for_red]
        blue_node.untried_moves = []
        for _ in range(10):
            good_for_blue.update(8.0)    # BLUE's own reward: high
            good_for_red.update(-8.0)    # BLUE's own reward: low (great for RED)
        chosen = blue_node.select_child(exploration_constant=0.1)
        self.assertIs(chosen, good_for_blue,
                      "opponent node must maximize its own reward (maxⁿ)")


class TestSearchStillReturnsLegalMoves(unittest.TestCase):
    def test_full_search_smoke(self):
        game = BlokusGame(enable_telemetry=False)
        player = game.get_current_player()
        moves = game.get_legal_moves(player)
        agent = MCTSAgent(iterations=10, seed=5, rollout_policy="greedy_sample",
                          rollout_cutoff_depth=6)
        move = agent.select_action(game.board, player, moves)
        keys = {(m.piece_id, m.orientation, m.anchor_row, m.anchor_col) for m in moves}
        self.assertIn((move.piece_id, move.orientation, move.anchor_row, move.anchor_col), keys)


if __name__ == "__main__":
    unittest.main()
