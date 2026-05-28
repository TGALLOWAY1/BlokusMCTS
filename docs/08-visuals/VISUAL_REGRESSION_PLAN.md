# Visual Regression Plan

> Repeatable process for visually auditing the frontend over time.
> Last audited: 2026-05-28. Capture results: [Screenshot Manifest](SCREENSHOT_MANIFEST.md).

## Goal

Catch unintended visual changes to the major screens between commits, with a
lightweight, reproducible capture step (not a pixel-diff CI gate yet).

## Prerequisites

- `cd frontend && npm install`
- Dev server: `npm run dev` (Vite, `http://localhost:5173`).
- A headless browser driver (e.g. Playwright: `npx playwright install chromium`).
- For research-only routes (`/benchmark`, `/history`, `/analysis/:id`), the
  backend must run (`python run_server.py`) with MongoDB configured, and at
  least one arena run / game present. Otherwise these render empty/error states.
- For `/` (Play) and `/story`, only the frontend is required, but the board needs
  Pyodide to download its WASM runtime from CDN — so **network access is
  required** for the in-browser MCTS to produce moves.

## Capture procedure

1. Start `npm run dev` (and `python run_server.py` for research routes).
2. For each route in the [Screenshot Manifest](SCREENSHOT_MANIFEST.md), at
   viewports `1440x900` (desktop) and `390x844` (mobile):
   - navigate, wait for network idle + key selector, screenshot to
     `docs/08-visuals/screenshots/<route>__<viewport>.png`.
3. Update the manifest's "Last captured" date and note any visual issues.

## Suggested script (Playwright, Node)

```js
// scripts (frontend) — pseudocode skeleton; not yet committed
const routes = ["/", "/story", "/benchmark", "/history", "/mcts-analysis"];
const viewports = { desktop: [1440,900], mobile: [390,844] };
for (const r of routes)
  for (const [name,[w,h]] of Object.entries(viewports)) {
    await page.setViewportSize({width:w,height:h});
    await page.goto(`http://localhost:5173${r}`, {waitUntil:"networkidle"});
    await page.screenshot({path:`docs/08-visuals/screenshots/${slug(r)}__${name}.png`, fullPage:true});
  }
```

## When to run

- Before merging any change under `frontend/src/`.
- Add to the [Regression Checklist](../04-quality/REGRESSION_CHECKLIST.md) visual section.

## Status of this pass (2026-05-28)

Live capture was attempted in the documentation container — see the
[Screenshot Manifest](SCREENSHOT_MANIFEST.md) for whether images were produced or
the capture was blocked (e.g. no headless browser / restricted network). When
blocked, this plan stands as the intended process.

## Future hardening

- Commit the capture script under `frontend/` and wire it into CI.
- Add pixel-diff comparison against a baseline set to fail on unexpected changes.
