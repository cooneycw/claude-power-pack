from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.project_next.collect import CollectionError, _spec_inventory, _spec_tasks, collect_repository
from lib.project_next.config import ProjectNextConfig


def test_collector_maps_git_github_and_worktree_state(tmp_path: Path) -> None:
    worktree_output = f"worktree {tmp_path}\nHEAD abc\nbranch refs/heads/main\n\n"
    outputs = {
        ("git", "rev-parse", "--show-toplevel"): str(tmp_path),
        ("gh", "repo", "view"): json.dumps({"nameWithOwner": "example/repo", "defaultBranchRef": {"name": "main"}}),
        ("gh", "issue", "list"): json.dumps(
            [
                {
                    "number": 1,
                    "title": "Task",
                    "body": "",
                    "labels": [{"name": "p1"}],
                    "assignees": [{"login": "maintainer"}],
                    "createdAt": "2026-01-01T00:00:00Z",
                    "updatedAt": "2026-01-02T00:00:00Z",
                    "url": "https://example.test/1",
                }
            ]
        ),
        ("gh", "pr", "list"): json.dumps(
            [
                {
                    "number": 2,
                    "title": "Task",
                    "body": "Closes #1",
                    "headRefName": "issue-1-task",
                    "closingIssuesReferences": [{"number": 1}],
                    "isDraft": False,
                    "mergeStateStatus": "CLEAN",
                    "reviewDecision": "APPROVED",
                    "statusCheckRollup": [{"conclusion": "SUCCESS"}],
                    "url": "https://example.test/pr/2",
                }
            ]
        ),
        ("git", "fetch", "origin"): "",
        ("git", "worktree", "list"): worktree_output,
        ("git", "status", "--short"): "",
        ("git", "log", "--oneline"): "abc current",
        ("git", "branch", "-a"): "main origin/main\nissue-1-task origin/issue-1-task\n",
    }

    def runner(command: list[str], cwd: Path) -> str:
        for prefix, output in outputs.items():
            if tuple(command[: len(prefix)]) == prefix:
                return output
        raise AssertionError(command)

    state = collect_repository(tmp_path, runner=runner)

    assert state.repository == "example/repo"
    assert state.inventory_complete is True
    assert state.issues[0].labels == ("p1",)
    assert state.pull_requests[0].checks_state == "success"
    assert state.worktrees[0].dirty is False
    assert {branch.name for branch in state.branches} == {"main", "issue-1-task"}


def test_collector_marks_truncated_inventory_incomplete(tmp_path: Path) -> None:
    def runner(command: list[str], cwd: Path) -> str:
        if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return str(tmp_path)
        if command[:3] == ["gh", "repo", "view"]:
            return json.dumps({"nameWithOwner": "example/repo", "defaultBranchRef": {"name": "main"}})
        if command[:3] == ["gh", "issue", "list"]:
            return json.dumps([{"number": 1, "title": "One"}, {"number": 2, "title": "Two"}])
        if command[:3] == ["gh", "pr", "list"]:
            return "[]"
        if command[:3] == ["git", "worktree", "list"]:
            return ""
        if command[:3] == ["git", "branch", "-a"] or command[:3] == ["git", "fetch", "origin"]:
            return ""
        raise AssertionError(command)

    state = collect_repository(tmp_path, ProjectNextConfig(issue_limit=1), runner)

    assert state.inventory_complete is False
    assert len(state.issues) == 1
    assert "truncated" in state.collector_warnings[0]


def test_collector_stops_when_repository_cannot_be_resolved(tmp_path: Path) -> None:
    def runner(command: list[str], cwd: Path) -> str:
        raise CollectionError("not a repository")

    with pytest.raises(CollectionError, match="cannot resolve git repository"):
        collect_repository(tmp_path, runner=runner)


