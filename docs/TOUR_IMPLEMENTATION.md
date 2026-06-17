# Take the Tour — Implementation Guide

> An interactive, mobile-friendly guided tour that explains MCTS Laboratory to
> recruiters, hiring managers, and software / AI / ML engineers in under three
> minutes. Route: **`/tour`** (alias **`/about`**).

The tour is a **standalone** experience. It never runs an MCTS search and works
even when the backend `/api` is unavailable (e.g. the static deploy build): live
metrics are used when present, otherwise clearly-labeled static fallbacks render.

---

## 1. Architecture

The tour follows a route-based, step-driven architecture (a guided-vs-overview
pattern adapted natively to this repo's React + Vite + Tailwind + framer-motion
stack — no external tour library, no Synapse code).

```
src/pages/TourPage.tsx              Route entry — wires state + layout
src/components/tour/
  tourTypes.ts                      Shared types (TourMode, TourStage, reducer types)
  useTourState.ts                   Pure reducer + localStorage persistence + swipe util
  tourData.ts                       Stage metadata + static demo data (fallbacks)
  tourMetrics.ts                    Adapter hook: real metrics -> view models w/ fallback
  ModeToggle.tsx                    Guided / Overview switch
  TourProgressRail.tsx              Horizontal stage chips + progress dots + step counter
  TourContainer.tsx                 Animated screen host (framer-motion, reduced-motion aware)
  TourNav.tsx                       Back / Next / Finish footer
  components/                       Small shared building blocks (MiniBoard, StatChip, ...)
  screens/                          One component per stage (see Step list)
  __tests__/                        Reducer / persistence / swipe / mode tests
```

| Piece | Responsibility |
|-------|----------------|
| `TourPage` | Owns `useTourState`, renders rail + container + nav, handles keyboard + swipe |
| `useTourState` | Active step index, guided/overview mode, navigation direction, persistence |
| `TourProgressRail` | Stage chips (horizontal scroll on mobile), dots, "Step N of M" |
| `TourContainer` | Cross-fade / slide between screens, respects `prefers-reduced-motion` |
| `TourNav` | Back / Next, Skip, Restart, and the final Play CTA |

## 2. Route

Registered in `src/App.tsx`:

- `/tour` — primary route
- `/about` — alias to the same page

Both are available in **research** and **deploy** profiles (the tour is the public
"front door"), unlike the research-only analytics routes.

## 3. Step list

| # | Stage | Screen | What it explains |
|---|-------|--------|------------------|
| 1 | Rules | `ScreenRules` | 20×20 board, 4 players, corner start, diagonal-only own-color contact, scoring |
| 2 | Complexity | `ScreenComplexity` | Branching factor, 4-player adversarial dynamics, spatial planning, blocking |
| 3 | Agents | `ScreenAgents` | Random / Heuristic / MCTS / Champion agents (only ones that exist) |
| 4 | Techniques | `ScreenTechniques` | UCT, RAVE, progressive widening, rollout policy, eval, opponent modeling, parallelism, adaptive control, transposition tables |
| 5 | Evaluation | `ScreenEvaluation` | Seeded arena tournaments, pairwise records, win rates, score stats, reproducible configs |
| 6 | TrueSkill | `ScreenTrueSkill` | TrueSkill (μ, σ), conservative rating, multi-seat validation, why single wins aren't enough |
| 7 | Champion | `ScreenChampion` | Candidate generation → overnight tournaments → aggregate → compare → promote |
| 8 | Play | `ScreenPlay` | Champion metadata + "Play the Champion" CTA to `/play` |

## 4. Data sources

| View | Real source | Hook / adapter |
|------|-------------|----------------|
| TrueSkill leaderboard | latest arena run `trueskill_ratings.leaderboard` | `useArenaLeaderboard` |
| Champion metadata | `GET /api/champion` (registry-backed) | `useChampion` |
| Champion config / techniques | `data/champion_registry.json` (mirrored statically in `tourData`) | static |

`tourMetrics.ts` wraps the hooks and returns a `{ source: 'live' | 'demo', ... }`
view model so screens can render an honest badge.

## 5. Fallback / demo data behavior

When a live source is missing or errors, the tour renders **static demo data**
defined in `tourData.ts` and marks it with a visible `Demo data` badge. Demo
values are drawn from real archived results (`arena_runs/`, `KEY_FINDINGS.md`,
`champion_registry.json`) so they are representative, not invented.

## 6. How real metrics are loaded

`tourMetrics.ts` calls `useArenaLeaderboard()` and `useChampion()`. If a hook
reports `available`/non-empty data, the tour uses it (`source: 'live'`). Otherwise
it falls back to the static tables (`source: 'demo'`). No screen blocks on the
network; the tour is fully usable offline.

## 7. How to add or edit tour steps

1. Add a stage entry to `TOUR_STAGES` in `tourData.ts` (id, label, title, icon, accent).
2. Create `screens/ScreenXxx.tsx` and add it to the `screens` array in `TourPage`.
3. The progress rail, dots, counter, and nav adapt automatically to the count.
4. Update the Step list table above.

Stage order and count are data-driven — no reducer changes needed.

## 8. Known limitations

- TrueSkill **progression over time** and an **overnight-run history** are shown
  with representative demo data; there is no per-run time-series API yet (see §9).
- Charts use lightweight inline SVG/CSS (plus one recharts line) to stay mobile-safe.
- Swipe is a best-effort enhancement; all navigation is reachable via buttons/keys.

## 9. Future improvements

- Add a `GET /api/champion-history` endpoint to drive a real TrueSkill progression
  line and champion timeline.
- Aggregate `arena_runs/*/summary.json` into a small static manifest at build time
  so the deploy build can show real leaderboards without a live backend.
- Optional: a tiny scripted board animation in `ScreenRules` driven by the engine
  replay format.
