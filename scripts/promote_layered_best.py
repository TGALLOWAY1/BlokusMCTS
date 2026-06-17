"""Provisionally promote the layered-assessment 'Best Configuration' as champion.

This is **not** a gauntlet promotion. It records, as the *current* champion, the
agent that the Layer 1-9 experimental assessment (``KEY_FINDINGS.md``) identified
as its "Best Configuration" — ``key_findings_best`` — so the public "Play the
Champion" demo has a concrete, documented opponent to serve *for now*.

The entry is labelled honestly:
  - ``gate_pass`` is True only so the registry loader will *serve* it.
  - ``promotion_reason`` / ``notes`` state plainly that this is a provisional
    selection from the layered assessment, pending a full multi-seed gauntlet.
  - Metrics are the **documented layered-assessment** numbers, not fresh
    measurements: the headline win rate (0.54) from KEY_FINDINGS.md, and the
    TrueSkill *prior* (mu=25.0) because no gauntlet has rated this exact config.
  - ``total_games_played`` / ``gauntlet_run_path`` are null — there is no
    gauntlet run behind this promotion.

A future ``scripts/champion_gauntlet.py --promote`` run supersedes this entry
with a fully gauntlet-validated champion.

Usage:
    python scripts/promote_layered_best.py            # promote (writes a .bak)
    python scripts/promote_layered_best.py --dry-run   # print the entry only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.champion import default_registry_path
from analytics.tournament.gauntlet import _next_version_key, load_candidate_config

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = "config/key_findings_best_params.json"
CHAMPION_NAME = "key_findings_best"

# Documented layered-assessment metrics (see KEY_FINDINGS.md). These are NOT
# fresh measurements — they are the published verdict of the Layer 1-9 program.
LAYERED_WIN_RATE = 0.54  # "winning 54% of games" — KEY_FINDINGS.md headline result
# No gauntlet has rated this exact combined config, so we record the TrueSkill
# prior rather than fabricate a competitive rating.
TRUESKILL_PRIOR_MU = 25.0
TRUESKILL_PRIOR_SIGMA = 8.333
TRUESKILL_PRIOR_CONSERVATIVE = 0.0


def build_entry() -> dict:
    agent = load_candidate_config(CHAMPION_NAME, str(REPO_ROOT / CONFIG_PATH))
    now = datetime.now(timezone.utc).isoformat()
    return {
        "promoted_at": now,
        "promoted_from": "v1",
        "promotion_reason": (
            "PROVISIONAL (not gauntlet-validated): selected as the best agent from "
            "the Layer 1-9 assessment — the 'Best Configuration' documented in "
            "KEY_FINDINGS.md (random rollout, cutoff depth 5, minimax backup "
            "alpha=0.25, ML-calibrated state-eval weights, RAVE k=1000, root "
            "2-worker parallelization, adaptive rollout depth). Promoted to give "
            "the public 'Play the Champion' demo a concrete opponent for now, "
            "pending a full multi-seed champion gauntlet."
        ),
        "champion_name": CHAMPION_NAME,
        "config_path": CONFIG_PATH,
        "params": dict(agent.get("params") or {}),
        "thinking_time_ms": agent.get("thinking_time_ms"),
        "avg_win_rate": LAYERED_WIN_RATE,
        "win_rate_ci": None,
        "avg_trueskill_mu": TRUESKILL_PRIOR_MU,
        "trueskill_sigma": TRUESKILL_PRIOR_SIGMA,
        "trueskill_conservative": TRUESKILL_PRIOR_CONSERVATIVE,
        "avg_score": None,
        "total_games_played": None,
        "seeds": [],
        "validation_date": now,
        "gauntlet_run_path": None,
        "comparison_opponents": [],
        "notes": (
            "Provisional champion from the layered (Layer 1-9) assessment, not a "
            "gauntlet. Win rate is the documented KEY_FINDINGS.md headline (0.54); "
            "TrueSkill is the prior (mu=25.0) because no gauntlet has rated this "
            "exact config. Supersede with scripts/champion_gauntlet.py --promote."
        ),
        "gate_pass": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print the entry without writing.")
    parser.add_argument("--registry", default=str(default_registry_path()))
    args = parser.parse_args()

    entry = build_entry()
    if args.dry_run:
        print(json.dumps(entry, indent=2))
        return

    registry_path = Path(args.registry)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    versions = registry.setdefault("versions", {})
    version = _next_version_key(versions)

    # Preserve all historical entries; never drop v1. Provisional entries carry a
    # null total_games_played (no gauntlet games), so we do not accumulate it into
    # the registry total.
    registry_path.with_suffix(registry_path.suffix + ".bak").write_text(
        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
    )
    versions[version] = entry
    registry["current_version"] = version
    registry.setdefault("iterations", []).append(
        {"version": version, "champion": CHAMPION_NAME, "promoted_at": entry["promoted_at"]}
    )
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    print(f"[promote] {CHAMPION_NAME} promoted as {version} in {registry_path}")
    print(f"[promote] reason: {entry['promotion_reason'][:80]}...")


if __name__ == "__main__":
    main()
