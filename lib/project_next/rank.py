"""Stable ranking and top-action selection."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .classify import classify_repository, issue_number_from_branch, pull_request_issue_numbers
from .config import ProjectNextConfig
from .models import (
    Action,
    BacklogSummary,
    BacklogTiers,
    Candidate,
    Classification,
    CleanupCandidate,
    Issue,
    RecommendationResult,
    RepositoryState,
    WorktreeDetail,
)

CONTRACT_VERSION = "1.3"
PHASE = re.compile(r"\b(?:wave|phase)[-\s:]*(?P<number>\d+)\b", re.IGNORECASE)


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _priority(issue: Issue, config: ProjectNextConfig) -> int:
    labels = issue.normalized_labels
    if labels & set(config.high_priority_labels):
        return 0
    if labels & set(config.medium_priority_labels):
        return 1
    return 2


def _phase(issue: Issue) -> int:
    for label in issue.normalized_labels:
        match = PHASE.search(label)
        if match:
            return int(match.group("number"))
    match = PHASE.search(issue.title)
    return int(match.group("number")) if match else 10_000


def _type_rank(issue: Issue, config: ProjectNextConfig) -> int:
    labels = issue.normalized_labels
    title = issue.title.casefold()
    if labels & set(config.planning_labels) or re.search(r"\b(?:epic|tracking|planning)\b", title):
        return 3
    if "bug" in labels or "task" in labels or re.search(r"\b(?:fix|restore|implement)\b", title):
        return 0
    if labels & set(config.quick_win_labels):
        return 1
    return 2


def _staleness(issue: Issue, state: RepositoryState, config: ProjectNextConfig) -> int:
    collected = _parse_time(state.collected_at) or datetime.now(timezone.utc)
    updated = _parse_time(issue.updated_at) or _parse_time(issue.created_at)
    if updated is None:
        return 1
    age = max(0, (collected - updated).days)
    return 0 if age >= config.stale_after_days else 1


def rank_key(issue: Issue, state: RepositoryState, config: ProjectNextConfig) -> tuple[int, ...]:
    labels = issue.normalized_labels
    critical = 0 if (labels & set(config.critical_labels) or ("bug" in labels and _priority(issue, config) == 0)) else 1
    quick_win = 0 if labels & set(config.quick_win_labels) else 1
    return (
        critical,
        _priority(issue, config),
        _phase(issue),
        _type_rank(issue, config),
        quick_win,
        _staleness(issue, state, config),
        issue.number,
    )


def _is_critical(issue: Issue, config: ProjectNextConfig) -> bool:
    labels = issue.normalized_labels
    return bool(labels & set(config.critical_labels) or ("bug" in labels and _priority(issue, config) == 0))


def _priority_evidence(issue: Issue, config: ProjectNextConfig) -> str:
    labels = issue.normalized_labels
    matched = sorted(labels & set(config.high_priority_labels))
    if matched:
        return f"high ({matched[0]})"
    matched = sorted(labels & set(config.medium_priority_labels))
    if matched:
        return f"medium ({matched[0]})"
    return "default"


def _phase_evidence(issue: Issue) -> str:
    phase = _phase(issue)
    return f"wave/phase {phase}" if phase < 10_000 else "unspecified"


def _type_evidence(issue: Issue, config: ProjectNextConfig) -> str:
    labels = issue.normalized_labels
    title = issue.title.casefold()
    if labels & set(config.planning_labels) or re.search(r"\b(?:epic|tracking|planning)\b", title):
        return "planning"
    if "bug" in labels or re.search(r"\bfix\b", title):
        return "bug"
    if "task" in labels or re.search(r"\b(?:restore|implement)\b", title):
        return "task"
    if labels & set(config.quick_win_labels):
        return "quick-win"
    return "feature"


def _candidate(issue: Issue, state: RepositoryState, config: ProjectNextConfig) -> Candidate:
    critical = _is_critical(issue, config)
    priority = _priority_evidence(issue, config)
    phase = _phase_evidence(issue)
    issue_type = _type_evidence(issue, config)
    quick_win = bool(issue.normalized_labels & set(config.quick_win_labels))
    stale = _staleness(issue, state, config) == 0
    evidence = ["critical" if critical else priority, phase, issue_type]
    if quick_win and issue_type != "quick-win":
        evidence.append("quick win")
    if stale:
        evidence.append("stale")
    return Candidate(
        issue_number=issue.number,
        rank_key=rank_key(issue, state, config),
        priority=priority,
        phase=phase,
        issue_type=issue_type,
        quick_win=quick_win,
        critical=critical,
        stale=stale,
        rationale="; ".join(evidence) + "; ordered by the deterministic rank tuple",
        command=f"$flow-auto {issue.number}",
    )


def _issue_rank(
    number: int, issues: dict[int, Issue], state: RepositoryState, config: ProjectNextConfig
) -> tuple[int, ...]:
    return rank_key(issues[number], state, config) if number in issues else (9, 9, 99_999, 9, 9, 9, number)


def _top_action(
    state: RepositoryState,
    classification: Classification,
    ranked: tuple[int, ...],
    config: ProjectNextConfig,
) -> Action | None:
    issues = {issue.number: issue for issue in state.issues}
    if not state.inventory_complete or state.collector_errors:
        detail = tuple(state.collector_errors or state.collector_warnings)
        return Action(
            kind="resolve_inventory",
            title="Restore complete repository inventory",
            reason="The issue inventory is incomplete, so a globally correct recommendation cannot be claimed.",
            evidence=detail,
        )

    pr_candidates: list[tuple[int, tuple[int, ...], int, Action]] = []
    action_priority = {"fix_gate": 0, "address_review": 1, "merge_pr": 2, "continue_pr": 3}
    for pr in state.pull_requests:
        mapped = [number for number in pull_request_issue_numbers(pr) if number in issues]
        issue_number = min(mapped, key=lambda number: _issue_rank(number, issues, state, config)) if mapped else None
        if pr.checks_state == "failure":
            kind = "fix_gate"
            reason = f"PR #{pr.number} has failing checks."
        elif pr.review_decision.upper() == "CHANGES_REQUESTED":
            kind = "address_review"
            reason = f"PR #{pr.number} has requested changes."
        elif (
            not pr.draft
            and pr.checks_state == "success"
            and pr.review_decision.upper() in {"APPROVED", ""}
            and pr.merge_state.upper() in {"CLEAN", "HAS_HOOKS", "UNSTABLE"}
        ):
            kind = "merge_pr"
            reason = f"PR #{pr.number} is ready to merge."
        else:
            kind = "continue_pr"
            reason = f"PR #{pr.number} is active and should be completed before broad new work."
        rank = _issue_rank(issue_number, issues, state, config) if issue_number else (9, 9, 99_999, 9, 9, 9, pr.number)
        pr_candidates.append(
            (
                action_priority[kind],
                rank,
                pr.number,
                Action(
                    kind=kind,
                    title=pr.title,
                    reason=reason,
                    issue_number=issue_number,
                    pull_request_number=pr.number,
                    evidence=(
                        f"head:{pr.head_ref}",
                        f"checks:{pr.checks_state}",
                        f"review:{pr.review_decision or 'unknown'}",
                    ),
                ),
            )
        )
    if pr_candidates:
        return min(pr_candidates, key=lambda item: item[:3])[3]

    dirty_worktrees = []
    for worktree in state.worktrees:
        if not worktree.dirty:
            continue
        match = re.search(r"(?:^|/)issue-(\d+)(?:-|$)", worktree.branch, re.IGNORECASE)
        issue_number = int(match.group(1)) if match else None
        dirty_worktrees.append((issue_number, worktree))
    if dirty_worktrees:
        issue_number, worktree = min(
            dirty_worktrees,
            key=lambda item: (
                _issue_rank(item[0], issues, state, config) if item[0] else (9, 9, 99_999, 9, 9, 9, 99_999)
            ),
        )
        return Action(
            kind="continue_work",
            title=issues[issue_number].title if issue_number in issues else f"Continue {worktree.branch}",
            reason="An active worktree has uncommitted changes.",
            issue_number=issue_number,
            evidence=(f"worktree:{worktree.path}", "dirty:true"),
        )

    if classification.in_flight:
        issue_number = min(classification.in_flight, key=lambda number: _issue_rank(number, issues, state, config))
        return Action(
            kind="continue_work",
            title=issues[issue_number].title,
            reason="The issue already has a branch or worktree in flight.",
            issue_number=issue_number,
            evidence=classification.in_flight_evidence.get(issue_number, ()),
        )

    if state.gate_status == "failing":
        return Action(
            kind="fix_gate",
            title="Repair the repository quality gate",
            reason="Known failing gates outrank starting broad feature work.",
            evidence=("gate:failing",),
        )

    if ranked:
        issue_number = ranked[0]
        return Action(
            kind="start_issue",
            title=issues[issue_number].title,
            reason="This is the highest-ranked issue that passed the availability gate.",
            issue_number=issue_number,
        )

    untracked = [worktree for worktree in state.worktrees if worktree.untracked_only]
    if untracked:
        worktree = min(untracked, key=lambda item: item.path)
        return Action(
            kind="review_untracked",
            title=f"Review untracked files in {worktree.branch or worktree.path}",
            reason="No issue is startable and a worktree holds untracked files that may be unfinished work.",
            evidence=(f"worktree:{worktree.path}", "untracked_only:true"),
        )

    invalid_mappings = tuple(task for task in state.spec_tasks if task.mapping_status in {"stale", "ambiguous"})
    if invalid_mappings:
        task = invalid_mappings[0]
        return Action(
            kind="resolve_spec_mapping",
            title=f"Repair {task.mapping_status} Spec Kit mapping for {task.task_id}",
            reason="Stale or ambiguous ledger state cannot safely represent synchronized work.",
            evidence=(task.source, task.stable_identity or "identity:missing"),
        )

    pending = tuple(task for task in state.spec_tasks if not task.synchronized)
    if pending:
        group = pending[0].group_id or pending[0].task_id
        return Action(
            kind="sync_spec",
            title=f"Sync specification group {group}",
            reason="The approved specification contains a group with no stable GitHub issue mapping.",
            evidence=(pending[0].source,),
        )
    return None


def _backlog_summary(issues: tuple[Issue, ...], config: ProjectNextConfig) -> BacklogSummary:
    counts = {
        "critical": 0,
        "bugs": 0,
        "features": 0,
        "docs": 0,
        "tech_debt": 0,
        "planning": 0,
        "other": 0,
    }
    for issue in issues:
        labels = issue.normalized_labels
        title = issue.title.casefold()
        if _is_critical(issue, config):
            category = "critical"
        elif "bug" in labels or re.search(r"\bfix\b", title):
            category = "bugs"
        elif labels & {"documentation", "docs"}:
            category = "docs"
        elif labels & {"tech-debt", "technical-debt", "chore", "refactor"}:
            category = "tech_debt"
        elif labels & set(config.planning_labels) or re.search(r"\b(?:epic|tracking|planning)\b", title):
            category = "planning"
        elif labels & {"feature", "enhancement"} or re.search(r"\bfeat(?:ure)?\b", title):
            category = "features"
        else:
            category = "other"
        counts[category] += 1
    return BacklogSummary(open=len(issues), **counts)


def _backlog_tiers(
    state: RepositoryState,
    classification: Classification,
    ranked: tuple[int, ...],
    config: ProjectNextConfig,
) -> BacklogTiers:
    issues = {issue.number: issue for issue in state.issues}
    critical = tuple(number for number in sorted(issues) if _is_critical(issues[number], config))
    critical_set = set(critical)
    active = tuple(number for number in classification.in_flight if number not in critical_set)
    blocked = tuple(number for number in classification.blocked if number not in critical_set)
    uncertain = tuple(number for number in classification.uncertain if number not in critical_set)
    safe_inventory = state.inventory_complete and not state.collector_errors
    available = [number for number in ranked if number not in critical_set] if safe_inventory else []
    planning = tuple(number for number in available if _type_evidence(issues[number], config) == "planning")
    planning_set = set(planning)
    quick_wins = tuple(
        number
        for number in available
        if number not in planning_set and bool(issues[number].normalized_labels & set(config.quick_win_labels))
    )
    quick_win_set = set(quick_wins)
    ready = tuple(number for number in available if number not in (planning_set | quick_win_set))
    pending_spec_sync = tuple(
        feature.name for feature in state.spec_features if feature.recommended_action != "none"
    )
    return BacklogTiers(
        critical=critical,
        active=active,
        blocked=blocked,
        uncertain=uncertain,
        ready=ready,
        quick_wins=quick_wins,
        planning=planning,
        pending_spec_sync=pending_spec_sync,
    )


def _issue_state(number: int | None, state: RepositoryState, classification: Classification) -> str:
    if number is None:
        return "unmapped"
    if number in classification.in_flight:
        return "in-flight"
    if number in classification.blocked:
        return "blocked"
    if number in classification.available:
        return "available"
    if number in classification.uncertain:
        return "uncertain"
    if number in {issue.number for issue in state.issues}:
        return "unknown"
    return "no-open-issue"


def _worktree_report(
    state: RepositoryState, classification: Classification
) -> tuple[tuple[WorktreeDetail, ...], tuple[CleanupCandidate, ...]]:
    details: list[WorktreeDetail] = []
    cleanup: list[CleanupCandidate] = []
    worktree_branches: set[str] = set()
    for worktree in state.worktrees:
        number = issue_number_from_branch(worktree.branch)
        primary = worktree.branch == state.default_branch
        issue_state = "default" if primary else _issue_state(number, state, classification)
        cleanup_recommended = not primary and issue_state in {"unmapped", "no-open-issue"}
        cleanup_reason = ""
        if cleanup_recommended:
            cleanup_reason = "branch does not map to an open issue; it may be merged, closed, or abandoned"
            action = (
                "Inspect uncommitted changes; do not remove automatically"
                if worktree.dirty
                else "Review with $flow-cleanup"
            )
            cleanup.append(
                CleanupCandidate(
                    target_type="worktree",
                    target=worktree.path,
                    branch=worktree.branch,
                    issue_number=number,
                    reason=cleanup_reason,
                    action=action,
                )
            )
        details.append(
            WorktreeDetail(
                path=worktree.path,
                branch=worktree.branch,
                issue_number=number,
                issue_state=issue_state,
                dirty=worktree.dirty,
                untracked_only=worktree.untracked_only,
                recent_commits=worktree.recent_commits,
                cleanup_recommended=cleanup_recommended,
                cleanup_reason=cleanup_reason,
            )
        )
        if worktree.branch:
            worktree_branches.add(worktree.branch)

    for branch in state.branches:
        short_name = branch.name.removeprefix("remotes/").removeprefix("origin/")
        if short_name == state.default_branch or short_name in worktree_branches:
            continue
        number = issue_number_from_branch(short_name)
        if number is not None and _issue_state(number, state, classification) != "no-open-issue":
            continue
        cleanup.append(
            CleanupCandidate(
                target_type="remote branch" if branch.remote else "branch",
                target=branch.name,
                branch=short_name,
                issue_number=number,
                reason="branch does not map to an open issue; verify whether it is merged or abandoned",
            )
        )
    return tuple(details), tuple(cleanup)


def _vocabulary_warnings(state: RepositoryState, config: ProjectNextConfig) -> tuple[str, ...]:
    """Say so when ranking has no label signal, instead of presenting issue order as rank."""
    used = {label for issue in state.issues for label in issue.normalized_labels}
    if not used or used & config.known_labels:
        return ()
    sample = ", ".join(sorted(used)[:8])
    return (
        "no issue label matches the configured priority, quick-win, or planning vocabulary, "
        f"so ranking falls back to issue type and age (labels in use: {sample}). "
        "Map this repository's labels in .project-next.json to restore priority ranking.",
    )


def recommend(state: RepositoryState, config: ProjectNextConfig | None = None) -> RecommendationResult:
    config = config or ProjectNextConfig()
    classification = classify_repository(state)
    issues = {issue.number: issue for issue in state.issues}
    ranked = tuple(
        issue.number
        for issue in sorted(
            (issues[number] for number in classification.available),
            key=lambda issue: rank_key(issue, state, config),
        )
    )
    next_startable = ranked[0] if ranked and state.inventory_complete and not state.collector_errors else None
    pending = tuple(task for task in state.spec_tasks if not task.synchronized)
    # Engine-level advice first: it is what the reader can act on, and collector warnings
    # can run long enough to push it past the rendered cap.
    warnings = _vocabulary_warnings(state, config) + tuple(state.collector_errors)
    warnings += tuple(state.collector_warnings)
    if classification.unmapped_worktrees:
        warnings += tuple(f"unmapped worktree: {item}" for item in classification.unmapped_worktrees)
    candidates = (
        tuple(_candidate(issues[number], state, config) for number in ranked)
        if next_startable is not None
        else ()
    )
    worktree_details, cleanup_candidates = _worktree_report(state, classification)
    return RecommendationResult(
        contract_version=CONTRACT_VERSION,
        repository=state.repository,
        inventory_complete=state.inventory_complete and not state.collector_errors,
        classification=classification,
        ranked_available=ranked,
        top_action=_top_action(state, classification, ranked, config),
        next_startable_issue=next_startable,
        unsynchronized_spec_tasks=pending,
        candidates=candidates,
        backlog_summary=_backlog_summary(state.issues, config),
        backlog_tiers=_backlog_tiers(state, classification, ranked, config),
        spec_features=state.spec_features,
        worktree_details=worktree_details,
        cleanup_candidates=cleanup_candidates,
        warnings=warnings,
    )
