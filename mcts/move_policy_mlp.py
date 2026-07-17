"""move_policy_v2 — shape-aware MLP move policy (Phase 6, D-017 / EXP-011).

Drop-in replacement for :class:`mcts.move_policy.MovePolicy` scoring:
implements the same interface the agent consumes (``score_move``,
``logits_for_moves``, ``priors_from_logits``, ``priors``) but scores each
candidate with a small numpy MLP over :mod:`mcts.move_encoding`
(move_encoding_v1: 9x9 six-channel patch + piece one-hot + scalars, 518
inputs -> hidden tanh -> 1 logit). Trained by teacher visit distillation
(training/experiments/move_scorer_mlp.py); EXP-011: held-out tie-aware
top-1 0.196-0.228 vs 0.140 fixed heuristic, pairwise 0.742-0.744 vs 0.591.

Artifact schema (JSON-safe dict)::

    {"model_type": "mlp_move_policy_v2",
     "encoding_version": "move_encoding_v1",
     "input_dim": 518, "hidden": 64,
     "W1": [[...]], "b1": [...], "W2": [...], "b2": float,
     "temperature": 1.0}

``MCTSAgent`` selects this class automatically when the ``policy_weights``
dict carries ``model_type == "mlp_move_policy_v2"``; legacy dicts still
build the log-linear ``MovePolicy``. Inference is plain numpy (Pyodide-safe).
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Sequence

import numpy as np

from engine.board import Board, Player
from engine.move_generator import LegalMoveGenerator, Move
from mcts.move_encoding import (
    INPUT_DIM,
    MOVE_ENCODING_VERSION,
    EncodingContext,
    encode_move,
)

MODEL_TYPE = "mlp_move_policy_v2"


class MLPMovePolicy:
    """Numpy-MLP move policy over move_encoding_v1 inputs."""

    def __init__(self, W1: np.ndarray, b1: np.ndarray, W2: np.ndarray,
                 b2: float, temperature: float = 1.0) -> None:
        self.W1 = np.asarray(W1, dtype=np.float64)
        self.b1 = np.asarray(b1, dtype=np.float64).reshape(-1)
        self.W2 = np.asarray(W2, dtype=np.float64).reshape(-1)
        self.b2 = float(b2)
        if self.W1.shape[0] != INPUT_DIM:
            raise ValueError(
                f"W1 expects input_dim {self.W1.shape[0]}, encoding gives {INPUT_DIM}")
        if self.W1.shape[1] != self.b1.shape[0] or self.W1.shape[1] != self.W2.shape[0]:
            raise ValueError("inconsistent hidden dimensions in MLP artifact")
        self.temperature = float(temperature) if temperature > 1e-6 else 1.0

    # -- scoring (MovePolicy-compatible interface) --------------------------

    def _logits_from_inputs(self, x: np.ndarray) -> np.ndarray:
        h = np.tanh(x @ self.W1 + self.b1)
        return h @ self.W2 + self.b2

    def score_move(self, board: Board, player: Player, move: Move,
                   move_generator: LegalMoveGenerator) -> float:
        context = EncodingContext(board, player)
        x = encode_move(context, move, move_generator).astype(np.float64)
        return float(self._logits_from_inputs(x[None, :])[0])

    def logits_for_moves(self, board: Board, player: Player,
                         moves: Sequence[Optional[Move]],
                         move_generator: LegalMoveGenerator) -> np.ndarray:
        out = np.full(len(moves), -math.inf, dtype=float)
        real = [(i, m) for i, m in enumerate(moves) if m is not None]
        if not real:
            return out
        context = EncodingContext(board, player)
        x = np.stack([encode_move(context, m, move_generator) for _, m in real]
                     ).astype(np.float64)
        z = self._logits_from_inputs(x)
        for (i, _), zi in zip(real, z):
            out[i] = float(zi)
        return out

    def priors_from_logits(self, logits: np.ndarray) -> np.ndarray:
        z = np.asarray(logits, dtype=float) / self.temperature
        finite = np.isfinite(z)
        if not finite.any():
            return np.full(z.shape[0], 1.0 / max(z.shape[0], 1))
        m = z[finite].max()
        exp = np.where(finite, np.exp(z - m), 0.0)
        total = exp.sum()
        if total <= 0:
            return np.full(z.shape[0], 1.0 / max(z.shape[0], 1))
        return exp / total

    def priors(self, board: Board, player: Player,
               moves: Sequence[Optional[Move]],
               move_generator: LegalMoveGenerator) -> np.ndarray:
        return self.priors_from_logits(
            self.logits_for_moves(board, player, moves, move_generator))

    # -- serialization -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_type": MODEL_TYPE,
            "encoding_version": MOVE_ENCODING_VERSION,
            "input_dim": int(self.W1.shape[0]),
            "hidden": int(self.W1.shape[1]),
            "W1": self.W1.tolist(),
            "b1": self.b1.tolist(),
            "W2": self.W2.tolist(),
            "b2": self.b2,
            "temperature": self.temperature,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MLPMovePolicy":
        if data.get("model_type") != MODEL_TYPE:
            raise ValueError(f"not an {MODEL_TYPE} artifact")
        version = data.get("encoding_version")
        if version != MOVE_ENCODING_VERSION:
            raise ValueError(
                f"artifact encoding {version!r} != runtime {MOVE_ENCODING_VERSION!r}")
        return cls(
            W1=np.asarray(data["W1"], dtype=np.float64),
            b1=np.asarray(data["b1"], dtype=np.float64),
            W2=np.asarray(data["W2"], dtype=np.float64),
            b2=float(data["b2"]),
            temperature=float(data.get("temperature", 1.0)),
        )


def is_mlp_policy_dict(data: Dict[str, Any]) -> bool:
    """True when a policy_weights dict is an MLP-policy artifact."""
    return isinstance(data, dict) and data.get("model_type") == MODEL_TYPE
