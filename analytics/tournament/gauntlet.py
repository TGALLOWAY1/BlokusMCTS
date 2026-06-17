"""Champion gauntlet: candidate loading, aggregation, ranking, promotion, registry.

Pure, testable helpers behind ``scripts/champion_gauntlet.py``. The CLI is
responsible for actually running the arena (which is slow and side-effecty);
everything in this module operates on already-collected game records or plain
dictionaries so it can be unit-tested with small deterministic mocks.

Design notes
------------
* Metrics are *reused* from the existing arena infrastructure
  (:func:`analytics.tournament.arena_stats.compute_summary` and
  :func:`analytics.tournament.statistics.wilson_score_interval`). No new
  metric definitions are invented here.
* Ranking is by TrueSkill conservative estimate (mu - 3*sigma), the repo's
  established leaderboard metric, with win rate as the tie-breaker.
* Promotion is intentionally conservative: every gate must pass, and the
  default behaviour is to refuse promotion when the evidence is ambiguous.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from analytics.tournament.arena_stats import compute_summary
from analytics.tournament.statistics import wilson_score_interval

# Keys in a champion *_params.json file that are metadata, not MCTS params.
_METADATA_KEYS = {"description", "champion_version", "thinking_time_ms", "type", "name"}

# Default set of candidates compared by the gauntlet. Each maps a stable
# display name to the config wrapper that defines it.
DEFAULT_CANDIDATES: Dict[str, str] = {
    "champion_v1": "config/champion_arena_params.json",
    "champion_minimal": "config/champion_minimal_params.json",
    "pool_peer_500ms": "config/pool_peer_500ms_params.json",
    "key_findings_best": "config/key_findings_best_params.json",
}


# ---------------------------------------------------------------------------
# Candidate config loading
# ---------------------------------------------------------------------------

def load_candidate_config(name: str, path: str | Path) -> Dict[str, Any]:
    """Load a champion ``*_params.json`` wrapper into an arena agent dict.

    The wrapper format keeps MCTS params at the top level alongside a few
    metadata keys (``description``, ``champion_version``, ``thinking_time_ms``).
    This splits them into the ``{name, type, thinking_time_ms, params}`` shape
    the arena harness expects.

    Returns a dict that also carries ``config_path`` and ``config_hash`` for
    provenance.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"Candidate config {path} must be a JSON object.")

    agent_type = str(payload.get("type", "mcts"))
    thinking_time = payload.get("thinking_time_ms")
    params = {
        key: value
        for key, value in payload.items()
        if key not in _METADATA_KEYS and not key.startswith("_")
    }
    agent = {
        "name": name,
        "type": agent_type,
        "thinking_time_ms": int(thinking_time) if thinking_time is not None else None,
        "params": params,
    }
    agent["config_path"] = str(path)
    agent["config_hash"] = config_hash(agent)
    return agent


