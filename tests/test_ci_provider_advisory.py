"""The pre-merge "no recorded CI provider" advisory (issue #1677).

`scripts/ci-provider-advisory.sh` prints ONE line when the project it is pointed
at has no usable provider record, and nothing otherwise. It always exits 0.
Silence covers both "recorded" and "could not ask", so the cases here pin each
of those separately - a test that only saw silence could not tell them apart.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADVISORY = ROOT / "scripts" / "ci-provider-advisory.sh"
HOOK = ROOT / "scripts" / "hook-pending-retro.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None, reason="requires bash and git"
)
pytest.importorskip("yaml")


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"CPP_CI_ADVISORY_ROOT": str(ROOT), **extra})
    return env


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, env=_env())


def _project(tmp_path: Path, *, pipeline: bool = True) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    _git(project, "init", "-q")
    if pipeline:
        (project / ".woodpecker.yml").write_text("steps: []\n")
    return project


def _advise(target: Path, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(ADVISORY), str(target)], env=_env(**extra),
                          stdin=subprocess.DEVNULL, capture_output=True, text=True)


def test_speaks_by_name_when_nothing_is_recorded(tmp_path: Path):
    project = _project(tmp_path)
    _git(project, "remote", "add", "origin", "git@github.com:example/widget.git")
    result = _advise(project)
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("CPP CI: example/widget has no recorded CI provider (")
    assert "exit 13" in lines[0] and "--record" in lines[0] and "main checkout" in lines[0]


def test_silent_when_recorded(tmp_path: Path):
    project = _project(tmp_path)
    (project / ".claude").mkdir()
    (project / ".claude/cicd.yml").write_text("pipeline:\n  providers: [woodpecker]\n")
    result = _advise(project)
    assert (result.returncode, result.stdout) == (0, "")


def test_speaks_on_an_invalid_record(tmp_path: Path):
    project = _project(tmp_path)
    (project / ".claude").mkdir()
    (project / ".claude/cicd.yml").write_text("pipeline:\n  providers: [unregistered-ci]\n")
    result = _advise(project)
    assert result.returncode == 0
    assert "has no recorded CI provider" in result.stdout and "unregistered" in result.stdout


def test_linked_worktree_is_silent_once_main_checkout_records(tmp_path: Path):
    """The issue's red case, end to end through the advisory."""
    main = _project(tmp_path)
    (main / ".gitignore").write_text(".claude/\n")
    _git(main, "add", ".")
    _git(main, "commit", "-q", "-m", "init")
    linked = tmp_path / "linked"
    _git(main, "worktree", "add", "-q", str(linked), "-b", "work")
    assert "has no recorded CI provider" in _advise(linked).stdout
    (main / ".claude").mkdir()
    (main / ".claude/cicd.yml").write_text("pipeline:\n  providers: [woodpecker]\n")
    assert _advise(linked).stdout == ""


def test_silent_for_a_repository_with_no_stake(tmp_path: Path):
    """No pipeline file and no .claude/: not this check's business."""
    assert _advise(_project(tmp_path, pipeline=False)).stdout == ""


def test_silent_outside_git(tmp_path: Path):
    result = _advise(tmp_path)
    assert (result.returncode, result.stdout) == (0, "")


def test_could_not_ask_is_silent_and_successful(tmp_path: Path):
    """A reader that cannot run must not cry wolf - and must not fail the hook."""
    project = _project(tmp_path)
    fake = tmp_path / "fake-root"
    (fake / "lib/cicd").mkdir(parents=True)
    (fake / "lib/cicd/providers.py").write_text("raise SystemExit('broken reader')\n")
    (fake / "lib/cicd/__main__.py").write_text("raise SystemExit('broken reader')\n")
    result = _advise(project, CPP_CI_ADVISORY_ROOT=str(fake))
    assert (result.returncode, result.stdout) == (0, "")


def _hook(cwd: Path, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(HOOK)], cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        env=_env(CPP_FRICTION_LOG=str(cwd / "absent.jsonl"), CPP_HOOK_SKIP_INSTALL_DRIFT="1", **extra),
    )


def test_session_start_hook_carries_the_advisory(tmp_path: Path):
    project = _project(tmp_path)
    result = _hook(project)
    assert result.returncode == 0
    assert result.stdout.count("has no recorded CI provider") == 1


def test_session_start_hook_is_silent_when_recorded_or_suppressed(tmp_path: Path):
    project = _project(tmp_path)
    assert _hook(project, CPP_HOOK_SKIP_CI_PROVIDER="1").stdout == ""
    (project / ".claude").mkdir()
    (project / ".claude/cicd.yml").write_text("pipeline:\n  providers: [woodpecker]\n")
    assert _hook(project).stdout == ""


def test_a_project_lib_package_does_not_shadow_the_reader(tmp_path: Path):
    """The session cwd is the project; its own `lib/` must not hide CPP's reader."""
    project = _project(tmp_path)
    (project / "lib").mkdir()
    (project / "lib/__init__.py").write_text("")
    result = subprocess.run(["bash", str(ADVISORY)], cwd=project, env=_env(),
                            stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert "has no recorded CI provider" in result.stdout
