# Nightly Training — Diagnosis (Phase 2)

_Diagnosed 2026-06-26 · state at generation 102. Evidence drawn from
`training/state/latest.json`, `training/state/history.jsonl`,
`training/state/ratings.sqlite`, `training/status.md`, and the code paths cited in
[`training_audit.md`](training_audit.md)._

**Verdict:** The champion has not improved because the learning loop has never closed
and the champion itself is weaker than a trivial baseline. The reported Elo movement is
noise, not skill. Four concrete root causes, in priority order:

## 1. The learning loop never closes — 0 promotions in 102 generations

Evidence (`latest.json`):
```
"champion": {"version": "gen0"}, "checkpoints": [],
"candidate_params": null, "last_eval": null,
"last_promoted_generation": null, "last_refit_generation": -1
```
- `data/champion_snapshots.csv` has **37,096 rows** (regression threshold is 200) and
  `data/td_trajectories.csv` has **1,611 rows** — the data to learn from exists.
- Yet no candidate was ever generated, evaluated, or promoted. `ratings.sqlite`
  `run_summary.promoted` is `0` for every row.

**Cause:** the candidate generation + evaluation block
(`nightly_run.py:300-347`) is gated behind the self‑play generation loop and an
`if … time.monotonic() < deadline` check, and is effectively never reached (see §2).

## 2. The candidate→eval→promote→report tail is starved/killed every run

Evidence: `training/status.md` and `training/reports/latest_diagnosis.md` are **frozen
at generation 1** (`run 20260622T003148Z`, Elo 1175, 2 games) while `latest.json` is at
**generation 102** (`run 20260625T212027Z`). The report writers
(`nightly_run.py:424-425`) run *after* candidate evaluation; if they had executed,
`status.md` would reflect gen 102. They have not run since gen 1.

**Cause:** `nightly_run.py:196` is an **unbounded generation loop** (no per‑generation
cap; ~23 min/generation in CI — gen 98 at 22:59 → gen 99 at 23:22). It consumes the
70 % generation budget and frequently the whole wall‑clock, so the post‑loop
candidate/eval/report code is skipped (deadline passed) or killed. The per‑generation
atomic `save_latest` (`:254`) still advances `generation`/`elo`, which is why state
moves forward while reports stall — masking the failure.

## 3. The Elo trajectory is noise, not skill

The champion config is **identical** across all 102 generations (§1), so any Elo change
is by definition not a skill change. Yet `history.jsonl` `champion_elo` over gens 98‑102:
```
1260.7 → 1252.3 → 1227.7 → 1264.1 → 1288.2     (±60 swing, fixed agent, 12 games/gen)
```
The headline figures in the brief — "1288.2 current, 1379.2 best, −91 gap, declining
−0.04 Elo/game" — are sampling variance from:
- tiny per‑evaluation game counts (12),
- a **rotating, unbenchmarked opponent set** (`select_challengers`), and
- Elo recomputed per generation from only that generation's games.

There is no fixed benchmark, so cross‑generation Elo is not comparable and "best
historical Elo" is just the luckiest sample.

## 4. The champion is weaker than the plain heuristic baseline

From `latest.json` `trueskill_ratings` (conservative = μ − 3σ):
```
champion : μ=36.40  σ=5.08  conservative=21.17   (1214 games)
heuristic: μ=52.74  σ=5.16  conservative=37.25   (1214 games)
```
The MCTS "champion" loses to the non‑search `heuristic` agent by ~16 μ. Its config
(`champion_params.params`) explains why:
```
rollout_policy = "random"           # rollouts are random, not heuristic
rollout_cutoff_depth = 5            # rollouts cut to 5 plies
adaptive_rollout_depth_base = 5
iterations_per_ms = 0.5             # 500 ms → ~250 iterations/move
```
This is a near‑crippled MCTS seeded from `config/key_findings_best_params.json`. Even a
perfectly working learning loop would be tuning evaluator weights on a broken search —
so the **base agent must be allowed to improve**, not just its weights.

## Secondary observations

- **No standalone candidate artifacts.** Candidates exist only transiently in memory;
  there is no `training/artifacts/candidates/` to inspect or re‑evaluate.
- **Vague failure messaging.** "No candidate was learned this cycle"
  (`status_report.py:141`, `email_summary.py:210`) hides which approach failed and why.
- **Seeds are reproducible but the opponent pool is not stable** — fixing seeds alone
  does not make Elo comparable while opponents rotate.
- **No rating‑uncertainty gating beyond TrueSkill σ** — promotion uses a Δμ margin but
  the report never surfaces win‑rate confidence bands, so a noisy +Elo could read as
  progress.

## What the redesign must fix (maps to implementation phases)

1. **Close the loop deterministically.** Generate candidates from existing data and
   evaluate them every run within a bounded budget — do not let an open‑ended self‑play
   loop starve learning. (Phase C orchestrator rewrite.)
2. **Make every failure explicit.** Each approach returns `created: bool` + a specific
   `reason`; the report tabulates them. (Phase B `Candidate` contract, Phase D report.)
3. **Evaluate against a fixed benchmark pool with fixed seeds** so deltas are
   comparable run‑to‑run. (Phase B `evaluation/benchmark_pool.py`, `head_to_head.py`.)
4. **Gate promotion on statistical evidence**, not a single Elo bump: head‑to‑head win
   margin + non‑overlapping win‑rate CI + no benchmark regression + min games/seeds.
   (Phase B `evaluation/promotion_gate.py`.)
5. **Allow champion replacement** by a stronger `baseline_mcts` seed
   (`rollout_policy="heuristic"`, more iterations) so the base agent can clear the
   sub‑heuristic floor. (Phase B `approaches/baseline_mcts.py`.)
