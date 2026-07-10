"""Regression tests for issue #566: worktree-remove.sh must not report a false
failure on a squash-merged branch.

Root cause: under ``set -euo pipefail``, ``git branch -d`` refuses a
squash-merged branch ("not fully merged" - the squash rewrote its commits into
one new commit on main, so the branch tip is not an ancestor of main), and the
old fallback was an interactive ``read -p`` confirmation. Non-interactive callers
(``/flow:auto``, ``/flow:merge``) have no TTY: ``read`` hit EOF and returned
non-zero, tripping ``set -e`` so the whole script exited non-zero AND left the
branch undeleted - a false "cleanup failed" even though the worktree removal
succeeded.

The fix: try ``git branch -d`` first (clean report for the fully-merged case),
then fall back to ``git branch -D`` non-interactively; branch-delete outcome
never fails the script - only a worktree-removal failure surfaces non-zero.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "worktree-remove.sh"

# The behaviour tests drive real ``git`` and ``bash`` subprocesses. The Woodpecker
# ``validate`` step runs in ``uv:python3.11-bookworm-slim``, which ships bash but
# NOT git, so those tests skip there (issue #430).
requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)


def _git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout


def _run_remove(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # stdin=DEVNULL reproduces the non-TTY EOF that made the old interactive
    # ``read -p`` fallback trip ``set -e``. ``timeout`` guards against a
    # regression that reintroduces a blocking prompt (it would hang forever).
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )


def _repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A main repo on ``main`` plus a linked worktree on branch ``feature``."""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    (main / "base.txt").write_text("base\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "base")
    wt = main / ".claude" / "worktrees" / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "feature")
    return main, wt


def _branch_exists(repo: Path, name: str) -> bool:
    out = _git(repo, "branch", "--list", name)
    return name in out


@requires_git
def test_squash_merged_branch_removed_cleanly(tmp_path: Path) -> None:
    """The core bug: a squash-merged branch must be removed with exit 0."""
    main, wt = _repo_with_worktree(tmp_path)
    # Work on the feature branch (in its worktree).
    (wt / "feat.txt").write_text("feature work\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "feature work")
    # Simulate a SQUASH merge: main gains an independent commit carrying the
    # work, so ``feature`` is no longer an ancestor of main and ``branch -d``
    # refuses - exactly the squash-merge shape.
    (main / "feat.txt").write_text("feature work\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "squashed feature (#566)")

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 0, f"false failure on squash-merged branch:\n{res.stderr}"
    assert not wt.exists(), "worktree directory was not removed"
    assert not _branch_exists(main, "feature"), "squash-merged branch was not deleted"
    # Non-interactive: it must never have asked for confirmation.
    assert "[y/N]" not in res.stdout and "[y/N]" not in res.stderr
    assert "force-deleted" in res.stdout.lower()


@requires_git
def test_fully_merged_branch_reported_and_deleted(tmp_path: Path) -> None:
    """A genuinely fully-merged (fast-forwardable) branch still deletes cleanly
    and is reported as fully merged (the safe ``-d`` path)."""
    main, wt = _repo_with_worktree(tmp_path)
    (wt / "feat.txt").write_text("feature work\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "feature work")
    # Fast-forward main to feature: now feature IS an ancestor of main.
    _git(main, "merge", "--ff-only", "feature")

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 0, res.stderr
    assert not _branch_exists(main, "feature"), "fully-merged branch was not deleted"
    assert "fully merged" in res.stdout.lower()


@requires_git
def test_removal_without_delete_branch_keeps_branch(tmp_path: Path) -> None:
    """Without --delete-branch the worktree goes but the branch is left intact."""
    main, wt = _repo_with_worktree(tmp_path)
    (wt / "feat.txt").write_text("feature work\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "feature work")

    res = _run_remove(main, str(wt), "--force")

    assert res.returncode == 0, res.stderr
    assert not wt.exists(), "worktree directory was not removed"
    assert _branch_exists(main, "feature"), "branch should be kept without --delete-branch"


@requires_git
def test_real_removal_failure_still_surfaces_nonzero(tmp_path: Path) -> None:
    """Only a genuine failure surfaces non-zero: a path that is not a worktree
    is rejected with a non-zero exit (the removal itself failed)."""
    main, _wt = _repo_with_worktree(tmp_path)
    res = _run_remove(main, str(main), "--force", "--delete-branch")
    assert res.returncode != 0, "a non-worktree path must be rejected non-zero"
