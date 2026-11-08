"""Execute the actual project:init Makefile snippet against owned scratch projects."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="bash is required for the command snippet")


def step4a() -> str:
    source = (ROOT / ".claude/commands/project/init.md").read_text()
    section = source.split("### 4a: Makefile Generation (from lib/cicd)", 1)[1]
    snippet = section.split("```bash\n", 1)[1].split("```", 1)[0]
    locator = "for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack;"
    assert snippet.count(locator) == 1
    # Only the host-specific locator changes; the executable snippet is source.
    return snippet.replace(locator, "for dir in " + shlex.quote(str(ROOT)) + ";")


def environment(tmp_path: Path, *, fail: bool = False) -> tuple[dict[str, str], Path]:
    binary = tmp_path / "bin"
    binary.mkdir()
    stub = binary / "uv"
    if fail:
        stub.write_text("#!/bin/sh\nexit 19\n")
    else:
        # Exercise the real CLI and guarded writer with the test interpreter,
        # without asking uv to create another environment or fetch dependencies.
        stub.write_text(f"#!{sys.executable}\n" + """import os, sys
assert sys.argv[1:3] == ['run', '--project'], sys.argv
assert sys.argv[4] == 'python', sys.argv
os.execv(sys.executable, [sys.executable, *sys.argv[5:]])
""")
    stub.chmod(0o755)
    env = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]}
    assert shutil.which("uv", path=env["PATH"]) == str(stub)
    return env, stub


def run_step(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    return subprocess.run([BASH, "-c", step4a()], cwd=repo, env=env, capture_output=True, text=True, timeout=20)


def test_silent_generator_failure_cannot_create_makefile_or_report_success(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    env, stub = environment(tmp_path, fail=True)
    precondition = subprocess.run([str(stub)], capture_output=True, text=True)
    assert precondition.returncode == 19 and precondition.stdout == ""
    assert not (repo / "Makefile").exists()
    result = run_step(repo, env)
    assert result.returncode == 19, result.stdout + result.stderr
    assert not (repo / "Makefile").exists()
    assert "Generated Makefile" not in result.stdout and "Wrote Makefile:" not in result.stdout
    assert not (repo / ".claude/cicd.yml").exists(), "failed generation must stop setup"


@pytest.mark.parametrize("framework,command", [("django", "manage.py test"), ("node", "npm test")])
def test_success_is_reported_by_the_actual_guarded_writer(tmp_path, framework, command):
    repo = tmp_path / "project"
    repo.mkdir()
    if framework == "django":
        (repo / "manage.py").write_text("# fixture Django entry\n")
        (repo / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="0.0.0"\n')
    else:
        (repo / "package.json").write_text(json.dumps({"name": "fixture", "version": "0.0.0"}))
        (repo / "package-lock.json").write_text("{}")
    env, _ = environment(tmp_path)
    result = run_step(repo, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert command in (repo / "Makefile").read_text()
    assert "Wrote Makefile:" in result.stdout
    assert "Generated Makefile from detected framework" not in result.stdout


@pytest.mark.parametrize("entry", ["file", "symlink", "dangling", "directory"])
def test_existing_entry_is_preserved_and_not_regenerated(tmp_path, entry):
    repo = tmp_path / "project"
    repo.mkdir()
    target = repo / "Makefile"
    external = tmp_path / "owner-content"
    if entry == "file":
        target.write_text("owner Makefile\n")
        target.chmod(0o640)
    elif entry == "directory":
        target.mkdir()
        (target / "owner-file").write_text("owner bytes\n")
    else:
        if entry == "symlink":
            external.write_text("owner bytes\n")
        else:
            assert not external.exists()
        target.symlink_to(external)
        assert target.is_symlink()
    before = target.lstat()
    env, _ = environment(tmp_path, fail=True)
    result = run_step(repo, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert target.lstat().st_ino == before.st_ino
    assert target.lstat().st_mode == before.st_mode
    if entry == "file":
        assert target.read_text() == "owner Makefile\n"
    elif entry == "directory":
        assert (target / "owner-file").read_text() == "owner bytes\n"
    elif entry == "symlink":
        assert target.is_symlink() and external.read_text() == "owner bytes\n"
    else:
        assert target.is_symlink() and not external.exists()
    assert "Preserved existing Makefile entry" in result.stdout
    assert "Wrote Makefile:" not in result.stdout