def test_spec_tasks_consume_stable_issue_sync_ledger(tmp_path: Path) -> None:
    feature = tmp_path / ".specify" / "specs" / "feature"
    feature.mkdir(parents=True)
    source = ".specify/specs/feature/tasks.md"
    identity = f"spec-sync:v1:example/repo:{source}:stage-1"
    (feature / "tasks.md").write_text(
        """## Stage 1: Foundation
- [ ] **T001** [US1] Implement `src/a.py`.
- [ ] **T002** [US1] Test `tests/test_a.py`.

## Issue Sync Ledger

<!-- spec-sync-ledger:start -->
| Stable identity | Granularity | Group | Tasks | Issue | URL | State |
|---|---|---|---|---:|---|---|
| `{identity}` | stage | `stage-1` | T001, T002 | #42 | https://github.com/example/repo/issues/42 | OPEN |
<!-- spec-sync-ledger:end -->
""".format(identity=identity)
    )
    warnings: list[str] = []

    tasks = _spec_tasks(tmp_path, "example/repo", warnings)

    assert warnings == []
    assert {task.mapping_status for task in tasks} == {"mapped"}
    assert {task.issue_numbers for task in tasks} == {(42,)}
    assert {task.group_id for task in tasks} == {"stage-1"}


def test_missing_stale_and_ambiguous_spec_mappings_are_uncertain(tmp_path: Path) -> None:
    feature = tmp_path / ".specify" / "specs" / "feature"
    feature.mkdir(parents=True)
    source = ".specify/specs/feature/tasks.md"
    stale_row = f"| `spec-sync:v1:wrong/repo:{source}:stage-1` | stage | `stage-1` | T001 | #1 | "
    mapped_row = f"| `spec-sync:v1:example/repo:{source}:stage-2` | stage | `stage-2` | T002 | #2 | "
    ambiguous_row = f"| `spec-sync:v1:example/repo:{source}:stage-3` | stage | `stage-3` | T002 | #3 | "
    (feature / "tasks.md").write_text(
        f"""- [ ] **T001** Implement `src/a.py`.
- [ ] **T002** Implement `src/b.py`.
- [ ] **T003** Implement `src/c.py`.

{chr(60)}!-- spec-sync-ledger:start --{chr(62)}
| Stable identity | Granularity | Group | Tasks | Issue | URL | State |
|---|---|---|---|---:|---|---|
{stale_row}https://github.com/wrong/repo/issues/1 | OPEN |
{mapped_row}https://github.com/example/repo/issues/2 | OPEN |
{ambiguous_row}https://github.com/example/repo/issues/3 | OPEN |
{chr(60)}!-- spec-sync-ledger:end --{chr(62)}
"""
    )
    warnings: list[str] = []

    tasks = {task.task_id: task for task in _spec_tasks(tmp_path, "example/repo", warnings)}

    assert tasks["T001"].mapping_status == "stale"
    assert tasks["T002"].mapping_status == "ambiguous"
    assert tasks["T003"].mapping_status == "missing"
    assert len(warnings) == 3


def test_spec_inventory_reports_file_readiness_and_partial_sync(tmp_path: Path) -> None:
    feature = tmp_path / ".specify" / "specs" / "checkout"
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text("# Checkout\n")
    (feature / "plan.md").write_text("# Plan\n")
    source = ".specify/specs/checkout/tasks.md"
    identity = f"spec-sync:v1:example/repo:{source}:stage-1"
    (feature / "tasks.md").write_text(
        f"""- [ ] **T001** Implement checkout.
- [ ] **T002** Test checkout.

| Stable identity | Granularity | Group | Tasks | Issue | URL | State |
|---|---|---|---|---:|---|---|
| `{identity}` | stage | `stage-1` | T001 | #42 | https://github.com/example/repo/issues/42 | OPEN |
"""
    )
    warnings: list[str] = []

    tasks, features = _spec_inventory(tmp_path, "example/repo", warnings)

    assert [task.mapping_status for task in tasks] == ["mapped", "missing"]
    assert len(warnings) == 1
    assert len(features) == 1
    readiness = features[0]
    assert (readiness.has_spec, readiness.has_plan, readiness.has_tasks) == (True, True, True)
    assert (readiness.mapped_tasks, readiness.total_tasks) == (1, 2)
    assert readiness.mapping_status == "partial"
    assert readiness.recommended_action == "sync remaining tasks to issues"