def config_hash(agent: Mapping[str, Any]) -> str:
    """Stable short hash of the agent's *behavioural* config.

    Excludes the display name and provenance fields so two configs that differ
    only by label hash identically.
    """
    payload = {
        "type": agent.get("type"),
        "thinking_time_ms": agent.get("thinking_time_ms"),
        "params": agent.get("params", {}),
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Aggregation across seeds
# ---------------------------------------------------------------------------

def aggregate_summary(
    games: Sequence[Mapping[str, Any]],
    *,
    agent_names: Sequence[str],
    thinking_time_ms_by_agent: Mapping[str, Optional[int]],
    seeds: Sequence[int],
    seat_policy: str = "round_robin",
    run_config: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Pool game records from every seed into one arena summary.

    Thin wrapper over :func:`compute_summary` so the pooled win rates, pairwise
    records, TrueSkill ratings, score stats and seat analysis all come from the
    same vetted code path the single-run arena uses.
    """
    return compute_summary(
        games,
        run_id="gauntlet_pooled",
        run_seed=seeds[0] if seeds else 0,
        seat_policy=seat_policy,
        agent_names=list(agent_names),
        thinking_time_ms_by_agent=dict(thinking_time_ms_by_agent),
        run_config=dict(run_config or {}),
    )


def build_leaderboard(summary: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Build per-candidate metric rows from a pooled arena summary."""
    win_stats = summary.get("win_stats", {})
    score_stats = summary.get("score_stats", {})
    ts_leaderboard = (summary.get("trueskill_ratings") or {}).get("leaderboard", [])
    ts_by_name = {entry["agent_id"]: entry for entry in ts_leaderboard}

    rows: List[Dict[str, Any]] = []
    for name, ws in win_stats.items():
        games = float(ws.get("games_played", 0.0))
        win_points = float(ws.get("win_points", 0.0))
        ci = wilson_score_interval(win_points, games)
        tse = ts_by_name.get(name, {})
        rows.append(
            {
                "name": name,
                "games_played": int(games),
                "win_rate": float(ws.get("win_rate", 0.0)),
                "win_rate_ci_lower": ci["lower"],
                "win_rate_ci_upper": ci["upper"],
                "outright_wins": int(ws.get("outright_wins", 0)),
                "shared_wins": int(ws.get("shared_wins", 0)),
                "avg_score": score_stats.get(name, {}).get("mean"),
                "trueskill_mu": tse.get("mu"),
                "trueskill_sigma": tse.get("sigma"),
                "trueskill_conservative": tse.get("conservative"),
            }
        )
    return rows


def _conservative_key(row: Mapping[str, Any]) -> float:
    value = row.get("trueskill_conservative")
    return float(value) if value is not None else float("-inf")


def rank_candidates(leaderboard: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Rank candidates by TrueSkill conservative (mu-3sigma), then win rate.

    Returns new dicts with an added 1-based ``rank`` field.
    """
    ranked = sorted(
        (dict(row) for row in leaderboard),
        key=lambda r: (_conservative_key(r), float(r.get("win_rate", 0.0))),
        reverse=True,
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    return ranked


def pairwise_record(
    summary: Mapping[str, Any], agent_a: str, agent_b: str
) -> Dict[str, int]:
    """Head-to-head record of ``agent_a`` vs ``agent_b`` (oriented to A)."""
    matchups = summary.get("pairwise_matchups", {})
    lo, hi = sorted([agent_a, agent_b])
    item = matchups.get(f"{lo}__vs__{hi}")
    if not item:
        return {"a_wins": 0, "b_wins": 0, "tie": 0, "total": 0}
    if item.get("agent_a") == agent_a:
        return {
            "a_wins": int(item["a_beats_b"]),
            "b_wins": int(item["b_beats_a"]),
            "tie": int(item["tie"]),
            "total": int(item["total"]),
        }
    return {
        "a_wins": int(item["b_beats_a"]),
        "b_wins": int(item["a_beats_b"]),
        "tie": int(item["tie"]),
        "total": int(item["total"]),
    }


# ---------------------------------------------------------------------------
# Promotion logic
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PromotionThresholds:
    """Tunable bar a candidate must clear to be promoted to champion."""

    min_seeds: int = 2
    min_total_games: int = 40
    min_mu_margin: float = 0.5  # Delta-mu over runner-up (repo's TrueSkill gate)
    num_agents: int = 4  # random baseline win rate = 1 / num_agents


@dataclass
class PromotionDecision:
    """Outcome of evaluating the promotion gates."""

    promote: bool
    champion: Optional[str]
    criteria: List[Dict[str, Any]] = field(default_factory=list)
    summary_line: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "promote": self.promote,
            "champion": self.champion,
            "criteria": self.criteria,
            "summary_line": self.summary_line,
        }


def evaluate_promotion(
    ranked: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    *,
    n_seeds: int,
    total_games: int,
    thresholds: Optional[PromotionThresholds] = None,
) -> PromotionDecision:
    """Decide whether the top-ranked candidate may be promoted to champion.

    Every gate must pass. The gates are deliberately conservative so that an
    ambiguous gauntlet results in "No validated champion promoted." rather than
    a premature promotion.
    """
    thresholds = thresholds or PromotionThresholds()

    if not ranked:
        return PromotionDecision(
            promote=False,
            champion=None,
            criteria=[],
            summary_line="No candidates evaluated; no validated champion promoted.",
        )
    if len(ranked) < 2:
        return PromotionDecision(
            promote=False,
            champion=None,
            criteria=[
                {
                    "name": "has_runner_up",
                    "passed": False,
                    "detail": "Need at least 2 candidates to compare head-to-head.",
                }
            ],
            summary_line="Only one candidate; no validated champion promoted.",
        )

    champion = ranked[0]
    runner_up = ranked[1]
    champ_name = champion["name"]
    runner_name = runner_up["name"]

    h2h = pairwise_record(summary, champ_name, runner_name)
    mu_margin = (
        float(champion["trueskill_mu"]) - float(runner_up["trueskill_mu"])
        if champion.get("trueskill_mu") is not None
        and runner_up.get("trueskill_mu") is not None
        else float("-inf")
    )
    random_baseline = 1.0 / float(thresholds.num_agents)

    criteria: List[Dict[str, Any]] = [
        {
            "name": "highest_ranking",
            "passed": champion.get("rank", 1) == 1,
            "detail": (
                f"{champ_name} is ranked #{champion.get('rank', 1)} by TrueSkill "
                f"conservative ({champion.get('trueskill_conservative')})."
            ),
        },
        {
            "name": "beats_runner_up_h2h",
            "passed": h2h["a_wins"] > h2h["b_wins"],
            "detail": (
                f"{champ_name} vs {runner_name} head-to-head: "
                f"{h2h['a_wins']}-{h2h['b_wins']} (ties {h2h['tie']}, "
                f"n={h2h['total']})."
            ),
        },
        {
            "name": "trueskill_margin",
            "passed": mu_margin >= thresholds.min_mu_margin,
            "detail": (
                f"Delta-mu over {runner_name} = {mu_margin:.3f} "
                f"(required >= {thresholds.min_mu_margin})."
            ),
        },
        {
            "name": "win_rate_ci_conclusive",
            "passed": float(champion["win_rate_ci_lower"]) > random_baseline,
            "detail": (
                f"Wilson-95 win-rate lower bound = "
                f"{float(champion['win_rate_ci_lower']):.3f} "
                f"(must exceed random baseline {random_baseline:.3f})."
            ),
        },
        {
            "name": "multiple_seeds",
            "passed": n_seeds >= thresholds.min_seeds,
            "detail": f"{n_seeds} seed(s) used (required >= {thresholds.min_seeds}).",
        },
        {
            "name": "enough_games",
            "passed": total_games >= thresholds.min_total_games,
            "detail": (
                f"{total_games} total games (required >= "
                f"{thresholds.min_total_games})."
            ),
        },
    ]

    promote = all(item["passed"] for item in criteria)
    if promote:
        summary_line = (
            f"PROMOTE: {champ_name} passes all {len(criteria)} gates "
            f"(beats {runner_name} {h2h['a_wins']}-{h2h['b_wins']}, "
            f"Delta-mu={mu_margin:.2f})."
        )
    else:
        failed = [item["name"] for item in criteria if not item["passed"]]
        summary_line = (
            "No validated champion promoted. "
            f"Top candidate {champ_name} failed gates: {', '.join(failed)}."
        )

    return PromotionDecision(
        promote=promote,
        champion=champ_name if promote else None,
        criteria=criteria,
        summary_line=summary_line,
    )


# ---------------------------------------------------------------------------
# Registry update
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_registry_entry(
    *,
    champion_row: Mapping[str, Any],
    config_path: str,
    params: Mapping[str, Any],
    seeds: Sequence[int],
    total_games: int,
    gauntlet_run_path: str,
    comparison_opponents: Sequence[str],
    promoted_from: Optional[str],
    promotion_reason: str,
    notes: str = "",
) -> Dict[str, Any]:
    """Construct a fully-populated registry entry for a validated champion."""
    now = _utc_now_iso()
    return {
        "promoted_at": now,
        "promoted_from": promoted_from,
        "promotion_reason": promotion_reason,
        "champion_name": champion_row["name"],
        "config_path": config_path,
        "params": dict(params),
        "avg_win_rate": champion_row["win_rate"],
        "win_rate_ci": {
            "lower": champion_row["win_rate_ci_lower"],
            "upper": champion_row["win_rate_ci_upper"],
        },
        "avg_trueskill_mu": champion_row["trueskill_mu"],
        "trueskill_sigma": champion_row["trueskill_sigma"],
        "trueskill_conservative": champion_row["trueskill_conservative"],
        "avg_score": champion_row["avg_score"],
        "total_games_played": int(total_games),
        "seeds": list(seeds),
        "validation_date": now,
        "gauntlet_run_path": gauntlet_run_path,
        "comparison_opponents": list(comparison_opponents),
        "notes": notes,
        "gate_pass": True,
    }


def _next_version_key(versions: Mapping[str, Any]) -> str:
    """Return the next ``vN`` key not already present in ``versions``."""
    max_n = 0
    for key in versions:
        if key.startswith("v"):
            try:
                max_n = max(max_n, int(key[1:]))
            except ValueError:
                continue
    return f"v{max_n + 1}"


def update_registry(
    registry_path: str | Path,
    entry: Mapping[str, Any],
    *,
    make_backup: bool = True,
) -> str:
    """Safely write a validated champion entry into the registry.

    Preserves all existing versions (historical entries are never dropped),
    bumps ``current_version`` to a fresh ``vN`` key, accumulates
    ``total_games_played``, appends an iteration record, and (by default)
    writes a ``.bak`` of the previous file first.

    Returns the new version key.
    """
    registry_path = Path(registry_path)
    if registry_path.exists():
        with registry_path.open("r", encoding="utf-8") as handle:
            registry = json.load(handle)
        if make_backup:
            backup = registry_path.with_suffix(registry_path.suffix + ".bak")
            backup.write_text(
                json.dumps(registry, indent=2) + "\n", encoding="utf-8"
            )
    else:
        registry = {
            "current_version": None,
            "versions": {},
            "iterations": [],
            "snapshot_csv_paths": [],
            "total_games_played": 0,
        }

    versions = registry.setdefault("versions", {})
    new_version = _next_version_key(versions)
    versions[new_version] = dict(entry)

    registry["current_version"] = new_version
    registry["total_games_played"] = int(
        registry.get("total_games_played", 0) or 0
    ) + int(entry.get("total_games_played", 0))
    registry.setdefault("iterations", []).append(
        {
            "version": new_version,
            "champion_name": entry.get("champion_name"),
            "validation_date": entry.get("validation_date"),
            "gauntlet_run_path": entry.get("gauntlet_run_path"),
        }
    )

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8") as handle:
        json.dump(registry, handle, indent=2)
        handle.write("\n")
    return new_version


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def render_gauntlet_markdown(report: Mapping[str, Any]) -> str:
    """Render a human-readable gauntlet report from the saved report dict."""
    lines: List[str] = []
    lines.append(f"# Champion Gauntlet — {report.get('gauntlet_id', 'run')}")
    lines.append("")
    lines.append("## Run Parameters")
    lines.append(f"- Date: `{report.get('created_at')}`")
    lines.append(f"- Seeds: `{report.get('seeds')}`")
    lines.append(f"- Games per seed: `{report.get('num_games_per_seed')}`")
    lines.append(f"- Total games: `{report.get('total_games')}`")
    lines.append(f"- Seat policy: `{report.get('seat_policy')}`")
    lines.append("")

    lines.append("## Candidates")
    lines.append("| Candidate | Config | Hash | Thinking ms |")
    lines.append("|---|---|---|---|")
    for cand in report.get("candidates", []):
        lines.append(
            f"| `{cand['name']}` | `{cand.get('config_path')}` | "
            f"`{cand.get('config_hash')}` | {cand.get('thinking_time_ms')} |"
        )
    lines.append("")

    lines.append("## Ranked Leaderboard")
    lines.append(
        "| Rank | Candidate | Win% | Wilson-95 CI | TrueSkill mu | sigma | "
        "Cons (mu-3sigma) | Avg score | Games |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in report.get("ranked", []):
        mu = row.get("trueskill_mu")
        sigma = row.get("trueskill_sigma")
        cons = row.get("trueskill_conservative")
        avg = row.get("avg_score")
        lines.append(
            f"| {row.get('rank')} | `{row['name']}` | "
            f"{row['win_rate'] * 100:.1f}% | "
            f"[{row['win_rate_ci_lower'] * 100:.1f}%, "
            f"{row['win_rate_ci_upper'] * 100:.1f}%] | "
            f"{mu:.2f} | {sigma:.2f} | {cons:.2f} | "
            f"{avg:.1f} | {row['games_played']} |"
        )
    lines.append("")

    lines.append("## Pairwise Records (outright score wins)")
    for line in report.get("pairwise_lines", []):
        lines.append(f"- {line}")
    lines.append("")

    lines.append("## Promotion Decision")
    decision = report.get("promotion", {})
    lines.append(f"**{decision.get('summary_line', '')}**")
    lines.append("")
    lines.append("| Gate | Passed | Detail |")
    lines.append("|---|---|---|")
    for crit in decision.get("criteria", []):
        mark = "✅" if crit["passed"] else "❌"
        lines.append(f"| `{crit['name']}` | {mark} | {crit['detail']} |")
    lines.append("")

    if report.get("registry_updated"):
        lines.append(
            f"> Registry updated: `{report.get('registry_path')}` "
            f"→ version `{report.get('registry_version')}`."
        )
    else:
        lines.append(
            "> Registry NOT modified "
            "(run without `--promote` or promotion gates not met)."
        )
    lines.append("")
    return "\n".join(lines).strip() + "\n"
