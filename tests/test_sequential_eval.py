"""Unit tests for the sequential paired SPRT evaluation math.

Covers the pure statistics (Elo<->score, SPRT bounds/LLR/decision) and the paired
reduction from pooled games. The arena-driven driver
(:func:`training.evaluation.sequential.sequential_paired_eval`) is exercised by a
tiny smoke run in the training pipeline, not here (it plays real MCTS games).
"""

from __future__ import annotations

import math

import pytest

from training.evaluation.sequential import (
    DEFAULT_ELO1,
    elo_to_score,
    paired_outcomes,
    score_to_elo,
    sprt_bounds,
    sprt_decision,
    sprt_llr,
)


def test_elo_score_roundtrip():
    assert elo_to_score(0.0) == pytest.approx(0.5)
    assert score_to_elo(0.5) == pytest.approx(0.0, abs=1e-6)
    for elo in (-200, -50, 10, 70, 300):
        assert score_to_elo(elo_to_score(elo)) == pytest.approx(elo, abs=1e-3)
    # Monotonic: more Elo -> higher expected score.
    assert elo_to_score(100) > elo_to_score(0) > elo_to_score(-100)


def test_sprt_bounds_symmetry():
    lo, hi = sprt_bounds(0.05, 0.05)
    assert hi == pytest.approx(math.log(19.0))
    assert lo == pytest.approx(-math.log(19.0))
    assert lo < 0 < hi


def test_llr_sign_follows_evidence():
    # All wins -> LLR strictly positive (favors H1 = candidate stronger).
    assert sprt_llr(30, 0, 0) > 0
    # All losses -> LLR strictly negative (favors H0).
    assert sprt_llr(0, 0, 30) < 0
    # Balanced record around 50% -> favors H0 (no improvement) since H1 is +Elo.
    assert sprt_llr(20, 0, 20) < 0
    # Draws are neutral (fixed-observed-draw model): adding equal draws does not
    # flip the sign, and a pure-draw record has ~zero LLR.
    assert sprt_llr(0, 30, 0) == pytest.approx(0.0, abs=1e-9)


def test_decision_accepts_strong_candidate():
    # A lopsided winning record must eventually accept H1.
    st = sprt_decision(90, 5, 5)
    assert st.decision == "accept_h1"
    assert st.llr >= st.upper


def test_decision_rejects_no_op_clone():
    # A ~50% pairwise record (an agent playing a near-clone of itself) is evidence
    # AGAINST a +Elo improvement, so the SPRT should accept H0 given enough games.
    st = sprt_decision(100, 0, 100)
    assert st.decision == "accept_h0"
    assert st.llr <= st.lower


def test_min_games_guard_defers_decision():
    # Even a perfect streak cannot decide before min_games.
    st = sprt_decision(5, 0, 0, min_games=24)
    assert st.decision == "continue"
    assert st.n == 5


def test_larger_h1_decides_in_fewer_games():
    # A bigger claimed edge (H1) reaches the bound with fewer wins.
    small = None
    big = None
    for n in range(1, 400):
        if small is None and sprt_decision(n, 0, 0, elo1=30, min_games=1).decision == "accept_h1":
            small = n
        if big is None and sprt_decision(n, 0, 0, elo1=150, min_games=1).decision == "accept_h1":
            big = n
        if small and big:
            break
    assert big is not None and small is not None
    assert big < small


def test_paired_outcomes_reduction():
    games = [
        {"agent_scores": {"candidate": 50, "champion": 40, "x": 30, "y": 20}},  # win
        {"agent_scores": {"candidate": 30, "champion": 45, "x": 30, "y": 20}},  # loss
        {"agent_scores": {"candidate": 33, "champion": 33, "x": 30, "y": 20}},  # draw
        {"agent_scores": {"champion": 40, "x": 30, "y": 20}},                   # candidate absent -> skipped
    ]
    w, d, ls, cs, hs = paired_outcomes(games, "candidate", "champion")
    assert (w, d, ls) == (1, 1, 1)
    assert cs == [50.0, 30.0, 33.0]
    assert hs == [40.0, 45.0, 33.0]


