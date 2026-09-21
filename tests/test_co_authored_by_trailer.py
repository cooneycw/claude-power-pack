"""Pin: no tracked file names a pinned Claude model+version in a
`Co-Authored-By:` trailer (issue #1037).

Eight instructions across seven files said the trailer should name one
pinned model+version literal, verbatim - stale, and unenforced. This suite
pins the fix and its negative controls (ADR 0008): a fixture file carrying
the pattern must fail, the corrected generic-guidance wording must pass, and
`git grep` itself failing must report UNKNOWN rather than a vacuous clean.
(This docstring avoids the literal on purpose - PINNED_TRAILER below is
built from two parts for the same reason: check-co-authored-by-trailer.py
scans this very file, and typing the worked example whole would trip it.)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.isolated_env import ISOLATED_PATH

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-co-authored-by-trailer.py"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git on PATH")

#: Built from parts so this file itself is not a tracked-in fixture the
#: checker's own future runs would trip over.
PINNED_TRAILER = "Co-Authored-By: " + "Claude Opus 4.6 <noreply@anthropic.com>"
GENERIC_TRAILER = "Co-Authored-By: <name> <noreply@anthropic.com>"


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True, text=True,
    )


def _run_without_git(root: Path) -> subprocess.CompletedProcess[str]:
    """PATH containing only Python's own directory - no `git` reachable at
    all, reproducing CI's `validate` image (issue #1037, pipeline 2128)."""
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
        env={"HOME": str(cwd), "PATH": ISOLATED_PATH,  # negative-fixture: allow PATH is isolation, not an absence
             "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
    )


def _padded_population(repo: Path, n: int = 60) -> None:
    """N clean filler files, so the MIN_TRACKED_FILES floor doesn't gate
    a fixture that's testing something else entirely."""
    for i in range(n):
        (repo / f"filler-{i}.md").write_text(f"# filler {i}\n", encoding="utf-8")


def _repo_with(tmp_path: Path, content: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AUTO.md").write_text(f"# Instructions\n\n- {content}\n", encoding="utf-8")
    _padded_population(repo)
    _git("init", "-q", cwd=repo)
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", "base", cwd=repo)
    return repo


@requires_git
def test_git_binary_entirely_absent_is_unknown_not_a_crash(tmp_path: Path) -> None:
    """CI pipeline 2128 (issue #1037): `git` not on PATH at all raised an
    uncaught FileNotFoundError - not a script-detected failure, a crash.
    `@requires_git` guards building the fixture only; the script itself then
    runs with no git reachable, which is the whole point of this test."""
    repo = _repo_with(tmp_path, "Nothing about attribution here.")

    proc = _run_without_git(repo)
    assert proc.returncode == 2, (
        f"expected UNKNOWN (exit 2) with git entirely absent, got "
        f"{proc.returncode}:\n{proc.stdout}{proc.stderr}"
    )
    assert "Traceback" not in proc.stderr


@requires_git
def test_a_pinned_trailer_is_a_committed_red_case(tmp_path: Path) -> None:
    repo = _repo_with(tmp_path, PINNED_TRAILER)

    proc = _run(repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "AUTO.md" in proc.stderr


@requires_git
def test_generic_guidance_passes(tmp_path: Path) -> None:
    repo = _repo_with(tmp_path, GENERIC_TRAILER)

    proc = _run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok" in proc.stdout


@requires_git
def test_no_trailer_at_all_passes(tmp_path: Path) -> None:
    repo = _repo_with(tmp_path, "Nothing about attribution here.")

    proc = _run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


@requires_git
def test_too_few_tracked_files_is_unknown_not_clean(tmp_path: Path) -> None:
    """Codex review (#1037): `git grep` returns the same exit 1 for "no match
    in eligible files" and "no eligible files at all" - a fixture with only
    one tracked file, no dash-shaped population padding, must report UNKNOWN
    rather than a vacuous clean (reproduced with `--root .pytest_cache` on
    the live checkout, which has no tracked files at all)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AUTO.md").write_text("# Instructions\n\nNothing about attribution here.\n", encoding="utf-8")
    _git("init", "-q", cwd=repo)
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", "base", cwd=repo)

    proc = _run(repo)
    assert proc.returncode == 2, (
        f"expected UNKNOWN (exit 2) for a too-small population, got "
        f"{proc.returncode}:\n{proc.stdout}{proc.stderr}"
    )


def test_git_grep_failure_is_unknown_not_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A search that errors must not read as "searched and found nothing.\""""
    import importlib.util

    spec = importlib.util.spec_from_file_location("co_authored_by_trailer", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    def _broken_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="fatal: not a git repository")

    monkeypatch.setattr(module.subprocess, "run", _broken_run)
    matches, returncode = module.find_pinned_trailers(tmp_path)
    assert matches is None
    assert returncode == 128
    assert module.main(["--root", str(tmp_path)]) == 2


@requires_git
def test_the_real_repo_has_no_pinned_trailer() -> None:
    """Regression-test EXECUTION against the live tree, not a committed case.

    Guarded: CI's `validate` image has no `git` binary at all (issue #1037,
    pipeline 2128) - the script's own handling of that is what the
    git-grep-failure test above pins, not this test's job."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
