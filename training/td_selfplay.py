"""Self-play trajectory collection for temporal-difference learning.

Plays full Blokus games with arena agents (reusing
:func:`analytics.tournament.arena_runner.build_agent`) and records, for every
player, the *ordered* sequence of decision-point states plus the terminal
state. Each consecutive pair becomes one TD transition row written to
``data/td_trajectories.csv`` via :mod:`training.trajectory_store`.

This is intentionally a thin, self-contained game loop rather than a hook into
the arena's per-move machinery: trajectory collection needs per-ply, per-player
feature capture that the fixed-ply snapshot path does not provide, and keeping
it separate avoids any risk to the existing snapshot / promotion flow.

Determinism: seeding mirrors the arena (``random.seed`` / ``np.random.seed`` per
game, agent seeds derived from the run seed), so a fixed ``seed`` reproduces the
same trajectories.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from analytics.tournament.arena_runner import AgentConfig, build_agent
from engine.board import Player
from engine.game import BlokusGame
from training.rich_features import (
    FeatureCache,
    board_occupancy,
    extract_rich_features,
    get_phase,
)
from training.trajectory_store import TrajectoryRow, append_trajectories

_PLAYERS: List[Player] = list(Player)
# Zero-valued feature placeholder reused for empty next-states.
_ZERO_FEATURES: Dict[str, float] = {}


@dataclass
class _DecisionPoint:
    ply: int
    phase: str
    board_occupancy: float
    current_player: int
    features: Dict[str, float]


@dataclass
class GameTrajectory:
    """All per-player decision points for one game plus its terminal labels."""

    game_id: str
    seed: int
    # player_id -> ordered decision points
    decisions: Dict[int, List[_DecisionPoint]] = field(default_factory=dict)
    terminal_features: Dict[int, Dict[str, float]] = field(default_factory=dict)
    final_scores: Dict[int, int] = field(default_factory=dict)
    final_ranks: Dict[int, int] = field(default_factory=dict)
    winner_id: Optional[int] = None
    seat_agent: Dict[int, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Outcome label helpers (raw labels; terminal_value blend happens at train time)
# ---------------------------------------------------------------------------


def compute_ranks(scores: Dict[int, int]) -> Dict[int, int]:
    """Competition ranking (1 = best). Ties share the better rank."""
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    ranks: Dict[int, int] = {}
    last_score: Optional[int] = None
    last_rank = 0
    for idx, (pid, score) in enumerate(ordered, start=1):
        if last_score is None or score != last_score:
            last_rank = idx
            last_score = score
        ranks[pid] = last_rank
    return ranks


def margin_labels(player_id: int, scores: Dict[int, int]) -> Dict[str, float]:
    """Compute score-margin labels for a player from the final score dict."""
    my = scores[player_id]
    others = [s for pid, s in scores.items() if pid != player_id]
    leader = max(scores.values())
    margin_to_winner = float(my - leader)  # <= 0
    higher = [s for s in others if s > my]
    margin_to_next = float(my - min(higher)) if higher else float(my - max(others)) if others else 0.0
    margin_over_last = float(my - min(others)) if others else 0.0
    return {
        "score_margin_to_winner": margin_to_winner,
        "score_margin_to_next": margin_to_next,
        "score_margin_over_last": margin_over_last,
    }


# ---------------------------------------------------------------------------
# Single-game play
# ---------------------------------------------------------------------------


def play_game(
    agents: Sequence[Dict[str, Any]],
    *,
    game_id: str,
    seed: int,
    max_turns: int = 2500,
    capture_every_ply: bool = False,
    capture_agents: Optional[Sequence[str]] = None,
) -> GameTrajectory:
    """Play one game; record per-player decision-point features and outcomes.

    ``agents`` is a list of 4 arena-style agent config dicts (each with a
    ``name``). Seats are assigned in order (player 1..4). When
    ``capture_every_ply`` is True, every player's features are captured at every
    ply (denser but slower); by default only the moving player's features are
    captured at each of its turns. ``capture_agents`` (agent names) restricts
    which seats' trajectories are recorded — labelling states with a *random*
    seat's final outcome teaches V(s) the value of random play, so training
    collection captures only the strong seats by default.
    """
    if len(agents) != 4:
        raise ValueError("play_game requires exactly 4 agent configs")

    random.seed(seed)
    np.random.seed(seed)

    seat_agent = {i + 1: str(agents[i].get("name", f"agent{i+1}")) for i in range(4)}
    agent_instances = {}
    for i, cfg in enumerate(agents):
        ac = AgentConfig.from_dict(cfg)
        agent_instances[i + 1] = build_agent(ac, seed=seed * 31 + i + 1)
    captured_seats = {
        pid for pid, name in seat_agent.items()
        if capture_agents is None or name in set(capture_agents)
    }

    game = BlokusGame()
    traj = GameTrajectory(game_id=game_id, seed=seed, seat_agent=seat_agent)
    for p in _PLAYERS:
        traj.decisions[p.value] = []

    turn_count = 0
    while not game.is_game_over() and turn_count < max_turns:
        current = game.get_current_player()
        legal_moves = game.get_legal_moves(current)
        turn_count += 1
        if not legal_moves:
            game.board._update_current_player()
            game._check_game_over()
            continue

        # Capture decision-point features BEFORE the move.
        cache = FeatureCache()
        ply = int(game.board.move_count)
        phase = get_phase(game.board)
        occ = board_occupancy(game.board)
        cur_id = int(current.value)
        if capture_every_ply:
            for p in _PLAYERS:
                if p.value not in captured_seats:
                    continue
                feats = extract_rich_features(game.board, p, cache=cache)
                traj.decisions[p.value].append(
                    _DecisionPoint(ply, get_phase(game.board), occ, cur_id, feats)
                )
        elif cur_id in captured_seats:
            feats = extract_rich_features(game.board, current, cache=cache)
            traj.decisions[cur_id].append(_DecisionPoint(ply, phase, occ, cur_id, feats))

        agent = agent_instances[cur_id]
        thinking = agents[cur_id - 1].get("thinking_time_ms")
        move, _stats = agent.choose_move(game.board, current, legal_moves, thinking)
        if move is None or not game.make_move(move, current):
            game.board._update_current_player()
            game._check_game_over()
            continue

    # --- Terminal labels -----------------------------------------------------
    result = game.get_game_result()
    scores = {int(pid): int(s) for pid, s in result.scores.items()}
    traj.final_scores = scores
    traj.final_ranks = compute_ranks(scores)
    traj.winner_id = int(result.winner_ids[0]) if len(result.winner_ids) == 1 else None

    # Terminal-state features for each captured player (game over board).
    term_cache = FeatureCache()
    for p in _PLAYERS:
        if p.value in captured_seats:
            traj.terminal_features[p.value] = extract_rich_features(game.board, p, cache=term_cache)

    return traj


# ---------------------------------------------------------------------------
# Trajectory → rows
# ---------------------------------------------------------------------------


def trajectory_to_rows(
    traj: GameTrajectory,
    *,
    run_id: str,
    agent_version: str,
    created_at: Optional[str] = None,
) -> List[TrajectoryRow]:
    """Flatten one game's per-player decision points into TD transition rows.

    For player ``p`` with decision points ``[d0, d1, ..., dk]`` and terminal
    state ``T``: rows ``d0..d_{k-1}`` are non-terminal (next-state = the
    following decision point), and ``dk`` is terminal (next-state = ``T``,
    ``terminal=1``). Rows are emitted in ``(player_id, ply)`` order.
    """
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    rows: List[TrajectoryRow] = []

    for pid in sorted(traj.decisions.keys()):
        points = traj.decisions[pid]
        if not points:
            continue
        score = int(traj.final_scores.get(pid, 0))
        rank = int(traj.final_ranks.get(pid, 4))
        margins = margin_labels(pid, traj.final_scores)
        won = (traj.winner_id == pid) or (rank == 1)
        top2 = rank <= 2
        agent_name = traj.seat_agent.get(pid, f"agent{pid}")
        terminal_feats = traj.terminal_features.get(pid, {})

        for i, dp in enumerate(points):
            is_terminal = i == len(points) - 1
            next_feats = terminal_feats if is_terminal else points[i + 1].features
            # Phase of the bootstrap target: the next decision point's phase for a
            # non-terminal transition (which may differ from dp.phase across a
            # phase boundary), or the row's own phase for a terminal transition
            # (unused — terminal rows bootstrap from the label, not V(s')).
            next_phase = dp.phase if is_terminal else points[i + 1].phase
            rows.append(
                TrajectoryRow(
                    run_id=run_id,
                    game_id=traj.game_id,
                    seed=traj.seed,
                    ply=dp.ply,
                    player_id=pid,
                    phase=dp.phase,
                    next_phase=next_phase,
                    board_occupancy=dp.board_occupancy,
                    current_player=dp.current_player,
                    state_features=dp.features,
                    next_state_features=next_feats,
                    reward=0.0,  # sparse reward: value lives in the terminal label
                    terminal=is_terminal,
                    final_rank=rank,
                    final_score=score,
                    score_margin_to_winner=margins["score_margin_to_winner"],
                    score_margin_to_next=margins["score_margin_to_next"],
                    score_margin_over_last=margins["score_margin_over_last"],
                    winner_id=traj.winner_id,
                    won_game=won,
                    top_2_finish=top2,
                    agent_name=agent_name,
                    agent_version=agent_version,
                    created_at=created_at,
                )
            )
    return rows


# ---------------------------------------------------------------------------
# Batch collection
# ---------------------------------------------------------------------------


def collect_trajectories(
    agents: Sequence[Dict[str, Any]],
    *,
    run_id: str,
    num_games: int,
    seed: int,
    agent_version: str = "champion",
    output_path: Optional[Any] = None,
    max_turns: int = 2500,
    capture_every_ply: bool = False,
    capture_agents: Optional[Sequence[str]] = None,
    verbose: bool = False,
) -> int:
    """Play ``num_games`` games and append TD trajectory rows to ``output_path``.

    Returns the total number of rows written. ``output_path`` defaults to
    ``data/td_trajectories.csv`` (see
    :data:`training.trajectory_store.DEFAULT_TRAJECTORY_CSV`).
    """
    from training.trajectory_store import DEFAULT_TRAJECTORY_CSV

    output_path = output_path or DEFAULT_TRAJECTORY_CSV
    created_at = datetime.now(timezone.utc).isoformat()
    total = 0
    for g in range(num_games):
        game_seed = seed + g
        game_id = f"{run_id}_g{g:04d}"
        traj = play_game(
            agents,
            game_id=game_id,
            seed=game_seed,
            max_turns=max_turns,
            capture_every_ply=capture_every_ply,
            capture_agents=capture_agents,
        )
        rows = trajectory_to_rows(
            traj, run_id=run_id, agent_version=agent_version, created_at=created_at
        )
        written = append_trajectories(rows, output_path)
        total += written
        if verbose:
            print(f"[td_selfplay] game {g+1}/{num_games}: {written} rows "
                  f"(scores={traj.final_scores})", flush=True)
    return total


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    from mcts.search_profiles import SEARCH_PROFILES
    from training.teacher_roster import champion_version, teacher_roster
    from training.trajectory_store import DEFAULT_TRAJECTORY_CSV

    p = argparse.ArgumentParser(
        description="Collect TD self-play trajectories into data/td_trajectories.csv."
    )
    p.add_argument("--num-games", type=int, default=20)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--run-id", default="tdcollect")
    p.add_argument("--output", default=str(DEFAULT_TRAJECTORY_CSV))
    p.add_argument("--profile", default="teacher", choices=sorted(SEARCH_PROFILES) + ["none"],
                   help="Search profile for the champion seats (default: teacher — "
                        "stronger search than the champion's own budget, so labels "
                        "come from a stronger teacher). 'none' keeps the stored budget.")
    p.add_argument("--thinking-time-ms", type=int, default=None,
                   help="Override every MCTS agent's thinking budget (small ⇒ fast collection; "
                        "overrides --profile's budget).")
    p.add_argument("--capture-every-ply", action="store_true",
                   help="Capture every player at every ply (denser, slower).")
    p.add_argument("--capture-all-seats", action="store_true",
                   help="Also record heuristic/random seats' trajectories "
                        "(default: champion seats only — weak-seat outcomes teach "
                        "the value of weak play).")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    profile = None if args.profile == "none" else args.profile
    agents = teacher_roster(profile)
    if args.thinking_time_ms is not None:
        for a in agents:
            if a.get("type", "mcts") == "mcts":
                a["thinking_time_ms"] = int(args.thinking_time_ms)

    # Record who generated the labels and at what budget with every row.
    budget = (args.thinking_time_ms if args.thinking_time_ms is not None
              else agents[0].get("thinking_time_ms"))
    agent_version = f"{champion_version()}@{profile or 'stored'}:{budget}"
    capture = None if args.capture_all_seats else ("champion", "champion2")

    total = collect_trajectories(
        agents,
        run_id=args.run_id,
        num_games=args.num_games,
        seed=args.seed,
        agent_version=agent_version,
        output_path=args.output,
        capture_every_ply=args.capture_every_ply,
        capture_agents=capture,
        verbose=args.verbose,
    )
    print(f"[td_selfplay] wrote {total} rows to {args.output} "
          f"(labels from {agent_version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
