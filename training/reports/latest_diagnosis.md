# Nightly Training Diagnosis

_Generated: 2026-07-07 01:15 UTC · run `20260706T195706Z` · generation 159_

**2 finding(s):**

- 🟠 **[warn] promotion_drought** — 19 generations since the last promotion (gen 140).
- 🔵 **[info] elo_variance** — Champion Elo swung 91 (peak 1398 → 1307) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1398, 1394, 1392, 1394, 1389, 1307]_