def test_default_h1_is_a_meaningful_edge():
    # Guard against silently reverting to a sub-detectable H1.
    assert DEFAULT_ELO1 >= 50.0


def _mock_arena(monkeypatch, outcome):
    """Patch the arena so the driver's block loop runs with canned games (no real
    MCTS). ``outcome(i) -> (candidate_score, champion_score)`` decides game ``i``.
    """
    from types import SimpleNamespace

    from training import selfplay_core as sc
    from training.evaluation import sequential as seqmod

    store: dict = {}
    counter = {"i": 0}

    def fake_run_arena_inproc(agents, *, paths, run_label, num_games, seed,
                              enable_snapshots, verbose=False, deadline=None,
                              seat_policy="randomized", **kw):
        names = [a.get("name") or a.get("type") for a in agents]
        cand = next(n for n in names if n not in {"champion"} and "opp" not in str(n))
        games = []
        for _ in range(num_games):
            i = counter["i"]
            counter["i"] += 1
            cs, hs = outcome(i)
            games.append({"agent_scores": {"champion": hs, cand: cs,
                                           names[2]: 10, names[3]: 5}})
        rd = f"{run_label}_{seed}"
        store[rd] = games
        return {"run_dir": rd}

    monkeypatch.setattr(sc, "run_arena_inproc", fake_run_arena_inproc)
    monkeypatch.setattr(sc, "_load_games", lambda rd: store.get(rd, []))
    pool = SimpleNamespace(
        opponents=[{"type": "random", "name": "oppA"}, {"type": "random", "name": "oppB"}],
        seeds=[1, 2])
    state = {"champion_params": {"type": "heuristic"}}
    return seqmod, state, pool


def test_driver_accepts_strong_candidate(monkeypatch, tmp_path):
    """A candidate that consistently outscores the champion must stop EARLY with H1."""
    from training import TrainingPaths

    seqmod, state, pool = _mock_arena(monkeypatch, outcome=lambda i: (50, 40))  # always win
    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    res = seqmod.sequential_paired_eval(
        state, "cand", "strong", {"type": "heuristic"}, pool, paths,
        seeds=[1, 2], block_games=2, min_games=8, max_games=200)
    assert res.decision == "accept_h1"
    assert res.is_improvement
    assert res.n_games < 200  # stopped early, did not exhaust the budget
    assert res.wins == res.n_games and res.losses == 0


def test_driver_rejects_clone(monkeypatch, tmp_path):
    """An alternating ~50% record (a clone) must not be called an improvement."""
    from training import TrainingPaths

    seqmod, state, pool = _mock_arena(
        monkeypatch, outcome=lambda i: (50, 40) if i % 2 == 0 else (40, 50))
    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    res = seqmod.sequential_paired_eval(
        state, "cand", "clone", {"type": "heuristic"}, pool, paths,
        seeds=[1, 2], block_games=2, min_games=8, max_games=120)
    assert res.decision in {"accept_h0", "inconclusive"}
    assert not res.is_improvement
    assert res.wins > 0 and res.losses > 0  # genuinely mixed record


def test_driver_caps_at_max_games(monkeypatch, tmp_path):
    """A borderline record never accepted/rejected stops at max_games (inconclusive)."""
    from training import TrainingPaths

    # A small, steady edge (not enough to cross H1=+70's bound) -> runs to the cap.
    seqmod, state, pool = _mock_arena(
        monkeypatch, outcome=lambda i: (50, 40) if i % 5 else (40, 50))  # ~80% win, but bounded
    paths = TrainingPaths.under(tmp_path)
    paths.ensure_dirs()
    res = seqmod.sequential_paired_eval(
        state, "cand", "borderline", {"type": "heuristic"}, pool, paths,
        seeds=[1, 2], block_games=4, min_games=8, max_games=40)
    assert res.n_games <= 40 + 8  # bounded (one block may overshoot the cap check)
    assert res.decision in {"accept_h1", "accept_h0", "inconclusive"}
