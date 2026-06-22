"""Durable nightly Blokus MCTS training pipeline.

This package turns the repo's existing (manual) self-improvement machinery into a
continuously-improving, *resumable* nightly training system. The cardinal rule —
the reason previous nightly attempts failed — is that **all training memory lives
on disk** under ``training/state/`` and every run loads, updates, and writes it
back so the next run continues seamlessly. Nothing of value lives only in process
memory, CI logs, or workflow state.

The heavy lifting (MCTS, arena, TrueSkill, evaluator-weight re-fitting, promotion
gates) is *reused* from the existing codebase — see :mod:`training.selfplay_core`.
This package adds the durable state layout, a never-overwritten SQLite rating
timeline, human-strength estimation, reports, and an email digest.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Repo root = parent of this package directory.
REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class TrainingPaths:
    """Absolute locations of every durable training artifact.

    Centralising path resolution means every module agrees on where state lives
    and tests can redirect everything to a tmp dir via :meth:`under`.

    Layout (canonical decisions, resolving the spec's path duplication):
      * ``training/status.md``                   -> canonical status report
      * ``training/reports/latest_diagnosis.md`` -> canonical diagnosis
      * ``training/state/reports/``              -> per-run *snapshots* of status.md
    """

    root: Path  # the repo root (or a tmp root in tests)
    state_dir: Path
    latest_json: Path
    champion_json: Path
    ratings_db: Path
    history_jsonl: Path
    checkpoints_dir: Path
    selfplay_runs_dir: Path
    state_reports_dir: Path  # state/reports/ (status snapshots)
    reports_dir: Path  # training/reports/ (latest_diagnosis.md lives here)
    status_md: Path
    diagnosis_md: Path

    @classmethod
    def under(cls, root: Path | str) -> "TrainingPaths":
        """Build paths rooted at ``root`` (``root/training/...``).

        Used both for the real pipeline (``root = REPO_ROOT``) and tests
        (``root = tmp_path``).
        """
        root = Path(root)
        training_dir = root / "training"
        state_dir = training_dir / "state"
        reports_dir = training_dir / "reports"
        return cls(
            root=root,
            state_dir=state_dir,
            latest_json=state_dir / "latest.json",
            champion_json=state_dir / "champion.json",
            ratings_db=state_dir / "ratings.sqlite",
            history_jsonl=state_dir / "history.jsonl",
            checkpoints_dir=state_dir / "checkpoints",
            selfplay_runs_dir=state_dir / "selfplay_runs",
            state_reports_dir=state_dir / "reports",
            reports_dir=reports_dir,
            status_md=training_dir / "status.md",
            diagnosis_md=reports_dir / "latest_diagnosis.md",
        )

    @classmethod
    def default(cls) -> "TrainingPaths":
        """Paths for the real repo (rooted at :data:`REPO_ROOT`)."""
        return cls.under(REPO_ROOT)

    def ensure_dirs(self) -> None:
        """Create every directory the pipeline writes into (idempotent)."""
        for d in (
            self.state_dir,
            self.checkpoints_dir,
            self.selfplay_runs_dir,
            self.state_reports_dir,
            self.reports_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
