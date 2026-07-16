"""Phase 7: teacher self-play data pipeline (agent-strength rescue).

Plays standard-scored self-play games between four TEACHER agents — the
Phase-4-validated D-016 configuration (progressive widening + ridge-model
leaves) at the D-008 teacher budget (500 iterations) — and records a FULL
training example per decision (master plan §14):

  record_schema teacher_record_v1:
    game_id, decision_index, ply, player_id, seat_map,
    state             (Board.to_dict(), board_state_v1 — BEFORE the move)
    legal_actions     (move_v1 dicts, canonical order)
    search            ({action, visits, q} per expanded root child;
                       q = root player's mean reward at that child)
    policy_target     (visit distribution over `search` entries, sums to 1)
    selected_action   (move_v1)
    root_value        (root player's visit-weighted mean child q)
    final_scores / final_ranks (per player.value, backfilled at game end)
    search_config, value_model {path, sha256}, game_seed, agent_seed

Output is a manifested, immutable dataset directory (JSONL shards per game +
manifest.json), mirroring data/value_dataset_v1 conventions. `--validate DIR`
re-checks every record against the engine (state round-trip, legal-move
regeneration, selected-action legality, policy-target alignment,
rank/score consistency, manifest counts) and must pass before any training
consumes the dataset.

    python -m training.experiments.teacher_selfplay \
        --games 18 --seed 20260715 --deadline-minutes 400 --out data/teacher_dataset_v1
    python -m training.experiments.teacher_selfplay --validate data/teacher_dataset_v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.board import STATE_SCHEMA_VERSION, Board, Player
from engine.game import SCORING_MODE_STANDARD, BlokusGame
from engine.move_generator import ACTION_SCHEMA_VERSION, Move, get_shared_generator
from mcts.mcts_agent import MCTSAgent

RECORD_SCHEMA_VERSION = "teacher_record_v2"  # v2: + move_selection field
TEACHER_ITERATIONS = 500  # D-008
VALUE_MODEL_PATH = "training/artifacts/value_models/v1/value_v1_ridge_baseline.joblib"

# Self-play diversity: model-leaf teacher agents are fully deterministic (no
# rollouts -> the seeded RNG is never consulted), so four identical teachers
# replay the SAME game regardless of seed (observed: 18/18 identical games).
# Standard remedy: for the first TEMPERATURE_DECISIONS decisions of each game,
# sample the played move from the root visit distribution (tau=1.0, seeded per
# game) instead of taking the argmax; later decisions use the argmax. The
# policy TARGET recorded for training is always the visit distribution.
TEMPERATURE_DECISIONS = 24  # ~first 6 decisions per player

TEACHER_SEARCH_CONFIG: Dict[str, Any] = {
    "iterations": TEACHER_ITERATIONS,
    "rollout_policy": "greedy_sample",
    "greedy_sample_size": 12,
    "rollout_cutoff_depth": 12,
    "heuristic_move_ordering": True,
    "exploration_constant": 1.414,
    "use_transposition_table": True,
    "progressive_widening_enabled": True,
    "pw_c": 2.0,
    "pw_alpha": 0.5,
}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_teacher(seed: int, search_config: Optional[Dict[str, Any]] = None,
                   value_model_path: Optional[str] = VALUE_MODEL_PATH) -> MCTSAgent:
    agent = MCTSAgent(seed=seed, value_model_path=value_model_path,
                      **(search_config or TEACHER_SEARCH_CONFIG))
    agent._capture_root_moves = True
    agent.num_workers = 1
    return agent


def play_teacher_game(game_seed: int, game_id: str,
                      value_model_sha: str,
                      search_config: Optional[Dict[str, Any]] = None,
                      value_model_path: Optional[str] = VALUE_MODEL_PATH,
                      ) -> List[Dict[str, Any]]:
    """Play one 4-teacher game; return the per-decision records (finals filled)."""
    import random as _random

    generator = get_shared_generator()
    game = BlokusGame(scoring_mode=SCORING_MODE_STANDARD, enable_telemetry=False)
    cfg = search_config or TEACHER_SEARCH_CONFIG
    agents = {p: _build_teacher(seed=game_seed * 31 + p.value,
                                search_config=cfg,
                                value_model_path=value_model_path)
              for p in Player}
    seat_map = {str(p.value): f"teacher_{p.value}" for p in Player}
    sample_rng = _random.Random(game_seed)

    records: List[Dict[str, Any]] = []
    decision_index = 0
    consecutive_passes = 0
    while consecutive_passes < len(Player):
        player = game.board.current_player
        legal_moves = generator.get_legal_moves(game.board, player)
        if not legal_moves:
            game.board._update_current_player()
            consecutive_passes += 1
            continue
        consecutive_passes = 0

        state_payload = game.board.to_dict()
        agent = agents[player]
        # select_action short-circuits on a single legal move WITHOUT running
        # a search or refreshing the capture attrs — clear them first so a
        # forced move can never inherit the previous decision's stale root
        # stats (review finding, PR #203).
        agent._last_root_move_stats = None
        move = agent.select_action(game.board, player, legal_moves)
        if move is None:
            game.board._update_current_player()
            continue

        if len(legal_moves) == 1:
            # Forced move: no search ran; the policy target is trivially 1.0.
            stats = [(legal_moves[0], 1, 0.0)]
        else:
            stats = agent._last_root_move_stats or []
        total_visits = sum(v for _, v, _ in stats) or 1
        search_entries = [
            {"action": m.to_dict(), "visits": int(v),
             "q": (r / v) if v else 0.0}
            for m, v, r in stats
        ]
        root_value = (
            sum(e["q"] * e["visits"] for e in search_entries) / total_visits
            if search_entries else 0.0
        )

        # Diversity: opening-phase visit sampling (see TEMPERATURE_DECISIONS).
        move_selection = "argmax"
        if decision_index < TEMPERATURE_DECISIONS and len(stats) > 1:
            move = sample_rng.choices(
                [m for m, _, _ in stats], weights=[v for _, v, _ in stats], k=1
            )[0]
            move_selection = "visit_sample_t1.0"
        records.append({
            "record_schema_version": RECORD_SCHEMA_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "action_schema_version": ACTION_SCHEMA_VERSION,
            "game_id": game_id,
            "decision_index": decision_index,
            "ply": int(game.board.move_count),
            "player_id": int(player.value),
            "seat_map": seat_map,
            "state": state_payload,
            "legal_actions": [m.to_dict() for m in legal_moves],
            "search": search_entries,
            "policy_target": [e["visits"] / total_visits for e in search_entries],
            "selected_action": move.to_dict(),
            "move_selection": move_selection,
            "root_value": float(root_value),
            "search_config": cfg,
            "value_model": ({"path": value_model_path, "sha256": value_model_sha}
                            if value_model_path else None),
            "game_seed": int(game_seed),
            "agent_seed": int(game_seed * 31 + player.value),
            "final_scores": None,   # backfilled below
            "final_ranks": None,
        })
        decision_index += 1
        assert game.make_move(move, player), f"{game_id}: teacher move rejected"
        # Reset agent NST/history continuity is unnecessary between moves;
        # tables are per-game by design.

    result = game.get_game_result()
    scores = {str(pid): int(s) for pid, s in result.scores.items()}
    ordered = sorted(result.scores.items(), key=lambda kv: -kv[1])
    ranks: Dict[str, int] = {}
    rank = 0
    prev_score = None
    for idx, (pid, score) in enumerate(ordered, start=1):
        if score != prev_score:
            rank = idx
            prev_score = score
        ranks[str(pid)] = rank
    for record in records:
        record["final_scores"] = scores
        record["final_ranks"] = ranks
    return records


# ---------------------------------------------------------------------------
# Generation CLI
# ---------------------------------------------------------------------------

def generate(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(out_dir.glob("game_*.jsonl"))
    if existing and not args.resume:
        raise SystemExit(
            f"{out_dir} already holds game shards — datasets are immutable. "
            "Use a new --out directory, or --resume to continue an interrupted "
            "generation (same seed scheme; completed shards untouched)."
        )
    if args.resume and existing:
        manifest_on_disk = json.loads((out_dir / "manifest.json").read_text())
        if manifest_on_disk.get("status") == "finalized":
            raise SystemExit(f"{out_dir} is finalized — refusing to resume.")
        if manifest_on_disk.get("seed") != args.seed:
            raise SystemExit(
                f"--resume seed mismatch: manifest has {manifest_on_disk.get('seed')}, "
                f"got {args.seed}."
            )
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                text=True, check=True).stdout.strip()
    except Exception:
        commit = "unknown"
    search_config = dict(TEACHER_SEARCH_CONFIG, iterations=args.iterations)
    value_model_path = args.value_model if args.value_model else None
    value_model_sha = _sha256(value_model_path) if value_model_path else None

    manifest = {
        "dataset_schema_version": "teacher_dataset_v1",
        "record_schema_version": RECORD_SCHEMA_VERSION,
        "purpose": "Phase 7 teacher self-play (gate C training corpus)",
        "generating_commit": commit,
        "scoring_mode": "standard",
        "teacher_search_config": search_config,
        "value_model": ({"path": value_model_path, "sha256": value_model_sha}
                        if value_model_path else None),
        "seed": args.seed,
        "num_games_requested": args.games,
        "status": "generating",
        "games_completed": 0,
        "records_written": 0,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    deadline = time.monotonic() + args.deadline_minutes * 60.0
    t0 = time.monotonic()
    # Count already-complete shards (resume) into the totals.
    total_records = sum(
        len(p.read_text().splitlines()) for p in out_dir.glob("game_*.jsonl")
    )
    completed = len(list(out_dir.glob("game_*.jsonl")))
    fresh_games = 0
    for g in range(args.games):
        if (out_dir / f"game_{g:04d}.jsonl").exists():
            continue  # completed before an interruption (resume)
        if fresh_games >= args.min_games and time.monotonic() >= deadline:
            print(f"deadline reached after {completed}/{args.games} games", flush=True)
            break
        game_seed = args.seed + g
        game_id = f"tds1_s{args.seed}_g{g:04d}"
        t_game = time.monotonic()
        records = play_teacher_game(
            game_seed, game_id, value_model_sha,
            search_config=search_config, value_model_path=value_model_path)
        shard = out_dir / f"game_{g:04d}.jsonl"
        with shard.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        completed += 1
        fresh_games += 1
        total_records += len(records)
        print(f"game {g + 1}/{args.games}: {len(records)} decisions in "
              f"{(time.monotonic() - t_game) / 60:.1f} min "
              f"(scores={records[0]['final_scores']})", flush=True)
        manifest.update(status="generating", games_completed=completed,
                        records_written=total_records)
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    manifest.update(status="finalized", games_completed=completed,
                    records_written=total_records,
                    elapsed_sec=round(time.monotonic() - t0, 1))
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\n{total_records} records / {completed} games "
          f"in {(time.monotonic() - t0) / 60:.1f} min -> {out_dir}")
    return 0


# ---------------------------------------------------------------------------
# Validator (must pass before training consumes the dataset)
# ---------------------------------------------------------------------------

def validate(dataset_dir: Path) -> int:
    generator = get_shared_generator()
    manifest = json.loads((dataset_dir / "manifest.json").read_text())
    shards = sorted(dataset_dir.glob("game_*.jsonl"))
    errors: List[str] = []
    records_seen = 0
    games_seen = 0

    def move_key(d: Dict[str, Any]):
        return (d["piece_id"], d["orientation"], d["anchor_row"], d["anchor_col"])

    for shard in shards:
        games_seen += 1
        for line_no, line in enumerate(shard.read_text().splitlines()):
            record = json.loads(line)
            records_seen += 1
            where = f"{shard.name}:{line_no}"
            board = Board.from_dict(record["state"])
            regenerated = {move_key(m.to_dict())
                           for m in generator.get_legal_moves(
                               board, Player(record["player_id"]))}
            recorded = [move_key(a) for a in record["legal_actions"]]
            if set(recorded) != regenerated:
                errors.append(f"{where}: legal-action set mismatch")
            if move_key(record["selected_action"]) not in regenerated:
                errors.append(f"{where}: selected action not legal")
            search_keys = [move_key(e["action"]) for e in record["search"]]
            if not set(search_keys) <= set(recorded):
                errors.append(f"{where}: search entry not in legal actions")
            pt = record["policy_target"]
            if len(pt) != len(record["search"]) or abs(sum(pt) - 1.0) > 1e-6:
                errors.append(f"{where}: policy target misaligned/unnormalized")
            scores = record["final_scores"]
            ranks = record["final_ranks"]
            if set(scores) != {"1", "2", "3", "4"} or set(ranks) != {"1", "2", "3", "4"}:
                errors.append(f"{where}: player-vector keys wrong")
            else:
                # Recompute standard-competition ranks from the scores and
                # require exact equality (equal scores <=> equal ranks;
                # review finding, PR #203).
                ordered = sorted(scores, key=lambda k: -scores[k])
                expected: Dict[str, int] = {}
                rank = 0
                prev = None
                for idx, key in enumerate(ordered, start=1):
                    if scores[key] != prev:
                        rank = idx
                        prev = scores[key]
                    expected[key] = rank
                if expected != {k: int(v) for k, v in ranks.items()}:
                    errors.append(f"{where}: ranks {ranks} != expected {expected}")
        if errors and len(errors) > 20:
            break

    if manifest.get("games_completed") != games_seen:
        errors.append(f"manifest games_completed={manifest.get('games_completed')} "
                      f"!= shards found {games_seen}")
    if manifest.get("records_written") != records_seen:
        errors.append(f"manifest records_written={manifest.get('records_written')} "
                      f"!= records found {records_seen}")

    if errors:
        print(f"VALIDATION FAILED ({len(errors)} errors):")
        for e in errors[:20]:
            print("  " + e)
        return 1
    print(f"VALIDATION PASSED: {records_seen} records / {games_seen} games, "
          f"manifest consistent.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m training.experiments.teacher_selfplay", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--games", type=int, default=18)
    parser.add_argument("--seed", type=int, default=20260715)
    parser.add_argument("--deadline-minutes", type=float, default=400.0)
    parser.add_argument("--min-games", type=int, default=4)
    parser.add_argument("--out", default="data/teacher_dataset_v1")
    parser.add_argument("--iterations", type=int, default=TEACHER_ITERATIONS,
                        help="search budget per move (default: D-008 teacher 500; "
                             "bulk corpora use 50)")
    parser.add_argument("--value-model", default=VALUE_MODEL_PATH,
                        help="leaf value-model artifact; pass '' for rollout leaves")
    parser.add_argument("--resume", action="store_true",
                        help="continue an interrupted (non-finalized) generation: "
                             "skip existing shards, same seed scheme")
    parser.add_argument("--validate", default=None, metavar="DIR",
                        help="validate an existing dataset directory and exit")
    args = parser.parse_args(argv)
    if args.validate:
        return validate(Path(args.validate))
    return generate(args)


if __name__ == "__main__":
    sys.exit(main())
