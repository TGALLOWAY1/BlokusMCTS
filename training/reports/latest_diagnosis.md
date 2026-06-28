# Nightly Training Diagnosis

_Generated: 2026-06-28 12:12 UTC · run `20260628T084106Z` · generation 126_

**2 finding(s):**

- 🔵 **[info] elo_variance** — Champion Elo swung 160 (peak 1258 → 1099) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1138, 1258, 1182, 1158, 1158, 1099]_
- 🔵 **[info] no_promotion_yet** — No champion promotion in 126 generations. The seed champion may already be near-optimal, or candidates aren't clearing the gates.
