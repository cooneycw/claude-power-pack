"""Real runner refusal stays bounded for special and oversized target pins."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHILD = r"""
import json,shlex,subprocess,sys
from pathlib import Path
from io import StringIO
from lib.cicd.runner import DeterministicRunner
from lib.cicd.steps import StepDef
root=Path(sys.argv[1]); sentinel=root/'later-effect'
argv=[sys.executable,'-c',f"from pathlib import Path;Path({str(sentinel)!r}).touch()"]
positive=subprocess.run(argv,check=True,timeout=3)
assert sentinel.is_file();sentinel.unlink()
print('OWNED_LATER_EFFECT_POSITIVE',flush=True)
result=DeterministicRunner(project_root=root,output=StringIO()).run('owned-policy',step_defs=[StepDef(id='test',command=shlex.join(argv),gate=True)])
print(json.dumps(dict(success=result.success,completed=result.steps_completed,error=result.error,details=result.step_details,effect=sentinel.exists())))
"""


@pytest.mark.skipif(
    os.name != "posix" or shutil.which("sh") is None or shutil.which("git") is None,
    reason="requires POSIX pin types, sh and git",
)
@pytest.mark.parametrize(
    "mode", ["fifo", "nonregular-symlink", "oversized", "regular", "regular-symlink", "override-fifo"]
)
def test_real_runner_bounded_pin_policy(tmp_path, mode):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="pin-fixture"\nversion="0"\nrequires-python=">=3.11"\n')
    pin = tmp_path / ".python-version"
    if mode in ("fifo", "override-fifo"):
        os.mkfifo(pin)
        assert pin.is_fifo()
    elif mode == "nonregular-symlink":
        assert Path("/dev/null").is_char_device()
        pin.symlink_to("/dev/null")  # Empty finite device, never an unbounded /dev/zero read.
    elif mode == "oversized":
        pin.write_bytes(b"3.12\n" * 1000)
        assert pin.stat().st_size == 5000
    elif mode == "regular-symlink":
        target = tmp_path / "owned-pin"
        target.write_text("3.12\n")
        pin.symlink_to(target.name)
    else:
        pin.write_text("3.12\n")
    env = dict(os.environ, PYTHONPATH=str(ROOT), UV_CACHE_DIR=str(tmp_path / "cache"), CPP_OFFLINE="1")
    env.pop("UV_PYTHON", None)
    if mode == "override-fifo":
        env["UV_PYTHON"] = "3.12"
    try:
        child = subprocess.run(
            [sys.executable, "-c", CHILD, str(tmp_path)], env=env, capture_output=True, text=True, timeout=3
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"target pin read exceeded strict parent deadline; child was killed: {exc.stdout!r}")
    assert child.returncode == 0, child.stderr
    assert "OWNED_LATER_EFFECT_POSITIVE" in child.stdout
    result = json.loads(child.stdout.splitlines()[-1])
    if mode in ("fifo", "nonregular-symlink", "oversized"):
        assert result["success"] is False and result["completed"] == 0
        assert "policy is unverified" in result["error"]
        assert result["details"][0]["status"] == "not-run" and not result["effect"]
    else:
        assert result["completed"] == 1 and result["effect"]


@pytest.mark.parametrize("failure", [None, "read", "decode"])
def test_pin_descriptor_is_closed_and_errors_are_value_free(tmp_path, monkeypatch, failure):
    from lib.cicd import runner

    pin = tmp_path / ".python-version"
    pin.write_bytes(b"\xff" if failure == "decode" else b"3.12\n")
    real_open = os.open
    opened = []

    def record_open(*args, **kwargs):
        fd = real_open(*args, **kwargs)
        opened.append(fd)
        return fd

    def unreadable(*args):
        raise OSError("owned-private-diagnostic-must-not-leak")

    monkeypatch.setattr(runner.os, "open", record_open)
    if failure == "read":
        monkeypatch.setattr(runner.os, "read", unreadable)
    if failure:
        with pytest.raises(runner.TargetPythonPolicyError) as caught:
            runner._observe_target_python_pin(pin)
        assert "policy is unverified" in str(caught.value)
        assert "owned-private-diagnostic" not in str(caught.value)
    else:
        assert runner._observe_target_python_pin(pin)
    assert len(opened) == 1
    with pytest.raises(OSError):
        os.fstat(opened[0])


@pytest.mark.parametrize("size,allowed", [(4096, True), (4097, False)])
def test_pin_bound_is_enforced_on_the_read_even_if_stat_size_is_stale(tmp_path, monkeypatch, size, allowed):
    import stat
    from types import SimpleNamespace

    from lib.cicd import runner

    pin = tmp_path / ".python-version"
    pin.write_bytes(b" " * size)
    monkeypatch.setattr(runner.os, "fstat", lambda fd: SimpleNamespace(st_mode=stat.S_IFREG, st_size=0))
    if allowed:
        assert runner._observe_target_python_pin(pin)
    else:
        with pytest.raises(runner.TargetPythonPolicyError, match="policy is unverified"):
            runner._observe_target_python_pin(pin)
