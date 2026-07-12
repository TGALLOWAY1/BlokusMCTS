"""Per-game play-quality diagnostics emitted by ``run_single_game`` (audit #2).

These counters (legal-move counts, piece usage by size, board occupancy, pass /
invalid-move rates, score spread) are computed at game-record time so the nightly
self-play logs carry the play-quality signal the audit asked for. A full game with
random agents is fast and deterministic under a fixed seed.
"""

from __future__ import annotations

from analytics.tournament.arena_runner import AgentConfig, RunConfig, run_single_game


def _run_one():
    agents = [AgentConfig(name=f"r{i}", type="random") for i in range(1, 5)]
    run_config = RunConfig(agents=agents, num_games=1, seed=1234, max_turns=2500)
    seat_assignment = {"1": "r1", "2": "r2", "3": "r3", "4": "r4"}
    agent_configs = {a.name: a for a in agents}
    record, _snapshots = run_single_game(
        run_id="pq_test",
        game_index=0,
        game_seed=1234,
        run_config=run_config,
        seat_assignment=seat_assignment,
        agent_configs=agent_configs,
    )
    return record


def test_record_carries_play_quality_block():
    rec = _run_one()
    assert rec["error"] is None, rec["error"]
    pq = rec["play_quality"]
    # Game actually progressed.
    assert pq["game_length_turns"] > 0
    assert rec["moves_made"] > 0


def test_record_carries_provenance_stamps():
    # Agent-strength rescue Phase 2: every game record declares which
    # state/action encodings and scoring objective produced it.
    from engine.board import STATE_SCHEMA_VERSION
    from engine.game import SCORING_MODE_STANDARD
    from engine.move_generator import ACTION_SCHEMA_VERSION

    rec = _run_one()
    assert rec["state_schema_version"] == STATE_SCHEMA_VERSION
    assert rec["action_schema_version"] == ACTION_SCHEMA_VERSION
    assert rec["scoring_mode"] == SCORING_MODE_STANDARD  # RunConfig default


def test_play_quality_values_are_well_formed():
    pq = _run_one()["play_quality"]

    # Legal-move stats are non-negative and ordered.
    assert pq["min_legal_moves"] >= 0
    assert pq["max_legal_moves"] >= pq["min_legal_moves"]
    assert pq["avg_legal_moves_per_turn"] >= 0.0

    # Rates are fractions in [0, 1].
    assert 0.0 <= pq["pass_rate"] <= 1.0
    assert 0.0 <= pq["board_occupancy"] <= 1.0

    # Piece sizes are the canonical Blokus range (1..5 squares).
    sizes = [int(k) for k in pq["piece_size_usage"]]
    assert sizes, "at least one piece should have been placed"
    assert all(1 <= s <= 5 for s in sizes)

    # Per-agent usage sums to the global usage for each size.
    global_counts = {int(k): v for k, v in pq["piece_size_usage"].items()}
    summed: dict[int, int] = {}
    for usage in pq["piece_size_usage_by_agent"].values():
        for k, v in usage.items():
            summed[int(k)] = summed.get(int(k), 0) + v
    assert summed == global_counts

    # Score-distribution summary is internally consistent.
    assert pq["final_score_max"] >= pq["final_score_min"]
    assert pq["final_score_spread"] == pq["final_score_max"] - pq["final_score_min"]
