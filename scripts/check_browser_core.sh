#!/usr/bin/env bash
#
# check_browser_core.sh
# CI guard: verify frontend/public/blokus_core.zip is in sync with the Python
# sources it bundles (engine/, mcts/, agents/, config/, worker_bridge.py).
#
# Compares the *contents* of the committed zip against a freshly built one,
# ignoring zip timestamps (which change on every build) and __pycache__/*.pyc.
# Exits non-zero if they drift, with a hint to rebuild.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ZIP="frontend/public/blokus_core.zip"
if [[ ! -f "$ZIP" ]]; then
  echo "❌ $ZIP is missing. Run: bash scripts/build_browser_core.sh"
  exit 1
fi

TMP="$(mktemp -d)"
cleanup() {
  # Restore the committed zip so the working tree is left unchanged.
  git checkout -- "$ZIP" 2>/dev/null || true
  rm -rf "$TMP"
}
trap cleanup EXIT

cp "$ZIP" "$TMP/committed.zip"
bash scripts/build_browser_core.sh >/dev/null
cp "$ZIP" "$TMP/fresh.zip"

mkdir -p "$TMP/committed" "$TMP/fresh"
unzip -qo "$TMP/committed.zip" -d "$TMP/committed"
unzip -qo "$TMP/fresh.zip" -d "$TMP/fresh"

if diff -r -x '__pycache__' -x '*.pyc' "$TMP/committed" "$TMP/fresh" >/dev/null 2>&1; then
  echo "✅ blokus_core.zip is in sync with engine/, mcts/, agents/, config/."
else
  echo "❌ blokus_core.zip is OUT OF SYNC with the Python sources."
  echo "   Fix: bash scripts/build_browser_core.sh && git add $ZIP"
  echo "   Diff (committed vs freshly built):"
  diff -r -x '__pycache__' -x '*.pyc' "$TMP/committed" "$TMP/fresh" || true
  exit 1
fi
