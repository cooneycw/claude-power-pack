"""The real shell wrapper loads CPP's configuration from an external cwd."""
import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "bootstrap-check.sh"
pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("python3") is None
    or shutil.which(sys.executable) is None,
    reason="requires bash and a Python interpreter",
)


def test_real_wrapper_lists_cpp_from_outside_and_ignores_caller_lure(tmp_path):
    assert importlib.util.find_spec("yaml") is not None, "the selected test interpreter must have real PyYAML"
    external = tmp_path / "caller"
    external.mkdir()
    assert external != ROOT and ROOT not in external.parents, "caller must be outside CPP"
    (external / ".claude").mkdir()
    (external / ".claude/bootstrap.yaml").write_text(
        'dependencies:\n  caller_owned_lure:\n    check_command: "exit 73"\n    description: "caller only"\n'
    )
    tools = tmp_path / "bin"
    tools.mkdir()
    # Pin only this TEST's ambient python3; the real wrapper's policy is unchanged.
    python = tools / "python3"
    python.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + ' "$@"\n')
    python.chmod(0o755)
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"])
    env.pop("PYTHONPATH", None)
    ready = subprocess.run([str(python), "-c", "import yaml"], cwd=external,
                           env=env, capture_output=True, text=True, timeout=20)
    assert ready.returncode == 0, ready.stderr
    inside = subprocess.run(["bash", str(WRAPPER), "--list"], cwd=ROOT,
                            env=env, capture_output=True, text=True, timeout=20)
    assert inside.returncode == 0 and "jq:" in inside.stdout, inside.stdout + inside.stderr
    outside = subprocess.run(["bash", str(WRAPPER), "--list"], cwd=external,
                             env=env, capture_output=True, text=True, timeout=20)
    assert outside.returncode == 0, outside.stdout + outside.stderr
    assert outside.stdout == inside.stdout
    assert "caller_owned_lure" not in outside.stdout
