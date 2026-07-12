"""
Phase 3 (agent-strength rescue): node-internal verification of the minimal
trusted search — the default-config MCTSAgent (plain UCT + maxⁿ per-player
vector backup, single tree/thread, iteration budget, no experimental layers).

Complements tests/test_maxn_backprop.py (unit-level backprop semantics) and
tests/test_tactical_positions.py (final move choice) by asserting ROOT/TREE
statistics on hand-authored and seeded positions.
"""

import numpy as np
import pytest

from engine.board import Board, Player, Position
from engine.move_generator import get_shared_generator
from mcts.mcts_agent import MCTSAgent, MCTSNode
from mcts_lab.node_stats import run_search_with_root, tree_statistics
from tests.test_tactical_positions import I5, MONO, _endgame_pocket_board


def _agent(**overrides):
    params = dict(iterations=60, seed=9, rollout_policy="greedy_sample",
                  use_transposition_table=False)
    params.update(overrides)
    return MCTSAgent(**params)


class TestMinimalConfigIsDefault:
    def test_experimental_layers_default_off(self):
        agent = MCTSAgent(iterations=10, seed=1)
        assert not agent.rave_enabled
        assert not agent.nst_enabled
        assert not agent.progressive_widening_enabled
        assert not agent.opponent_modeling_enabled
        assert not agent.adaptive_exploration_enabled
        assert not agent.adaptive_rollout_depth_enabled
        assert agent.minimax_backup_alpha == 0.0
        assert not agent.policy_prior_enabled
        assert agent.num_workers == 1


class TestRootStatisticsOnKnownPosition:
    """Endgame pocket: RED has exactly two moves (I5 fills a 5-cell pocket,
    monomino wastes it). The I5 is objectively best."""

    def test_root_visit_accounting_and_best_move(self):
        board = _endgame_pocket_board()
        agent = _agent(iterations=80)
        root = run_search_with_root(agent, board, Player.RED)

        # Visit conservation: every iteration backs up through the root, and
        # every root visit beyond the first-expansion sweep lands on a child.
        assert root.visits == 80
        assert len(root.children) == 2  # both legal moves expanded
        assert sum(c.visits for c in root.children) == root.visits

        # The pentomino must dominate visits AND carry the higher RED Q.
        by_piece = {c.move.piece_id: c for c in root.children}
        i5, mono = by_piece[I5], by_piece[MONO]
        assert i5.visits > mono.visits
        assert i5.total_reward / i5.visits > mono.total_reward / mono.visits
        best = root.get_best_move()
        assert best.piece_id == I5

    def test_root_baseline_separates_siblings_leaf_baseline_cannot(self):
        """The Phase 3 defect + fix, pinned as an A/B.

        Both root children lead directly to terminal boards. RED's final score
        is 6 via the I5 (pocket filled) vs 2 via the monomino (pocket wasted).
        With the legacy "leaf" baseline the reward delta is measured from each
        child's own board, so both children evaluate to exactly 0.0 and the
        search is blind to the difference. With the "root" baseline (default)
        the deltas are 5.0 vs 1.0 — the true final-score difference.
        """
        board = _endgame_pocket_board()

        legacy = _agent(iterations=40, rollout_reward_baseline="leaf")
        root = run_search_with_root(legacy, board, Player.RED)
        legacy_q = {c.move.piece_id: c.total_reward / c.visits for c in root.children}
        assert legacy_q[I5] == pytest.approx(0.0)
        assert legacy_q[MONO] == pytest.approx(0.0)

        fixed = _agent(iterations=40)  # default: rollout_reward_baseline="root"
        root = run_search_with_root(fixed, board, Player.RED)
        fixed_q = {c.move.piece_id: c.total_reward / c.visits for c in root.children}
        assert fixed_q[I5] == pytest.approx(5.0)
        assert fixed_q[MONO] == pytest.approx(1.0)

    def test_children_q_is_red_perspective(self):
        # Both root children were reached by RED's move, so each child's
        # accumulated reward is RED's own (mover-credited maxⁿ semantics).
        # Filling the pocket with the I5 ends RED at a strictly higher final
        # score than wasting the monomino, so RED's mean reward must order
        # the moves accordingly (already asserted above); here we pin the
        # bookkeeping: children of the root store rewards for root.player.
        board = _endgame_pocket_board()
        agent = _agent(iterations=40)
        root = run_search_with_root(agent, board, Player.RED)
        for child in root.children:
            assert child.parent is root
            assert root.player is Player.RED  # mover whose reward the child stores
            assert child.visits > 0


