"""Rich leaf evaluator — the 45-feature TD value model at MCTS leaves.

The live agent's :class:`~mcts.state_evaluator.BlokusStateEvaluator` consumes
only the **8** SE features projected out of the TD model, discarding the 37 rich
features (and with them the single most predictive signals —
``score_margin_vs_leader`` and ``rank_so_far``; see
``docs/RICH_FEATURE_ANALYSIS.md``). This module lets the *full* TD-learned linear
value reach search by evaluating it at MCTS **leaves** — where evaluation is
called once per simulation, not once per rollout step.

The TD artifact (``training/state/td_evaluator_weights.json``) persists
``rich_phase_weights``: a per-phase ``{"weights": {name: w}, "bias": b}`` map over
the 45 :data:`~training.rich_features.RICH_FEATURE_NAMES`. The evaluator selects
the phase by board occupancy (the same early/mid/late thresholds the rest of the
stack uses) and returns ``Σ w_i·f_i + bias`` — a value in roughly ``[-1, 1]``.

Cost control (the hard constraint): full 45-feature extraction enumerates legal
moves for **all four** players (~15-25 ms/leaf), so a *feature subset* selects a
cost tier (see :data:`~training.rich_features.LEAF_FEATURE_SUBSETS`). The default
``"score"`` subset drops every legal-move enumeration and the territory BFS,
costing ~0.8 ms/leaf while keeping the highest-signal features. Excluded features
are zeroed, so their TD weights simply drop out of the dot product.

Graceful fallback: when the artifact is missing or carries no trained rich
weights, :meth:`RichLeafEvaluator.evaluate` falls back to the 8-feature
:class:`BlokusStateEvaluator`, and :attr:`available` is ``False``.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Optional

import numpy as np

from engine.board import Board, Player
from engine.move_generator import get_shared_generator

from .state_evaluator import BlokusStateEvaluator

# Default location of the TD artifact holding ``rich_phase_weights``.
DEFAULT_RICH_LEAF_WEIGHTS_PATH = "training/state/td_evaluator_weights.json"

_PHASES = ("early", "mid", "late")


class RichLeafEvaluator:
    """Evaluate an MCTS leaf with the 45-feature TD-learned linear value model.

    Args:
        weights_path: Path to the TD artifact with ``rich_phase_weights``.
        feature_subset: Cost tier — ``"score"`` (default, cheapest),
            ``"no_opp_mobility"``, or ``"full"`` (see
            :data:`training.rich_features.LEAF_FEATURE_SUBSETS`).
        fallback_evaluator: 8-feature evaluator used when rich weights are
            unavailable (defaults to a fresh :class:`BlokusStateEvaluator`).
    """

    def __init__(
        self,
        weights_path: Optional[str] = DEFAULT_RICH_LEAF_WEIGHTS_PATH,
        *,
        feature_subset: str = "score",
        fallback_evaluator: Optional[BlokusStateEvaluator] = None,
    ) -> None:
        # Imported lazily so the agent module does not hard-depend on the
        # training package at import time.
        from training.rich_features import (
            LEAF_FEATURE_SUBSETS,
            RICH_FEATURE_NAMES,
            FeatureCache,
            extract_leaf_features,
        )

        if feature_subset not in LEAF_FEATURE_SUBSETS:
            raise ValueError(
                f"feature_subset must be one of {sorted(LEAF_FEATURE_SUBSETS)}, "
                f"got '{feature_subset}'"
            )

        self.weights_path = weights_path
        self.feature_subset = feature_subset
        self._rich_feature_names = RICH_FEATURE_NAMES
        self._feature_cache_cls = FeatureCache
        self._extract_leaf_features = extract_leaf_features
        # Share the engine's move generator so per-leaf FeatureCache construction
        # is free (a fresh LegalMoveGenerator costs ~1.8 ms).
        self._move_generator = get_shared_generator()
        self._fallback = fallback_evaluator or BlokusStateEvaluator()

        # Per-phase (weight_vector, bias). weight_vector is ordered to match
        # RICH_FEATURE_NAMES so it dots directly with the extracted vector.
        self._phase_weights: Dict[str, np.ndarray] = {}
        self._phase_bias: Dict[str, float] = {}
        self.available: bool = False
        self.load_error: Optional[str] = None
        self._load_weights()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_weights(self) -> None:
        """Load ``rich_phase_weights`` from the artifact; set ``available``.

        Falls back silently (``available=False``) on any problem — missing file,
        malformed JSON, missing/untrained weights — recording ``load_error``.
        """
        path = self.weights_path
        if not path or not os.path.exists(path):
            self.load_error = f"weights file not found: {path}"
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                artifact = json.load(fh)
        except (OSError, ValueError) as exc:
            self.load_error = f"failed to read weights: {exc}"
            return

        rich = artifact.get("rich_phase_weights")
        if not isinstance(rich, dict):
            self.load_error = "artifact has no 'rich_phase_weights'"
            return

        index = {name: i for i, name in enumerate(self._rich_feature_names)}
        n = len(self._rich_feature_names)
        loaded_any = False
        for phase in _PHASES:
            entry = rich.get(phase)
            if not isinstance(entry, dict):
                continue
            weights_map = entry.get("weights")
            if not isinstance(weights_map, dict):
                continue
            vec = np.zeros(n, dtype=float)
            for name, w in weights_map.items():
                idx = index.get(name)
                if idx is not None:
                    vec[idx] = float(w)
            self._phase_weights[phase] = vec
            self._phase_bias[phase] = float(entry.get("bias", 0.0))
            # A phase counts as usable when it is flagged trained or carries any
            # non-zero weight (older artifacts may omit the "trained" flag).
            if entry.get("trained", True) and (
                np.any(vec != 0.0) or self._phase_bias[phase] != 0.0
            ):
                loaded_any = True

        self.available = loaded_any
        if not loaded_any:
            self.load_error = "no trained rich phase weights found"

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, board: Board, player: Player) -> float:
        """Return the leaf value for *player* from the TD model.

        Phase is selected from board occupancy. When rich weights are
        unavailable, returns the 8-feature ``BlokusStateEvaluator`` score (also
        in a sane range) so callers degrade gracefully.
        """
        if not self.available:
            return self._fallback.evaluate(board, player)

        phase = BlokusStateEvaluator.get_phase(board)
        weights = self._phase_weights.get(phase)
        if weights is None:
            return self._fallback.evaluate(board, player)

        cache = self._feature_cache_cls(move_generator=self._move_generator)
        feats = self._extract_leaf_features(
            board, player, subset=self.feature_subset, cache=cache
        )
        # feats is the full ordered feature dict (zeros outside the subset), so a
        # plain dot over RICH_FEATURE_NAMES applies the subset exactly.
        x = np.fromiter(
            (feats[name] for name in self._rich_feature_names),
            dtype=float,
            count=len(self._rich_feature_names),
        )
        return float(np.dot(weights, x) + self._phase_bias[phase])
