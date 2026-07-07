# Nightly Training Diagnosis

_Generated: 2026-07-07 20:27 UTC · run `20260707T151216Z` · generation 162_

**2 finding(s):**

- 🟠 **[warn] promotion_drought** — 22 generations since the last promotion (gen 140).
- 🔵 **[info] elo_variance** — Champion Elo swung 71 (peak 1394 → 1323) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1394, 1389, 1307, 1326, 1323, 1323]_
