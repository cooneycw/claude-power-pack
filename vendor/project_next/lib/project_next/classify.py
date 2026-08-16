"""Deterministic repository-state classification."""

from __future__ import annotations

import re
from collections import defaultdict

from .models import Classification, Issue, PullRequest, RepositoryState

ISSUE_BRANCH = re.compile(r"(?:^|/)issue-(?P<number>\d+)(?:-|$)", re.IGNORECASE)

# A declaration is only a dependency when a lead-in phrase is immediately followed by a
# reference. "Strong" phrases assert a blocker outright, so a strong phrase that names no
# machine-readable target is genuine uncertainty. "Weak" phrases are ordinary English that
# happens to read like sequencing ("run after the release"), so they only count when a
# reference actually follows and never raise uncertainty on their own.
# "Blocker" and "prerequisite" are ordinary nouns, so they only count as a declaration in
# their field-label form ("**Blockers:** #12"), never mid-sentence ("heavy blocker overlap").
STRONG_DEPENDENCY_LEAD = re.compile(
    r"\b(?:depends?\s+(?:on|upon)|depending\s+on|blocked\s+by)\b|\b(?:blockers?|prerequisites?)\b(?=[\s*_]*[:\-])",
    re.IGNORECASE,
)
WEAK_DEPENDENCY_LEAD = re.compile(r"\b(?:requires?|required\s+by|needs|after|follows)\b", re.IGNORECASE)
# Markdown emphasis and punctuation routinely sit between the phrase and its references,
# as in "**Depends on:** #367" or "(depends on T004)".
REFERENCE_CONNECTOR = re.compile(r"[\s:*_>()\[\]]*")
ISSUE_REFERENCE = re.compile(r"#(?P<start>\d+)(?:\s*[-–—]\s*#?(?P<end>\d+))?")
TASK_REFERENCE = re.compile(r"(?P<task>[A-Z]{1,4}(?:-[A-Z]{1,4})?\d{2,4})\b")
REFERENCE_SEPARATOR = re.compile(r"[\s,;&/–—-]*(?:and|plus|then)?[\s]*", re.IGNORECASE)
DANGLING_REFERENCE = re.compile(r"#(?!\d)")
CODE_FENCE = re.compile(r"^\s*(?:```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")
DECLARED_TASK = re.compile(r"^-\s*\[[ xX]\]\s+(?:\*\*)?(?P<id>[A-Za-z]{1,4}(?:-[A-Za-z]{1,4})?\d{1,4})(?:\*\*)?\b")
CHECKLIST_ISSUE = re.compile(r"^-\s*\[\s\]\s+.*?#(?P<number>\d+)\b", re.IGNORECASE)
EXPLICIT_PR_ISSUE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|issue)\s*:?[\s#]+(?P<number>\d+)\b",
    re.IGNORECASE,
)
# Guards an "#367-#376" style range from expanding into an implausible span.
MAX_REFERENCE_RANGE = 50


def issue_number_from_branch(branch: str) -> int | None:
    match = ISSUE_BRANCH.search(branch)
    return int(match.group("number")) if match else None


def pull_request_issue_numbers(pr: PullRequest) -> tuple[int, ...]:
    numbers = set(pr.closing_issue_numbers)
    branch_issue = issue_number_from_branch(pr.head_ref)
    if branch_issue is not None:
        numbers.add(branch_issue)
    numbers.update(int(match.group("number")) for match in EXPLICIT_PR_ISSUE.finditer(f"{pr.title}\n{pr.body}"))
    return tuple(sorted(numbers))


def strip_code(text: str) -> str:
    """Drop fenced blocks and inline spans so code never reads as dependency prose."""
    kept: list[str] = []
    fenced = False
    for line in text.splitlines():
        if CODE_FENCE.match(line):
            fenced = not fenced
            continue
        kept.append("" if fenced else INLINE_CODE.sub(" ", line))
    return "\n".join(kept)


def _skip(pattern: re.Pattern[str], line: str, position: int) -> int:
    match = pattern.match(line, position)
    return match.end() if match else position


