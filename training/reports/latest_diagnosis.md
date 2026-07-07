# Nightly Training Diagnosis

_Generated: 2026-07-07 07:33 UTC · run `20260707T021805Z` · generation 160_

**2 finding(s):**

- 🟠 **[warn] promotion_drought** — 20 generations since the last promotion (gen 140).
- 🔵 **[info] elo_variance** — Champion Elo swung 68 (peak 1394 → 1326) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1394, 1392, 1394, 1389, 1307, 1326]_
