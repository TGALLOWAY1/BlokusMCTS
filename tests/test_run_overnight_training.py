"""Tests for the overnight training orchestrator (scripts/run_overnight_training.py).

These cover the safety-critical contract:
  * promotion is opt-in only (no --promote => no --promote forwarded to gauntlet),
  * --dry-run never executes anything,
  * the command plan references real repo scripts,
  * resume skip logic keys off the declared output artifact.
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "run_overnight_training", REPO_ROOT / "scripts" / "run_overnight_training.py"
)
rot = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rot)


def _plan(argv, run_dir="/tmp/run"):
    args = rot.parse_args(argv)
    return rot.build_pipeline(args, Path(run_dir))


def test_default_runs_gauntlet_only():
    stages = _plan([])
    names = [s["name"] for s in stages]
    assert names == ["gauntlet"], names


def test_no_promote_by_default():
    stages = _plan([])
    gauntlet = next(s for s in stages if s["name"] == "gauntlet")
    assert "--promote" not in gauntlet["cmd"]


def test_promote_flag_forwards_to_gauntlet():
    stages = _plan(["--promote"])
    gauntlet = next(s for s in stages if s["name"] == "gauntlet")
    assert "--promote" in gauntlet["cmd"]


def test_full_pipeline_ordering():
    stages = _plan(["--generate-data", "--train-eval"])
    names = [s["name"] for s in stages]
    assert names == ["generate_data", "train_eval", "gauntlet"], names


def test_no_gauntlet_flag():
    stages = _plan(["--generate-data", "--no-gauntlet"])
    names = [s["name"] for s in stages]
    assert names == ["generate_data"], names


def test_plan_references_real_scripts():
    stages = _plan(["--generate-data", "--train-eval"])
    for s in stages:
        # second element of argv is the script path
        script = Path(s["cmd"][1])
        assert script.exists(), f"{s['name']} references missing script {script}"


def test_data_gen_defaults_to_valid_agent():
    # fast_mcts is archived/invalid; the wrapper must not default to it.
    stages = _plan(["--generate-data"])
    gen = next(s for s in stages if s["name"] == "generate_data")
    idx = gen["cmd"].index("--agent-type")
    assert gen["cmd"][idx + 1] == "mcts"


def test_resume_skip_logic(tmp_path):
    snap = tmp_path / "snapshots.parquet"
    stage = {"produces": snap}
    assert rot._should_skip(stage, resume=True) is False
    snap.write_text("x")
    assert rot._should_skip(stage, resume=True) is True
    assert rot._should_skip(stage, resume=False) is False


def test_dry_run_executes_nothing(capsys, tmp_path):
    rc = rot.main(["--dry-run", "--output-dir", str(tmp_path / "nope")])
    assert rc == 0
    # dry-run must not create the run directory
    assert not (tmp_path / "nope").exists()
    out = capsys.readouterr().out
    assert "dry-run" in out.lower()
