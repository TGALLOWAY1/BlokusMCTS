# Continuous-training handoff — make the nightly loop actually improve the agent

**Audience:** the next coding-agent session.
**Goal (from the repo owner):** the nightly cycle should produce *gradual, real
strength gains* over days/weeks. Games must not be played pointlessly — every
run should either move the champion forward or produce evidence that measurably
narrows what to try next.

**Status quo it must replace:** the champion has been **frozen at `gen140`
since 2026-07-02**. The reported Elo wiggles (~1307–1398) are *measurement
noise around an unchanging agent*, not learning. This document explains exactly
why, and gives a concrete, prioritized plan to fix it.

Read `AUDIT_REPORT.md` §7 and §8 first — this file assumes that context.

---

## 1. Why the agent is frozen (the core defect)

The nightly workflow (`.github/workflows/nightly-mcts-training.yml`) runs
`python -m training.nightly_run --approaches mcts_sweep,progressive_widening,heuristic_tune
--sequential-eval …`. That dispatches to **`run_approaches()`**
(`training/nightly_run.py:827`), **not** the legacy self-play loop `run()`
(`training/nightly_run.py:174`).

The critical fact:

> **`run_approaches()` generates no fresh game experience.** It never calls
> `run_generation` / `accumulate_snapshots` / `collect_trajectories`. Only the
> *unused* legacy `run()` does (`nightly_run.py:233`).

So each night the loop:

1. Builds candidates from three approaches, **none of which learn from new data**:
   - `mcts_sweep` — just sets `exploration_constant` to a fixed grid point (no data).
   - `progressive_widening` — a search-param toggle (no data).
   - `heuristic_tune` — re-fits the Layer-6 evaluator on
     `data/champion_snapshots.csv` … which is a **frozen 44,832-row corpus of
     pre-`gen140` (broken-search) games** (`scripts/champion_loop.py:55,383`).
2. Plays a screen of champion-vs-candidate games (the SPRT).
3. Finds no candidate that beats the champion → no promotion → commits an
   unchanged champion and an Elo re-rating that is pure noise.

There **is** a separate `policy_selfplay` collection step in the workflow
(visit-count targets at a *40 ms* thinking budget), but it feeds the `policy`
approach, which is **held out of the default roster** (§7.1) — so those games
mostly don't feed anything that runs.

**Net:** the loop is a candidate *comparison* harness with the generators
switched off. It cannot ratchet because nothing produces experience stronger
than the current champion, and the one learning candidate (`heuristic_tune`)
trains on stale, weak-search data.

### Secondary reasons a real gain wouldn't be detected even if produced

- **Candidate roster collapsed onto the champion** (§7.1): `baseline` is
  byte-identical to the champion and self-retires; `policy` self-distils back
  into the fixed heuristic. Most "candidates" are near-copies → coin-flip
  screens.
- **Eval variance** (§7.2): the fixed-N gate re-rates from a fresh K=32 Elo
  tracker (±72–90 Elo noise on a frozen agent). The `--sequential-eval` SPRT
  fixes the *screen* variance, but at `elo1=70` and ~4 min/game on a 2-core
  GitHub runner, candidates keep hitting **inconclusive** at ~26–29 games
  (`training/state/latest.json`).
- **Runner budget** (§7.3): 2 cores, 350-min job cap, forced 100 ms thinking.
  This is the binding constraint on games/night and per-game strength.

---

## 2. What this PR already fixed (build on it, don't redo)

- **Search actually works now** (`AUDIT_REPORT.md` §8.2): the state evaluator
  no longer returns 0.0 for most positions (tanh squash), rollouts are ~6×
  cheaper (`LegalMoveGenerator.sample_legal_moves`), the transposition table no
  longer freezes stochastic rollouts, and the learned-leaf reward is on-scale.
  Measured: the same champion config went **72.9% → 89.6%** vs the pool (§8.5).
- **Data-generation infrastructure exists and is correct** but is **not wired
  into the nightly loop**:
  - `training/teacher_roster.py` — builds a roster from the **registry
    champion** at a named search profile (default `teacher`).
  - `mcts/search_profiles.py` — `fast/balanced/strong/teacher` budgets;
    `teacher` = 1200 iters + progressive widening (needed because early-game
    branching factor > budget, so a non-widened tree never reaches depth 2).
  - `training/td_selfplay.py` / `training/policy_selfplay.py` — now collect from
    the registry champion, champion-seats-only, with provenance
    (`gen140@teacher:1200`) stamped per row.
  - `training/diagnostics/search_quality.py` — measures search depth / label
    stability across budgets. **This is your before/after instrument.**
  - A fresh 732-row teacher-budget corpus is committed at
    `data/td_trajectories.csv`; `rich_leaf` / `td` train on it.
