# Nightly Training Diagnosis

_Generated: 2026-07-10 02:01 UTC · run `20260709T204602Z` · generation 171_

**2 finding(s):**

- 🟠 **[warn] promotion_drought** — 31 generations since the last promotion (gen 140).
- 🔵 **[info] elo_variance** — Champion Elo swung 49 (peak 1410 → 1361) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1392, 1359, 1410, 1396, 1405, 1361]_
