"""Pin: every stated "current version" agrees with pyproject.toml (issue #1037).

`CLAUDE.md:167` said "Current version: 7.5.0" against pyproject.toml's
"8.0.0" - stale for four days, in the document loaded into every session.
Nothing compared them. This suite pins the fix and its own negative controls
(ADR 0008): a fixture tree with a mismatched location must fail, a tree
where everything agrees must pass, and - the required second control from
review - a tree whose derivable locations fall below the floor must report
UNKNOWN rather than a vacuous clean.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-version-consistency.py"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git on PATH")


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True, text=True,
    )


def _run_without_git(root: Path) -> subprocess.CompletedProcess[str]:
    """PATH containing only Python's own directory - no `git` reachable at
    all, reproducing CI's `validate` image (issue #1037, pipeline 2128:
    `FileNotFoundError: [Errno 2] No such file or directory: 'git'` raised
    from inside `subprocess.run` before any script code could react to it)."""
    git_free_path = str(Path(sys.executable).parent)
    assert shutil.which("git", path=git_free_path) is None, "fixture must lack git"
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True, text=True,
        env={"PATH": git_free_path},
    )


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
        env={"HOME": str(cwd), "PATH": "/usr/bin:/bin",  # negative-fixture: allow PATH is isolation, not an absence
             "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
    )


def _build_repo(tmp_path: Path, *, claude_version: str, readme_extra: str = "") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nversion = "8.0.0"\n', encoding="utf-8")
    (repo / "CLAUDE.md").write_text(
        f"# Project\n\n## Version\n\nCurrent version: {claude_version}\n", encoding="utf-8"
    )
    (repo / "README.md").write_text(
        f"**v8.0.0** - a thing.\n{readme_extra}\n### v8.0.0 (2026-09-15)\n- notes\n",
        encoding="utf-8",
    )
    (repo / "CHANGELOG.md").write_text("## [8.0.0] - 2026-09-15\n- notes\n", encoding="utf-8")
    return repo


@requires_git
def test_a_mismatched_location_is_a_committed_red_case(tmp_path: Path) -> None:
    """Fixture, not the live repo - persists after CLAUDE.md's own fix lands."""
    repo = _build_repo(tmp_path, claude_version="7.5.0")
    _git("init", "-q", cwd=repo)
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", "base", cwd=repo)

    proc = _run(repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "CLAUDE.md" in proc.stderr
    assert "7.5.0" in proc.stderr


@requires_git
def test_all_locations_agreeing_passes(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path, claude_version="8.0.0")
    _git("init", "-q", cwd=repo)
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", "base", cwd=repo)

    proc = _run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok" in proc.stdout


@requires_git
def test_too_few_derivable_locations_is_unknown_not_clean(tmp_path: Path) -> None:
    """Required fix 2 (review): a vacuous derived set must not read as clean.

    No README.md, no CHANGELOG.md, and CLAUDE.md phrased so the "Current
    version:" pattern does not match - the derived location set is empty,
    which must never be reported as "every location agrees."
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nversion = "8.0.0"\n', encoding="utf-8")
    (repo / "CLAUDE.md").write_text(
        "# Project\n\nThe version right now is eight point oh point oh.\n", encoding="utf-8"
    )
    _git("init", "-q", cwd=repo)
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", "base", cwd=repo)

    proc = _run(repo)
    assert proc.returncode == 2, (
        f"expected UNKNOWN (exit 2) for a vacuous derived set, got "
        f"{proc.returncode}:\n{proc.stdout}{proc.stderr}"
    )
    assert "UNKNOWN" in proc.stderr or "UNKNOWN" in proc.stdout


@requires_git
def test_git_ls_files_failure_is_unknown_not_outvoted_by_readme(tmp_path: Path) -> None:
    """Codex review (#1037): a broken tracked-file enumeration must not hide
    behind README/CHANGELOG alone satisfying the location floor.

    No `.git` directory at all, so `git ls-files` fails outright - but
    README.md and CHANGELOG.md, read directly off disk, still supply enough
    locations to clear MIN_LOCATIONS on their own. Before the fix this read
    as "2 location(s) agree" without ever having looked at CLAUDE.md.
    """
    repo = _build_repo(tmp_path, claude_version="7.5.0")  # would mismatch, if examined

    proc = _run(repo)
    assert proc.returncode == 2, (
        f"expected UNKNOWN (exit 2) for a failed enumeration, got "
        f"{proc.returncode}:\n{proc.stdout}{proc.stderr}"
    )
    assert "git ls-files" in proc.stderr


def test_git_binary_entirely_absent_is_unknown_not_a_crash(tmp_path: Path) -> None:
    """CI pipeline 2128 (issue #1037): `git` not on PATH at all raised an
    uncaught FileNotFoundError - not a script-detected failure, a crash. No
    `@requires_git`: this test's whole point is running WITHOUT git."""
    repo = _build_repo(tmp_path, claude_version="8.0.0")

    proc = _run_without_git(repo)
    assert proc.returncode == 2, (
        f"expected UNKNOWN (exit 2) with git entirely absent, got "
        f"{proc.returncode}:\n{proc.stdout}{proc.stderr}"
    )
    assert "Traceback" not in proc.stderr


@requires_git
def test_a_vendored_readme_version_is_excluded(tmp_path: Path) -> None:
    """Codex review (#1037): a vendored project's own version claim is a
    neighbour's fact, not CPP's - comparing it to pyproject.toml would fail
    a genuinely clean tree over content this repo does not own."""
    repo = _build_repo(tmp_path, claude_version="8.0.0")
    vendor_readme = repo / "vendor" / "project_next" / "README.md"
    vendor_readme.parent.mkdir(parents=True)
    vendor_readme.write_text("Current version: 1.2.3\n", encoding="utf-8")
    _git("init", "-q", cwd=repo)
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", "base", cwd=repo)

    proc = _run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


@requires_git
def test_the_real_repo_is_currently_consistent() -> None:
    """Regression-test EXECUTION against the live tree, not a committed case.

    This is the one-shot run the fixtures above do not replace: it proves
    the fix actually landed here, in this checkout, right now - but unlike
    the fixtures, it stops being a red/green pair the moment CLAUDE.md
    happens to be correct, which is why the committed fixtures above exist
    independently of this test's own history.

    Guarded like the fixture tests: the script's own git absence handling
    is what the git-failure fixture above pins, not this test's job (issue
    #1037, CI pipeline 2128 - the `validate` image has no `git` binary at
    all, and this test crashed uncaught before the script itself was fixed
    to report UNKNOWN instead).
    """
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
