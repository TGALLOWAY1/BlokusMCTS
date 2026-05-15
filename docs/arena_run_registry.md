# Arena Run Registry

Per-run catalogue of what each recent arena run is good for and what it
cannot prove. Authoritative companion to `docs/CHAMPION_PROGRESSION.md`.

## Status labels

- `diagnostic_failure` — the run revealed that a candidate is worse than
  expected. Data is valid; the "this agent is strong" framing is not.
- `candidate_validation` — the run was structured as a promotion gate.
  Includes pass/fail.
- `validated_baseline` — pool anchor with stable TrueSkill across runs;
  safe to reuse as a reference opponent.
- `superseded` — replaced by a later, higher-coverage run with the same
  agents and pool.
- `invalid` — bad config or run integrity issue; do not use for any
  claim.
- `planned` — config exists, run has not been executed yet.

## Runs

| Run / PR | Agents | Games | Main result | Status | Reusable for | Not reusable for |
|---|---|---|---|---|---|---|
| `arena_runs/20260507_034719_002f9dab/` (PR #146) | `champion_v1`, `pool_l45_100ms`, `pool_l9_partial_200ms`, `pool_peer_500ms` | 40 | `pool_peer_500ms` 52.5% WR vs `champion_v1` 37.5% WR; pairwise champ-vs-peer 16–24. | `diagnostic_failure` | Regression evidence vs v1; TrueSkill anchor for `pool_peer_500ms` (μ≈47.9); `se_*` snapshot rows (~1,272). | Any "champion is strong" claim; promotion to `v2`. |
| `arena_runs/20260508_033725_002f9dab/` (PR #147) | Same as above | 40 | Identical winner ordering; same v1 underperformance. | `diagnostic_failure` (repro of #146) | Cross-seed consistency check for the v1 loss; additional `se_*` rows. | Independent evidence — same agents, same outcome class. |
| `arena_runs/20260510_133320_002f9dab/` (PR #148) | Same as above | 40 | Same outcome class — v1 loses to peer. | `diagnostic_failure` (repro of #146/#147) | Same as above. | Same as above. |
| `arena_runs/champion_gauntlet_v2/20260508_060102_e8621532/` (PR #146/#147) | `champion_v1`, `pool_heuristic`, `pool_l45_100ms`, `pool_peer_500ms` | 60 | v1 vs heuristic pairwise 39–17 (WR 65.0%); v1 vs peer 26–34 (loses). | `diagnostic_failure` (heuristic gap promising; peer gap is the headline finding) | Wilson-95 CI on v1 vs `pool_heuristic` (LB = 52.4%); `se_*` rows for refit. | Headline "beats humans" claim — CI LB below 0.65; v1 strength claim — peer beats it. |
| `arena_runs/champion_gauntlet_v2/20260510_134844_e8621532/` (PR #148) | Same as above | 60 | Mid-run crash + resume; outcome class matches earlier v2 runs. | `diagnostic_failure` (with snapshot loss — see note) | Game-result aggregation (`games.jsonl` complete); cross-seed peer-loss confirmation. | Snapshot-driven refit at full coverage: only ~192 of expected 1,920 snapshot rows survived the crash. |
| `arena_runs/champion_gauntlet_v2/20260514_024853_e8621532/` (PR #148) | Same as above | 60 | `pool_peer_500ms` μ−3σ=29.45 vs `champion_v1` μ−3σ=19.65 (Δμ≈10 to peer). | `diagnostic_failure` (the definitive v1-loses run) | TrueSkill anchors for whole pool (`pool_peer`, `pool_heuristic`, `pool_l45`); regression evidence cited in the roadmap. | Promotion of v1; any "champion holds up to peers" framing. |
| Night-1 champion reset (planned) | `champion_minimal`, `champion_v1`, `pool_peer_500ms`, `pool_heuristic` | 60 (4 smoke first) | TBD | `planned` / `candidate_validation` (gate: Δμ ≥ 0.5 + positive pairwise on `champion_minimal` vs `champion_v1`) | Promotion to `champion_v2` *if* the gate passes; otherwise becomes the next `diagnostic_failure` row in this table. | Headline "beats humans" — that is Night 4, not Night 1. |

Config for the planned Night-1 run:
`scripts/arena_config_night1_champion_reset.json`.

## How to update this registry

When a new run completes:

1. Add a row with the run directory, agents, game count, the headline
   pairwise result, and the appropriate status label.
2. Fill in **Reusable for** with concrete artifacts: anchors, snapshot
   counts, regression evidence — not vague claims.
3. Fill in **Not reusable for** with the claims this run cannot
   support. This is the most important column: it is what keeps a future
   reader (and future Claude) from reusing diagnostic data as if it were
   a champion proof.
4. Cross-link the run from `docs/CHAMPION_PROGRESSION.md` if it changes
   the lineage status.
