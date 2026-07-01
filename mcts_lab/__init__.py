"""mcts_lab — the canonical training/evaluation workflow for this repo.

Five small CLIs, each runnable with ``python -m``:

    python -m mcts_lab.checks                     # sanity: rules, determinism, agent loading
    python -m mcts_lab.eval --agents champion,baseline --games 20 --seeds 20260620,20260621
    python -m mcts_lab.self_play --games 24       # grow the self-play snapshot corpus
    python -m mcts_lab.train                      # generate candidate configs from the corpus
    python -m mcts_lab.promote --candidate <artifact.json>   # gated champion replacement

These are thin, readable wrappers around the durable pipeline in ``training/``
(state under ``training/state/``, arena in ``analytics/tournament/``). The
nightly CI workflow runs the same underlying code via ``training.nightly_run``.

The flow is always:

    current champion -> candidate (train) -> evaluated candidate (eval/promote
    screen) -> confirmation run -> promoted champion (training/state/champion.json)
"""

from __future__ import annotations
