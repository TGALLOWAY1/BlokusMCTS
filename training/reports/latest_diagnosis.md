# Nightly Training Diagnosis

_Generated: 2026-07-11 07:26 UTC · run `20260711T021059Z` · generation 176_

**2 finding(s):**

- 🟠 **[warn] promotion_drought** — 36 generations since the last promotion (gen 140).
- 🔵 **[info] elo_variance** — Champion Elo swung 123 (peak 1394 → 1271) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1361, 1358, 1385, 1284, 1394, 1271]_
