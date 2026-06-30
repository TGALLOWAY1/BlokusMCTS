"""Atomic, durable persistence for the training pipeline.

Every other module goes through here so file-format details and the durability
contract live in one place. The contract:

* **Atomic writes** — JSON is written to a sibling ``.tmp`` file then
  ``os.replace``-d into place, so a crash (or a killed CI job) never leaves a
  half-written ``latest.json``/``champion.json``. The previous file survives.
* **Append-only history** — ``history.jsonl`` is opened in append mode and
  ``fsync``-ed, so per-generation progress is never lost mid-run.
* **Reconstruct-from-disk** — ``load_latest``/``load_champion`` return a complete
  default when nothing exists yet, so a cold start and a resume take the same path.
"""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from training import TrainingPaths


# ---------------------------------------------------------------------------
# Low-level atomic primitives
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, obj: Any) -> None:
    """Write ``obj`` as pretty JSON to ``path`` atomically (tmp + os.replace).

    The temp file is fsync-ed before the rename so the bytes are durable, then
    the directory entry swap is itself atomic on POSIX. A crash leaves either the
    old file or the new file — never a truncated one.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(obj, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def read_json(path: Path) -> Any:
    """Read JSON from ``path`` (caller handles non-existence)."""
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    """Append a single JSON record as one line, flushed and fsync-ed.

    Append is the durable choice for per-generation history: each line is
    self-contained, so an interrupted run keeps every completed generation.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[Dict[str, Any]]:
    """Read all records from a JSONL file (skip blank/malformed lines)."""
    path = Path(path)
    records: list[Dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


# ---------------------------------------------------------------------------
# Default state documents
# ---------------------------------------------------------------------------

# Human-strength target (Elo). Kept here so a cold-start ``latest.json`` already
# carries the target the reports/estimator read back.
DEFAULT_HUMAN_TARGET_ELO = 1700

SCHEMA_VERSION = 1

# ``history.jsonl`` carries two shapes of row: the legacy self-play *generation*
# record (champion-loop era) and the multi-agent *approach-comparison* record.
# Stamping each row with a schema version + kind lets diagnostics validate only
# comparable rows together instead of flagging the older shape as "malformed" or
# "missing result-like fields" (audit follow-up #3). Older rows predate the stamp
# and are classified structurally by :func:`classify_history_row`.
HISTORY_SCHEMA_VERSION = 2
HISTORY_KIND_APPROACH = "approach_comparison"
HISTORY_KIND_LEGACY = "legacy_generation"
HISTORY_KIND_MALFORMED = "malformed"
HISTORY_KIND_UNKNOWN = "unknown"


def classify_history_row(row: Dict[str, Any]) -> str:
    """Classify a ``history.jsonl`` row by schema kind.

    Prefers the explicit ``kind`` stamp (rows written at or after
    ``HISTORY_SCHEMA_VERSION`` 2). Falls back to structural inference for rows
    written before the stamp existed:

    * ``approach_comparison`` — carries approach-comparison result fields
      (``approaches``/``candidates_created``/``winner``);
    * ``legacy_generation`` — the champion-loop self-play record (``challengers``);
    * ``malformed`` — a row the reader could not parse (``_malformed`` marker);
    * ``unknown`` — parseable but matching neither shape.
    """
    if not isinstance(row, dict):
        return HISTORY_KIND_UNKNOWN
    if row.get("_malformed"):
        return HISTORY_KIND_MALFORMED
    kind = row.get("kind")
    if kind in (HISTORY_KIND_APPROACH, HISTORY_KIND_LEGACY):
        return kind
    if any(k in row for k in ("approaches", "candidates_created", "winner")):
        return HISTORY_KIND_APPROACH
    if "challengers" in row:
        return HISTORY_KIND_LEGACY
    return HISTORY_KIND_UNKNOWN


def default_latest_state() -> Dict[str, Any]:
    """A complete ``latest.json`` for a brand-new pipeline.

    Keeps champion_loop-compatible keys (``trueskill_ratings``, ``checkpoints``,
    ``champion_params``, ``last_refit_generation``, ``total_snapshot_rows``) so
    the reused ``build_tracker`` / ``select_challengers`` / ``refit`` helpers work
    unchanged against this document.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": None,
        "generation": 0,
        "total_games": 0,
        "games_today": 0,
        "days_trained": 0,
        "champion": {
            "name": "champion",
            "version": "gen0",
            "config_ref": "state/champion.json",
        },
        "elo": 1200.0,
        "trueskill_mu": 25.0,
        "trueskill_sigma": 25.0 / 3.0,
        "trueskill_ratings": {},
        "champion_params": None,  # filled on cold start from the seed champion
        "candidate_params": None,
        "last_refit_generation": -1,
        "total_snapshot_rows": 0,
        "checkpoints": [],
        "human_target_elo": DEFAULT_HUMAN_TARGET_ELO,
        "estimated_games_to_target": None,
        "estimated_days_to_target": None,
        "estimate_confidence": "none",
        "last_promoted_generation": None,
        "last_eval": None,  # latest candidate-eval summary (baselines for the email)
        "last_error": None,
        "updated_at": _utc_now_iso(),
    }


def default_champion_state() -> Dict[str, Any]:
    """A placeholder ``champion.json`` (params filled in by the cold-start seed)."""
    return {
        "name": "champion",
        "version": "gen0",
        "promoted_at": None,
        "rating": {
            "elo": 1200.0,
            "trueskill_mu": 25.0,
            "trueskill_sigma": 25.0 / 3.0,
            "conservative": 0.0,
        },
        "params": None,
        "flat_config": None,
        "lineage": [],
    }


# ---------------------------------------------------------------------------
# High-level load / save
# ---------------------------------------------------------------------------

def load_latest(paths: TrainingPaths) -> Dict[str, Any]:
    """Load ``latest.json`` or return a fresh default (cold start == resume path)."""
    if paths.latest_json.exists():
        state = read_json(paths.latest_json)
        # Forward-compatible: backfill any keys added since this file was written.
        defaults = default_latest_state()
        for key, value in defaults.items():
            state.setdefault(key, value)
        return state
    return default_latest_state()


def save_latest(paths: TrainingPaths, state: Dict[str, Any]) -> None:
    """Persist ``latest.json`` atomically, stamping ``updated_at``."""
    state = dict(state)
    state["updated_at"] = _utc_now_iso()
    atomic_write_json(paths.latest_json, state)


def load_champion(paths: TrainingPaths) -> Dict[str, Any]:
    """Load ``champion.json`` or return a fresh default."""
    if paths.champion_json.exists():
        return read_json(paths.champion_json)
    return default_champion_state()


def save_champion(paths: TrainingPaths, champion: Dict[str, Any]) -> None:
    """Persist ``champion.json`` atomically."""
    atomic_write_json(paths.champion_json, champion)


def write_checkpoint(paths: TrainingPaths, generation: int, checkpoint: Dict[str, Any]) -> Path:
    """Write a per-promotion champion checkpoint, returning its path.

    Checkpoints are an immutable historical record (never deleted) and double as
    the "historical champions" pool for the evaluation battery.
    """
    paths.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    dest = paths.checkpoints_dir / f"champion_gen{generation}.json"
    atomic_write_json(dest, copy.deepcopy(checkpoint))
    return dest


def list_checkpoints(paths: TrainingPaths) -> list[Dict[str, Any]]:
    """Return all champion checkpoints, oldest first (by generation)."""
    if not paths.checkpoints_dir.exists():
        return []
    out: list[Dict[str, Any]] = []
    for f in paths.checkpoints_dir.glob("champion_gen*.json"):
        try:
            out.append(read_json(f))
        except (json.JSONDecodeError, OSError):
            continue
    out.sort(key=lambda c: int(c.get("generation", 0)))
    return out
