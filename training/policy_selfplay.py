"""Self-play collection of MCTS visit-count targets for the learned move policy.

Plays full Blokus games with arena agents (reusing
:func:`analytics.tournament.arena_runner.build_agent`) and, at every decision
made by an MCTS agent, records the **root visit distribution** over that
decision's legal moves. Each candidate move contributes one CSV row carrying its
four move-features (:func:`mcts.move_heuristic.compute_move_features`), its
``piece_id`` and its MCTS visit count; rows sharing a ``decision_id`` form one
training example. The visit distribution is the search's own improved policy, and
distilling it (:mod:`training.policy_learning`) yields a move policy that guides
the *next* generation's search — the core of the expert-iteration loop.

Written to ``data/policy_targets.csv``. Kept deliberately separate from the arena
per-move machinery (like :mod:`training.td_selfplay`) so it never touches the
snapshot / promotion flow. Determinism mirrors the arena: fixed ``seed`` ⇒ same
games and same recorded visit counts.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from analytics.tournament.arena_runner import AgentConfig, build_agent
from engine.board import Player
from engine.game import BlokusGame
from engine.move_generator import get_shared_generator
from mcts.mcts_agent import MCTSAgent
from mcts.move_heuristic import MOVE_FEATURE_NAMES, compute_move_features
from mcts.move_policy import PolicySample
from training import REPO_ROOT
from training.rich_features import board_occupancy, get_phase

DEFAULT_POLICY_CSV = REPO_ROOT / "data" / "policy_targets.csv"

POLICY_CSV_COLUMNS: List[str] = [
    "run_id", "game_id", "seed", "ply", "player_id", "phase", "board_occupancy",
    "decision_id", "piece_id",
    "feat_piece_size", "feat_corners", "feat_center", "feat_blocking",
    "visits", "n_moves",
]

_PLAYERS: List[Player] = list(Player)


# ---------------------------------------------------------------------------
# CSV store
# ---------------------------------------------------------------------------


def append_policy_rows(rows: List[Dict[str, Any]], path: Path | str = DEFAULT_POLICY_CSV) -> int:
    """Append policy-target rows to the CSV (writing the header if new). Returns count."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=POLICY_CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return len(rows)


def load_policy_samples(path: Path | str = DEFAULT_POLICY_CSV) -> List[PolicySample]:
    """Load and group CSV rows into per-decision :class:`PolicySample` targets.

    Decisions with fewer than two candidate moves or zero total visits carry no
    learnable ranking signal and are skipped.
    """
    path = Path(path)
    if not path.exists():
        return []
    groups: Dict[str, Dict[str, List[float]]] = {}
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = row["decision_id"]
            g = groups.setdefault(key, {"feats": [], "pids": [], "visits": []})
            g["feats"].append([
                float(row["feat_piece_size"]), float(row["feat_corners"]),
                float(row["feat_center"]), float(row["feat_blocking"]),
            ])
            g["pids"].append(int(row["piece_id"]))
            g["visits"].append(float(row["visits"]))

    samples: List[PolicySample] = []
    for g in groups.values():
        visits = np.asarray(g["visits"], dtype=float)
        total = visits.sum()
        if len(visits) < 2 or total <= 0:
            continue
        samples.append(PolicySample(
            features=np.asarray(g["feats"], dtype=float),
            piece_ids=np.asarray(g["pids"], dtype=int),
            target=visits / total,
        ))
    return samples


# ---------------------------------------------------------------------------
# Single-game collection
# ---------------------------------------------------------------------------


@dataclass
class _CollectStats:
    decisions: int = 0
    rows: int = 0


def _record_decision(
    underlying: MCTSAgent,
    board: Any,
    player: Player,
    *,
    run_id: str,
    game_id: str,
    seed: int,
    ply: int,
    decision_idx: int,
) -> List[Dict[str, Any]]:
    """Build CSV rows from an MCTS agent's last root visit distribution."""
    move_visits = getattr(underlying, "_last_root_move_visits", None)
    if not move_visits:
        return []
    gen = get_shared_generator()
    phase = get_phase(board)
    occ = float(board_occupancy(board))
    decision_id = f"{game_id}_p{player.value}_d{decision_idx}"
    n_moves = len(move_visits)
    rows: List[Dict[str, Any]] = []
    for move, visits in move_visits:
        f_size, f_corners, f_center, f_blocking = compute_move_features(board, player, move, gen)
        rows.append({
            "run_id": run_id, "game_id": game_id, "seed": seed, "ply": ply,
            "player_id": int(player.value), "phase": phase, "board_occupancy": occ,
            "decision_id": decision_id, "piece_id": int(move.piece_id),
            "feat_piece_size": f_size, "feat_corners": f_corners,
            "feat_center": f_center, "feat_blocking": f_blocking,
            "visits": int(visits), "n_moves": n_moves,
        })
    return rows


