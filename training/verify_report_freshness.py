"""Guardrail: assert the durable state reflects a completed multi-agent run.

Exit code is the contract (used by the nightly workflow and by tests):

* ``0`` — ``training/state/latest.json`` carries a completed approach-comparison
  record (``last_approach_comparison``) **and** that record was produced by the
  current run (``run_id`` matches), i.e. the report about to be emailed is a
  genuine, fresh multi-agent result.
* ``1`` — no approach-comparison record at all (the run almost certainly timed
  out / was cancelled before persisting, so the email would otherwise render a
  stale old-style report).
* ``2`` — a record exists but its ``run_id`` does not match the state's current
  ``run_id`` (stale record from an earlier run).

This is intentionally dependency-free (stdlib only) so it runs even if the
training step crashed before heavyweight imports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

APPROACH_COMPARISON_KEY = "last_approach_comparison"
DEFAULT_STATE = "training/state/latest.json"


def check(state_path: str = DEFAULT_STATE) -> int:
    path = Path(state_path)
    if not path.exists():
        print(f"[verify] FAIL: state file not found: {state_path}")
        return 1
    try:
        state = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        print(f"[verify] FAIL: could not read state {state_path}: {exc}")
        return 1

    record = state.get(APPROACH_COMPARISON_KEY)
    if not record:
        print(
            "[verify] FAIL: no completed multi-agent approach comparison in "
            f"`{state_path}` (`{APPROACH_COMPARISON_KEY}` is absent). The run likely "
            "did not finish persisting its result; the email will be INCOMPLETE."
        )
        return 1

    run_id = state.get("run_id")
    rec_run_id = record.get("run_id")
    if run_id and rec_run_id and rec_run_id != run_id:
        print(
            f"[verify] FAIL: approach comparison is from run `{rec_run_id}` but the "
            f"current run is `{run_id}` — the record is stale."
        )
        return 2

    rows = record.get("rows") or []
    winner = record.get("winner")
    print(
        f"[verify] OK: multi-agent approach comparison present for run "
        f"`{rec_run_id or run_id}` ({len(rows)} approach row(s), "
        f"winner={winner or 'none'})."
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=DEFAULT_STATE,
                        help="Path to the durable latest-state JSON.")
    args = parser.parse_args(argv)
    return check(args.state)


if __name__ == "__main__":
    raise SystemExit(main())
