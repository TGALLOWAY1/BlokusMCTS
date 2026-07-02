"""Reporting era — which slice of the durable timeline the morning report trusts.

The durable rating timeline (``training/state/ratings.sqlite``) is **append-only**
and stretches back to the very first nightly run. Not all of that history is
comparable, though: a run's Elo is only trustworthy if the code that produced it
was correct. When the arena/search code changes in a way that invalidates earlier
measurements, mixing the two eras drags a stale "best historical", a misleading
trend line, and phantom promotion markers into the report.

This module is the **single source of truth** for the cut-off. Every report
(email, status markdown, Elo plot) resolves the active era here and filters the
timeline with ``since_run_id`` so the trend, rolling average, best-historical
marker, promotion markers, recent generations, and human-target projection are all
computed from the same, trustworthy slice.

Nothing is ever deleted — old rows stay in the database. The era only *filters*
what the default report shows; an all-time view is always available for debugging.

Known eras (oldest cut-off first)
---------------------------------
* ``multi-agent`` — the pipeline switched from the legacy single-line self-play
  loop to the multi-agent approach-comparison framework in commit ``3b36f7c``
  (2026-06-26 05:57 UTC). See :data:`ratings_db.MULTI_AGENT_EPOCH_RUN_ID`.
* ``debugged-backprop`` *(default)* — MCTS backpropagation could credit the wrong
  players when a tree was occasionally reused to speed up a rollout, so every
  pre-fix arena result rewarded the wrong nodes. The fix landed in commit
  ``732bd9c`` *"fix(mcts): maxⁿ per-player reward backpropagation"* at
  **2026-07-01 20:36:25 UTC**. The first nightly run whose checkout *started*
  after that commit is ``20260701T204805Z`` (generation 139) — every run at/after
  it played a debugged arena, so that is the default cut-off.

Changing / overriding the cut-off
---------------------------------
If you ever need to move the boundary (e.g. a future bug fix invalidates more
history), edit :data:`DEBUGGED_BACKPROP_ERA` below — one constant re-bases every
report consistently. You can also override at runtime without editing code:

* ``MCTS_REPORTING_ERA=all-time`` (or ``multi-agent`` / ``debugged-backprop``)
  selects a named era.
* ``MCTS_REPORTING_ERA_RUN_ID=<run_id>`` pins an arbitrary custom cut-off (any run
  id at/after it is kept). This wins over ``MCTS_REPORTING_ERA``.

Run ids are minted as ``%Y%m%dT%H%M%SZ`` (see ``nightly_run._new_run_id``) so they
sort lexicographically by wall-clock time; ``run_id >= since_run_id`` therefore
keeps exactly the era's rows.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional

from training import ratings_db

# ---------------------------------------------------------------------------
# The backprop-fix boundary (see module docstring for provenance).
# ---------------------------------------------------------------------------
# Commit 732bd9c "fix(mcts): maxⁿ per-player reward backpropagation" — 2026-07-01
# 20:36:25 UTC. First nightly run whose checkout started after the fix:
DEBUGGED_BACKPROP_EPOCH_RUN_ID = "20260701T204805Z"  # generation 139
DEBUGGED_BACKPROP_FIX_COMMIT = "732bd9c"
DEBUGGED_BACKPROP_FIX_TIMESTAMP = "2026-07-01T20:36:25Z"


@dataclass(frozen=True)
class ReportingEra:
    """A named slice of the durable timeline.

    ``since_run_id`` is ``None`` for the all-time view; otherwise it is the
    inclusive lower-bound run id every filtered query uses.
    """

    key: str
    label: str
    since_run_id: Optional[str]
    description: str

    @property
    def is_all_time(self) -> bool:
        return self.since_run_id is None

    def banner(self) -> str:
        """One-line header the reports print so the reader knows the scope."""
        if self.is_all_time:
            return f"Reporting era: {self.label} (all recorded runs — debugging view)"
        return (
            f"Reporting era: {self.label}. Earlier runs are preserved but excluded "
            "from trend, best historical, promotion markers, and projection "
            f"calculations (cut-off run `{self.since_run_id}`)."
        )


ALL_TIME = ReportingEra(
    key="all-time",
    label="All-time",
    since_run_id=None,
    description="Every recorded run, including pre-fix history. Debugging view only.",
)

MULTI_AGENT = ReportingEra(
    key="multi-agent",
    label="Multi-agent framework era",
    since_run_id=ratings_db.MULTI_AGENT_EPOCH_RUN_ID,
    description="Runs from the multi-agent approach-comparison framework onward "
                "(commit 3b36f7c, 2026-06-26).",
)

DEBUGGED_BACKPROP = ReportingEra(
    key="debugged-backprop",
    label="Debugged MCTS backprop era",
    since_run_id=DEBUGGED_BACKPROP_EPOCH_RUN_ID,
    description="Runs whose arena used the fixed maxⁿ per-player reward "
                f"backpropagation (commit {DEBUGGED_BACKPROP_FIX_COMMIT}, "
                f"{DEBUGGED_BACKPROP_FIX_TIMESTAMP}). This is the default reporting era.",
)

# The report defaults to the debugged-backprop era so the morning email is based on
# debugged arena runs only.
DEFAULT_ERA = DEBUGGED_BACKPROP

_ERAS: Dict[str, ReportingEra] = {e.key: e for e in (ALL_TIME, MULTI_AGENT, DEBUGGED_BACKPROP)}

# Env var names for runtime overrides (documented in the module docstring).
ENV_ERA_KEY = "MCTS_REPORTING_ERA"
ENV_ERA_RUN_ID = "MCTS_REPORTING_ERA_RUN_ID"


def known_eras() -> Dict[str, ReportingEra]:
    """Copy of the named-era registry (for CLI help / tests)."""
    return dict(_ERAS)


def resolve_era(key: Optional[str] = None) -> ReportingEra:
    """Resolve the active reporting era.

    Precedence (highest first):

    1. ``MCTS_REPORTING_ERA_RUN_ID`` env var — a custom cut-off run id.
    2. An explicit ``key`` argument (from a ``--era`` CLI flag).
    3. ``MCTS_REPORTING_ERA`` env var — a named era.
    4. :data:`DEFAULT_ERA` (debugged-backprop).

    An unknown key falls back to the default rather than raising, so a typo in a
    workflow env var can never break the nightly email.
    """
    custom_run_id = os.getenv(ENV_ERA_RUN_ID)
    if custom_run_id:
        run_id = custom_run_id.strip()
        return ReportingEra(
            key="custom",
            label=f"Custom cut-off (run ≥ {run_id})",
            since_run_id=run_id,
            description=f"Custom reporting cut-off pinned via {ENV_ERA_RUN_ID}={run_id}.",
        )
    if key is None:
        key = os.getenv(ENV_ERA_KEY)
    if key:
        era = _ERAS.get(key.strip().lower())
        if era is not None:
            return era
    return DEFAULT_ERA
