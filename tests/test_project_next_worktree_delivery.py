"""Worktree delivery verdicts for project-next cleanup candidates (issue #1257).

The verdict is read to decide ``git worktree remove``, a destructive action no
later step re-derives, so each verdict it can report has a committed case here
(ADR 0008): matching blobs -> ``delivered``; one differing file, a dirty tree, an
untracked file, or a deletion the base never took -> not ``delivered``; any git
failure -> ``unknown``.

The squash shape is built for real: the branch is NOT an ancestor of the base and
``rev-list --count base..HEAD`` is non-zero while its work is fully delivered.
That is the state the nit-store measurement found both ancestry readings wrong on.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project-next.py"
SPEC = importlib.util.spec_from_file_location("cpp_project_next_delivery", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
project_next = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = project_next
SPEC.loader.exec_module(project_next)

# The Woodpecker validate image has no git, so these skip there; the runner-
# injected cases at the bottom of this file are the ones that run in CI.
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git on PATH")

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch) -> None:
    # The adapter's own runner inherits the environment, so isolate it too.
    for key, value in GIT_ENV.items():
        monkeypatch.setenv(key, value)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


def _write(repo: Path, files: dict[str, str | None]) -> None:
    for name, content in files.items():
        if content is None:
            (repo / name).unlink()
        else:
            (repo / name).write_text(content)


class Scenario:
    """A bare origin, a primary checkout on main, and one unmapped worktree branch."""

    def __init__(self, tmp_path: Path) -> None:
        self.origin = tmp_path / "origin.git"
        _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(self.origin))
        self.main = tmp_path / "main"
        _git(tmp_path, "clone", "-q", str(self.origin), str(self.main))
        _git(self.main, "checkout", "-q", "-b", "main")
        _write(self.main, {"a.txt": "a0\n", "b.txt": "b0\n", "c.txt": "c0\n"})
        _commit_all(self.main, "base")
        _git(self.main, "push", "-q", "origin", "main")
        self.branch = "feature-cleanup"
        self.worktree = tmp_path / "wt"
        _git(self.main, "worktree", "add", "-q", str(self.worktree), "-b", self.branch)

    def branch_commit(self, files: dict[str, str | None], *, push: bool = False) -> None:
        _write(self.worktree, files)
        _commit_all(self.worktree, "branch work")
        if push:
            _git(self.worktree, "push", "-q", "origin", self.branch)

    def land_on_main(self, files: dict[str, str | None], message: str = "squash") -> None:
        """A squash merge: the same content as a NEW commit, not the branch's commit."""
        _write(self.main, files)
        _commit_all(self.main, message)
        _git(self.main, "push", "-q", "origin", "main")
        _git(self.main, "fetch", "-q", "origin")

    def result(self) -> object:
        state = project_next.RepositoryState.from_dict(
            {
                "repository": "example/project",
                "default_branch": "main",
                "collected_at": "2026-09-26T00:00:00Z",
                "worktrees": [
                    {"path": str(self.main), "branch": "main"},
                    {"path": str(self.worktree), "branch": self.branch},
                ],
            }
        )
        return project_next.recommend(state)

    def verdict(self) -> object:
        (item,) = project_next.worktree_delivery(self.main, self.result(), "main")
        return item


@pytest.fixture()
def scenario(tmp_path: Path) -> Scenario:
    return Scenario(tmp_path)


@requires_git
def test_squash_merged_branch_with_identical_blobs_is_delivered(scenario: Scenario) -> None:
    work = {"a.txt": "a1\n", "b.txt": "b1\n"}
    scenario.branch_commit(work)
    scenario.land_on_main(work)

    # The ancestry readings the issue forbids really are wrong in this state.
    assert _git(scenario.worktree, "rev-list", "--count", "origin/main..HEAD").strip() == "1"
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"], cwd=scenario.worktree
    )
    assert ancestor.returncode == 1

    item = scenario.verdict()
    assert item.verdict == "delivered"
    assert item.committed == "delivered"
    assert item.tree == "clean"
    assert item.changed_paths == 2
    assert item.remote_branch == "absent"
    assert item.issue_state == "unmapped"


@requires_git
def test_one_differing_file_is_not_proven_and_named(scenario: Scenario) -> None:
    scenario.branch_commit({"a.txt": "a1\n", "b.txt": "b1\n"})
    scenario.land_on_main({"a.txt": "a1\n", "b.txt": "b-other\n"})

    item = scenario.verdict()
    assert item.verdict == "not-proven"
    assert item.committed == "not-proven"
    assert item.differing_paths == ("b.txt",)
    assert "1 of 2" in item.reason


