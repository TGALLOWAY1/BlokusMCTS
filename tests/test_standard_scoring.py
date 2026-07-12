"""
Standard Blokus scoring: the +5 monomino-played-last bonus and the
standard-by-default scoring mode (agent-strength rescue decision D-002).
"""

import pytest

from analytics.tournament.arena_runner import RunConfig
from engine.board import MONOMINO_PIECE_ID, Board, Player, Position
from engine.game import (
    SCORING_MODE_HOUSE,
    SCORING_MODE_STANDARD,
    BlokusGame,
)


def _mark_all_pieces_used(board: Board, player: Player, last_piece_id: int) -> None:
    """Simulate a finished inventory: all 21 pieces used, given piece last."""
    for piece_id in range(1, 22):
        board.player_pieces_used[player].add(piece_id)
    board.player_last_piece[player] = last_piece_id


class TestMonominoLastBonus:
    def test_all_pieces_with_monomino_last_gets_plus_twenty(self):
        board = Board()
        board.place_piece([Position(0, 0)], Player.RED, MONOMINO_PIECE_ID)
        _mark_all_pieces_used(board, Player.RED, MONOMINO_PIECE_ID)
        # 1 covered square + 15 all-pieces + 5 monomino-last
        assert board.get_score(Player.RED) == 1 + 15 + 5

    def test_all_pieces_with_other_piece_last_gets_plus_fifteen(self):
        board = Board()
        board.place_piece([Position(0, 0), Position(0, 1)], Player.RED, 2)
        _mark_all_pieces_used(board, Player.RED, last_piece_id=2)
        assert board.get_score(Player.RED) == 2 + 15

    def test_monomino_last_without_all_pieces_gets_no_bonus(self):
        board = Board()
        board.place_piece([Position(0, 0)], Player.RED, MONOMINO_PIECE_ID)
        assert board.player_last_piece[Player.RED] == MONOMINO_PIECE_ID
        assert board.get_score(Player.RED) == 1

    def test_no_pieces_played_scores_zero(self):
        board = Board()
        assert board.player_last_piece[Player.RED] is None
        assert board.get_score(Player.RED) == 0

    def test_last_piece_tracks_most_recent_placement(self):
        board = Board()
        board.place_piece([Position(0, 0)], Player.RED, MONOMINO_PIECE_ID)
        board.place_piece([Position(1, 1), Position(1, 2)], Player.RED, 2)
        assert board.player_last_piece[Player.RED] == 2
        # Other players unaffected
        assert board.player_last_piece[Player.BLUE] is None

    def test_board_copy_preserves_last_piece(self):
        board = Board()
        board.place_piece([Position(0, 0)], Player.RED, MONOMINO_PIECE_ID)
        clone = board.copy()
        assert clone.player_last_piece[Player.RED] == MONOMINO_PIECE_ID
        # Copies must be independent (corner-adjacent continuation, legal)
        assert clone.place_piece([Position(1, 1), Position(1, 2)], Player.RED, 2)
        assert clone.player_last_piece[Player.RED] == 2
        assert board.player_last_piece[Player.RED] == MONOMINO_PIECE_ID

    def test_bonus_applies_in_both_scoring_modes(self):
        # The monomino bonus is part of the BASE score, so house mode
        # (standard + positional bonuses) includes it too.
        for mode in (SCORING_MODE_STANDARD, SCORING_MODE_HOUSE):
            game = BlokusGame(scoring_mode=mode, enable_telemetry=False)
            board = game.board
            board.place_piece([Position(0, 0)], Player.RED, MONOMINO_PIECE_ID)
            _mark_all_pieces_used(board, Player.RED, MONOMINO_PIECE_ID)
            without_bonus = board.get_score(Player.RED) - 5
            board.player_last_piece[Player.RED] = 2
            assert board.get_score(Player.RED) == without_bonus


class TestScoringModeDefaults:
    def test_blokus_game_defaults_to_standard(self):
        assert BlokusGame(enable_telemetry=False).scoring_mode == SCORING_MODE_STANDARD

    def test_run_config_defaults_to_standard(self):
        config = RunConfig.from_dict(_minimal_run_config_dict())
        assert config.scoring_mode == SCORING_MODE_STANDARD

    def test_run_config_round_trips_scoring_mode(self):
        raw = _minimal_run_config_dict()
        raw["scoring_mode"] = SCORING_MODE_HOUSE
        config = RunConfig.from_dict(raw)
        assert config.scoring_mode == SCORING_MODE_HOUSE
        assert RunConfig.from_dict(config.to_dict()).scoring_mode == SCORING_MODE_HOUSE

    def test_run_config_rejects_invalid_scoring_mode(self):
        raw = _minimal_run_config_dict()
        raw["scoring_mode"] = "tournament"
        with pytest.raises(ValueError, match="scoring_mode"):
            RunConfig.from_dict(raw)


def _minimal_run_config_dict() -> dict:
    return {
        "agents": [
            {"name": f"random_{i}", "type": "random", "params": {}}
            for i in range(4)
        ],
        "num_games": 1,
        "seed": 20260620,
    }
