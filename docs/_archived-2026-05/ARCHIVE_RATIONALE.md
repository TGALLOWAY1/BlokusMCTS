# Archived Documentation — 2026-05

These docs were moved out of the active `docs/` tree during the May 2026
documentation-infrastructure pass. They are **preserved, not deleted** (moved
with `git mv`, full history intact) because they remain useful for the audit
trail. None of them describes current product behavior.

Two reasons for archival:

- **Stale (RL-era v1):** describes the reinforcement-learning environment the
  project began as, before it pivoted to an MCTS-centered platform. The RL code
  itself was archived to `archive/rl/` on 2026-03-06. These docs reference
  training scripts (`training/trainer.py`, `training/evaluate_agent.py`), PPO /
  MaskablePPO, PettingZoo/Gymnasium, and training-history UI that no longer
  exist on the mainline.
- **Historical (superseded / point-in-time):** dated experiment results or
  roadmaps that have been superseded by a canonical doc. The canonical
  champion-status narrative is `docs/CHAMPION_PROGRESSION.md`; the per-run
  catalogue is `docs/arena_run_registry.md`.

| Archived file | Category | Reason |
|---|---|---|
| `evaluation.md` | Stale (RL-era) | RL agent evaluation protocol (`training/evaluate_agent.py`, PPO checkpoints, MongoDB `EvaluationRun`, training-history UI). Links to docs that no longer exist. |
| `engine/env_no_legal_moves.md` | Stale (RL-era) | Audit of the RL environment's no-legal-moves / dead-agent handling (PettingZoo AEC, MaskablePPO). Superseded by `docs/engine/win_detection_notes.md`'s replacement and current engine behavior. |
| `engine/win_detection_notes.md` | Stale (RL-era) | Win-detection audit framed around RL training callbacks and MongoDB logging. Engine win detection is now covered by the engine code and `docs/engine/move-generation-optimization.md` context. |
| `engine/move-generation-notes.md` | Historical | Pre-M6 baseline description of the naive move generator. Superseded by `docs/engine/move-generation-optimization.md`. |
| `overnight_training_roadmap.md` | Historical | Undated 30-day roadmap; banner already marked it superseded by `CHAMPION_PROGRESSION.md`. |
| `overnight_training_roadmap_2026-03-30.md` | Historical | Dated roadmap; explicitly superseded by `CHAMPION_PROGRESSION.md`. |
| `overnight_training_roadmap_2026-05-07.md` | Historical | Dated roadmap; explicitly superseded by `CHAMPION_PROGRESSION.md`. The live operational plan is `docs/overnight_training_roadmap_2026-05-14.md` (kept active). |
| `night1_results_2026-05-13.md` | Historical | Night-1 gauntlet result snapshot; superseded by `CHAMPION_PROGRESSION.md`. |
| `night1_results_2026-05-14.md` | Historical | Duplicate Night-1 gauntlet result snapshot (different run dates); superseded by `CHAMPION_PROGRESSION.md`. |
| `overnight_arena_critical_findings.md` | Historical | Dated 300-game arena findings (2026-04-01/02); conclusions folded into `KEY_FINDINGS.md` and the layer reports in `archive/reports/`. |
| `trueskill_final.md` | Historical | Dated TrueSkill leaderboard snapshot referencing now-retired agent variants. Current ratings live per-run in `arena_runs/*/summary.json`. |
| `layer3_validation_report.md` | Historical | Dated Layer-3 ablation snapshot (2026-03-25); findings summarized in `KEY_FINDINGS.md` / root `README.md`. Full layer reports are in `archive/reports/`. |
| `audits/mcts_audit_remediation_plan.md` | Historical | Pre-implementation remediation plan; replaced by `docs/audits/mcts_audit_remediation_summary.md` (kept active). |

To read any archived doc in its original context, use git history (the moves
preserved it) or open it here directly.
