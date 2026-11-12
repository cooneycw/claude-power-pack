"""The outer CPP interpreter selection must preserve an existing environment."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/flow-finish-gate.sh"


def owned_runtime(tmp_path):
    cpp = tmp_path / "owned cpp"
    cpp.mkdir()
    for name in ("pyproject.toml", "uv.lock", ".python-version"):
        shutil.copy2(ROOT / name, cpp / name)
    shutil.copytree(ROOT / "lib", cpp / "lib", ignore=shutil.ignore_patterns("__pycache__"))
    target = tmp_path / "target"
    target.mkdir()
    (target / "Makefile").write_text("lint:\n\t@true\ntest:\n\t@true\ntypecheck:\n\t@true\n")
    return cpp, target


def fingerprint(venv):
    """Read actual files, excluding import-created bytecode caches."""
    return {
        str(path.relative_to(venv)): (
            "link:" + os.readlink(path) if path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest()
        )
        for path in venv.rglob("*")
        if (path.is_file() or path.is_symlink()) and "__pycache__" not in path.parts
    }


@pytest.mark.skipif(
    shutil.which("uv") is None or shutil.which("bash") is None
    or shutil.which("git") is None or shutil.which("make") is None,
    reason="requires uv, bash, git and make",
)
@pytest.mark.parametrize("mode", ["--check-summary", "--plan"])
@pytest.mark.parametrize("rebuild", [False, True])
def test_mismatched_environment_is_refused_without_mutation(tmp_path, mode, rebuild):
    from tests.conftest import find_python, uv_child_env

    env = uv_child_env()
    python = find_python("uv", env, "3.12")
    cpp, target = owned_runtime(tmp_path)
    venv = cpp / ".venv"
    subprocess.run(["uv", "venv", "--python", str(python), str(venv)], env=env, check=True, capture_output=True)
    version = subprocess.check_output([str(venv / "bin/python"), "--version"], text=True).strip()
    assert version.startswith("Python 3.12."), version
    sentinel = venv / "lib/python3.12/site-packages/owned-package.txt"
    sentinel.write_text("A running process still needs this environment.\n")
    before = fingerprint(venv)
    before_cfg = (venv / "pyvenv.cfg").read_text()
    assert before and sentinel.is_file()
    env.update(FLOW_GATE_CPP_DIR=str(cpp), UV_PYTHON_DOWNLOADS="never", UV_OFFLINE="1")
    if rebuild:
        find_python("uv", env, "3.11")
        env["FLOW_GATE_REBUILD_CPP_VENV"] = "1"
    result = subprocess.run(
        ["bash", str(SCRIPT), mode] + (["check"] if mode == "--plan" else []), cwd=target, env=env,
        capture_output=True, text=True, timeout=30,
    )
    after = fingerprint(venv)
    print(json.dumps(dict(
        before=hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
        after=hashlib.sha256(json.dumps(after, sort_keys=True).encode()).hexdigest(),
        before_cfg=before_cfg, after_cfg=(venv / "pyvenv.cfg").read_text(),
        package_preserved=sentinel.exists(), exit=result.returncode,
        stdout=result.stdout, stderr=result.stderr,
    ), sort_keys=True))
    if rebuild:
        assert result.returncode in (0, 3), result.stdout + result.stderr
        assert "explicitly allowing CPP environment rebuild" in result.stderr
        version = subprocess.check_output([str(venv / "bin/python"), "--version"], text=True).strip()
        assert version.startswith("Python 3.11."), version
        assert after != before and not sentinel.exists()
        return
    unchanged = after == before
    assert unchanged, "the gate replaced or changed the existing Python 3.12 environment"
    assert result.returncode == 1, result.stdout + result.stderr
    assert "cpp-runtime-environment-mismatch" in result.stdout + result.stderr
    assert "3.12" in result.stdout + result.stderr and "3.11" in result.stdout + result.stderr
    command = next(line.strip() for line in result.stderr.splitlines() if line.startswith("  uv sync "))
    import shlex

    assert shlex.split(command) == [
        "uv", "sync", "--project", str(cpp), "--python", "3.11", "--no-python-downloads", "--extra", "dev",
    ]


@pytest.mark.skipif(
    shutil.which("uv") is None or shutil.which("bash") is None
    or shutil.which("git") is None or shutil.which("make") is None,
    reason="requires uv, bash, git and make",
)
@pytest.mark.parametrize("dev", [False, True, None, "stdlib", "virtualenv", "equivalent-fields"])
def test_fresh_pin_and_matching_environment_are_preserved(tmp_path, dev):
    from tests.conftest import find_python, uv_child_env

    env = uv_child_env()
    find_python("uv", env, "3.11")
    cpp, target = owned_runtime(tmp_path)
    venv = cpp / ".venv"
    before = None
    if dev is not None:
        # Plain sync must follow the committed pin, with no --python hint.
        sync = subprocess.run(
            ["uv", "sync", "--no-python-downloads", "--project", str(cpp)]
            + (["--extra", "dev"] if dev is True else []),
            env=env, capture_output=True, text=True, timeout=60,
        )
        assert sync.returncode == 0, sync.stderr
        if dev in ("stdlib", "virtualenv", "equivalent-fields"):
            cfg = venv / "pyvenv.cfg"
            content = cfg.read_text()
            line = next(line for line in content.splitlines() if line.startswith("version_info = "))
            version = line.split(" = ")[1]
            spelling = f"version = {version}" if dev == "stdlib" else f"version_info = {version}.final.0"
            cfg.write_text(content.replace(line, spelling))
            if dev == "equivalent-fields":
                cfg.write_text(cfg.read_text() + f"version = {version}\n")
            assert spelling in cfg.read_text()
        before = fingerprint(venv)
    else:
        assert not venv.exists(), "this case must exercise automatic bootstrap"
    env.update(FLOW_GATE_CPP_DIR=str(cpp), UV_PYTHON_DOWNLOADS="never")
    result = subprocess.run(
        ["bash", str(SCRIPT), "--check-summary"], cwd=target, env=env,
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode in (0, 3), result.stdout + result.stderr
    version = subprocess.check_output([str(venv / "bin/python"), "--version"], text=True).strip()
    assert version.startswith("Python 3.11."), version
    if before is not None:
        assert fingerprint(venv) == before


@pytest.mark.skipif(
    shutil.which("uv") is None or shutil.which("bash") is None
    or shutil.which("git") is None or shutil.which("make") is None,
    reason="requires uv, bash, git and make",
)
@pytest.mark.parametrize("broken", ["constant", "contradictory", "contradictory-optin", "wrong-executable"])
def test_unverified_environment_is_refused_before_uv(tmp_path, broken):
    import shlex

    from tests.conftest import find_python, uv_child_env

    env = uv_child_env()
    python = find_python("uv", env, "3.11")
    cpp, target = owned_runtime(tmp_path)
    venv = cpp / ".venv"
    subprocess.run(
        ["uv", "venv", "--python", str(python), "--no-python-downloads", str(venv)],
        env=env, check=True, capture_output=True,
    )
    interpreter = venv / "bin/python"
    version = subprocess.check_output(
        [str(interpreter), "-c", "import sys; print('.'.join(map(str,sys.version_info[:3])))"], text=True,
    ).strip()
    if broken in ("constant", "wrong-executable"):
        # Unlink the owned symlink before writing; its target is shared Python.
        interpreter.unlink()
        command = f"echo {version}" if broken == "constant" else f"exec {shlex.quote(str(python))} \"$@\""
        interpreter.write_text("#!/bin/sh\n" + command + "\n")
        interpreter.chmod(0o755)
        assert not interpreter.is_symlink() and interpreter.read_text().startswith("#!/bin/sh")
    else:
        cfg = venv / "pyvenv.cfg"
        cfg.write_text(cfg.read_text() + "version = 3.12.3\n")
        assert "version_info = 3.11." in cfg.read_text() and "version = 3.12.3" in cfg.read_text()
    if broken == "contradictory-optin":
        env["FLOW_GATE_REBUILD_CPP_VENV"] = "1"
    before = fingerprint(venv)
    env.update(FLOW_GATE_CPP_DIR=str(cpp), UV_PYTHON_DOWNLOADS="never", UV_OFFLINE="1")
    result = subprocess.run(
        ["bash", str(SCRIPT), "--check-summary"], cwd=target, env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "cpp-runtime-environment-unverified" in result.stdout
    assert fingerprint(venv) == before


@pytest.mark.skipif(shutil.which("uv") is None, reason="requires uv")
def test_pin_on_host_with_only_312_refuses_without_download(tmp_path):
    from tests.conftest import find_python, uv_child_env

    env = uv_child_env()
    python = find_python("uv", env, "3.12")
    cpp, _ = owned_runtime(tmp_path)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    (binaries / "python3.12").symlink_to(python)
    uv = shutil.which("uv")
    env.update(
        PATH=str(binaries), UV_PYTHON_INSTALL_DIR=str(tmp_path / "no-managed-python"),
        UV_PYTHON_PREFERENCE="only-system", UV_PYTHON_DOWNLOADS="never",
    )
    present = subprocess.run([uv, "python", "find", "3.12"], cwd=cpp, env=env, capture_output=True, text=True)
    absent = subprocess.run([uv, "python", "find", "3.11"], cwd=cpp, env=env, capture_output=True, text=True)
    assert present.returncode == 0 and absent.returncode != 0, (present, absent)
    result = subprocess.run(
        [uv, "sync", "--extra", "dev", "--no-python-downloads", "--project", str(cpp)],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0 and "3.11" in result.stderr, result.stderr
    assert "download" in result.stderr.lower(), result.stderr
    assert not (cpp / ".venv").exists()
