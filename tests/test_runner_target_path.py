"""Design-stage #1801 regressions, using the real CPP_RUN array and runner.

This executes only one owned custom plan. It does not run a finish gate.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/runner_target_path"
pytestmark = pytest.mark.skipif(
    shutil.which("uv") is None or shutil.which("bash") is None
    or shutil.which("sh") is None or shutil.which("python3") is None,
    reason="needs uv, bash, sh and Python for the owned real-runner fixture",
)


def run_probe(work: Path, target_uv_environment: bool) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    target = work / "target"
    target.mkdir()
    target_venv = target / ".target-venv"
    target_python = shutil.which("python3", path="/usr/bin:/bin")
    assert target_python, "precondition: fixture needs an interpreter outside CPP's venv"
    subprocess.run(["uv", "venv", "--python", target_python, "--no-python-downloads", str(target_venv)],
                   check=True, capture_output=True, text=True, timeout=30)
    target_path = f"{target_venv / 'bin'}:/usr/local/bin:/usr/bin:/bin"
    assert shutil.which("python3", path=target_path) == str(target_venv / "bin/python3")
    assert str(target_venv / "bin") != str(ROOT / ".venv/bin")
    shutil.copy2(FIXTURE / "probe.sh", target / "probe.sh")
    (target / ".claude").mkdir()
    (target / ".claude/cicd_tasks.yml").write_text(
        'version: "1"\nsteps:\n  path_probe:\n    command: sh probe.sh\n'
        '    timeout: 30\nplans:\n  path_probe:\n    steps: [path_probe]\n')
    # Extract the shipped assignment verbatim, rather than duplicate its argv.
    source = (ROOT / "scripts/flow-finish-gate.sh").read_text()
    wrapper = "CPP_RUN=(" + source.split("CPP_RUN=(", 1)[1].split("\n\n", 1)[0]
    assert wrapper.endswith("python -m lib.cicd)"), "the wrapper extraction must be complete"
    (work / "wrapper.txt").write_text(wrapper + "\n")
    env = os.environ.copy()
    for key in ("UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV", "PYTHONHOME", "UV_PYTHON",
                "CPP_RUNNER_TARGET_PATH", "CPP_RUNNER_TARGET_PATH_PRESENT"):
        env.pop(key, None)
    env.update(PATH=target_path, CPP_DIR=str(ROOT), PYTHONPATH=f"{FIXTURE}:{ROOT}",
               CPP_OFFLINE="1", UV_OFFLINE="1",
               CPP_PATH_PROBE_RUNNER_RECORD=str(work / "runner-environment.json"))
    if target_uv_environment:
        env["UV_PROJECT_ENVIRONMENT"] = str(target_venv)
    caller = {key: env.get(key) for key in ("PATH", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")}
    done = subprocess.run(["bash", "-c", wrapper + '\n"${CPP_RUN[@]}" run --plan path_probe'],
                          cwd=target, env=env, capture_output=True, text=True, timeout=60, check=False)
    (work / "stdout.log").write_text(done.stdout)
    (work / "stderr.log").write_text(done.stderr)
    assert done.returncode == 0, done.stdout + done.stderr
    observed = {"caller": caller,
                "runner": json.loads((work / "runner-environment.json").read_text()),
                "step": json.loads((target / "step-environment.json").read_text()),
                "command_v": (target / "step-command-v.txt").read_text().strip(),
                "version_output": (target / "step-version.txt").read_text().strip(),
                "target_python": str(target_venv / "bin/python3"),
                "source": str(ROOT / "scripts/flow-finish-gate.sh"),
                "runner_source": str(ROOT / "lib/cicd/runner.py")}
    (work / "observation.json").write_text(json.dumps(observed, indent=2) + "\n")
    return observed


@pytest.mark.parametrize("target_uv_environment", [False, True])
def test_bare_python_uses_the_target_callers_interpreter(tmp_path: Path, target_uv_environment: bool) -> None:
    observed = run_probe(tmp_path, target_uv_environment)
    assert observed["step"]["VIRTUAL_ENV"] is None
    expected_uv = observed["caller"]["UV_PROJECT_ENVIRONMENT"]
    assert observed["step"]["UV_PROJECT_ENVIRONMENT"] == expected_uv
    assert observed["command_v"] == observed["target_python"], observed
    assert observed["step"]["PATH"] == observed["caller"]["PATH"], observed


@pytest.mark.parametrize("target_uv_environment", [False, True])
def test_the_runners_own_interpreter_stays_in_cpp(tmp_path: Path, target_uv_environment: bool) -> None:
    observed = run_probe(tmp_path, target_uv_environment)
    assert Path(observed["runner"]["executable"]).parent == ROOT / ".venv/bin"
    assert observed["runner"]["prefix"] == str(ROOT / ".venv")
    assert observed["runner"]["version"].startswith("3.11.")
    assert observed["runner"]["VIRTUAL_ENV"] == str(ROOT / ".venv")