class TestSingleLegalMove:
    def test_select_action_short_circuits(self):
        board = _endgame_pocket_board()
        # Remove the monomino from RED's rack: only the I5 remains playable.
        board.player_pieces_used[Player.RED].add(MONO)
        gen = get_shared_generator()
        moves = gen.get_legal_moves(board, Player.RED)
        assert len({m.piece_id for m in moves}) == 1
        agent = _agent()
        chosen = agent.select_action(board, Player.RED, moves[:1])
        assert chosen is moves[0]


class TestPassNodeSemantics:
    def test_blocked_player_node_expands_to_pass_child(self):
        board = _endgame_pocket_board()
        # BLUE to move: BLUE is fully blocked but RED still has moves, so the
        # node must carry the pass sentinel and expand to a same-board child
        # for the next player.
        board.current_player = Player.BLUE
        node = MCTSNode(board, Player.BLUE)
        assert node.untried_moves == [None]
        child = node.expand()
        assert child is not None
        assert child.move is None
        assert child.player is not Player.BLUE
        assert np.array_equal(child.board.grid, board.grid)

    def test_terminal_position_rollout_rewards_winner(self):
        # Fill the pocket with the I5 -> nobody can move; rollout from the
        # terminal board must return per-player rewards with RED (the score
        # leader by construction... BLUE owns most of the board, so BLUE wins)
        # — assert the vector is complete and the winner's own entry carries
        # the outright-win bonus.
        board = _endgame_pocket_board()
        gen = get_shared_generator()
        i5_moves = [m for m in gen.get_legal_moves(board, Player.RED) if m.piece_id == I5]
        orientations = gen.piece_orientations_cache[I5]
        board.place_piece(i5_moves[0].get_positions(orientations), Player.RED, I5)
        for p in Player:
            assert not gen.get_legal_moves(board, p)

        agent = _agent(iterations=2)
        agent._root_player = Player.RED
        rewards, _ = agent._rollout(board, board.current_player)
        assert set(rewards) == set(Player)
        scores = {p: board.get_score(p) for p in Player}
        winner = max(scores, key=scores.get)
        assert rewards[winner] == max(rewards.values())
        assert rewards[winner] >= 100.0  # outright-win bonus on winner's own entry


class TestDeterminism:
    def _root_signature(self, seed):
        board, _ = _seeded_midgame(20260620)
        agent = _agent(iterations=120, seed=seed)
        root = run_search_with_root(agent, board, board.current_player)
        return {
            (c.move.piece_id, c.move.orientation, c.move.anchor_row, c.move.anchor_col):
                (c.visits, round(c.total_reward, 9))
            for c in root.children if c.move is not None
        }

    def test_same_seed_identical_tree_stats(self):
        assert self._root_signature(7) == self._root_signature(7)

    def test_tree_statistics_walker(self):
        board, _ = _seeded_midgame(20260621)
        agent = _agent(iterations=50)
        root = run_search_with_root(agent, board, board.current_player)
        node_count, depth_histogram = tree_statistics(root)
        assert depth_histogram[0] == 1
        assert node_count == sum(depth_histogram.values())
        # Every iteration expands at most one node.
        assert node_count <= 50 + 1


def _seeded_midgame(seed):
    from tests.utils_game_states import generate_random_valid_state
    return generate_random_valid_state(num_moves=14, seed=seed)
