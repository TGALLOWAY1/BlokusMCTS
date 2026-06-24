"""Tests for rich Blokus feature extraction (training/rich_features.py)."""

from __future__ import annotations

import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.board import Player
from engine.game import BlokusGame
from training import rich_features as rf
from mcts.state_evaluator import FEATURE_NAMES as SE_FEATURE_NAMES


def _play(plies: int, seed: int = 0) -> BlokusGame:
    random.seed(seed)
    np.random.seed(seed)
    game = BlokusGame()
    for _ in range(plies):
        p = game.get_current_player()
        moves = game.get_legal_moves(p)
        if not moves:
            game.board._update_current_player()
            game._check_game_over()
            continue
        game.make_move(moves[len(moves) // 2], p)
        if game.is_game_over():
            break
    return game


def test_feature_set_is_superset_of_agent_features():
    # Every SE feature the live agent consumes must be present (for projection).
    for name in SE_FEATURE_NAMES:
        assert name in rf.RICH_FEATURE_NAMES
    # The SE features occupy the leading block (so the projection slice is stable).
    assert rf.RICH_FEATURE_NAMES[: len(SE_FEATURE_NAMES)] == list(SE_FEATURE_NAMES)


def test_all_features_numeric_and_finite_empty_board():
    game = BlokusGame()
    cache = rf.FeatureCache()
    feats = rf.extract_rich_features(game.board, Player.RED, cache=cache)
    assert set(feats) == set(rf.RICH_FEATURE_NAMES)
    for name, val in feats.items():
        assert isinstance(val, float), name
        assert math.isfinite(val), name


def test_all_features_numeric_and_finite_midgame():
    game = _play(20, seed=3)
    cache = rf.FeatureCache()
    for player in Player:
        feats = rf.extract_rich_features(game.board, player, cache=cache)
        assert set(feats) == set(rf.RICH_FEATURE_NAMES)
        for name, val in feats.items():
            assert math.isfinite(val), f"{player}:{name}"


def test_legal_move_counts_non_negative_and_consistent():
    game = _play(16, seed=7)
    feats = rf.extract_rich_features(game.board, Player.RED)
    for key in (
        "legal_move_count",
        "legal_move_count_small_pieces",
        "legal_move_count_medium_pieces",
        "legal_move_count_large_pieces",
        "playable_piece_count",
        "total_playable_piece_area",
    ):
        assert feats[key] >= 0.0, key


def test_remaining_piece_features_match_inventory():
    game = _play(8, seed=1)
    board = game.board
    feats = rf.extract_rich_features(board, Player.RED)
    used = board.player_pieces_used[Player.RED]
    expected_remaining = 21 - len(used)
    assert math.isclose(feats["remaining_piece_count"], expected_remaining / 21.0, rel_tol=1e-9)
    # completion_ratio is the complement.
    assert math.isclose(feats["completion_ratio"], len(used) / 21.0, rel_tol=1e-9)


def test_rank_and_score_features_at_start_are_balanced():
    # On the empty board every player has score 0 ⇒ tied for rank 1.
    game = BlokusGame()
    feats = rf.extract_rich_features(game.board, Player.RED)
    assert math.isclose(feats["rank_so_far"], 1.0)  # 1st of 4 ⇒ (4-1)/3 = 1.0
    assert math.isclose(feats["score_margin_vs_leader"], 0.0)


def test_score_margin_reflects_lead():
    # Give RED a strong lead by playing several RED moves directly.
    random.seed(0)
    np.random.seed(0)
    game = BlokusGame()
    # Play one full round so all players have placed, then a few extra RED-ish moves.
    for _ in range(12):
        p = game.get_current_player()
        moves = game.get_legal_moves(p)
        if not moves:
            game.board._update_current_player()
            continue
        game.make_move(moves[0], p)
    red_cells = int(np.count_nonzero(game.board.grid == Player.RED.value))
    feats = rf.extract_rich_features(game.board, Player.RED)
    # rank_so_far is in [0,1]; score margins are bounded by tanh.
    assert -1.0 <= feats["score_margin_vs_leader"] <= 1.0
    assert -1.0 <= feats["score_margin_vs_next_player"] <= 1.0
    assert red_cells >= 0


def test_feature_cache_reduces_enumeration():
    game = _play(14, seed=5)

    class CountingGen:
        def __init__(self):
            self.calls = 0
            from engine.move_generator import LegalMoveGenerator
            self._gen = LegalMoveGenerator()

        def get_legal_moves(self, board, player):
            self.calls += 1
            return self._gen.get_legal_moves(board, player)

    cache = rf.FeatureCache()
    cache.move_generator = CountingGen()
    rf.extract_rich_features(game.board, Player.RED, cache=cache)
    # 4 players enumerated at most once each (focal + 3 opponents + leader, but
    # leader is one of the already-cached players).
    assert cache.move_generator.calls <= 4


def test_phase_thresholds():
    game = BlokusGame()
    assert rf.get_phase(game.board) == "early"
    # Fill ~30% of the board ⇒ mid.
    game.board.grid[:6, :] = 1  # 120/400 = 0.30
    assert rf.get_phase(game.board) == "mid"
    game.board.grid[:12, :] = 1  # 240/400 = 0.60
    assert rf.get_phase(game.board) == "late"
