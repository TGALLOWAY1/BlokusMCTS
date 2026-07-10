# Nightly Training Diagnosis

_Generated: 2026-07-10 14:50 UTC · run `20260710T093326Z` · generation 173_

**2 finding(s):**

- 🟠 **[warn] promotion_drought** — 33 generations since the last promotion (gen 140).
- 🔵 **[info] elo_variance** — Champion Elo swung 25 (peak 1410 → 1385) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1410, 1396, 1405, 1361, 1358, 1385]_
