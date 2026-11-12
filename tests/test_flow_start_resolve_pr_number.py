"""`flow-start-resolve.sh` refuses a pull request number (issue #1713).

`gh issue view <N>` answers for a pull request as well as an issue, so
`/flow:auto <PR number>` used to create a branch and a worktree named for a
pull request. The resolver now reads the url in the same way it reads the
state, and refuses a pull request BEFORE anything is created, through the
existing `ERROR=` / `FLOW_START_RESOLVE: error` lines.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-start-resolve.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None, reason="requires git and bash"
)

# Answers the calls the resolver makes; FAKE_GH_URL chooses issue or pull request.
FAKE_GH = """#!/usr/bin/env bash
case "$*" in
  *"issue view"*"--json state"*) printf '%s\\n' OPEN ;;
  *"issue view"*"--json title"*) printf '%s\\n' "Fix the frobnicator" ;;
  *"issue view"*"--json labels"*) : ;;
  *"issue view"*"--json url"*)
    [ "${FAKE_GH_URL:-}" = "fail" ] && exit 1
    printf '%s\\n' "${FAKE_GH_URL:-}" ;;
  *"pr list"*) printf '%s\\n' none ;;
  *) exit 1 ;;
esac
"""
ISSUE_URL = "https://github.com/acme/widget/issues/42"
PULL_URL = "https://github.com/acme/widget/pull/42"


def _git(repo: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    return subprocess.run(["git", *args], cwd=repo, env=env, check=True,
                          capture_output=True, text=True).stdout


@pytest.fixture
def clone(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin-repo"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    (origin / "a.txt").write_text("a0\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "init")
    repo = tmp_path / "clone-repo"
    _git(tmp_path, "clone", "-q", str(origin), str(repo))
    gh = tmp_path / "fake-gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    return repo, gh


def _run(repo: Path, gh: Path, url: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, FLOW_START_RESOLVE_GH=str(gh), FAKE_GH_URL=url,
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    env.pop("FLOW_WORKTREE_BASE", None)
    return subprocess.run(["bash", str(SCRIPT), "42", "--session-cwd", str(repo)],
                          cwd=repo, env=env, capture_output=True, text=True)


def _created(repo: Path) -> dict[str, object]:
    """Everything a successful resolve leaves behind: branch, worktree, claim."""
    worktrees = _git(repo, "worktree", "list", "--porcelain")
    return {
        "branches": _git(repo, "branch", "--format=%(refname:short)", "--list", "issue-42-*").split(),
        "worktree_count": worktrees.count("worktree "),
        "locked": "locked" in worktrees,
        "siblings": sorted(p.name for p in repo.parent.iterdir() if "issue-42" in p.name),
    }


def test_a_pull_request_number_is_refused_and_nothing_is_created(clone) -> None:
    repo, gh = clone
    before = _created(repo)
    assert before == {"branches": [], "worktree_count": 1, "locked": False, "siblings": []}, before
    res = _run(repo, gh, PULL_URL)
    assert res.returncode == 1, res.stdout + res.stderr
    assert "FLOW_START_RESOLVE: error" in res.stdout
    assert "ERROR=#42 is a pull request, not an issue" in res.stdout
    assert "WT_CREATED=1" not in res.stdout
    assert _created(repo) == before, "a refused pull request number still created something"


def test_the_same_number_as_an_issue_still_resolves(clone) -> None:
    """The half that shows the refusal is about the url, not a gate wedged shut."""
    repo, gh = clone
    res = _run(repo, gh, ISSUE_URL)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "FLOW_START_RESOLVE: ok" in res.stdout
    assert _created(repo)["branches"] == ["issue-42-fix-the-frobnicator"]


@pytest.mark.parametrize("url", ["fail", "", "not a url at all"])
def test_an_unreadable_url_fails_open(clone, url) -> None:
    """The state fetch already succeeded, so an unreadable or unfamiliar url
    proceeds as before: it must never refuse a real issue."""
    repo, gh = clone
    res = _run(repo, gh, url)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "FLOW_START_RESOLVE: ok" in res.stdout
