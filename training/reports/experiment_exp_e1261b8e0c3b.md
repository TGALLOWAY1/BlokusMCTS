# Experiment Report — `exp_e1261b8e0c3b`

_TD vs regression candidate comparison_

## Setup

- **Date:** 2026-06-25T03:02:41.481580+00:00
- **Code version:** `7db06a9`
- **Seeds:** [201, 202, 203, 204] (4)
- **Games per arena/seed:** 2
- **Total pooled games:** 40
- **Thinking time:** 50 ms
- **Competitors:** champion, heuristic, random, regression, td

## Ranking

| # | Agent | Win% (95% CI) | Avg rank | Score margin | TrueSkill μ±σ | Elo | W/L/D |
|---|---|---|---|---|---|---|---|
| 1 | `heuristic` | 51.6% (35–68) | 1.62 | -1.8 | 48.27±7.54 | 1442 | 16/15/1 |
| 2 | `regression` | 39.1% (24–56) | 1.88 | -2.3 | 38.37±7.44 | 1322 | 12/19/1 |
| 3 | `td` | 25.0% (13–42) | 2.31 | -9.1 | 28.32±7.37 | 1277 | 8/24/0 |
| 4 | `champion` | 9.4% (3–24) | 2.59 | -13.6 | 22.45±7.30 | 1157 | 3/29/0 |
| 5 | `random` | 0.0% (0–11) | 3.88 | -34.4 | -11.04±7.41 | 803 | 0/32/0 |

## Rank distribution

| Agent | 1st | 2nd | 3rd | 4th |
|---|---|---|---|---|
| `heuristic` | 17 | 10 | 5 | 0 |
| `regression` | 13 | 10 | 9 | 0 |
| `td` | 8 | 10 | 10 | 4 |
| `champion` | 3 | 12 | 12 | 5 |
| `random` | 0 | 0 | 4 | 28 |

## Head-to-head: candidate vs baseline

- **Candidate:** `td` · **Baseline:** `regression`
- **Direct record (cand/base/tie):** 7/17/0
- **Win rate:** candidate 25.0% vs baseline 39.1%
- **Avg rank:** candidate 2.31 vs baseline 1.88
- **TrueSkill Δμ:** -10.051
- **Elo Δ:** -45

### Recommendation

**INCONCLUSIVE — differences within noise (win-rate CIs overlap); collect more games/seeds before deciding.**

## Reproducibility

Re-run with the saved manifest (`manifest.json`). Per-game seeds derive deterministically from the manifest seeds and arena index, so the same manifest reproduces the same games.

Competitor config hashes:

- `champion`: `e1651cde36c8` (current)
- `heuristic`: `8a0201e92c05` (baseline)
- `random`: `c3e415fc6a80` (baseline)
- `regression`: `0b1d79b9b339` (regression)
- `td`: `4570a490c275` (temporal_difference)
