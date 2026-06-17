#!/usr/bin/env bash
# check_browser_core.sh
# CI-friendly guard: verify frontend/public/blokus_core.zip exists and is not
# stale relative to engine/, mcts/, agents/, config/challenge_champion_config.json,
# and browser_python/worker_bridge.py (the sources build_browser_core.sh bundles).
# Exits non-zero if the bundle is missing or out of date so deploys can't ship a
# Pyodide worker that drifts from the Python engine.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ZIP="$ROOT/frontend/public/blokus_core.zip"

if [[ ! -f "$ZIP" ]]; then
  echo "❌ Missing $ZIP — run: bash scripts/build_browser_core.sh" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 1. Extract the committed bundle.
unzip -q "$ZIP" -d "$TMP/bundle"

# 2. Recreate the expected source tree (mirrors build_browser_core.sh inputs).
mkdir -p "$TMP/expected/engine" "$TMP/expected/mcts" "$TMP/expected/agents" "$TMP/expected/config"
cp -R "$ROOT"/engine/* "$TMP/expected/engine/"
cp -R "$ROOT"/mcts/* "$TMP/expected/mcts/"
cp -R "$ROOT"/agents/* "$TMP/expected/agents/"
cp "$ROOT"/config/challenge_champion_config.json "$TMP/expected/config/"
cp "$ROOT"/browser_python/worker_bridge.py "$TMP/expected/worker_bridge.py"

# 3. Compare contents (ignores zip timestamps / byte-level metadata).
if diff -r -x '__pycache__' -x '*.pyc' "$TMP/expected" "$TMP/bundle" >"$TMP/diff.txt" 2>&1; then
  echo "✅ blokus_core.zip is present and up to date."
else
  echo "❌ blokus_core.zip is STALE. Re-run: bash scripts/build_browser_core.sh && commit." >&2
  echo "--- differences (expected vs bundle) ---" >&2
  cat "$TMP/diff.txt" >&2
  exit 1
fi
