# Nightly Training — Approach-Comparison Framework

The nightly job is a **controlled approach-comparison framework**: every run
generates candidate agents from several learning/tuning strategies, evaluates the
created ones against a **fixed benchmark pool with fixed seeds**, and promotes a
candidate **only when it passes a statistical gate** — not because Elo bounced up
once. This replaced the previous "run many self-play generations and hope Elo
improves" loop, which never promoted a candidate in 102 generations and reported
matchup/seed noise as progress (see `reports/training_audit.md` and
`reports/training_diagnosis.md`).

## Run it

```bash
# Compare several approaches under a wall-clock budget (the nightly default).
python -m training.nightly_run \
  --approaches td,mcts_sweep,heuristic_tune,baseline \
  --games 100 --time-budget-minutes 45

# Dry run — prints the plan + each approach's created/reason verdict and writes
# NOTHING to tracked state (artifacts go to a temp dir).
python -m training.nightly_run --dry-run --approaches td --games 8

# 'all' expands to the full roster (adds the hybrid approach).
python -m training.nightly_run --approaches all --games 100 --time-budget-minutes 45
```

The legacy self-play generation loop is still available when `--approaches` is
omitted (`python -m training.nightly_run --hours 5 --games-per-arena 12`).

## Architecture (separation of concerns)

```
training/
  approaches/          # candidate generation — one Candidate per strategy
    base.py            #   Candidate contract + artifact schema/validation/IO
    baseline_mcts.py   #   stronger search seed (heuristic rollouts, more iters)
    td_learning.py     #   temporal-difference evaluator re-fit
    heuristic_tuning.py#   regression re-fit of Layer-6 weights
    mcts_param_sweep.py#   search-parameter variant
    hybrid_td_mcts.py  #   strong search + TD-learned evaluator
  evaluation/          # measurement + promotion
    benchmark_pool.py  #   fixed, versioned opponent roster + fixed seeds
    head_to_head.py    #   pooled 4-agent battery vs the pool (per candidate)
    promotion_gate.py  #   statistical gate (H2H + Elo/TrueSkill Δ + CI + min games)
    rating_analysis.py #   noise-aware trajectory summary (is the move real?)
    report.py          #   approach_comparison record + markdown
  nightly_run.py       # orchestrator (run_approaches) + CLI + promotion/persistence
  reports/             # training_audit.md, training_diagnosis.md, approach_comparison.md
  artifacts/candidates/# <approach>_<run_id>.json — every candidate (created or not)
```

Heavy lifting (MCTS, arena, TrueSkill, Elo, the conservative gate) is **reused**
from `analytics.tournament.*` and `training.selfplay_core` / `training.experiments`.

## The Candidate contract

Each approach returns one `Candidate` with `created: bool` and a **specific**
`reason`. A failed candidate never says "No candidate was learned this cycle" — it
says exactly why, e.g. `td: only 140 valid rows in 'late' phase (need 200)` or
`hybrid: no TD weights artifact at …`. Every candidate (created or not) is written
to `training/artifacts/candidates/<approach>_<run_id>.json` and validated before it
can reach the arena.

## The promotion gate

A candidate is promoted only if **all** hold (`evaluation/promotion_gate.py`):

- the repo's conservative 6-gate decision passes (ranked #1 vs champion + pool,
  beats runner-up, Δμ margin, Wilson win-rate, ≥2 seeds, ≥40 games),
- it **beats the champion head-to-head** (strictly more wins),
- a **positive Elo delta** over the champion,
- a **positive TrueSkill μ delta** (≥ margin) over the champion.

Because the benchmark pool includes the plain `heuristic` agent (which currently
beats the weak champion), a candidate must be genuinely strong — not merely better
than a broken champion — to win.

## Reporting

- `training/status.md` and the email both render the **Approach Comparison table**
  (Approach · Created · Games · Win% vs Champ · Elo Δ · TrueSkill Δ · Promoted ·
  Reason) plus a noise-aware Elo-trajectory line.
- `training/reports/approach_comparison.md` has the full per-approach detail.
- `training/reports/elo_trend.png` adds a rolling average, best-historical line,
  human target, and promotion markers.

## Durability

State still resumes from disk every run: `state/latest.json`, `state/champion.json`,
`state/ratings.sqlite`, `state/history.jsonl`, `state/checkpoints/`. Ratings/history
are updated **only after a valid evaluation**; dry runs never touch tracked state.