@requires_git
def test_unlanded_branch_is_not_proven(scenario: Scenario) -> None:
    scenario.branch_commit({"a.txt": "a1\n"}, push=True)

    item = scenario.verdict()
    assert item.verdict == "not-proven"
    assert item.remote_branch == "present"


@requires_git
def test_dirty_tree_with_matching_blobs_is_never_delivered(scenario: Scenario) -> None:
    work = {"a.txt": "a1\n"}
    scenario.branch_commit(work)
    scenario.land_on_main(work)
    (scenario.worktree / "c.txt").write_text("uncommitted\n")

    item = scenario.verdict()
    assert item.committed == "delivered"
    assert item.tree == "dirty"
    assert item.verdict == "not-proven"


@requires_git
def test_untracked_file_is_never_delivered(scenario: Scenario) -> None:
    work = {"a.txt": "a1\n"}
    scenario.branch_commit(work)
    scenario.land_on_main(work)
    (scenario.worktree / "notes.txt").write_text("only here\n")

    item = scenario.verdict()
    assert item.tree == "untracked"
    assert item.verdict == "not-proven"


@requires_git
def test_deletion_counts_only_when_the_base_deleted_it_too(scenario: Scenario) -> None:
    scenario.branch_commit({"c.txt": None})
    assert scenario.verdict().verdict == "not-proven"

    scenario.land_on_main({"c.txt": None})
    assert scenario.verdict().verdict == "delivered"


@requires_git
def test_base_moving_an_unrelated_file_does_not_count_against_the_branch(scenario: Scenario) -> None:
    work = {"a.txt": "a1\n"}
    scenario.branch_commit(work)
    scenario.land_on_main(work)
    scenario.land_on_main({"b.txt": "b-later\n"}, message="later unrelated work")

    assert scenario.verdict().verdict == "delivered"


@requires_git
def test_base_editing_a_delivered_file_again_degrades_to_not_proven(scenario: Scenario) -> None:
    # The documented limit: blob identity cannot tell "landed then edited" from
    # "never landed", so it says not-proven - never undelivered, never delivered.
    work = {"a.txt": "a1\n"}
    scenario.branch_commit(work)
    scenario.land_on_main(work)
    scenario.land_on_main({"a.txt": "a2\n"}, message="later edit")

    assert scenario.verdict().verdict == "not-proven"


@requires_git
def test_branch_with_no_changes_is_delivered_with_reason(scenario: Scenario) -> None:
    item = scenario.verdict()
    assert item.verdict == "delivered"
    assert item.changed_paths == 0
    assert "no path" in item.reason


@requires_git
def test_config_hidden_untracked_file_is_still_seen(scenario: Scenario) -> None:
    work = {"a.txt": "a1\n"}
    scenario.branch_commit(work)
    scenario.land_on_main(work)
    _git(scenario.worktree, "config", "status.showUntrackedFiles", "no")
    (scenario.worktree / "notes.txt").write_text("only here\n")
    # Precondition: the configured porcelain really hides it.
    assert _git(scenario.worktree, "status", "--porcelain") == ""

    item = scenario.verdict()
    assert item.tree == "untracked"
    assert item.verdict == "not-proven"


@requires_git
def test_config_hidden_submodule_change_is_still_compared(scenario: Scenario) -> None:
    gitlink = _git(scenario.main, "rev-parse", "HEAD").strip()
    _git(scenario.worktree, "update-index", "--add", "--cacheinfo", f"160000,{gitlink},vendored")
    _git(scenario.worktree, "commit", "-qm", "advance a gitlink main never took")
    _git(scenario.worktree, "config", "diff.ignoreSubmodules", "all")
    # Precondition: the configured diff really drops the gitlink.
    assert _git(scenario.worktree, "diff", "--raw", "origin/main", "HEAD") == ""

    item = scenario.verdict()
    assert item.committed == "not-proven"
    assert item.differing_paths == ("vendored",)


@requires_git
def test_remote_moved_past_the_local_base_is_unknown(scenario: Scenario, tmp_path: Path) -> None:
    work = {"a.txt": "a1\n"}
    scenario.branch_commit(work)
    scenario.land_on_main(work)
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(scenario.origin), str(other))
    _write(other, {"a.txt": "reverted\n"})
    _commit_all(other, "revert on the remote, not yet fetched here")
    _git(other, "push", "-q", "origin", "main")

    item = scenario.verdict()
    assert item.verdict == "unknown"
    assert "stale" in item.reason


@requires_git
def test_open_issue_worktrees_are_not_annotated(scenario: Scenario) -> None:
    state = project_next.RepositoryState.from_dict(
        {
            "repository": "example/project",
            "default_branch": "main",
            "collected_at": "2026-09-26T00:00:00Z",
            "issues": [{"number": 7, "title": "Open work"}],
            "worktrees": [{"path": str(scenario.worktree), "branch": "issue-7-open-work"}],
        }
    )
    assert project_next.worktree_delivery(scenario.main, project_next.recommend(state), "main") == ()


