# Phase 1 — Forensic Audit

- **Purpose:** determine what causes the plateau (champion frozen at gen140, 39-generation
  promotion drought), map the full state-to-result pipeline, classify component trust, and
  decide the repository strategy — before any implementation work.

- **Work completed:** full-repo exploration at baseline commit `cabe2dd`; component trust
  classification (`../AUDIT_INVENTORY.md`); data compatibility report (`../DATA_LINEAGE.md`);
  repo-strategy decision (D-001); risk ranking below.

## Pipeline trace (implementation owner for every step)

| Step | Owner |
|---|---|
| Game state | `engine/board.py` (grid + bitboard, incremental frontier), `engine/game.py` |
| Legal moves | `engine/move_generator.py::get_legal_moves` (frontier+bitboard fast path; naive+grid reference retained) |
| Agent configuration | `agents/registry.py`, `mcts/champion_profile.py`, `training/state/champion.json` → `mcts_lab/_common.resolve_agent` |
| Search selection | `mcts/mcts_agent.py::MCTSNode.ucb1_value` / `select_child` (UCT + optional prior/bias terms; every node maximizes the acting player) |
| Expansion | `MCTSNode.expand` (ordered untried moves; pass-node sentinel) |
| Evaluation / rollout | `_simulation` → rich-leaf TD / learned win-prob / rollout (`greedy_sample` default) → `_evaluate_all_players` static vector |
| Backup | `_backpropagation` (per-player maxⁿ vector; mover-credited) |
| Move selection | root max-visits (root-parallel merges child stats) |
| Self-play record | `training/selfplay_core.run_arena_inproc` → snapshots (`data/champion_snapshots.csv`), TD trajectories (`data/td_trajectories.csv`), policy targets (`training/policy_selfplay.py` → `data/policy_targets.csv`) |
| Training target → model update | `training/approaches/*` linear refits; `training/td_learning.py`; `training/policy_learning.py` (no neural net anywhere) |
| Checkpoint | candidate JSON artifacts (`training/artifacts/candidates/`), champion checkpoints (`training/state/checkpoints/`) |
| Candidate evaluation | `training/evaluation/{benchmark_pool,head_to_head,sequential}.py` + `analytics/tournament/arena_runner.py` |
| Promotion / rating update | `training/evaluation/promotion_gate.py` + `analytics/tournament/gauntlet.evaluate_promotion` (6-gate) → `training/state_store.save_champion`; TrueSkill/Elo → `training/ratings_db.py` (append-only) |

Every step has exactly one owner; no duplicate/diverging implementations remain in-tree (the
July 2026 cleanup removed FastMCTS et al.; internal redundant engine paths are deliberate
test references).

## Risk-ranked findings

1. **Search scaling is unproven post-fix (highest risk).** The prior audit (AUDIT_REPORT §8)
   measured effectively depth-1 search at nightly budgets (branching factor > iteration count)
   and fixed evaluator clamping — but no post-fix strength-vs-compute curve exists. If more
   compute does not buy strength, every learning phase is moot. → Phase 4 mandatory gate.
2. **Candidate generation appears exhausted.** All three roster approaches produce uniformly
   negative deltas vs the champion (EXP-000: ΔElo −60 to −117 over 48–56 paired games each);
   1 promotion in 41 runs. The plumbing (durable resume, SPRT, gate) audits clean — the
   *approach family* (small linear refits over small corpora, no held-out sets) is the suspect.
   → Phases 5–8 replace the candidate source; do not spend more compute on nightly iterations.
3. **The objective is the wrong game.** Default scoring is the non-standard house mode
   (+5/corner, +2/center; `engine/game.py:25-38`); the standard +5 monomino-last bonus is
   missing from `Board.get_score` (`engine/board.py:562`) despite AUDIT_REPORT §3.8 claiming
   scoring verified. Decided: standard scoring becomes the target (D-002). → Phase 2.
