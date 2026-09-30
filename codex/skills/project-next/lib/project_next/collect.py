"""Read-only git, GitHub, and spec-kit collection adapter."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ProjectNextConfig
from .models import Branch, Issue, PullRequest, RepositoryState, SpecFeature, SpecTask, Worktree

CommandRunner = Callable[[list[str], Path], str]
TASK = re.compile(r"^-\s*\[\s\]\s+(?:\*\*)?(?P<id>[A-Za-z]+\d+)(?:\*\*)?\s+(?P<title>.+)$")
ISSUE_REF = re.compile(r"#(?P<number>\d+)\b")
TASK_ID = re.compile(r"\bT\d{3}\b")
LEDGER_IDENTITY = re.compile(r"^spec-sync:v1:(?P<repo>[^:]+/[^:]+):(?P<source>.+):(?P<group>[^:]+)$")


class CollectionError(RuntimeError):
    """A required repository-state command failed."""


def subprocess_runner(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if completed.returncode:
        message = (completed.stderr or completed.stdout or "command failed").strip().splitlines()[0]
        raise CollectionError(f"{' '.join(command[:3])}: {message}")
    return completed.stdout


def _json(output: str) -> Any:
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise CollectionError(f"command returned invalid JSON: {exc}") from exc


def _labels(items: Any) -> tuple[str, ...]:
    return tuple(str(item.get("name", "")) if isinstance(item, dict) else str(item) for item in (items or ()))


def _assignees(items: Any) -> tuple[str, ...]:
    return tuple(
        str(item.get("login") or item.get("name") or "") if isinstance(item, dict) else str(item)
        for item in (items or ())
    )


def _checks_state(rollup: Any) -> str:
    if not rollup:
        return "unknown"
    conclusions = {
        str(item.get("conclusion") or item.get("state") or item.get("status") or "").upper()
        for item in rollup
        if isinstance(item, dict)
    }
    if conclusions & {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}:
        return "failure"
    if conclusions & {"PENDING", "QUEUED", "IN_PROGRESS", "EXPECTED", "WAITING"}:
        return "pending"
    if conclusions and conclusions <= {"SUCCESS", "SKIPPED", "NEUTRAL"}:
        return "success"
    return "unknown"


def _parse_worktrees(output: str, repository: Path, runner: CommandRunner, warnings: list[str]) -> tuple[Worktree, ...]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in output.splitlines() + [""]:
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value

    worktrees: list[Worktree] = []
    for entry in entries:
        path = Path(entry.get("worktree", repository))
        branch = entry.get("branch", "").removeprefix("refs/heads/")
        try:
            status = runner(["git", "status", "--short"], path)
            commits = runner(["git", "log", "--oneline", "-5"], path).splitlines()
        except CollectionError as exc:
            warnings.append(str(exc))
            status = ""
            commits = []
        entries_changed = [line for line in status.splitlines() if line.strip()]
        # A stray untracked file is not work in progress, so it must not outrank a real
        # recommendation the way a tracked modification does.
        tracked = [line for line in entries_changed if not line.startswith("??")]
        worktrees.append(
            Worktree(
                path=str(path),
                branch=branch,
                dirty=bool(tracked),
                untracked_only=bool(entries_changed) and not tracked,
                recent_commits=tuple(commits),
            )
        )
    return tuple(worktrees)


def _parse_branches(output: str) -> tuple[Branch, ...]:
    branches: list[Branch] = []
    for line in output.splitlines():
        name, _, upstream = line.strip().partition(" ")
        if not name or name.endswith("/HEAD"):
            continue
        branches.append(
            Branch(name=name, upstream=upstream, remote=name.startswith("remotes/") or name.startswith("origin/"))
        )
    return tuple(branches)


def _spec_inventory(
    repository: Path, repository_name: str, warnings: list[str]
) -> tuple[tuple[SpecTask, ...], tuple[SpecFeature, ...]]:
    specs = repository / ".specify" / "specs"
    if not specs.is_dir():
        return (), ()
    tasks: list[SpecTask] = []
    features: list[SpecFeature] = []
    for feature_path in sorted(path for path in specs.iterdir() if path.is_dir()):
        path = feature_path / "tasks.md"
        feature_tasks: list[SpecTask] = []
        if not path.is_file():
            has_spec = (feature_path / "spec.md").is_file()
            has_plan = (feature_path / "plan.md").is_file()
            if not has_spec:
                action = "create spec.md"
            elif not has_plan:
                action = "create plan.md"
            else:
                action = "create tasks.md"
            features.append(
                SpecFeature(
                    name=feature_path.name,
                    path=feature_path.relative_to(repository).as_posix(),
                    has_spec=has_spec,
                    has_plan=has_plan,
                    recommended_action=action,
                )
            )
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            warnings.append(f"cannot read {path}: {exc}")
            continue
        relative = path.relative_to(repository).as_posix()
        ledger_by_task: dict[str, list[dict[str, str]]] = {}
        for line_number, line in enumerate(lines, start=1):
            if not line.lstrip().startswith("| `spec-sync:v1:"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) != 7:
                warnings.append(f"{relative}:{line_number}: malformed Issue Sync ledger row")
                continue
            identity, granularity, group_id, task_ids, issue_cell, url, state = cells
            row = {
                "identity": identity.strip("`"),
                "granularity": granularity,
                "group_id": group_id.strip("`"),
                "issue": issue_cell,
                "url": url,
                "state": state,
            }
            parsed_ids = TASK_ID.findall(task_ids)
            if not parsed_ids:
                warnings.append(f"{relative}:{line_number}: ledger row has no task identifiers")
            for task_id in parsed_ids:
                ledger_by_task.setdefault(task_id, []).append(row)

        for line in lines:
            match = TASK.match(line.strip())
            if not match:
                continue
            task_id = match.group("id")
            candidates = ledger_by_task.get(task_id, [])
            group_id = ""
            identity = ""
            mapping_state = ""
            issue_numbers: tuple[int, ...] = ()
            status = "missing"
            if len(candidates) > 1:
                status = "ambiguous"
            elif candidates:
                candidate = candidates[0]
                group_id = candidate["group_id"]
                identity = candidate["identity"]
                mapping_state = candidate["state"].upper()
                identity_match = LEDGER_IDENTITY.match(identity)
                issue_numbers = tuple(int(item.group("number")) for item in ISSUE_REF.finditer(candidate["issue"]))
                expected = (
                    identity_match is not None
                    and identity_match.group("repo") == repository_name
                    and identity_match.group("source") == relative
                    and identity_match.group("group") == group_id
                    and len(issue_numbers) == 1
                    and candidate["url"].endswith(f"/issues/{issue_numbers[0]}")
                )
                status = "mapped" if expected else "stale"
            feature_tasks.append(
                SpecTask(
                    task_id=task_id,
                    title=match.group("title").strip(),
                    feature=path.parent.name,
                    source=str(path.relative_to(repository)),
                    issue_numbers=issue_numbers,
                    synchronized=status == "mapped",
                    group_id=group_id,
                    stable_identity=identity,
                    mapping_status=status,
                    mapping_state=mapping_state,
                )
            )
        # One warning per file and status; a per-task warning buries everything else.
        unmapped: dict[str, list[str]] = {}
        for task in feature_tasks:
            if task.mapping_status != "mapped":
                unmapped.setdefault(task.mapping_status, []).append(task.task_id)
        for status, task_ids in sorted(unmapped.items()):
            listed = ", ".join(task_ids[:6])
            if len(task_ids) > 6:
                listed += f", and {len(task_ids) - 6} more"
            warnings.append(f"{relative}: spec-sync mapping is {status} for {len(task_ids)} task(s): {listed}")

        tasks.extend(feature_tasks)
        statuses = {task.mapping_status for task in feature_tasks}
        mapped = sum(task.synchronized for task in feature_tasks)
        if not feature_tasks:
            mapping_status = "not-applicable"
            action = "add actionable tasks"
        elif "ambiguous" in statuses:
            mapping_status = "ambiguous"
            action = "repair ambiguous issue mappings"
        elif "stale" in statuses:
            mapping_status = "stale"
            action = "repair stale issue mappings"
        elif mapped == len(feature_tasks):
            mapping_status = "complete"
            action = "none"
        elif mapped:
            mapping_status = "partial"
            action = "sync remaining tasks to issues"
        else:
            mapping_status = "missing"
            action = "sync tasks to issues"
        if not (feature_path / "spec.md").is_file():
            action = "create spec.md"
        elif not (feature_path / "plan.md").is_file():
            action = "create plan.md"
        features.append(
            SpecFeature(
                name=feature_path.name,
                path=feature_path.relative_to(repository).as_posix(),
                has_spec=(feature_path / "spec.md").is_file(),
                has_plan=(feature_path / "plan.md").is_file(),
                has_tasks=True,
                total_tasks=len(feature_tasks),
                mapped_tasks=mapped,
                mapping_status=mapping_status,
                recommended_action=action,
            )
        )
    return tuple(tasks), tuple(features)


def _spec_tasks(repository: Path, repository_name: str, warnings: list[str]) -> tuple[SpecTask, ...]:
    """Compatibility wrapper for callers that only need task mappings."""
    return _spec_inventory(repository, repository_name, warnings)[0]


def collect_repository(
    repository: Path,
    config: ProjectNextConfig | None = None,
    runner: CommandRunner = subprocess_runner,
) -> RepositoryState:
    config = config or ProjectNextConfig()
    repository = repository.resolve()
    warnings: list[str] = []
    errors: list[str] = []
    complete = True

    try:
        root = runner(["git", "rev-parse", "--show-toplevel"], repository).strip()
        repository = Path(root).resolve()
    except CollectionError as exc:
        raise CollectionError(f"cannot resolve git repository at {repository}: {exc}") from exc

    try:
        repo_data = _json(runner(["gh", "repo", "view", "--json", "nameWithOwner,defaultBranchRef,url"], repository))
        repo_name = str(repo_data["nameWithOwner"])
        default_branch = str((repo_data.get("defaultBranchRef") or {}).get("name") or "main")
    except (CollectionError, KeyError, TypeError) as exc:
        raise CollectionError(f"cannot resolve GitHub repository: {exc}") from exc

    issue_fields = "number,title,labels,assignees,updatedAt,createdAt,url,body"
    try:
        raw_issues = _json(
            runner(
                [
                    "gh",
                    "issue",
                    "list",
                    "--state",
                    "open",
                    "--limit",
                    str(config.issue_limit + 1),
                    "--json",
                    issue_fields,
                ],
                repository,
            )
        )
        if len(raw_issues) > config.issue_limit:
            complete = False
            warnings.append(
                f"more than {config.issue_limit} open issues exist; inventory is truncated "
                "and no global next issue is safe"
            )
            raw_issues = raw_issues[: config.issue_limit]
        issues = tuple(
            Issue(
                number=int(item["number"]),
                title=str(item["title"]),
                body=str(item.get("body") or ""),
                labels=_labels(item.get("labels")),
                assignees=_assignees(item.get("assignees")),
                created_at=str(item.get("createdAt") or ""),
                updated_at=str(item.get("updatedAt") or ""),
                url=str(item.get("url") or ""),
            )
            for item in raw_issues
        )
    except (CollectionError, KeyError, TypeError) as exc:
        errors.append(f"open issue inventory unavailable: {exc}")
        complete = False
        issues = ()

    pr_fields = (
        "number,title,body,headRefName,closingIssuesReferences,isDraft,mergeStateStatus,"
        "reviewDecision,statusCheckRollup,url"
    )
    try:
        raw_prs = _json(
            runner(["gh", "pr", "list", "--state", "open", "--limit", "200", "--json", pr_fields], repository)
        )
        pull_requests = tuple(
            PullRequest(
                number=int(item["number"]),
                title=str(item["title"]),
                body=str(item.get("body") or ""),
                head_ref=str(item.get("headRefName") or ""),
                closing_issue_numbers=tuple(
                    int(reference["number"]) for reference in item.get("closingIssuesReferences") or ()
                ),
                draft=bool(item.get("isDraft", False)),
                merge_state=str(item.get("mergeStateStatus") or "UNKNOWN"),
                review_decision=str(item.get("reviewDecision") or ""),
                checks_state=_checks_state(item.get("statusCheckRollup")),
                url=str(item.get("url") or ""),
            )
            for item in raw_prs
        )
    except (CollectionError, KeyError, TypeError) as exc:
        errors.append(f"open pull request inventory unavailable: {exc}")
        complete = False
        pull_requests = ()

    try:
        runner(["git", "fetch", "origin", "--quiet"], repository)
    except CollectionError as exc:
        warnings.append(f"remote branch refresh failed: {exc}")
        complete = False

    try:
        worktrees = _parse_worktrees(
            runner(["git", "worktree", "list", "--porcelain"], repository), repository, runner, warnings
        )
    except CollectionError as exc:
        errors.append(f"worktree inventory unavailable: {exc}")
        complete = False
        worktrees = ()

    try:
        branches = _parse_branches(
            runner(["git", "branch", "-a", "--format=%(refname:short) %(upstream:short)"], repository)
        )
    except CollectionError as exc:
        errors.append(f"branch inventory unavailable: {exc}")
        complete = False
        branches = ()

    spec_tasks, spec_features = _spec_inventory(repository, repo_name, warnings)
    return RepositoryState(
        repository=repo_name,
        default_branch=default_branch,
        collected_at=datetime.now(timezone.utc).isoformat(),
        issues=issues,
        pull_requests=pull_requests,
        worktrees=worktrees,
        branches=branches,
        spec_tasks=spec_tasks,
        spec_features=spec_features,
        inventory_complete=complete,
        collector_warnings=tuple(warnings),
        collector_errors=tuple(errors),
    )
