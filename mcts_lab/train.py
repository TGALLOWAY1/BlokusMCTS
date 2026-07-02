"""Candidate generation: turn self-play data into candidate agent configs.

    python -m mcts_lab.train                       # all default approaches
    python -m mcts_lab.train --approaches baseline,heuristic_tune

Each approach produces exactly one candidate artifact (JSON with an
arena-loadable ``agent_config`` and a specific created/not-created reason)
under ``training/artifacts/candidates/``. Promotion is a separate, gated step:
``python -m mcts_lab.promote --candidate <artifact>``.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from mcts_lab._common import load_state

DEFAULT_APPROACHES = "baseline,heuristic_tune,td"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--approaches", default=DEFAULT_APPROACHES,
                    help=f"comma-separated approach names (default {DEFAULT_APPROACHES}); "
                         f"see training/approaches/")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    from training import TrainingPaths
    from training import approaches as ap_pkg
    from training.approaches.base import (
        ApproachContext, validate_candidate_artifact, write_candidate_artifact,
    )

    paths = TrainingPaths.default()
    paths.ensure_dirs()
    state = load_state(paths)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    now_iso = datetime.now(timezone.utc).isoformat()

    names = [n for n in args.approaches.split(",") if n.strip()]
    ctx = ApproachContext(state=state, repo_root=paths.root, run_id=run_id,
                          now_iso=now_iso, verbose=args.verbose)
    exit_code = 1
    for approach in ap_pkg.build_approaches(names):
        cand = approach.generate(ctx)
        ok, why = validate_candidate_artifact(cand.to_artifact(run_id, now_iso))
        if cand.created and not ok:
            cand.created = False
            cand.agent_config = None
            cand.reason = f"{cand.approach}: invalid candidate artifact ({why})"
        path = write_candidate_artifact(cand, repo_root=paths.root, run_id=run_id, now_iso=now_iso)
        status = "created" if cand.created else "SKIPPED"
        print(f"{cand.approach:<18} {status:<8} {cand.reason}")
        print(f"{'':<18} artifact: {path}")
        if cand.created:
            exit_code = 0

    if exit_code == 0:
        print("\nnext: python -m mcts_lab.promote --candidate <artifact.json>")
    else:
        print("\nno candidate was created — see reasons above "
              "(usually: not enough self-play data; run mcts_lab.self_play first)")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
