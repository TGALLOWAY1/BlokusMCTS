"""Model-artifact leaf evaluator for MCTS (agent-strength rescue, D-015 gate 3).

Loads a joblib artifact ``{"model", "feature_names", ...}`` (produced by
``training/experiments/value_model.py``) and serves per-player leaf values on
the normalized-final-score scale (final_score / 100). It is a drop-in for the
agent's rich-leaf slot — ``MCTSAgent._evaluate_rich_leaf`` multiplies by the
x100 reward scale, landing values back on score points.

Per-board caching: ``evaluate`` is called once per player at a leaf, but one
feature pass covers all four players; results are cached keyed on the FULL
authoritative state (per-player bitmasks + piece inventories + current
player) — the union occupancy mask alone can collide across different
ownership/inventories.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from engine.board import Board, Player
from engine.move_generator import get_shared_generator


class ValueModelLeafEvaluator:
    """Duck-type of RichLeafEvaluator.evaluate backed by a sklearn artifact."""

    def __init__(self, artifact_path: str) -> None:
        # Lazy imports keep mcts import-time free of training/joblib deps.
        import joblib

        from training.rich_features import RICH_FEATURE_NAMES

        artifact = joblib.load(artifact_path)
        self.artifact_path = str(artifact_path)
        self.model = artifact["model"]
        self.feature_names: List[str] = list(artifact["feature_names"])
        self.target: str = str(artifact.get("target", "final_score / 100"))
        unknown = [n for n in self.feature_names if n not in RICH_FEATURE_NAMES]
        if unknown:
            raise ValueError(
                f"Artifact {artifact_path} uses unknown feature names: {unknown[:5]}"
            )
        self._move_generator = get_shared_generator()
        self._cache_key: Optional[tuple] = None
        self._cache: Dict[int, float] = {}
        self.available = True

    @classmethod
    def from_fitted(cls, model, feature_names: List[str]) -> "ValueModelLeafEvaluator":
        """Build directly from an in-memory fitted model (probes/tests)."""
        instance = cls.__new__(cls)
        instance.artifact_path = "<in-memory>"
        instance.model = model
        instance.feature_names = list(feature_names)
        instance.target = "final_score / 100"
        instance._move_generator = get_shared_generator()
        instance._cache_key = None
        instance._cache = {}
        instance.available = True
        return instance

    def _board_key(self, board: Board) -> tuple:
        return (
            tuple(board.player_bits[p] for p in Player),
            tuple(tuple(sorted(board.player_pieces_used[p])) for p in Player),
            board.current_player.value,
        )

    def evaluate(self, board: Board, player: Player) -> float:
        """Return the model's normalized final-score prediction for *player*."""
        from training.rich_features import FeatureCache, extract_rich_features

        key = self._board_key(board)
        if key != self._cache_key:
            cache = FeatureCache(move_generator=self._move_generator)
            rows = []
            players = list(Player)
            for p in players:
                feats = extract_rich_features(board, p, cache=cache)
                rows.append([float(feats.get(n, 0.0)) for n in self.feature_names])
            preds = self.model.predict(np.asarray(rows, dtype=float))
            self._cache = {p.value: float(v) for p, v in zip(players, preds)}
            self._cache_key = key
        return self._cache[player.value]
