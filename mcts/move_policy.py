"""Learned move policy — a compact prior over legal moves for PUCT-guided MCTS.

Motivation
----------
The canonical MCTS agent scores moves with a *fixed*-weight domain heuristic
(:func:`mcts.move_heuristic.compute_move_heuristic`, weights ``[1, 2, 0.5, 1]``)
in two hot places: the ``greedy_sample`` rollout policy and heuristic move
ordering. There is no *learned* signal shaping the tree search itself — which is
exactly why deeper search stopped converting into strength (see ``AUDIT_REPORT.md``
§6.4: "the highest-leverage next feature is a stronger rollout/move-ordering policy
learned from MCTS visit counts").

This module learns that policy. It is a compact log-linear (softmax) model over
the same four cheap move features plus a per-piece bias::

    logit(move) = w · phi(move) + piece_bias[piece_id]
    P(move)     = softmax(logit / temperature)   over the legal moves at a state

Trained by distilling the MCTS **root visit distribution** collected during
self-play (``training/policy_selfplay.py``) — the search's own improved policy is
the supervised target (AlphaZero / Expert-Iteration style). The learned ``P`` is
fed back into the agent as:

* the **PUCT prior** ``P(s, a)`` in tree selection, and
* the rollout / move-ordering score (replacing the fixed heuristic).

The model is deliberately tiny (4 weights + 21 piece biases): cheap enough to run
per-node in the search, and it degrades gracefully — an untrained default
reproduces the existing fixed heuristic exactly, so enabling the prior without
trained weights never changes behaviour.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from engine.board import Board, Player
from engine.move_generator import LegalMoveGenerator, Move
from mcts.move_heuristic import MOVE_FEATURE_NAMES, compute_move_features

# Artifact / feature-set version. Bump if MOVE_FEATURE_NAMES changes.
POLICY_FEATURE_SET_VERSION = "move_policy_v1"

NUM_MOVE_FEATURES = len(MOVE_FEATURE_NAMES)  # 4

# Fixed weights that reproduce compute_move_heuristic's raw score exactly, so the
# default (untrained) policy ranks moves identically to the current heuristic.
DEFAULT_FEATURE_WEIGHTS: Tuple[float, ...] = (1.0, 2.0, 0.5, 1.0)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@dataclass
class MovePolicy:
    """Log-linear softmax policy over legal moves.

    ``feature_weights`` weights the four :func:`compute_move_features` values;
    ``piece_bias`` is a per-``piece_id`` additive logit (captures "which piece is
    good to play now", the knowledge the progressive-history table approximates).
    ``temperature`` sharpens (<1) or flattens (>1) the softmax used for priors.
    """

    feature_weights: np.ndarray
    piece_bias: Dict[int, float] = field(default_factory=dict)
    temperature: float = 1.0

    def __post_init__(self) -> None:
        self.feature_weights = np.asarray(self.feature_weights, dtype=float).reshape(-1)
        if self.feature_weights.shape[0] != NUM_MOVE_FEATURES:
            raise ValueError(
                f"feature_weights must have length {NUM_MOVE_FEATURES}, "
                f"got {self.feature_weights.shape[0]}"
            )
        self.piece_bias = {int(k): float(v) for k, v in dict(self.piece_bias).items()}
        self.temperature = float(self.temperature) if self.temperature > 1e-6 else 1.0

    # -- scoring -----------------------------------------------------------

    def logit_from_features(self, feats: Sequence[float], piece_id: int) -> float:
        """Raw (pre-softmax) score for one move given its precomputed features."""
        return float(np.dot(self.feature_weights, feats)) + self.piece_bias.get(int(piece_id), 0.0)

    def score_move(
        self, board: Board, player: Player, move: Move, move_generator: LegalMoveGenerator
    ) -> float:
        """Logit for a single move (higher = better). Monotone rollout/ordering score."""
        feats = compute_move_features(board, player, move, move_generator)
        return self.logit_from_features(feats, move.piece_id)

    def logits_for_moves(
        self,
        board: Board,
        player: Player,
        moves: Sequence[Move],
        move_generator: LegalMoveGenerator,
    ) -> np.ndarray:
        """Vector of logits for a list of moves (``None`` / pass moves score ``-inf``)."""
        out = np.empty(len(moves), dtype=float)
        for i, m in enumerate(moves):
            if m is None:
                out[i] = -math.inf
                continue
            out[i] = self.score_move(board, player, m, move_generator)
        return out

    def priors_from_logits(self, logits: np.ndarray) -> np.ndarray:
        """Softmax(logits / temperature), robust to ``-inf`` (pass) and overflow."""
        z = np.asarray(logits, dtype=float) / self.temperature
        finite = np.isfinite(z)
        if not finite.any():
            # Degenerate (all-pass): uniform over the moves.
            return np.full(z.shape[0], 1.0 / max(z.shape[0], 1))
        m = z[finite].max()
        exp = np.where(finite, np.exp(z - m), 0.0)
        total = exp.sum()
        if total <= 0:
            return np.full(z.shape[0], 1.0 / max(z.shape[0], 1))
        return exp / total

    def priors(
        self,
        board: Board,
        player: Player,
        moves: Sequence[Move],
        move_generator: LegalMoveGenerator,
    ) -> np.ndarray:
        """Prior probability distribution ``P(a | s)`` over the given legal moves."""
        return self.priors_from_logits(self.logits_for_moves(board, player, moves, move_generator))

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_set_version": POLICY_FEATURE_SET_VERSION,
            "feature_names": list(MOVE_FEATURE_NAMES),
            "feature_weights": [float(w) for w in self.feature_weights],
            "piece_bias": {str(k): float(v) for k, v in self.piece_bias.items()},
            "temperature": float(self.temperature),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MovePolicy":
        weights = data.get("feature_weights")
        if weights is None:
            raise ValueError("policy dict missing 'feature_weights'")
        piece_bias = data.get("piece_bias") or {}
        return cls(
            feature_weights=np.asarray(weights, dtype=float),
            piece_bias={int(k): float(v) for k, v in piece_bias.items()},
            temperature=float(data.get("temperature", 1.0)),
        )


def default_move_policy(temperature: float = 1.0) -> MovePolicy:
    """Untrained policy whose ranking is identical to the fixed move heuristic."""
    return MovePolicy(
        feature_weights=np.array(DEFAULT_FEATURE_WEIGHTS, dtype=float),
        piece_bias={},
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# Training (visit-count distillation)
# ---------------------------------------------------------------------------


@dataclass
class PolicySample:
    """One training example: a decision point with its search-visit target.

    ``features`` is ``(n_moves, 4)``; ``piece_ids`` is ``(n_moves,)``;
    ``target`` is a probability distribution ``(n_moves,)`` (visit counts
    normalised) — the MCTS-improved policy at this state.
    """

    features: np.ndarray
    piece_ids: np.ndarray
    target: np.ndarray


@dataclass
class PolicyTrainConfig:
    learning_rate: float = 0.20
    epochs: int = 40
    l2: float = 1e-4
    temperature: float = 1.0
    seed: int = 12345
    # Piece ids present in Blokus (1..21). Fixed so the bias vector is stable.
    piece_ids: Tuple[int, ...] = tuple(range(1, 22))


@dataclass
class PolicyTrainResult:
    policy: MovePolicy
    loss: float
    loss_history: List[float]
    top1_agreement: float
    n_samples: int


def _softmax(z: np.ndarray) -> np.ndarray:
    m = z.max()
    e = np.exp(z - m)
    return e / e.sum()


def train_move_policy(
    samples: List[PolicySample], config: Optional[PolicyTrainConfig] = None
) -> PolicyTrainResult:
    """Fit a :class:`MovePolicy` by distilling visit-count targets (softmax CE).

    Minimises per-decision cross-entropy between the model's softmax over the
    legal moves and the (normalised) MCTS visit distribution, via full-batch
    gradient descent with L2 regularisation. Pure / deterministic (no I/O).
    """
    cfg = config or PolicyTrainConfig()
    piece_index = {int(p): i for i, p in enumerate(cfg.piece_ids)}
    n_pieces = len(cfg.piece_ids)

    # Seed feature weights at the fixed-heuristic prior; biases at zero.
    w = np.array(DEFAULT_FEATURE_WEIGHTS, dtype=float)
    b = np.zeros(n_pieces, dtype=float)

    usable = [s for s in samples if s.features.shape[0] >= 2 and np.isfinite(s.target).all()]
    loss_history: List[float] = []

    for _epoch in range(cfg.epochs):
        gw = np.zeros_like(w)
        gb = np.zeros_like(b)
        epoch_loss = 0.0
        for s in usable:
            feats = s.features  # (n,4)
            pids = s.piece_ids.astype(int)  # (n,)
            t = s.target  # (n,)
            bias_vec = np.array([b[piece_index[p]] if p in piece_index else 0.0 for p in pids])
            z = (feats @ w + bias_vec)  # (n,)
            q = _softmax(z)
            # Cross-entropy loss (target is a distribution).
            epoch_loss += float(-(t * np.log(np.clip(q, 1e-12, 1.0))).sum())
            # dL/dz = q - t
            dz = q - t  # (n,)
            gw += feats.T @ dz
            for j, p in enumerate(pids):
                if p in piece_index:
                    gb[piece_index[p]] += dz[j]
        n = max(len(usable), 1)
        gw = gw / n + cfg.l2 * w
        gb = gb / n + cfg.l2 * b
        w -= cfg.learning_rate * gw
        b -= cfg.learning_rate * gb
        loss_history.append(epoch_loss / n)

    piece_bias = {int(cfg.piece_ids[i]): float(b[i]) for i in range(n_pieces) if abs(b[i]) > 1e-9}
    policy = MovePolicy(feature_weights=w, piece_bias=piece_bias, temperature=cfg.temperature)

    # Diagnostic: how often the model's argmax matches the visit argmax.
    agree = 0
    for s in usable:
        bias_vec = np.array(
            [piece_bias.get(int(p), 0.0) for p in s.piece_ids.astype(int)]
        )
        z = s.features @ w + bias_vec
        if int(np.argmax(z)) == int(np.argmax(s.target)):
            agree += 1
    top1 = agree / max(len(usable), 1)

    return PolicyTrainResult(
        policy=policy,
        loss=loss_history[-1] if loss_history else 0.0,
        loss_history=loss_history,
        top1_agreement=top1,
        n_samples=len(usable),
    )
