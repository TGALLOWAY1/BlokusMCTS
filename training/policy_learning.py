"""Train the learned move policy from collected MCTS visit-count targets.

Reads ``data/policy_targets.csv`` (produced by :mod:`training.policy_selfplay`),
distils the per-decision visit distributions into a compact log-linear move
policy (:func:`mcts.move_policy.train_move_policy`), and writes an artifact to
``training/state/policy_weights.json``. The artifact's ``policy`` block is exactly
what the agent consumes as ``policy_weights`` (PUCT prior + rollout/ordering).

CLI::

    python -m training.policy_learning \
        --input data/policy_targets.csv \
        --output training/state/policy_weights.json
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcts.move_heuristic import MOVE_FEATURE_NAMES
from mcts.move_policy import (
    POLICY_FEATURE_SET_VERSION,
    PolicySample,
    PolicyTrainConfig,
    PolicyTrainResult,
    train_move_policy,
)
from training import REPO_ROOT
from training.policy_selfplay import DEFAULT_POLICY_CSV, load_policy_samples

DEFAULT_OUTPUT = REPO_ROOT / "training" / "state" / "policy_weights.json"

# Minimum grouped decisions required before we trust a fitted policy.
MIN_SAMPLES = 200


def build_artifact(result: PolicyTrainResult, config: PolicyTrainConfig) -> Dict[str, Any]:
    """Assemble the serialisable policy-weights artifact."""
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "learning_method": "visit_count_distillation",
        "feature_set_version": POLICY_FEATURE_SET_VERSION,
        "feature_names": list(MOVE_FEATURE_NAMES),
        "n_samples": result.n_samples,
        "policy": result.policy.to_dict(),
        "training_metrics": {
            "loss": float(result.loss),
            "top1_agreement": float(result.top1_agreement),
            "n_samples": result.n_samples,
            "epochs": config.epochs,
            "learning_rate": config.learning_rate,
            "l2": config.l2,
        },
    }


def write_artifact(artifact: Dict[str, Any], output: Path | str = DEFAULT_OUTPUT) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2)
    return output


def train_from_file(
    input_path: Path | str,
    config: Optional[PolicyTrainConfig] = None,
    *,
    min_samples: int = MIN_SAMPLES,
) -> Tuple[Optional[PolicyTrainResult], str, List[PolicySample]]:
    """Load targets and train. Returns ``(result_or_None, reason, samples)``.

    ``result`` is ``None`` (with an explanatory ``reason``) when the corpus is
    missing / too small / produced a non-finite loss.
    """
    samples = load_policy_samples(input_path)
    if not samples:
        return None, f"policy: no usable rows in {input_path}", samples
    if len(samples) < min_samples:
        return (None,
                f"policy: only {len(samples)} decisions (need {min_samples}); "
                "collect more via `python -m training.policy_selfplay`",
                samples)
    result = train_move_policy(samples, config or PolicyTrainConfig())
    if not math.isfinite(result.loss):
        return None, f"policy: non-finite training loss ({result.loss})", samples
    return result, "policy: trained", samples


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Distil MCTS visit counts into a move policy.")
    p.add_argument("--input", default=str(DEFAULT_POLICY_CSV))
    p.add_argument("--output", default=str(DEFAULT_OUTPUT))
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--learning-rate", type=float, default=0.20)
    p.add_argument("--l2", type=float, default=1e-4)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--min-samples", type=int, default=MIN_SAMPLES)
    p.add_argument("--dry-run", action="store_true",
                   help="Train and print metrics but do not write the artifact.")
    args = p.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[policy_learning] Input not found: {input_path}")
        print("[policy_learning] Collect targets first via training.policy_selfplay.")
        return 1

    config = PolicyTrainConfig(
        learning_rate=args.learning_rate, epochs=args.epochs,
        l2=args.l2, temperature=args.temperature,
    )
    result, reason, samples = train_from_file(
        input_path, config, min_samples=int(args.min_samples)
    )
    if result is None:
        print(f"[policy_learning] {reason}")
        return 1

    artifact = build_artifact(result, config)
    print(f"[policy_learning] samples={result.n_samples} loss={result.loss:.5f} "
          f"top1_agreement={result.top1_agreement:.3f}")
    print(f"[policy_learning] feature_weights={artifact['policy']['feature_weights']}")

    if args.dry_run:
        print("[policy_learning] --dry-run: not writing artifact.")
        return 0

    out = write_artifact(artifact, args.output)
    print(f"[policy_learning] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
