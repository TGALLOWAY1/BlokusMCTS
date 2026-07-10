# Nightly Training Diagnosis

_Generated: 2026-07-10 07:33 UTC · run `20260710T021746Z` · generation 172_

**2 finding(s):**

- 🟠 **[warn] promotion_drought** — 32 generations since the last promotion (gen 140).
- 🔵 **[info] elo_variance** — Champion Elo swung 51 (peak 1410 → 1358) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1359, 1410, 1396, 1405, 1361, 1358]_
