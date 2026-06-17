"""Vercel serverless entrypoint (deploy profile).

Vercel auto-detects Python serverless functions in the ``/api`` directory, so
this module is the mount point the platform invokes. It exposes the same
deploy-profile FastAPI app as ``api-runtime/app.py`` (used for local runs):

* gameplay routes (``/api/games`` ...),
* read-only metadata (``/api/champion``, ``/api/arena-runs``),
* ``/health``.

Research routes and MongoDB are never registered in the deploy profile.

``vercel.json`` rewrites ``/api/*`` and ``/health`` to this function; Vercel
preserves the original request path, so FastAPI's own routing resolves the
endpoint. Read-only data (``data/champion_registry.json`` and
``arena_runs/**/summary.json``) is shipped via the ``includeFiles`` glob in
``vercel.json`` so the registry/leaderboard loaders resolve at runtime.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the repo root is importable so the function can load ``webapi`` and the
# pure-Python engine/mcts/agents packages it depends on.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("APP_PROFILE", "deploy")

from webapi.app import create_app  # noqa: E402

# ASGI application object detected by Vercel's Python runtime.
app = create_app(profile="deploy", include_research_routes=False)
