# Nightly Training Diagnosis

_Generated: 2026-06-29 23:13 UTC · run `20260629T194250Z` · generation 131_

**2 finding(s):**

- 🔵 **[info] elo_variance** — Champion Elo swung 84 (peak 1099 → 1015) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1099, 1086, 1058, 1031, 1014, 1015]_
- 🔵 **[info] no_promotion_yet** — No champion promotion in 131 generations. The seed champion may already be near-optimal, or candidates aren't clearing the gates.
