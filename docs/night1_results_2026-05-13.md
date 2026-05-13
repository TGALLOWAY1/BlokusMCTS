# Night 1 Results — Champion Gauntlet v1 + v2

**Date executed:** 2026-05-10 to 2026-05-13  
**Plan reference:** `docs/overnight_training_roadmap_2026-05-07.md`, Night 1

## Run Directories

| Gauntlet | Run ID | Config |
|---|---|---|
| v1 (40 games) | `arena_runs/20260510_133320_002f9dab/` | `scripts/arena_config_champion_gauntlet.json` |
| v2 (60 games) | `arena_runs/champion_gauntlet_v2/20260510_134844_e8621532/` | `scripts/arena_config_champion_gauntlet_v2.json` |

## Output Verification

| Run | `summary.json` | `games.jsonl` | `snapshots.csv` | `se_*` cols | Completed |
|---|---|---|---|---|---|
| v1 | ✓ | 40/40 games, 0 errors | 1272 rows | 8 | ✓ |
| v2 | ✓ | 60/60 games, 0 errors | 192 rows† | 8 | ✓ |

† V2 process crashed (SIGKILL, no stderr) at game 54; resumed via `--resume`. Game records and summary are complete for all 60 games. Snapshots only captured the 6 resumed games (192 rows) because `snapshots.csv` is written once at run-end, not incrementally. Combined snapshot total: **1464 rows** (expected 3200; gap = 1728 missing from v2 games 0–53).

## Gauntlet v1 Results (seed 20260503)

**Pool:** champion vs pool_l45_100ms vs pool_l9_partial_200ms vs pool_peer_500ms

| Agent | Overall WR | TrueSkill μ | μ−3σ |
|---|---|---|---|
| pool_peer_500ms | 52.5% (21/40) | 47.9 | 25.7 |
| **champion** | **37.5% (15/40)** | **38.2** | **16.3** |
| pool_l45_100ms | 7.5% (3/40) | 9.2 | −12.3 |
| pool_l9_partial_200ms | 2.5% (1/40) | 6.0 | −15.3 |

**Champion pairwise:**
- vs pool_l45_100ms: **31/40 = 77.5%** (beats decisively)
- vs pool_l9_partial_200ms: **33/40 = 82.5%** (beats decisively)
- vs pool_peer_500ms: **16/40 = 40.0%** (loses — pool_peer is stronger)

## Gauntlet v2 Results (seed 20260601)

**Pool:** champion vs pool_heuristic vs pool_l45_100ms vs pool_peer_500ms

| Agent | Overall WR | TrueSkill μ | μ−3σ |
|---|---|---|---|
| pool_peer_500ms | 49.2% (29/60) | 50.6 | 29.5 |
| **champion** | **38.3% (23/60)** | **41.3** | **20.4** |
| pool_heuristic | 11.7% (7/60) | 11.9 | −8.3 |
| pool_l45_100ms | 0.8% (0/60) | −2.5 | −23.3 |

**Champion pairwise (with Wilson-95 CI):**
- vs pool_heuristic: **39/60 = 65.0%** [52.4%, 75.8%]
- vs pool_l45_100ms: **52/60 = 86.7%** [75.8%, 93.1%]
- vs pool_peer_500ms: **26/60 = 43.3%** [31.6%, 55.9%]

## Interpretation

**Human-proxy (pool_heuristic) headline:** 65.0% WR, Wilson-95 CI lower bound = **52.4%** — below the 65% threshold required to defensively claim ≥70% target. This is expected: the roadmap requires Night 5 (4 seeds × 60 = 240 games) for the defensible headline claim. Night 1 establishes the baseline; 65% point estimate is promising.

**Pool_peer_500ms is the limiting agent.** Champion wins only 40% (v1) and 43% (v2) pairwise vs the near-peer. TrueSkill ranking is consistent across both gauntlets: pool_peer > champion > heuristic/weaker. Night 6 (full POOL_CATALOG arena) will place this in context.

**Snapshot gap.** V2 contributes only 192 snapshot rows vs the expected 1920. Night 3 refit will train on 1464 total rows (v1: 1272, v2: 192). This is still a meaningful dataset for refitting phase-weights, but is a known quality gap to flag.

## Portfolio Readiness Status After Night 1

| Gap from roadmap | Status |
|---|---|
| Gauntlets not executed | **RESOLVED** — both run, summary.json present |
| No human baseline | **BASELINE ESTABLISHED** — 65% WR vs pool_heuristic (60 games) |
| Statistical thinness | Partial — CI ±13% on heuristic match; Night 5 still required for claim |
| Snapshot coverage for refit | **DEGRADED** — 1464/3200 rows; document before Night 3 |

## Night 1 Status Block

```
Night executed: N1
Run id: 20260510_133320_002f9dab (v1), champion_gauntlet_v2/20260510_134844_e8621532 (v2)
Outputs present: yes — summary.json, games.jsonl, snapshots.csv in both dirs
Verification claim: N1: 40+60=100 games completed; se_* columns confirmed; champion 65% vs pool_heuristic
Verification result: PASS (with noted snapshot gap: 1464/3200 rows due to v2 crash+resume)
Promotion (Night 3 only): N/A
Follow-ups for human review:
  - V2 snapshots.csv has only 192 rows (6 games); 1728 rows from games 0–53 are unrecoverable.
    If Night 3 refit quality is insufficient, re-run v2 from scratch to get full 1920 rows.
  - Champion loses to pool_peer_500ms (~43% pairwise). Pool_peer is the binding constraint
    on champion strength — Night 3 refit may not change this without structural improvements.
  - Wilson-95 CI lower bound on heuristic WR is 52.4% (not 65%). Night 5 multi-seed run
    is required before any "beats humans" claim can be made.
```
