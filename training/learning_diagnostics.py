"""Learning-process observability for the TD value model.

``td_loss`` / ``mean_abs_td_error`` tell you the model fits its own bootstrap
targets — they say *nothing* about whether the resulting agent plays better. This
module adds the missing observability:

* **Feature importance** — per-phase weight magnitude ranking from a TD artifact,
  so you can see *what concepts* the evaluator is leaning on.
* **Weight drift / stability** — compare two artifacts to find the fastest-moving
  and least-stable features between training runs.
* **Loss → strength correlation** — a durable history (``learning_history.jsonl``)
  pairing each run's training loss with the candidate's measured strength (Elo /
  TrueSkill) and promotion outcome, plus the Pearson correlation between them. This
  is the number that answers "is optimising TD loss actually meaningful?".

Pure functions over plain dicts; the JSONL store is the only I/O.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

PHASES = ("early", "mid", "late")


# ---------------------------------------------------------------------------
# Feature importance (from a TD artifact's rich weights)
# ---------------------------------------------------------------------------


def feature_importance(
    artifact: Dict[str, Any], phase: str, *, top: int = 0
) -> List[Tuple[str, float]]:
    """Rank features for one phase by absolute learned weight (descending).

    Reads ``rich_phase_weights[phase].weights`` from a TD artifact (see
    :func:`training.td_learning.build_artifact`). Returns ``[(name, |weight|), ...]``.
    """
    rich = (artifact.get("rich_phase_weights") or {}).get(phase) or {}
    weights = rich.get("weights") or {}
    ranked = sorted(((n, abs(float(w))) for n, w in weights.items()),
                    key=lambda kv: kv[1], reverse=True)
    return ranked[:top] if top else ranked


def signed_weights(artifact: Dict[str, Any], phase: str) -> Dict[str, float]:
    rich = (artifact.get("rich_phase_weights") or {}).get(phase) or {}
    return {n: float(w) for n, w in (rich.get("weights") or {}).items()}


# ---------------------------------------------------------------------------
# Weight drift / stability between two artifacts
# ---------------------------------------------------------------------------


@dataclass
class WeightDrift:
    phase: str
    l2_drift: float                       # ||w_new - w_old||
    cosine_similarity: float              # direction stability (1 = unchanged)
    per_feature_movement: Dict[str, float]  # name -> |Δw|
    fastest_changing: List[Tuple[str, float]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "l2_drift": self.l2_drift,
            "cosine_similarity": self.cosine_similarity,
            "fastest_changing": self.fastest_changing,
        }


def weight_drift(
    prev_artifact: Dict[str, Any], new_artifact: Dict[str, Any], phase: str, *, top: int = 5
) -> WeightDrift:
    """Quantify how much one phase's weight vector moved between two artifacts."""
    import math

    old = signed_weights(prev_artifact, phase)
    new = signed_weights(new_artifact, phase)
    names = sorted(set(old) | set(new))
    movement: Dict[str, float] = {}
    dot = norm_old = norm_new = sq = 0.0
    for n in names:
        a, b = old.get(n, 0.0), new.get(n, 0.0)
        movement[n] = abs(b - a)
        dot += a * b
        norm_old += a * a
        norm_new += b * b
        sq += (b - a) ** 2
    l2 = math.sqrt(sq)
    cos = (dot / math.sqrt(norm_old * norm_new)) if norm_old > 0 and norm_new > 0 else 0.0
    fastest = sorted(movement.items(), key=lambda kv: kv[1], reverse=True)[:top]
    return WeightDrift(phase, l2, cos, movement, fastest)


# ---------------------------------------------------------------------------
# Loss → strength history + correlation
# ---------------------------------------------------------------------------


DEFAULT_HISTORY = "training/state/learning_history.jsonl"


def record_learning_event(
    path: Path | str,
    *,
    run_id: str,
    learning_method: str,
    td_loss: Optional[float],
    candidate_elo: Optional[float] = None,
    candidate_trueskill_mu: Optional[float] = None,
    promoted: Optional[bool] = None,
    training_rows: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Append one training→strength observation to the durable history JSONL."""
    rec = {
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "learning_method": learning_method,
        "td_loss": None if td_loss is None else float(td_loss),
        "candidate_elo": None if candidate_elo is None else float(candidate_elo),
        "candidate_trueskill_mu": None if candidate_trueskill_mu is None
        else float(candidate_trueskill_mu),
        "promoted": None if promoted is None else bool(promoted),
        "training_rows": training_rows,
    }
    if extra:
        rec.update(extra)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(rec) + "\n")
    return rec


def load_learning_history(path: Path | str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    return cov / ((vx ** 0.5) * (vy ** 0.5))


def loss_to_strength_correlation(
    history: Sequence[Dict[str, Any]], *, strength_field: str = "candidate_trueskill_mu"
) -> Dict[str, Any]:
    """Correlate training ``td_loss`` against measured candidate strength.

    A meaningful learning signal has a *negative* correlation (lower loss → higher
    strength). Near-zero or positive correlation is the headline evidence that
    optimising TD loss is **not** producing stronger agents.
    """
    pairs = [
        (float(h["td_loss"]), float(h[strength_field]))
        for h in history
        if h.get("td_loss") is not None and h.get(strength_field) is not None
    ]
    if len(pairs) < 2:
        return {"n": len(pairs), "pearson": None, "strength_field": strength_field,
                "interpretation": "Insufficient paired observations (need >= 2)."}
    xs, ys = zip(*pairs)
    r = _pearson(xs, ys)
    if r is None:
        interp = "No variance in loss or strength — correlation undefined."
    elif r <= -0.3:
        interp = "Lower TD loss tracks higher strength — loss is a useful proxy."
    elif r >= 0.3:
        interp = "Lower TD loss tracks LOWER strength — optimising loss may hurt play."
    else:
        interp = "Weak/no relationship — TD loss is not a reliable strength proxy yet."
    return {"n": len(pairs), "pearson": r, "strength_field": strength_field,
            "interpretation": interp}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_feature_importance(artifact: Dict[str, Any], *, top: int = 10) -> str:
    lines = ["# TD Feature Importance (per phase)", ""]
    for phase in PHASES:
        ranked = feature_importance(artifact, phase, top=top)
        rich = (artifact.get("rich_phase_weights") or {}).get(phase) or {}
        trained = rich.get("trained")
        lines += [f"## {phase}" + ("" if trained else " _(prior — insufficient rows)_"), ""]
        if not ranked:
            lines += ["_no weights_", ""]
            continue
        lines += ["| rank | feature | |weight| |", "|---|---|---|"]
        for i, (name, mag) in enumerate(ranked, start=1):
            lines.append(f"| {i} | `{name}` | {mag:.4f} |")
        lines.append("")
    return "\n".join(lines)


def render_correlation(corr: Dict[str, Any]) -> str:
    r = corr.get("pearson")
    rtxt = "n/a" if r is None else f"{r:+.3f}"
    return (
        "## Loss → Strength Correlation\n\n"
        f"- **Pairs:** {corr.get('n')}\n"
        f"- **Strength field:** `{corr.get('strength_field')}`\n"
        f"- **Pearson r:** {rtxt}\n"
        f"- _{corr.get('interpretation')}_\n"
    )