# --- runner-injected cases: no git needed, so these are the ones CI runs -------


def _unmapped_result() -> object:
    state = project_next.RepositoryState.from_dict(
        {
            "repository": "example/project",
            "default_branch": "main",
            "collected_at": "2026-09-26T00:00:00Z",
            "worktrees": [{"path": "/nowhere/wt", "branch": "feature-x"}],
        }
    )
    return project_next.recommend(state)


def _runner(overrides: dict[str, object]):
    """Answers like a clean, fully delivered worktree unless a command is overridden."""
    defaults = {
        "ls-remote": "main-sha\trefs/heads/main\n",
        "rev-parse": "main-sha\n",
        "status": "",
        "merge-base": "base-sha\n",
        "diff": ":100644 100644 aaa bbb M\0a.txt\0",
        "diff-base": "",
    }
    calls: list[list[str]] = []

    def run(command: list[str], cwd: Path) -> str:
        calls.append(command)
        key = command[1]
        if key == "diff" and command[-2].startswith("refs/remotes/"):
            key = "diff-base"
        answer = overrides.get(key, defaults.get(key, ""))
        if isinstance(answer, Exception):
            raise answer
        return str(answer)

    run.calls = calls  # type: ignore[attr-defined]
    return run


def test_positive_control_for_the_injected_runner_is_delivered() -> None:
    # Without this, the failure cases below could pass against a runner that
    # never produces `delivered` at all.
    (item,) = project_next.worktree_delivery(Path("/nowhere"), _unmapped_result(), "main", _runner({}))
    assert item.verdict == "delivered"
    assert item.remote_branch == "absent"


@pytest.mark.parametrize("failing", ["merge-base", "diff", "diff-base", "status"])
def test_any_git_failure_is_unknown_never_delivered(failing: str) -> None:
    runner = _runner({failing: project_next.CollectionError(f"git {failing}: boom")})
    (item,) = project_next.worktree_delivery(Path("/nowhere"), _unmapped_result(), "main", runner)
    assert item.verdict == "unknown"
    assert "boom" in item.reason


def test_unreadable_diff_stream_is_unknown_not_empty() -> None:
    runner = _runner({"diff-base": "garbage-without-colon\0a.txt\0"})
    (item,) = project_next.worktree_delivery(Path("/nowhere"), _unmapped_result(), "main", runner)
    assert item.verdict == "unknown"


def test_unreachable_remote_cannot_confirm_the_base_so_is_unknown() -> None:
    runner = _runner({"ls-remote": project_next.CollectionError("git ls-remote: offline")})
    (item,) = project_next.worktree_delivery(Path("/nowhere"), _unmapped_result(), "main", runner)
    assert item.remote_branch == "unknown"
    assert item.verdict == "unknown"
    assert "could not be asked" in item.reason


def test_stale_local_base_is_unknown_even_when_blobs_match() -> None:
    runner = _runner({"rev-parse": "old-sha\n"})
    (item,) = project_next.worktree_delivery(Path("/nowhere"), _unmapped_result(), "main", runner)
    assert item.verdict == "unknown"
    assert "stale" in item.reason


def test_fixture_input_is_unknown_and_runs_no_git() -> None:
    (item,) = project_next.worktree_delivery(Path("/nowhere"), _unmapped_result(), "main", runner=None)
    assert item.verdict == "unknown"
    assert "fixture" in item.reason


def test_every_mode_renders_the_verdict() -> None:
    result = _unmapped_result()
    delivery = project_next.worktree_delivery(Path("/nowhere"), result, "main", _runner({}))
    extensions = project_next.CppExtensions(
        relationships=(), spec_lifecycle=(), planning_routes=(), warnings=(), worktree_delivery=delivery
    )
    state = project_next.RepositoryState.from_dict(
        {"repository": "example/project", "default_branch": "main", "collected_at": "2026-09-26T00:00:00Z"}
    )
    compact = project_next.render_cpp(result, state, "compact", extensions)
    assert "- /nowhere/wt (feature-x): **delivered**" in compact
    assert "| /nowhere/wt | feature-x | unmapped | delivered |" in project_next.render_cpp(
        result, state, "full", extensions
    )
    assert "Worktree delivery: delivered 1 | not-proven 0 | unknown 0" in project_next.render_cpp(
        result, state, "brief", extensions
    )
    assert extensions.to_dict()["worktree_delivery"][0]["verdict"] == "delivered"
