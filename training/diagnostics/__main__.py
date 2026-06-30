"""CLI entry for deterministic training diagnosis."""
from __future__ import annotations

from training import TrainingPaths, ratings_db, state_store
from training.diagnostics import write_diagnosis


def main() -> int:
    paths = TrainingPaths.default()
    paths.ensure_dirs()
    conn = ratings_db.connect(paths.ratings_db)
    try:
        state = state_store.load_latest(paths)
        findings = write_diagnosis(paths, conn, state)
        print(f"wrote {paths.diagnosis_md} ({len(findings)} finding(s))")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
