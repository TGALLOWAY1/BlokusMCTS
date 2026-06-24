"""Reproducible experiment framework for validating TD vs regression learning.

The nightly pipeline *produces* candidates; this package answers the question the
pipeline cannot: **is a candidate actually stronger, and is the difference real?**
It runs candidates and baselines under identical, seeded conditions, pools every
game, and reports wins/ranks/score-margins/Elo/TrueSkill with confidence
intervals — plus a manifest that lets any run be reproduced byte-for-byte.

Modules
-------
* :mod:`training.experiments.manifest` — experiment manifests (id, date, config).
* :mod:`training.experiments.compare`  — the candidate-comparison harness +
  ``compare_learning_modes`` CLI.
* :mod:`training.experiments.report`   — markdown experiment reports.
"""

from __future__ import annotations
