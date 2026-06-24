"""Durable per-game trajectory storage for temporal-difference learning.

Where the legacy regression pipeline stores isolated fixed-ply snapshots in
``data/champion_snapshots.csv`` (and keeps doing so, untouched), TD learning
needs *ordered transitions*: for each player, the sequence of ``(state,
next_state, reward, terminal)`` tuples that lets a TD(0) update reconstruct
``error = reward + γ·V(s')  − V(s)``.

This module owns the on-disk schema (``data/td_trajectories.csv``) and the
read/append/validation helpers. It is deliberately backwards-compatible and
additive — it never touches the snapshot CSV.

Row schema
----------
Bookkeeping columns (see :data:`TRAJECTORY_META_COLUMNS`) plus two feature
blocks:

* ``f_<name>``  — current-state rich features (``rich_blokus_v1``).
* ``nf_<name>`` — next-state rich features (zeros + ``terminal=1`` on the final
  transition of a player's trajectory).

Feature column names are derived from
:data:`training.rich_features.RICH_FEATURE_NAMES`, so the feature-set version is
implicitly pinned by the column layout and recorded explicitly in
``feature_set_version``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from training import REPO_ROOT
from training.rich_features import FEATURE_SET_VERSION, RICH_FEATURE_NAMES

DEFAULT_TRAJECTORY_CSV = REPO_ROOT / "data" / "td_trajectories.csv"

# Per-row bookkeeping columns (everything that is not a feature value).
TRAJECTORY_META_COLUMNS: List[str] = [
    "run_id",
    "game_id",
    "seed",
    "ply",
    "player_id",
    "phase",
    "next_phase",
    "board_occupancy",
    "current_player",
    "reward",
    "terminal",
    "final_rank",
    "final_score",
    "score_margin_to_winner",
    "score_margin_to_next",
    "score_margin_over_last",
    "winner_id",
    "won_game",
    "top_2_finish",
    "agent_name",
    "agent_version",
    "feature_set_version",
    "created_at",
]

# Feature column prefixes.
STATE_PREFIX = "f_"
NEXT_PREFIX = "nf_"

STATE_FEATURE_COLUMNS: List[str] = [f"{STATE_PREFIX}{n}" for n in RICH_FEATURE_NAMES]
NEXT_FEATURE_COLUMNS: List[str] = [f"{NEXT_PREFIX}{n}" for n in RICH_FEATURE_NAMES]

TRAJECTORY_COLUMNS: List[str] = (
    TRAJECTORY_META_COLUMNS + STATE_FEATURE_COLUMNS + NEXT_FEATURE_COLUMNS
)


@dataclass
class TrajectoryRow:
    """One TD transition for a single player at a single decision point."""

    run_id: str
    game_id: str
    seed: int
    ply: int
    player_id: int
    phase: str
    board_occupancy: float
    current_player: int
    state_features: Dict[str, float]
    next_state_features: Dict[str, float]
    reward: float
    terminal: bool
    final_rank: int
    final_score: int
    score_margin_to_winner: float
    score_margin_to_next: float
    score_margin_over_last: float
    winner_id: Optional[int]
    won_game: bool
    top_2_finish: bool
    agent_name: str
    agent_version: str
    created_at: str
    feature_set_version: str = FEATURE_SET_VERSION
    # Phase of the *next* state (the bootstrap target's phase). Stored explicitly
    # so TD updates can evaluate V(s_{t+1}) with the correct phase weights even
    # when a transition crosses a phase boundary. Empty string means "unknown";
    # the trainer then falls back to the current phase.
    next_phase: str = ""

    def to_csv_dict(self) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "run_id": self.run_id,
            "game_id": self.game_id,
            "seed": int(self.seed),
            "ply": int(self.ply),
            "player_id": int(self.player_id),
            "phase": self.phase,
            "next_phase": self.next_phase or self.phase,
            "board_occupancy": float(self.board_occupancy),
            "current_player": int(self.current_player),
            "reward": float(self.reward),
            "terminal": int(bool(self.terminal)),
            "final_rank": int(self.final_rank),
            "final_score": int(self.final_score),
            "score_margin_to_winner": float(self.score_margin_to_winner),
            "score_margin_to_next": float(self.score_margin_to_next),
            "score_margin_over_last": float(self.score_margin_over_last),
            "winner_id": "" if self.winner_id is None else int(self.winner_id),
            "won_game": int(bool(self.won_game)),
            "top_2_finish": int(bool(self.top_2_finish)),
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "feature_set_version": self.feature_set_version,
            "created_at": self.created_at,
        }
        for name in RICH_FEATURE_NAMES:
            row[f"{STATE_PREFIX}{name}"] = float(self.state_features.get(name, 0.0))
            row[f"{NEXT_PREFIX}{name}"] = float(self.next_state_features.get(name, 0.0))
        return row


def append_trajectories(
    rows: Iterable[TrajectoryRow],
    path: Path | str = DEFAULT_TRAJECTORY_CSV,
) -> int:
    """Append trajectory rows to ``path`` (creating it + header if needed).

    Returns the number of rows written. The header is written exactly once; on an
    existing file we trust the prior header rather than rewriting it.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    written = 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRAJECTORY_COLUMNS)
        if write_header:
            writer.writeheader()
        for r in rows:
            writer.writerow(r.to_csv_dict())
            written += 1
    return written


