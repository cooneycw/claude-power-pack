"""The shipped finish path uses CPP 3.11 while target policy remains independent."""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-finish-gate.sh"


@pytest.mark.skipif(
    shutil.which("uv") is None
    or shutil.which("bash") is None
    or shutil.which("make") is None
    or shutil.which("git") is None,
    reason="requires existing uv, bash, make and git",
)
@pytest.mark.parametrize("explicit_user_policy", [False, True])
@pytest.mark.parametrize("target_environment", [None, "relative", "absolute"])
def test_actual_finish_preserves_dual_native_runtime_policy(tmp_path, explicit_user_policy, target_environment):
    env = os.environ.copy()
    env.pop("UV_PYTHON", None)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    env.update(UV_PYTHON_DOWNLOADS="never", UV_OFFLINE="1", UV_CACHE_DIR=str(tmp_path / "cache"), CPP_OFFLINE="1")
    interpreters = {}
    for minor in ("3.11", "3.12"):
        probe = subprocess.run(
            ["uv", "python", "find", "--no-python-downloads", minor],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if probe.returncode:
            pytest.skip(f"native Python {minor} unavailable; discovery forbids downloads")
        path = Path(probe.stdout.strip())
        version = subprocess.check_output([str(path), "-c", "import sys;print(sys.version_info[:3])"], text=True)
        assert version.startswith("(" + minor.replace(".", ", ") + ","), (path, version)
        interpreters[minor] = path
    target = tmp_path / "target env $literal"
    target.mkdir()
    (target / "pyproject.toml").write_text(
        '[project]\nname="runtime-fixture"\nversion="0.0.0"\nrequires-python=">=3.11"\n'
    )
    (target / ".python-version").write_text("3.12\n")
    (target / "probe.py").write_text(
        "import sys,os,json\nfrom pathlib import Path\n"
        'Path("runtime.json").write_text(json.dumps(dict(version=list(sys.version_info[:3]),'
        'uv_python=os.environ.get("UV_PYTHON"),uv_project_environment=os.environ.get("UV_PROJECT_ENVIRONMENT"),'
        'handoff_keys=[key for key in os.environ if key.startswith("CPP_RUNNER_TARGET_UV_")])))\n'
        'print("owned runtime probe; no test summary")\n'
    )
    (target / "Makefile").write_text(
        "lint:\n\t@echo owned-lint\ntest:\n\t@uv run --no-python-downloads python probe.py\n"
        "typecheck:\n\t@echo owned-typecheck\n"
    )
    env["FLOW_GATE_CPP_DIR"] = str(ROOT)
    policy = str(interpreters["3.12"]) if explicit_user_policy else None
    if policy is not None:
        env["UV_PYTHON"] = policy
    environment_policy = None
    if target_environment:
        virtual = target / ".target env $literal"
        create = subprocess.run(
            ["uv", "venv", "--python", str(interpreters["3.12"]), "--no-python-downloads", str(virtual)],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert create.returncode == 0, create.stderr
        environment_policy = str(virtual) if target_environment == "absolute" else virtual.name
        env["UV_PROJECT_ENVIRONMENT"] = environment_policy

        def snapshot():
            entries = {}
            for path in sorted(virtual.rglob("*")):
                name = str(path.relative_to(virtual))
                if path.is_symlink():
                    entries[name] = ("symlink", os.readlink(path))
                elif path.is_file():
                    entries[name] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
                else:
                    entries[name] = ("directory",)
            return entries

        before = snapshot()
        summary = subprocess.run(
            ["bash", str(SCRIPT), "--check-summary"], cwd=target, env=env, capture_output=True, text=True, timeout=30
        )
        assert summary.returncode in (0, 3), summary.stdout + summary.stderr
        assert snapshot() == before, "outer CPP selection must not rebuild/populate the target environment"
    result = subprocess.run(
        ["bash", str(SCRIPT), "--plan", "check"], cwd=target, env=env, capture_output=True, text=True, timeout=60
    )
    # This is a runtime probe, not pytest execution: missing test-summary
    # evidence must remain WARN rather than manufacturing a passing test gate.
    assert result.returncode == 3, result.stdout + result.stderr
    runtime = json.loads((target / "runtime.json").read_text())
    assert runtime["version"][:2] == [3, 12]
    assert runtime["uv_python"] == policy
    assert runtime["uv_project_environment"] == environment_policy
    assert runtime["handoff_keys"] == []
    outer = subprocess.check_output([str(ROOT / ".venv/bin/python"), "--version"], text=True).strip()
    assert outer.startswith("Python 3.11."), outer
    print(json.dumps(dict(outer=outer, target=runtime, helper_exit=result.returncode)))


def test_unreadable_target_pin_is_explicitly_refused_before_target_execution(tmp_path, monkeypatch):
    import sys
    from io import StringIO

    from lib.cicd.runner import DeterministicRunner, TargetPythonPolicyError, _build_step_env
    from lib.cicd.steps import StepDef

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="bad-pin-fixture"\nversion="0.0.0"\nrequires-python=">=3.11"\n'
    )
    pin = tmp_path / ".python-version"
    pin.symlink_to(pin.name)
    assert pin.is_symlink()
    monkeypatch.delenv("UV_PYTHON", raising=False)
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "cache"))
    with pytest.raises(TargetPythonPolicyError, match="policy is unverified"):
        _build_step_env(tmp_path)
    sentinel = tmp_path / "UNSAFE_READY"
    command = shlex.join([sys.executable, "-c", f"from pathlib import Path; Path({str(sentinel)!r}).touch()"])
    positive = subprocess.run(command, shell=True, cwd=tmp_path, capture_output=True, text=True, timeout=15)
    assert positive.returncode == 0, positive.stderr
    assert sentinel.is_file(), "the exact later-effect command must be capable of writing"
    sentinel.unlink()
    assert not sentinel.exists()
    result = DeterministicRunner(project_root=tmp_path, output=StringIO()).run(
        "owned-policy", step_defs=[StepDef(id="test", command=command, gate=True)]
    )
    assert not result.success and result.steps_completed == 0
    assert "policy is unverified" in result.error
    assert result.step_details[0]["status"] == "not-run"
    assert not sentinel.exists()
