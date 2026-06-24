"""Feature-scale auditing for the rich TD feature set (``rich_blokus_v1``).

The TD value model is *linear*, so a single feature whose magnitude dwarfs the
others silently dominates the dot product and the learned weights. This module
verifies the properties :mod:`training.rich_features` claims — every feature is
finite, bounded to roughly ``[-1, 1]``, and no single feature dominates the
variance — and flags any regression.

Why an audit and not a normalisation layer
------------------------------------------
Every rich feature is already squashed into a bounded range at extraction time:
counts are divided by an upper bound and ``min(..., 1.0)``-clamped, signed margins
pass through ``tanh``, and the final pass replaces any non-finite value with 0.0
(see :func:`training.rich_features.extract_rich_features`). The audit therefore
*enforces* that contract rather than re-scaling on top of it — a second
normalisation layer would only mask a feature that had silently broken its bound.
Run this whenever the feature set changes; the bundled test asserts the invariants
on synthetic boards.

Pure core (:func:`summarize_features`) takes a matrix + names so it is unit-tested
without touching the board engine. The :func:`audit_random_states` /
:func:`audit_trajectory_csv` helpers and the CLI wrap it.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from training.rich_features import RICH_FEATURE_NAMES

# Expected envelope for a well-normalised feature. Values outside this are not
# necessarily wrong, but warrant a look (the linear model has no scale guard).
EXPECTED_MIN = -1.05
EXPECTED_MAX = 1.05
# A feature contributing more than this fraction of total feature variance is
# "dominant" — it will steer the linear value model disproportionately.
DOMINANCE_VARIANCE_FRACTION = 0.40
# Std above this on a [-1, 1] feature is unusually spread (informational).
HIGH_STD = 0.60


@dataclass
class FeatureStats:
    name: str
    count: int
    n_nan: int
    n_inf: int
    min: float
    max: float
    mean: float
    std: float
    variance: float
    frac_at_zero: float
    frac_at_one: float
    variance_fraction: float = 0.0  # share of total variance across all features

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "n_nan": self.n_nan,
            "n_inf": self.n_inf,
            "min": self.min,
            "max": self.max,
            "mean": self.mean,
            "std": self.std,
            "variance": self.variance,
            "frac_at_zero": self.frac_at_zero,
            "frac_at_one": self.frac_at_one,
            "variance_fraction": self.variance_fraction,
        }


@dataclass
class FeatureAuditReport:
    n_samples: int
    stats: List[FeatureStats]
    findings: List[Dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(f["severity"] in ("warn", "critical") for f in self.findings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_samples": self.n_samples,
            "ok": self.ok,
            "findings": self.findings,
            "stats": [s.to_dict() for s in self.stats],
        }


def summarize_features(
    matrix: Sequence[Sequence[float]],
    names: Sequence[str] = RICH_FEATURE_NAMES,
) -> FeatureAuditReport:
    """Audit a ``(n_samples, n_features)`` matrix. Pure (no I/O).

    Computes per-feature stats and emits findings for non-finite values, range
    violations, and variance dominance.
    """
    arr = np.asarray(matrix, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    n_samples = arr.shape[0]
    n_features = arr.shape[1] if arr.size else len(names)
    if n_features != len(names):
        raise ValueError(f"matrix has {n_features} cols but {len(names)} names given")

    finite_mask = np.isfinite(arr)
    # Per-feature variance over finite values only (NaN/inf shouldn't poison it).
    variances: List[float] = []
    stats: List[FeatureStats] = []
    for j, name in enumerate(names):
        col = arr[:, j] if arr.size else np.array([])
        fmask = finite_mask[:, j] if arr.size else np.array([], dtype=bool)
        finite = col[fmask] if col.size else col
        n_nan = int(np.sum(np.isnan(col))) if col.size else 0
        n_inf = int(np.sum(np.isinf(col))) if col.size else 0
        if finite.size:
            cmin, cmax = float(np.min(finite)), float(np.max(finite))
            cmean, cstd = float(np.mean(finite)), float(np.std(finite))
            cvar = float(np.var(finite))
            frac_zero = float(np.mean(np.isclose(finite, 0.0)))
            frac_one = float(np.mean(np.isclose(finite, 1.0)))
        else:
            cmin = cmax = cmean = cstd = cvar = 0.0
            frac_zero = frac_one = 0.0
        variances.append(cvar)
        stats.append(FeatureStats(
            name=name, count=int(finite.size), n_nan=n_nan, n_inf=n_inf,
            min=cmin, max=cmax, mean=cmean, std=cstd, variance=cvar,
            frac_at_zero=frac_zero, frac_at_one=frac_one,
        ))

    total_var = float(sum(variances)) or 1.0
    for s, v in zip(stats, variances):
        s.variance_fraction = float(v / total_var)

    findings = _derive_findings(stats)
    return FeatureAuditReport(n_samples=n_samples, stats=stats, findings=findings)


def _derive_findings(stats: List[FeatureStats]) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    for s in stats:
        if s.n_nan or s.n_inf:
            findings.append({
                "severity": "critical", "feature": s.name,
                "message": f"{s.n_nan} NaN / {s.n_inf} inf values — extraction is "
                           "leaking non-finite features into training.",
            })
        if s.min < EXPECTED_MIN or s.max > EXPECTED_MAX:
            findings.append({
                "severity": "warn", "feature": s.name,
                "message": f"range [{s.min:.3f}, {s.max:.3f}] exceeds expected "
                           f"[{EXPECTED_MIN}, {EXPECTED_MAX}] — feature is not bounded "
                           "like the others and may dominate the linear value.",
            })
        if s.variance_fraction > DOMINANCE_VARIANCE_FRACTION:
            findings.append({
                "severity": "warn", "feature": s.name,
                "message": f"contributes {s.variance_fraction * 100:.0f}% of total "
                           "feature variance — dominant feature in a linear model.",
            })
        if s.std > HIGH_STD:
            findings.append({
                "severity": "info", "feature": s.name,
                "message": f"high spread (std={s.std:.3f}); confirm this is intended.",
            })
    return findings


# ---------------------------------------------------------------------------
# Sample sources
# ---------------------------------------------------------------------------


def audit_trajectory_csv(
    path: Path | str, *, use_next_state: bool = False
) -> FeatureAuditReport:
    """Audit the feature columns of a stored trajectory CSV."""
    from training import trajectory_store

    rows = trajectory_store.load_trajectories(path)
    if not rows:
        return FeatureAuditReport(n_samples=0, stats=[], findings=[{
            "severity": "info", "feature": "*",
            "message": f"No trajectory rows found at {path}.",
        }])
    vec = trajectory_store.next_state_vector if use_next_state else trajectory_store.state_vector
    matrix = [vec(r) for r in rows]
    # Drop all-zero next-state rows (terminal placeholders) when auditing next states.
    if use_next_state:
        matrix = [m for m in matrix if any(m)]
    return summarize_features(matrix)


def audit_random_states(
    num_boards: int = 200, *, seed: int = 12345, max_plies: int = 60
) -> FeatureAuditReport:
    """Sample features from random partial games (no MCTS — fast coverage).

    Plays uniformly-random legal moves and snapshots the moving player's rich
    feature vector, giving broad coverage of board occupancies / phases.
    """
    import random

    from engine.board import Player
    from engine.game import BlokusGame
    from training.rich_features import FeatureCache, extract_rich_features

    rng = random.Random(seed)
    players = list(Player)
    matrix: List[List[float]] = []
    games = 0
    while len(matrix) < num_boards and games < num_boards * 4 + 50:
        games += 1
        game = BlokusGame()
        plies = 0
        while not game.is_game_over() and plies < max_plies and len(matrix) < num_boards:
            current = game.get_current_player()
            legal = game.get_legal_moves(current)
            plies += 1
            if not legal:
                game.board._update_current_player()
                game._check_game_over()
                continue
            cache = FeatureCache()
            feats = extract_rich_features(game.board, current, cache=cache)
            matrix.append([float(feats[n]) for n in RICH_FEATURE_NAMES])
            move = rng.choice(legal)
            if not game.make_move(move, current):
                game.board._update_current_player()
                game._check_game_over()
    if not matrix:
        return FeatureAuditReport(n_samples=0, stats=[], findings=[])
    return summarize_features(matrix)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_report(report: FeatureAuditReport, *, top: int = 0) -> str:
    lines = [
        "# Rich Feature Normalisation Audit",
        "",
        f"_Samples: {report.n_samples} · status: "
        f"{'✅ OK' if report.ok else '⚠️ issues found'}_",
        "",
    ]
    if report.findings:
        icon = {"critical": "🔴", "warn": "🟠", "info": "🔵"}
        lines += ["## Findings", ""]
        for f in report.findings:
            lines.append(f"- {icon.get(f['severity'], '•')} **[{f['severity']}] "
                         f"`{f['feature']}`** — {f['message']}")
        lines.append("")
    else:
        lines += ["**No issues detected.** All features finite and in range.", ""]

    rows = sorted(report.stats, key=lambda s: s.variance_fraction, reverse=True)
    if top:
        rows = rows[:top]
    lines += [
        "## Feature statistics (by variance share)",
        "",
        "| Feature | min | max | mean | std | var% | %=0 | %=1 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in rows:
        lines.append(
            f"| `{s.name}` | {s.min:.3f} | {s.max:.3f} | {s.mean:.3f} | {s.std:.3f} "
            f"| {s.variance_fraction * 100:.1f}% | {s.frac_at_zero * 100:.0f}% "
            f"| {s.frac_at_one * 100:.0f}% |"
        )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Audit rich-feature normalisation.")
    p.add_argument("--input", default=None,
                   help="Trajectory CSV to audit (default: sample random boards).")
    p.add_argument("--num-boards", type=int, default=200,
                   help="Random boards to sample when --input is not given.")
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--next-state", action="store_true",
                   help="Audit next-state (nf_) columns instead of current-state.")
    p.add_argument("--output", default=None, help="Write the markdown report here.")
    args = p.parse_args(argv)

    if args.input:
        report = audit_trajectory_csv(args.input, use_next_state=args.next_state)
    else:
        report = audit_random_states(num_boards=args.num_boards, seed=args.seed)

    md = render_report(report)
    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"[feature_audit] wrote {args.output}")
    else:
        print(md)
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
