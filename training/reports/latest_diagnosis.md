# Nightly Training Diagnosis

_Generated: 2026-06-28 22:33 UTC · run `20260628T190235Z` · generation 128_

**2 finding(s):**

- 🔵 **[info] elo_variance** — Champion Elo swung 124 (peak 1182 → 1058) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1182, 1158, 1158, 1099, 1086, 1058]_
- 🔵 **[info] no_promotion_yet** — No champion promotion in 128 generations. The seed champion may already be near-optimal, or candidates aren't clearing the gates.
