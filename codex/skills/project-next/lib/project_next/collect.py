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
REFS_LINE = re.compile(r"\bRefs\s*:?\s*((?:#\d+[\s,;]*(?:and\s*)?)+)", re.IGNORECASE)
CROSS_REPO_ISSUE = re.compile(r"(?<![\w./-])(?P<owner>[\w.-]+)/(?P<name>[\w.-]+)#(?P<number>\d+)\b")
#: Aliased GraphQL lookups per request; bounded so one request stays well inside
#: GitHub's query-complexity limit.
LOOKUP_BATCH = 20
#: A per-issue search returning more hits than this cannot prove absence for that issue.
PER_ISSUE_SEARCH_LIMIT = 50
#: Cross-repo references looked up per run; the rest stay unknown, never closed.
MAX_EXTERNAL_LOOKUPS = 60


class CollectionError(RuntimeError):
    """A required repository-state command failed."""


def gh_field_remediation(command: list[str], diagnostic: str) -> str | None:
    """Recognize only gh's local rejection of a known field we requested."""
    if command[:3] not in (["gh", "issue", "list"], ["gh", "pr", "list"]) or "--json" not in command:
        return None
    index = command.index("--json") + 1
    if index >= len(command):
        return None
    lines = diagnostic.strip().splitlines()
    if len(lines) < 3 or lines[1] != "Available fields:":
        return None
    match = re.fullmatch(r'Unknown JSON field: "([A-Za-z][A-Za-z0-9]*)"', lines[0])
    known = {"closingIssuesReferences", "blockedBy", "blocking", "parent", "subIssues"}
    if not match or match[1] not in known or match[1] not in command[index].split(","):
        return None
    if any(not re.fullmatch(r"  [A-Za-z][A-Za-z0-9]*", line) for line in lines[2:]):
        return None
    return (
        f"gh JSON field {match[1]} is unsupported by this installation. Upgrade gh "
        "(standard-source capability floor 2.94.0; backports require capability verification); "
        "inventory remains unexamined. This local field error does not establish authentication state."
    )


def subprocess_runner(command: list[str], cwd: Path) -> str:
    timeout = 30 if command[:5] == ["gh", "pr", "list", "--state", "merged"] else None
    if command[:3] == ["gh", "api", "graphql"]:
        timeout = 60
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout)
    if completed.returncode:
        diagnostic = (completed.stderr or "").strip() or (completed.stdout or "").strip() or "command failed"
        message = gh_field_remediation(command, diagnostic) or diagnostic.splitlines()[0]
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


