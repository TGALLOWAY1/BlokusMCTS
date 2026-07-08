# Nightly Training Diagnosis

_Generated: 2026-07-08 07:33 UTC · run `20260708T021620Z` · generation 164_

**3 finding(s):**

- 🟠 **[warn] promotion_drought** — 24 generations since the last promotion (gen 140).
- 🔵 **[info] elo_variance** — Champion Elo swung 57 (peak 1377 → 1321) but the champion config is unchanged (no promotion in this window), so this is sampling variance, not a skill regression. Treat the Elo timeline as noise until a promotion actually changes the agent.
  - _evidence: last 6 points: [1307, 1326, 1323, 1323, 1377, 1321]_
- 🔵 **[info] refit_pending** — Only 192 snapshot rows accumulated (need 200 before the evaluator can re-fit) — no candidate will be generated until then.
  - _evidence: rows=192_