def load_trajectories(path: Path | str = DEFAULT_TRAJECTORY_CSV) -> List[Dict[str, Any]]:
    """Load all trajectory rows as plain dicts (numeric fields coerced).

    Rows are returned in file order; callers that need canonical ordering should
    use :func:`sort_trajectories`.
    """
    path = Path(path)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            out.append(_coerce_row(raw))
    return out


def sort_trajectories(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return rows ordered by ``(game_id, player_id, ply)`` — TD-update order."""
    return sorted(
        rows,
        key=lambda r: (str(r.get("game_id", "")), int(r.get("player_id", 0)), int(r.get("ply", 0))),
    )


def _coerce_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(raw)
    int_cols = ("seed", "ply", "player_id", "current_player", "terminal",
                "final_rank", "final_score", "won_game", "top_2_finish")
    float_cols = ("board_occupancy", "reward", "score_margin_to_winner",
                  "score_margin_to_next", "score_margin_over_last")
    for c in int_cols:
        if c in out and out[c] not in (None, ""):
            out[c] = int(float(out[c]))
    for c in float_cols:
        if c in out and out[c] not in (None, ""):
            out[c] = float(out[c])
    wid = out.get("winner_id", "")
    out["winner_id"] = None if wid in (None, "") else int(float(wid))
    for c in TRAJECTORY_COLUMNS:
        if c.startswith(STATE_PREFIX) or c.startswith(NEXT_PREFIX):
            if c in out and out[c] not in (None, ""):
                out[c] = float(out[c])
    return out


def state_vector(row: Dict[str, Any]) -> List[float]:
    """Extract the ordered current-state feature vector from a loaded row."""
    return [float(row.get(f"{STATE_PREFIX}{n}", 0.0)) for n in RICH_FEATURE_NAMES]


def next_state_vector(row: Dict[str, Any]) -> List[float]:
    """Extract the ordered next-state feature vector from a loaded row."""
    return [float(row.get(f"{NEXT_PREFIX}{n}", 0.0)) for n in RICH_FEATURE_NAMES]


_VALID_PHASES = ("early", "mid", "late")


def annotate_next_phase(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fill in each row's ``next_phase`` (the phase of its bootstrap target).

    Backwards-compatible: trajectory CSVs written before the ``next_phase`` column
    existed have no value, so we reconstruct it from the trajectory structure.
    For a non-terminal transition the next state *is* the player's following
    decision point, so ``next_phase`` = that following row's ``phase``. Terminal
    transitions bootstrap from the terminal label (not a value estimate), so their
    ``next_phase`` is left as the row's own phase — it is never consumed.

    The input is assumed sorted by ``(game_id, player_id, ply)`` (use
    :func:`sort_trajectories` first). Rows already carrying a valid ``next_phase``
    are left untouched, so freshly-collected data is a no-op pass.

    Returns the same list (mutated in place) for chaining.
    """
    n = len(rows)
    for i, row in enumerate(rows):
        existing = str(row.get("next_phase") or "").strip()
        if existing in _VALID_PHASES:
            continue
        cur_phase = str(row.get("phase") or "early")
        if int(row.get("terminal", 0)):
            row["next_phase"] = cur_phase
            continue
        nxt = rows[i + 1] if i + 1 < n else None
        same_trajectory = (
            nxt is not None
            and str(nxt.get("game_id", "")) == str(row.get("game_id", ""))
            and int(nxt.get("player_id", -1)) == int(row.get("player_id", -2))
        )
        if same_trajectory:
            cand = str(nxt.get("phase") or cur_phase)
            row["next_phase"] = cand if cand in _VALID_PHASES else cur_phase
        else:
            # No recoverable successor row (e.g. truncated data): fall back to the
            # current phase, reproducing the pre-fix single-phase behaviour.
            row["next_phase"] = cur_phase
    return list(rows)