4. **Two champion sources of truth disagree.** Training champion `gen140`
   (`training/state/champion.json`) vs serving registry `v2 = key_findings_best`
   (`data/champion_registry.json`, what `agents/champion.py` and the web demo load). The
   validated champion is not what users play. → D-009 reserved; Phase 9.
5. **Determinism leaks (avoidable, codified in `../BENCHMARK_PROTOCOL.md`):** wall-clock budget
   mode; env flags read at import time (`engine/move_generator.py:63-88`); tree-parallel mode's
   documented races; within-game persistence of history/NST tables. Iteration budgets +
   single-thread gate games + fixed seeds neutralize all of these today.
6. **Learning hygiene gaps:** no held-out evaluation in any current fit; `policy_targets.csv`
   has no era/budget column (teacher rows mixed with old near-random 40 ms rows);
   `champion_snapshots.csv` is era-mixed. → Phase 7 validator + fresh manifested datasets.
7. **Minor:** Zobrist hash recomputed from scratch per call (perf only);
   `docs/00-overview/DOCUMENTATION_INDEX.md` dead links (hygiene);
   Elo pairwise decomposition in a 4-player game is a known approximation (TrueSkill already
   primary).

## Audit-hypothesis verdicts (from the governing master prompt §1)

| Hypothesis | Verdict |
|---|---|
| Backprop credit to wrong player | **Was real, fixed 2026-07-01** (commit `732bd9c`); regression suite `tests/test_maxn_backprop.py`; pre-fix data quarantined by era cutoffs |
| Workers not receiving intended config | Not observed; root-parallel workers get pickled board + derived seeds + full config (`mcts/parallel.py`); config-extraction test exists |
| Training data mixed across incompatible configs | **Partially real** — see risks 6; era tags exist for TD rows only |
| Multiple diverging MCTS implementations | No longer — single implementation since July 2026 cleanup |
| Expensive deep rollouts, little information | Plausible, unmeasured post-fix → Phase 5 |
| Large branching → shallow search / starved children | **Confirmed pre-fix at nightly budgets** (AUDIT_REPORT §8); post-fix magnitude unknown → Phase 4 |
| Compute not translating to strength | Unknown — the central question → Phase 4 gate |
| Elo over-trusted in a multiplayer, non-transitive setting | Mitigated (TrueSkill-primary, Wilson CIs, SPRT) but matchup-matrix retention/non-transitivity monitoring incomplete → Phase 9 |

- **Components changed:** none (audit only).
- **Tests added:** none.
- **Experiments run:** EXP-000 (baseline snapshot).
- **Unexpected findings:** missing monomino bonus contradicting AUDIT_REPORT §3.8; serving vs
  training champion split; policy_targets era-blindness.

- **Gate criteria:** every loop component has an identified owner and data path; major
  correctness risks documented; repository strategy explicitly decided; next phase can proceed
  without depending on unknown legacy behavior.
- **Gate result:** **PASS.**

- **Remaining risks:** risks 1–6 above are open by design — they are the work of Phases 2–9,
  now scheduled with explicit gates rather than unknowns.
- **Decision:** D-001 (stay in this repo), D-002 (standard scoring), D-003 (freeze), D-004
  (branch naming); open decisions D-005…D-011 reserved in `../DECISIONS.md`.
- **Next phase:** Phase 2 — trusted engine (standard scoring first; exact task list in
  `../HANDOFF.md`).

- **Reproduction commands:**
  ```bash
  python -m mcts_lab.checks
  python -m pytest tests/test_maxn_backprop.py tests/test_move_generation_equivalence.py tests/test_legality_bitboard_equivalence.py -q
  python - <<'EOF'
  import json; s=json.load(open('training/state/latest.json'))
  print(s['generation'], s['total_games'], s['last_promoted_generation'])
  EOF
  ```
- **Artifacts:** `../AUDIT_INVENTORY.md`, `../DATA_LINEAGE.md`, `../DECISIONS.md`,
  `../EXPERIMENT_LOG.md` (EXP-000).