def _reference_list(line: str, position: int) -> tuple[set[int], set[str], int]:
    """Consume a comma/range separated run of issue and task references at `position`."""
    issues: set[int] = set()
    tasks: set[str] = set()
    consumed = 0
    while position < len(line):
        issue_match = ISSUE_REFERENCE.match(line, position)
        task_match = None if issue_match else TASK_REFERENCE.match(line, position)
        if issue_match:
            start = int(issue_match.group("start"))
            end = int(issue_match.group("end") or start)
            span = end - start
            issues.update(range(start, end + 1) if 0 < span <= MAX_REFERENCE_RANGE else (start,))
            position = issue_match.end()
        elif task_match:
            tasks.add(task_match.group("task").upper())
            position = task_match.end()
        else:
            break
        consumed += 1
        position = _skip(REFERENCE_SEPARATOR, line, position)
    return issues, tasks, consumed


def _line_references(line: str) -> tuple[set[int], set[str], list[str]]:
    issues: set[int] = set()
    tasks: set[str] = set()
    unresolved: list[str] = []
    for pattern, strong in ((STRONG_DEPENDENCY_LEAD, True), (WEAK_DEPENDENCY_LEAD, False)):
        for lead in pattern.finditer(line):
            start = _skip(REFERENCE_CONNECTOR, line, lead.end())
            found_issues, found_tasks, consumed = _reference_list(line, start)
            issues |= found_issues
            tasks |= found_tasks
            if consumed or not strong:
                continue
            detail = "an issue reference is present but not attached to the phrase"
            if not ISSUE_REFERENCE.search(line) and not DANGLING_REFERENCE.search(line):
                detail = "the blocker names no issue or spec task"
            unresolved.append(f"'{lead.group(0).strip()}' declares a dependency but {detail}: {line.strip()}")
    return issues, tasks, unresolved


def _dependencies(issue: Issue, task_issues: dict[str, set[int]]) -> tuple[set[int], list[str], set[str]]:
    text = strip_code(f"{issue.title}\n{issue.body}")
    lines = text.splitlines()
    declared_tasks = set()
    for line in lines:
        match = DECLARED_TASK.match(line.strip())
        if match:
            declared_tasks.add(match.group("id").upper())

    dependencies: set[int] = set()
    referenced_tasks: set[str] = set()
    uncertainty: list[str] = []
    for line in lines:
        found_issues, found_tasks, unresolved = _line_references(line)
        dependencies |= found_issues
        referenced_tasks |= found_tasks
        uncertainty.extend(unresolved)

    for line in lines:
        match = CHECKLIST_ISSUE.search(line.strip())
        if match and re.search(r"\b(?:wave|phase|epic|parent)\b", issue.title, re.IGNORECASE):
            dependencies.add(int(match.group("number")))

    # Task IDs the issue defines itself describe its own internal ordering, not a blocker.
    unresolved_tasks: set[str] = set()
    for task in sorted(referenced_tasks - declared_tasks):
        mapped = task_issues.get(task)
        if mapped:
            dependencies |= mapped
        else:
            unresolved_tasks.add(task)

    dependencies.discard(issue.number)
    return dependencies, uncertainty, unresolved_tasks


def _task_issue_index(state: RepositoryState) -> dict[str, set[int]]:
    """Map spec task IDs onto open issues via the Issue Sync ledger, then issue titles."""
    from_titles: dict[str, set[int]] = defaultdict(set)
    for issue in state.issues:
        match = TASK_REFERENCE.match(issue.title.strip())
        if match and re.match(r"[\s:.·|—-]", issue.title.strip()[match.end() : match.end() + 1] or " "):
            from_titles[match.group("task").upper()].add(issue.number)

    index: dict[str, set[int]] = defaultdict(set)
    # A task ID claimed by two open issues identifies nothing, so it stays unresolved.
    for task, numbers in from_titles.items():
        if len(numbers) == 1:
            index[task].update(numbers)
    for task in state.spec_tasks:
        if task.issue_numbers and task.mapping_status not in {"stale", "ambiguous"}:
            index[task.task_id.upper()] = set(task.issue_numbers)
    return dict(index)


