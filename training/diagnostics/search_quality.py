"""Search-quality diagnostic: is the search deep enough to teach from?

Measures, for the champion (or any agent config) across a ladder of iteration
budgets, on a fixed set of seeded probe positions:

* wall-clock per move and per iteration,
* tree size / max / mean depth, root children expanded, visit entropy,
* how much of the budget the root soaks up (children with >= 2 visits),
* move-choice agreement with the largest ("reference") budget,
* move-choice stability and root-value spread across repeated seeded runs.

This is the measurement behind the "shallow search => weak training labels"
hypothesis: if the chosen move rarely changes between the smallest and the
reference budget, the extra iterations are not converting into decisions; if
it changes a lot, the small-budget labels (visit counts, outcomes) are noise.

    python -m training.diagnostics.search_quality \
        --budgets 50,250,1000 --repeats 2 --plies 4,16,32,52

Writes a JSON report (default training/reports/search_quality.json) and
prints a per-position table plus a summary.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from engine.game import BlokusGame
from mcts.mcts_agent import MCTSAgent
from training import REPO_ROOT

DEFAULT_OUTPUT = REPO_ROOT / "training" / "reports" / "search_quality.json"


# ---------------------------------------------------------------------------
# Probe positions
# ---------------------------------------------------------------------------


@dataclass
class ProbePosition:
    ply: int
    board: Any
    player: Any
    legal_moves: List[Any]


def generate_probe_positions(plies: Sequence[int], seed: int) -> List[ProbePosition]:
    """Play a seeded heuristic-agent game and snapshot boards at the given plies."""
    from agents.heuristic_agent import HeuristicAgent

    wanted = sorted(set(int(p) for p in plies))
    game = BlokusGame()
    agent = HeuristicAgent(seed=seed)
    positions: List[ProbePosition] = []
    ply = 0
    while not game.is_game_over() and wanted:
        player = game.get_current_player()
        moves = game.get_legal_moves(player)
        if not moves:
            game.board._update_current_player()
            game._check_game_over()
            continue
        if ply == wanted[0]:
            positions.append(
                ProbePosition(
                    ply=ply,
                    board=copy.deepcopy(game.board),
                    player=player,
                    legal_moves=list(moves),
                )
            )
            wanted.pop(0)
        move = agent.select_action(game.board, player, moves)
        if move is None or not game.make_move(move, player):
            break
        ply += 1
    return positions


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


def _move_key(move: Any) -> Optional[str]:
    if move is None:
        return None
    return f"{move.piece_id}:{move.orientation}@{move.anchor_row},{move.anchor_col}"


@dataclass
class RunMeasurement:
    budget: int
    seed: int
    move: Optional[str]
    elapsed_s: float
    tree_size: int
    tree_depth_max: int
    tree_depth_mean: float
    root_children: int
    root_children_multivisit: int
    visit_entropy: float
    best_move_q: Optional[float]
    second_best_q: Optional[float]
    top_moves: List[Dict[str, Any]] = field(default_factory=list)


def measure_search(
    position: ProbePosition,
    agent_params: Dict[str, Any],
    budget: int,
    seed: int,
) -> RunMeasurement:
    """Run one seeded search at ``budget`` iterations and capture tree metrics."""
    params = dict(agent_params)
    params.pop("iterations", None)
    params.pop("time_limit", None)
    agent = MCTSAgent(iterations=budget, seed=seed, **params)
    board = copy.deepcopy(position.board)
    t0 = time.monotonic()
    move = agent.select_action(board, position.player, list(position.legal_moves))
    elapsed = time.monotonic() - t0
    stats = agent.stats
    top = stats.get("topMoves") or []
    multivisit = sum(1 for m in top if m.get("visits", 0) >= 2)
    # topMoves is capped at 10; recover the real multi-visit count from entropy
    # data if present. Fall back to the capped count (still informative).
    return RunMeasurement(
        budget=budget,
        seed=seed,
        move=_move_key(move),
        elapsed_s=round(elapsed, 3),
        tree_size=int(stats.get("tree_size", 0)),
        tree_depth_max=int(stats.get("tree_depth_max", 0)),
        tree_depth_mean=float(stats.get("tree_depth_mean", 0.0)),
        root_children=int(stats.get("root_legal_moves", 0)),
        root_children_multivisit=multivisit,
        visit_entropy=float(stats.get("visit_entropy", 0.0)),
        best_move_q=stats.get("best_move_q"),
        second_best_q=stats.get("second_best_q"),
        top_moves=[
            {k: m.get(k) for k in ("piece_id", "orientation", "anchor_row", "anchor_col", "visits", "q_value")}
            for m in top[:5]
        ],
    )


def run_diagnostic(
    agent_params: Dict[str, Any],
    *,
    budgets: Sequence[int],
    plies: Sequence[int],
    repeats: int,
    seed: int,
) -> Dict[str, Any]:
    """Run the full ladder and aggregate agreement/stability metrics."""
    budgets = sorted(set(int(b) for b in budgets))
    reference_budget = budgets[-1]
    positions = generate_probe_positions(plies, seed=seed)

    per_position: List[Dict[str, Any]] = []
    for pos in positions:
        runs: Dict[int, List[RunMeasurement]] = {}
        for budget in budgets:
            runs[budget] = [
                measure_search(pos, agent_params, budget,
                               seed=(seed * 1000 + budget * 17 + r) % (2**31))
                for r in range(repeats)
            ]
        ref_moves = [m.move for m in runs[reference_budget]]
        entry: Dict[str, Any] = {
            "ply": pos.ply,
            "branching_factor": len(pos.legal_moves),
            "player": int(pos.player.value),
            "reference_budget": reference_budget,
            "budgets": {},
        }
        for budget in budgets:
            ms = runs[budget]
            moves = [m.move for m in ms]
            entry["budgets"][str(budget)] = {
                "runs": [asdict(m) for m in ms],
                "mean_elapsed_s": round(float(np.mean([m.elapsed_s for m in ms])), 3),
                "ms_per_iteration": round(1000.0 * float(np.mean([m.elapsed_s for m in ms])) / budget, 2),
                "mean_tree_depth_max": round(float(np.mean([m.tree_depth_max for m in ms])), 2),
                "mean_tree_size": round(float(np.mean([m.tree_size for m in ms])), 1),
                "move_stability": round(
                    max((moves.count(mv) for mv in set(moves)), default=0) / max(len(moves), 1), 3
                ),
                "agreement_with_reference": round(
                    float(np.mean([mv in ref_moves for mv in moves])), 3
                ),
                "q_spread": round(
                    float(np.std([m.best_move_q for m in ms if m.best_move_q is not None] or [0.0])), 4
                ),
            }
        per_position.append(entry)

    summary: Dict[str, Any] = {"budgets": {}}
    for budget in budgets:
        rows = [p["budgets"][str(budget)] for p in per_position]
        summary["budgets"][str(budget)] = {
            "mean_tree_depth_max": round(float(np.mean([r["mean_tree_depth_max"] for r in rows])), 2),
            "mean_ms_per_iteration": round(float(np.mean([r["ms_per_iteration"] for r in rows])), 2),
            "mean_move_stability": round(float(np.mean([r["move_stability"] for r in rows])), 3),
            "mean_agreement_with_reference": round(
                float(np.mean([r["agreement_with_reference"] for r in rows])), 3
            ),
        }
    return {
        "agent_params": agent_params,
        "budgets": list(budgets),
        "reference_budget": reference_budget,
        "repeats": repeats,
        "seed": seed,
        "positions": per_position,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def champion_agent_params() -> Dict[str, Any]:
    """The registry champion's engine params (search settings + eval weights)."""
    from mcts_lab._common import load_state
    from training import TrainingPaths

    state = load_state(TrainingPaths.default())
    champ = state.get("champion_params") or {}
    params = dict(champ.get("params") or {})
    # champion.json historically double-nests params.params.
    if "params" in params and isinstance(params["params"], dict):
        params = dict(params["params"])
    # Strip arena/build-layer keys that MCTSAgent's constructor does not take.
    for key in ("deterministic_time_budget", "iterations_per_ms", "thinking_time_ms",
                "type", "name", "parallel_strategy"):
        params.pop(key, None)
    params["num_workers"] = 1
    return params


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budgets", default="50,250,1000",
                    help="comma-separated iteration budgets; the largest is the reference")
    ap.add_argument("--plies", default="4,16,32,52",
                    help="comma-separated plies at which to snapshot probe positions")
    ap.add_argument("--repeats", type=int, default=2,
                    help="seeded repeats per (position, budget) for stability measurement")
    ap.add_argument("--seed", type=int, default=20260707)
    ap.add_argument("--agent-json", default=None,
                    help="path to a JSON dict of MCTSAgent params (default: registry champion)")
    ap.add_argument("--out", default=str(DEFAULT_OUTPUT))
    args = ap.parse_args(argv)

    if args.agent_json:
        agent_params = json.loads(Path(args.agent_json).read_text(encoding="utf-8"))
    else:
        agent_params = champion_agent_params()

    random.seed(args.seed)
    np.random.seed(args.seed % (2**32))

    budgets = [int(b) for b in args.budgets.split(",") if b.strip()]
    plies = [int(p) for p in args.plies.split(",") if p.strip()]
    report = run_diagnostic(
        agent_params, budgets=budgets, plies=plies, repeats=args.repeats, seed=args.seed
    )

    print(f"{'ply':>4} {'bf':>4} | " + " | ".join(f"{b:>6}it" for b in report["budgets"]))
    for pos in report["positions"]:
        cells = []
        for b in report["budgets"]:
            r = pos["budgets"][str(b)]
            cells.append(f"d{r['mean_tree_depth_max']:.0f} a{r['agreement_with_reference']:.2f}")
        print(f"{pos['ply']:>4} {pos['branching_factor']:>4} | " + " | ".join(f"{c:>8}" for c in cells))
    print("\nsummary (per budget): depth / ms-per-iter / stability / agreement-with-ref")
    for b, s in report["summary"]["budgets"].items():
        print(f"  {b:>6} iters: depth={s['mean_tree_depth_max']:.1f} "
              f"ms/iter={s['mean_ms_per_iteration']:.1f} "
              f"stability={s['mean_move_stability']:.2f} "
              f"agreement={s['mean_agreement_with_reference']:.2f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
