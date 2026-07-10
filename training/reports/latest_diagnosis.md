# Nightly Training Diagnosis

_Generated: 2026-07-10 20:22 UTC · run `20260710T150635Z` · generation 174_

**2 finding(s):**

- 🟠 **[warn] promotion_drought** — 34 generations since the last promotion (gen 140).
- 🔵 **[info] elo_variance** — Champion Elo swung 121 (peak 1405 → 1284) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1396, 1405, 1361, 1358, 1385, 1284]_