def _cycle_members(graph: dict[int, set[int]]) -> set[int]:
    index = 0
    indices: dict[int, int] = {}
    lowlinks: dict[int, int] = {}
    stack: list[int] = []
    on_stack: set[int] = set()
    cycles: set[int] = set()

    def strong_connect(node: int) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for dependency in sorted(graph.get(node, set())):
            if dependency not in graph:
                continue
            if dependency not in indices:
                strong_connect(dependency)
                lowlinks[node] = min(lowlinks[node], lowlinks[dependency])
            elif dependency in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[dependency])

        if lowlinks[node] != indices[node]:
            return
        component: list[int] = []
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        if len(component) > 1:
            cycles.update(component)

    for node in sorted(graph):
        if node not in indices:
            strong_connect(node)
    return cycles


def classify_repository(state: RepositoryState) -> Classification:
    issue_numbers = {issue.number for issue in state.issues}
    evidence: dict[int, set[str]] = defaultdict(set)
    unmapped_worktrees: list[str] = []

    for worktree in state.worktrees:
        number = issue_number_from_branch(worktree.branch)
        if number in issue_numbers:
            evidence[number].add(f"worktree:{worktree.path}{':dirty' if worktree.dirty else ':clean'}")
        elif worktree.branch and worktree.branch != state.default_branch:
            unmapped_worktrees.append(f"{worktree.path} ({worktree.branch})")

    for branch in state.branches:
        number = issue_number_from_branch(branch.name)
        if number in issue_numbers:
            kind = "remote-branch" if branch.remote else "local-branch"
            evidence[number].add(f"{kind}:{branch.name}")

    for pr in state.pull_requests:
        for number in pull_request_issue_numbers(pr):
            if number in issue_numbers:
                evidence[number].add(f"pr:#{pr.number}")

    task_issues = _task_issue_index(state)
    dependency_map: dict[int, set[int]] = {}
    uncertainty: dict[int, list[str]] = defaultdict(list)
    for issue in state.issues:
        dependencies, reasons, unresolved_tasks = _dependencies(issue, task_issues)
        dependency_map[issue.number] = dependencies
        uncertainty[issue.number].extend(reasons)
        if not state.inventory_complete:
            unknown = sorted(dependencies - issue_numbers)
            if unknown:
                uncertainty[issue.number].append(
                    "dependency state unavailable for " + ", ".join(f"#{number}" for number in unknown)
                )
            # With a complete inventory an unmatched task ID means the work is not an open
            # issue, which is the same "already satisfied" reading a closed #reference gets.
            if unresolved_tasks:
                uncertainty[issue.number].append(
                    "dependency state unavailable for spec " + ", ".join(sorted(unresolved_tasks))
                )

    cycles = _cycle_members(dependency_map)
    blocked_by: dict[int, set[int]] = defaultdict(set)
    for number in cycles:
        blocked_by[number].update(dependency_map[number] & cycles)

    changed = True
    while changed:
        changed = False
        for issue_number, dependencies in dependency_map.items():
            before = set(blocked_by[issue_number])
            for dependency in dependencies:
                if dependency in issue_numbers:
                    blocked_by[issue_number].add(dependency)
                    blocked_by[issue_number].update(blocked_by.get(dependency, set()))
            blocked_by[issue_number].discard(issue_number)
            if blocked_by[issue_number] != before:
                changed = True

    in_flight = set(evidence)
    uncertain = {number for number, reasons in uncertainty.items() if reasons} - in_flight
    blocked = {number for number, blockers in blocked_by.items() if blockers} - in_flight - uncertain
    available = issue_numbers - in_flight - blocked - uncertain

    partitions = (in_flight, blocked, available, uncertain)
    if set().union(*partitions) != issue_numbers or sum(len(group) for group in partitions) != len(issue_numbers):
        raise AssertionError("project-next classifications are not disjoint and exhaustive")

    return Classification(
        in_flight=tuple(sorted(in_flight)),
        blocked=tuple(sorted(blocked)),
        available=tuple(sorted(available)),
        uncertain=tuple(sorted(uncertain)),
        dependency_map={number: tuple(sorted(values)) for number, values in sorted(dependency_map.items())},
        blocked_by={number: tuple(sorted(values)) for number, values in sorted(blocked_by.items()) if values},
        in_flight_evidence={number: tuple(sorted(values)) for number, values in sorted(evidence.items())},
        uncertainty={number: tuple(values) for number, values in sorted(uncertainty.items()) if values},
        unmapped_worktrees=tuple(sorted(unmapped_worktrees)),
    )
