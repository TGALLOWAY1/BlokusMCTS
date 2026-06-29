# Nightly Training Diagnosis

_Generated: 2026-06-29 13:53 UTC · run `20260629T102152Z` · generation 129_

**2 finding(s):**

- 🔵 **[info] elo_variance** — Champion Elo swung 127 (peak 1158 → 1031) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1158, 1158, 1099, 1086, 1058, 1031]_
- 🔵 **[info] no_promotion_yet** — No champion promotion in 129 generations. The seed champion may already be near-optimal, or candidates aren't clearing the gates.