- **`rich_leaf` approach** deploys the 45-feature TD value at MCTS leaves. It
  screened *tied* with the champion on 24 games (§8.5) — competitive, not yet a
  clear beat. More/better data is the lever, not more code.

---

## 3. The plan — in priority order

Each workstream has an **acceptance test** so "done" is measurable, not vibes.
Do them roughly in order; #1 is the one that unblocks continuous improvement.

### P1 — Regenerate fresh experience every cycle (this is the fix)

The loop must produce new games from the *current* champion at a **teacher
budget stronger than the champion's own play budget**, then train the learning
candidates on that fresh data. Expert iteration: teacher (deep search) labels →
student (evaluator / policy) fits → student sharpens next teacher.

**Do:**
- In `run_approaches()` (`training/nightly_run.py:827`), before candidate
  generation, add a data-refresh step that:
  - Collects TD trajectories via `training.td_selfplay.collect_trajectories`
    using `training.teacher_roster.teacher_roster("teacher")` (or `"strong"` if
    the runner can't afford `teacher`), appending to `data/td_trajectories.csv`.
  - Optionally also grows `data/champion_snapshots.csv` from the *fixed-search*
    champion (the current corpus is pre-fix and should be **rotated out**, not
    appended to — see P4).
  - Hard-cap it on wall-clock (like the existing 15-min policy step) so it never
    starves eval.
- Make `heuristic_tune` / `td` / `rich_leaf` train on the **refreshed** data.
- Keep the champion registry write path untouched — promotion stays gated.

**Budget note:** the 2-core Actions runner probably can't both regenerate data
*and* run a meaningful SPRT in 315 min. Prefer **splitting the cadence**: a
data-generation job (or a dedicated box, §7.3) that commits fresh
`data/*.csv`, and the Actions job consuming it for train+eval. Document whatever
split you choose in the workflow file.

**Acceptance:** after a cycle, `data/td_trajectories.csv` contains rows whose
`agent_version` is the *current* champion + profile (not a stale gen), and the
`td`/`rich_leaf` candidate artifacts report `source_rows` from the new corpus.
`training.diagnostics.search_quality` on the teacher profile shows tree depth
≥ 3 at mid-game plies (proof the labels come from real search, not depth-1).

### P2 — Make the teacher genuinely stronger than the student

A student trained on and evaluated at the *same* budget as its teacher can't
exceed it. The point of expert iteration is teacher > student.

**Do:**
- Generate labels at `teacher` (1200 iters + widening); evaluate/play candidates
  at `balanced`/`strong`. The asymmetry is the whole mechanism.
- For the `policy` approach specifically: bump its collection budget well above
  the current **40 ms** (that's near-random) and only re-enable it in the roster
  once its move-policy model is richer than the fixed heuristic it currently
  reproduces (§7.3). Until then leave it out — it's a no-op.

**Acceptance:** a candidate trained on teacher-budget data beats the same
candidate trained on champion-budget data, head-to-head, on the fixed seeds.

### P3 — Give the SPRT enough power to promote small gains

Even a real +30 Elo candidate currently can't clear the screen in the games the
runner affords.

**Do (pick the cheapest sufficient subset):**
- Lower `--sprt-elo1` from 70 toward ~30–40 once data quality is fixed (chase
  smaller true edges). Tune `--sprt-max-games` to the runner budget.
- Reduce per-game cost so more paired games fit: the ~6× faster rollouts from
  this PR already help; consider a lower eval `thinking_time_ms` *for the
  screen only* (the paired SPRT cares about game count, not per-move strength).
- Parallelize the arena across the runner's cores (the sequential loop is
  single-process today) — or move eval off Actions (§7.3).

**Acceptance:** a synthetic candidate known to be ~+50 Elo (e.g. champion at 2×
iterations) is *accepted* by the SPRT within the nightly budget. If it can't,
the gate is still too weak — fix that before trusting null results.

### P4 — Retire the poisoned snapshot corpus

`data/champion_snapshots.csv` (44,832 rows) was generated by the broken-search
champion; `heuristic_tune` fits it every night. Fixing the search (this PR)
makes it stale, not just old.

**Do:** archive it, regenerate from the fixed-search champion (P1), and have
`heuristic_tune` fit the fresh corpus. Keep a row cap / recency window so it
tracks the *current* champion rather than averaging over all history.

**Acceptance:** `heuristic_tune`'s candidate, evaluated on fixed seeds, is ≥ the
champion (today it lands ~45%, i.e. *below* — a symptom of the stale corpus).

### P5 — Add exploration to self-play (stop imitating the champion)

Once P1–P4 land, the remaining ceiling is that self-play only ever sees the
champion's own lines.

**Do:** root temperature / Dirichlet noise at the root during data-generation
games, and a small population of past checkpoints
(`training/state/checkpoints/`) as opponents so the learning signal is "beat a
diverse field," not "imitate the champion." Keep this **off** for evaluation
games (eval must stay deterministic/paired).

**Acceptance:** trajectory diversity (distinct board states / entropy of visited
positions) increases vs the no-noise baseline, and a candidate trained on the
diversified corpus doesn't regress head-to-head.

---

## 4. File & entry-point map

| Concern | Where |
|---|---|
| Nightly orchestration (active mode) | `training/nightly_run.py:827` `run_approaches()` |
| Nightly orchestration (legacy self-play, currently unused) | `training/nightly_run.py:174` `run()` → `sc.run_generation` |
| Workflow (cron, args, budgets) | `.github/workflows/nightly-mcts-training.yml` |
| Candidate approaches | `training/approaches/*.py` + registry `__init__.py` |
| Self-play data (TD) | `training/td_selfplay.py`, corpus `data/td_trajectories.csv` |
| Self-play data (snapshots, for regression refit) | `scripts/champion_loop.py` (`SNAPSHOT_CSV`), corpus `data/champion_snapshots.csv` |
| Policy visit-count targets | `training/policy_selfplay.py`, corpus `data/policy_targets.csv` |
| Teacher roster / search profiles | `training/teacher_roster.py`, `mcts/search_profiles.py` |
| Evaluation (fixed-N) | `training/evaluation/head_to_head.py`, `mcts_lab/eval.py` |
| Evaluation (sequential SPRT — the good one) | `training/evaluation/sequential.py` |
| Promotion gate | `training/evaluation/promotion_gate.py`, `analytics/tournament/gauntlet.py` |
| Champion registry (single source of truth) | `training/state/champion.json` (writer: `mcts_lab.promote` only) |
| Search-quality diagnostic | `training/diagnostics/search_quality.py` |
| Manual loop CLIs | `mcts_lab/{self_play,train,promote,eval,checks}.py` |

---

## 5. How to know it's working (measure, don't hope)

- **The signal of improvement is a PROMOTION**, i.e. `training/state/champion.json`
  `version` advancing past `gen140`, with the new champion checkpointed under
  `training/state/checkpoints/`. **Not** the Elo number — that is noise around a
  frozen agent until a promotion happens (§7.2).
- Track the **champion-vs-fixed-pool win-rate on fixed seeds** across
  generations (`mcts_lab.eval --agents champion,heuristic,random --seeds
  20260620,20260621`). A ratcheting champion should show a rising, low-variance
  trend here; noise won't.
- Use `training/diagnostics/search_quality.py` to confirm training labels come
  from real search (depth ≥ 3 mid-game), not depth-1.
- Every run should be attributable: if a candidate was rejected, the report
  should say *why* (SPRT accept_h0 vs inconclusive vs failed conservative gate),
  so a night with no promotion still tells you something.

---

## 6. Traps — do NOT do these

- **Do not chase the Elo number.** It's ±90 noise on a frozen agent. Watch
  promotions and fixed-seed win-rate.
- **Do not re-normalize the reward scale to [0,1].** It was tried this session
  and measured a **72.9% → 29.2%** champion regression — the pinned
  `exploration_constant` is calibrated to the O(100) scale (`AUDIT_REPORT.md`
  §8.2). If you want to change the reward scale, re-tune exploration *in the
  same change* and gate it through `mcts_sweep`, never as a bare default.
- **Do not hand-edit `training/state/champion.json`.** Only `mcts_lab.promote`
  (or the gated nightly path) may write it (`CLAUDE.md`).
- **Do not trust a null SPRT result until P3 is done.** "No candidate beat the
  champion" currently also means "the gate can't detect small gains at this
  budget." Prove the gate can accept a known-good candidate first.
- **Do not append to the stale snapshot corpus** — rotate it (P4).
- **Do not add a big RL/neural system.** The linear evaluator + move policy are
  adequate; the bottleneck is fresh data + measurement power, not model capacity
  (`CLAUDE.md`, Phase-7 constraints in the original task).

---

## 7. Suggested first move for the next session

Implement **P1** end-to-end behind a workflow flag (`--refresh-data` /
`--teacher-profile`), prove the acceptance test on a *local* short run
(`mcts_lab.self_play` + `mcts_lab.train --approaches rich_leaf,heuristic_tune` +
`mcts_lab.eval`), then wire it into `run_approaches()` and update the workflow.
That single change converts the nightly job from "compare the champion to copies
of itself on stale data" into an actual expert-iteration loop — the
prerequisite for every other gain here.
