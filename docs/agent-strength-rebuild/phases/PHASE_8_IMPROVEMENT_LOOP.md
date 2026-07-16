# Phase 8 — Prove the Search-and-Learning Improvement Loop (in progress)

- **Purpose:** demonstrate the cycle better data → better evaluator → stronger search →
  better data, with evidence on every arrow.

- **Status of the gates:**
  | Gate | Status | Evidence |
  |---|---|---|
  | A — search improves the raw policy | **PASS (standing)** | every scaling experiment: search agents ≫ the raw heuristic/ordering policy (e.g. EXP-007: +26.9 pts, p<0.0001) |
  | B — new model alone vs old model alone | Covered via C's training half | v2 beats v1 on held-out teacher games (R² 0.234 vs −0.384; pairwise 0.678 vs 0.658) |
  | C — new model improves search at equal budget | **PARTIAL — MORE EVIDENCE REQUIRED** | EXP-007: vm2 57.5% vs vm1 42.5% first-place, rank 1.35 vs 1.50, but paired diff +2.25 (p=0.596) at n=20 |
  | D — generation N+1 > N (full protocol) | Not yet run | follows a passed C |

- **Work completed (this turn of the loop):**
  1. Phase 7 corpus (`data/teacher_dataset_v1`, validated) → v2 training
     (`training/experiments/value_model_v2.py`, game-level held-out split, data-mix as the
     controlled variable).
  2. **Distribution-shift finding (the training half's decisive result):** the frozen v1
     evaluator is badly miscalibrated on stronger teacher play (held-out R² −0.384,
     MAE 11.8 pts); retraining on teacher data restores calibration (0.234 / 7.27). The
     re-anchoring mechanism the loop depends on is real and works.
  3. EXP-007 direct same-table arena: no regression, positive direction, not significant.

- **Honest bottleneck analysis:** ordering quality — what argmax move selection actually
  consumes — moved only 0.658 → 0.678, consistent with the EXP-004 feature ceiling
  (~0.68 pairwise on `rich_blokus_v1`). Calibration improved a lot; ordering barely.
  One generation of teacher data cannot push through a representation ceiling, and more
  games/data alone are §20 default escapes, not fixes.

- **Gate result (C):** **PARTIAL — MORE EVIDENCE REQUIRED.**
- **Next distinguishing work:** the Phase 6 representation upgrade —
  (a) extend the feature set (the rich-feature machinery is append-only versioned;
  candidates: opponent-interaction, territory-potential, endgame-parity features), or
  (b) the move-level candidate-scoring evaluator (master plan §13's preferred direction).
  Acceptance: held-out pairwise ordering must clear the 0.68 ceiling decisively BEFORE
  spending arena compute; then gate C re-runs on the fixed protocol.
- **Loop assets now standing:** validated teacher-data pipeline (regenerable at will),
  v2 evaluator artifact (best current, calibrated), fixed cheap gates (ladder + direct
  table), saturation-knee metric for evaluator quality.

- **Reproduction commands:**
  ```bash
  python -m training.experiments.value_model_v2
  python -m training.experiments.search_scaling \
      --agents-json training/experiments/exp007_agents.json \
      --label exp007_vm2_vs_vm1 --games-per-seed 10 --seeds 20260620,20260621
  ```
- **Artifacts:** EXP-007 run dirs; `training/artifacts/value_models/v2/`;
  `../EXPERIMENT_LOG.md` EXP-007.