def play_and_collect(
    agents: Sequence[Dict[str, Any]],
    *,
    run_id: str,
    game_id: str,
    seed: int,
    output_path: Path | str = DEFAULT_POLICY_CSV,
    max_turns: int = 2500,
) -> _CollectStats:
    """Play one game, recording every MCTS seat's root visit distribution."""
    if len(agents) != 4:
        raise ValueError("play_and_collect requires exactly 4 agent configs")

    random.seed(seed)
    np.random.seed(seed)

    adapters: Dict[int, Any] = {}
    underlying: Dict[int, Optional[MCTSAgent]] = {}
    for i, cfg in enumerate(agents):
        adapter = build_agent(AgentConfig.from_dict(cfg), seed=seed * 31 + i + 1)
        adapters[i + 1] = adapter
        agent = getattr(adapter, "agent", None)
        if isinstance(agent, MCTSAgent):
            agent._capture_root_moves = True  # enable visit-distribution capture
            # Force single-process search: the root-parallel path returns early
            # and never records per-child visit counts, so capture requires one
            # in-process tree (also cleaner / deterministic for a training target).
            agent.num_workers = 1
            underlying[i + 1] = agent
        else:
            underlying[i + 1] = None

    game = BlokusGame()
    stats = _CollectStats()
    decision_idx: Dict[int, int] = {p.value: 0 for p in _PLAYERS}
    pending_rows: List[Dict[str, Any]] = []

    turn_count = 0
    while not game.is_game_over() and turn_count < max_turns:
        current = game.get_current_player()
        legal_moves = game.get_legal_moves(current)
        turn_count += 1
        if not legal_moves:
            game.board._update_current_player()
            game._check_game_over()
            continue

        cur_id = int(current.value)
        ply = int(game.board.move_count)
        board_before = game.board.copy()
        thinking = agents[cur_id - 1].get("thinking_time_ms")
        move, _stats = adapters[cur_id].choose_move(game.board, current, legal_moves, thinking)

        mcts_agent = underlying[cur_id]
        if mcts_agent is not None and len(legal_moves) >= 2:
            rows = _record_decision(
                mcts_agent, board_before, current,
                run_id=run_id, game_id=game_id, seed=seed, ply=ply,
                decision_idx=decision_idx[cur_id],
            )
            if rows:
                pending_rows.extend(rows)
                stats.decisions += 1
                decision_idx[cur_id] += 1

        if move is None or not game.make_move(move, current):
            game.board._update_current_player()
            game._check_game_over()
            continue

    if pending_rows:
        stats.rows = append_policy_rows(pending_rows, output_path)
    return stats


def collect_policy_targets(
    agents: Sequence[Dict[str, Any]],
    *,
    run_id: str,
    num_games: int,
    seed: int,
    output_path: Path | str = DEFAULT_POLICY_CSV,
    verbose: bool = False,
) -> int:
    """Play ``num_games`` games and append policy-target rows. Returns rows written."""
    total = 0
    for g in range(num_games):
        game_seed = seed + g
        # Bake the game seed into the id so re-running collection with a different
        # seed under the same run-id never produces colliding decision_ids (which
        # load_policy_samples groups on) — that would merge unrelated positions.
        stats = play_and_collect(
            agents, run_id=run_id, game_id=f"{run_id}_s{game_seed}_g{g:04d}",
            seed=game_seed, output_path=output_path,
        )
        total += stats.rows
        if verbose:
            print(f"[policy_selfplay] game {g+1}/{num_games}: "
                  f"{stats.decisions} decisions, {stats.rows} rows", flush=True)
    return total


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _default_agents() -> List[Dict[str, Any]]:
    """Champion (MCTS) vs a mix of opponents — the champion seat drives collection."""
    try:
        import copy as _copy

        from scripts.champion_loop import BASE_CHAMPION_PARAMS

        champ = _copy.deepcopy(BASE_CHAMPION_PARAMS)
        champ["name"] = "champion"
        champ2 = _copy.deepcopy(BASE_CHAMPION_PARAMS)
        champ2["name"] = "champion2"
        return [
            champ,
            {"name": "heuristic", "type": "heuristic"},
            champ2,
            {"name": "random", "type": "random"},
        ]
    except Exception:
        return [
            {"name": "heuristic", "type": "heuristic"},
            {"name": "random", "type": "random"},
            {"name": "heuristic2", "type": "heuristic"},
            {"name": "random2", "type": "random"},
        ]


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Collect MCTS visit-count policy targets into data/policy_targets.csv."
    )
    p.add_argument("--num-games", type=int, default=20)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--run-id", default=None,
                   help="Collection run id (default: a unique timestamped id so "
                        "separate runs never collide in data/policy_targets.csv).")
    p.add_argument("--output", default=str(DEFAULT_POLICY_CSV))
    p.add_argument("--thinking-time-ms", type=int, default=None,
                   help="Override every MCTS agent's thinking budget (small ⇒ fast collection).")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    run_id = args.run_id or (
        "policycollect_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    agents = _default_agents()
    if args.thinking_time_ms is not None:
        for a in agents:
            if a.get("type", "mcts") == "mcts":
                a["thinking_time_ms"] = int(args.thinking_time_ms)

    total = collect_policy_targets(
        agents, run_id=run_id, num_games=args.num_games, seed=args.seed,
        output_path=args.output, verbose=args.verbose,
    )
    print(f"[policy_selfplay] wrote {total} rows to {args.output} "
          f"(feature order: {list(MOVE_FEATURE_NAMES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
