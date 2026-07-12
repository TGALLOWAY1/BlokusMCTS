# Nightly Training Diagnosis

_Generated: 2026-07-12 00:16 UTC · run `20260711T190001Z` · generation 179_

**2 finding(s):**

- 🟠 **[warn] promotion_drought** — 39 generations since the last promotion (gen 140).
- 🔵 **[info] elo_variance** — Champion Elo swung 30 (peak 1418 → 1389) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1284, 1394, 1271, 1418, 1408, 1389]_
