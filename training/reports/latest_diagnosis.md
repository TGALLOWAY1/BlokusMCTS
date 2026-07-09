# Nightly Training Diagnosis

_Generated: 2026-07-09 00:43 UTC · run `20260708T192653Z` · generation 167_

**2 finding(s):**

- 🟠 **[warn] promotion_drought** — 27 generations since the last promotion (gen 140).
- 🔵 **[info] elo_variance** — Champion Elo swung 33 (peak 1392 → 1359) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1323, 1377, 1321, 1374, 1392, 1359]_