#: NEGATIVE-CONTROL: controls/project-next
#:     Registered per issue #1398 (ADR 0008 census row 23: `project-next.py` +
#:     the vendored engine, consumer `/project:next`, class G - a gate that
#:     lets work THROUGH, whose JSON output the command document declares
#:     authoritative, so nothing downstream re-derives it). A worktree whose
#:     `git status` call fails here must read as UNEXAMINED, never as clean -
#:     the pre-#1398 behaviour, vendored as this control's anchor, did the
#:     latter and fed a removal-leaning cleanup action for work nothing had
#:     actually verified was safe to discard.
#: NEGATIVE-CONTROL: controls/project-next-worktree-log
#:     Registered per issue #1488 (same instrument, row 23 - an independently
#:     blind sub-check, registered separately rather than as a new case on the
#:     control above: a log-only failure must not discard an already-
#:     successful status read, and the two sub-checks' anchors do not agree
#:     on each other's known-bad input, so one shared anchor set cannot prove
#:     both).
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
        status_unknown_reason = ""
        try:
            status = runner(["git", "status", "--short"], path)
        except CollectionError as exc:
            # UNEXAMINED, not clean (#1398). `status = ""` used to mean both "no
            # changes" and "could not ask" - indistinguishable from the outside,
            # and the second one is a worktree whose state nothing has verified.
            warnings.append(str(exc))
            status_unknown_reason = str(exc)
            status = ""
        try:
            commits = runner(["git", "log", "--oneline", "-5"], path).splitlines()
        except CollectionError as exc:
            warnings.append(str(exc))
            commits = []
        entries_changed = [line for line in status.splitlines() if line.strip()]
        # A stray untracked file is not work in progress, so it must not outrank a real
        # recommendation the way a tracked modification does.
        tracked = [line for line in entries_changed if not line.startswith("??")]
        worktrees.append(
            Worktree(
                path=str(path),
                branch=branch,
                dirty=None if status_unknown_reason else bool(tracked),
                untracked_only=bool(entries_changed) and not tracked,
                recent_commits=tuple(commits),
                status_unknown_reason=status_unknown_reason,
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


def _refs_numbers(text: str) -> set[int]:
    """Issue numbers named on `Refs #N` lines, the non-closing delivery convention."""
    numbers: set[int] = set()
    for line in text.splitlines():
        for match in REFS_LINE.finditer(line):
            numbers.update(int(ref.group("number")) for ref in ISSUE_REF.finditer(match.group(1)))
    return numbers


def _graphql(runner: CommandRunner, repository: Path, query: str) -> dict[str, Any]:
    payload = _json(runner(["gh", "api", "graphql", "-f", f"query={query}"], repository))
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict) or payload.get("errors"):
        detail = payload.get("errors") if isinstance(payload, dict) else payload
        raise CollectionError(f"graphql lookup failed: {str(detail)[:200]}")
    return payload["data"]


def _per_issue_merged_refs(
    runner: CommandRunner, repository: Path, repo_name: str, numbers: list[int]
) -> tuple[set[int], set[int]]:
    """Ask, per open issue, whether a merged PR names it on a `Refs` line (#1626).

    Replaces "the newest 200 merged PRs" as the evidence when that window is full, so
    the answer is about THIS issue rather than about how many PRs the repository has
    ever merged. GitHub search narrows the candidates; each hit's own title and body
    are re-read locally, so a number appearing in unrelated prose is not delivery.
    Returns (issues with a merged Refs PR, issues the search could not settle). Raises
    CollectionError when a request itself fails, so the caller can fail closed.
    """
    referenced: set[int] = set()
    unsettled: set[int] = set()
    for start in range(0, len(numbers), LOOKUP_BATCH):
        batch = numbers[start : start + LOOKUP_BATCH]
        fields = " ".join(
            f'i{number}: search(type: ISSUE, first: {PER_ISSUE_SEARCH_LIMIT}, '
            f'query: "repo:{repo_name} is:pr is:merged {number}") '
            "{ issueCount nodes { ... on PullRequest { number title body } } }"
            for number in batch
        )
        data = _graphql(runner, repository, f"query {{ {fields} }}")
        for number in batch:
            result = data.get(f"i{number}")
            if not isinstance(result, dict) or not isinstance(result.get("nodes"), list):
                unsettled.add(number)
                continue
            if int(result.get("issueCount") or 0) > PER_ISSUE_SEARCH_LIMIT:
                unsettled.add(number)
            for node in result["nodes"]:
                if not isinstance(node, dict):
                    continue
                if number in _refs_numbers(f"{node.get('title') or ''}\n{node.get('body') or ''}"):
                    referenced.add(number)
    return referenced, unsettled - referenced


def _external_references(issues: tuple[Issue, ...], repo_name: str) -> list[str]:
    from .classify import strip_code

    found: set[str] = set()
    for issue in issues:
        for match in CROSS_REPO_ISSUE.finditer(strip_code(issue.body)):
            ref = f"{match.group('owner')}/{match.group('name')}#{match.group('number')}"
            if f"{match.group('owner')}/{match.group('name')}".lower() != repo_name.lower():
                found.add(ref)
    return sorted(found)


def _external_issue_states(
    runner: CommandRunner, repository: Path, references: list[str], warnings: list[str]
) -> dict[str, str]:
    """Look up cross-repo `owner/repo#N` references (#1626). Fail-open to UNKNOWN.

    A reference left out of the result is unknown and stays uncertain in the
    classifier; nothing here can make an unlooked-up blocker read as satisfied.
    """
    states: dict[str, str] = {}
    if len(references) > MAX_EXTERNAL_LOOKUPS:
        warnings.append(
            f"{len(references)} cross-repo references found; only the first {MAX_EXTERNAL_LOOKUPS} were looked up"
        )
        references = references[:MAX_EXTERNAL_LOOKUPS]
    for start in range(0, len(references), LOOKUP_BATCH):
        batch = references[start : start + LOOKUP_BATCH]
        parts = []
        for index, ref in enumerate(batch):
            repo, _, number = ref.partition("#")
            owner, _, name = repo.partition("/")
            parts.append(
                f'r{index}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) '
                f"{{ issueOrPullRequest(number: {int(number)}) "
                "{ __typename ... on Issue { state } ... on PullRequest { state } } }"
            )
        try:
            payload = _json(runner(["gh", "api", "graphql", "-f", f"query=query {{ {' '.join(parts)} }}"], repository))
        except (CollectionError, subprocess.TimeoutExpired) as exc:
            warnings.append(f"cross-repo dependency lookup failed; those references stay uncertain: {exc}")
            continue
        data = payload.get("data") if isinstance(payload, dict) else None
        for index, ref in enumerate(batch):
            node = ((data or {}).get(f"r{index}") or {}).get("issueOrPullRequest") if isinstance(data, dict) else None
            kind = str((node or {}).get("__typename") or "")
            state = str((node or {}).get("state") or "").upper()
            if state == "OPEN":
                states[ref] = "OPEN"
            elif (kind == "Issue" and state == "CLOSED") or (kind == "PullRequest" and state == "MERGED"):
                states[ref] = "CLOSED"
            # A pull request closed WITHOUT merging delivered nothing: it stays unknown,
            # so the dependency stays uncertain rather than reading as satisfied.
    return states


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

    # One bounded bulk read. A full page cannot establish absence of older Refs, so a
    # full page is followed by a per-issue lookup (#1626) before anything is unknown.
    merged_refs: set[int] = set()
    merged_refs_unknown: set[int] = set()
    merged_history_complete = True
    window_full = False
    try:
        merged_prs = _json(
            runner(
                ["gh", "pr", "list", "--state", "merged", "--limit", "200", "--json", "number,title,body"],
                repository,
            )
        )
        if not isinstance(merged_prs, list):
            raise CollectionError("merged PR history is not a JSON list")
        window_full = len(merged_prs) >= 200
        for item in merged_prs:
            merged_refs |= _refs_numbers(f"{item.get('title') or ''}\n{item.get('body') or ''}")
    except (CollectionError, subprocess.TimeoutExpired, KeyError, TypeError, AttributeError) as exc:
        merged_history_complete = False
        errors.append(f"merged PR history unavailable: {exc}")
    if merged_history_complete and window_full:
        unchecked = sorted({issue.number for issue in issues} - merged_refs)
        try:
            found, merged_refs_unknown = _per_issue_merged_refs(runner, repository, repo_name, unchecked)
            merged_refs |= found
            if merged_refs_unknown:
                warnings.append(
                    "merged PR search could not settle partial delivery for "
                    + ", ".join(f"#{number}" for number in sorted(merged_refs_unknown))
                )
        except (CollectionError, subprocess.TimeoutExpired, KeyError, TypeError, AttributeError) as exc:
            merged_history_complete = False
            warnings.append(
                f"merged PR history truncated at 200 and the per-issue lookup failed ({exc}); partial delivery unknown"
            )
    if not merged_history_complete:
        complete = False

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

    external_states = _external_issue_states(runner, repository, _external_references(issues, repo_name), warnings)
    spec_tasks, spec_features = _spec_inventory(repository, repo_name, warnings)
    return RepositoryState(
        repository=repo_name,
        default_branch=default_branch,
        collected_at=datetime.now(timezone.utc).isoformat(),
        issues=issues,
        pull_requests=pull_requests,
        merged_refs_issue_numbers=tuple(sorted(merged_refs & {issue.number for issue in issues})),
        merged_pr_history_complete=merged_history_complete,
        merged_refs_unknown_issue_numbers=tuple(sorted(merged_refs_unknown)),
        external_issue_states=external_states,
        worktrees=worktrees,
        branches=branches,
        spec_tasks=spec_tasks,
        spec_features=spec_features,
        inventory_complete=complete,
        collector_warnings=tuple(warnings),
        collector_errors=tuple(errors),
    )
