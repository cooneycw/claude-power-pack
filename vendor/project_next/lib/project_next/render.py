"""Versioned human-readable project-next output modes."""

from __future__ import annotations

from .models import Action, Candidate, RecommendationResult, RepositoryState

MAX_LISTED_WARNINGS = 5
MAX_UNCERTAINTY_REASONS = 2
MAX_REASON_CHARS = 160


def _capped(items: tuple[str, ...], limit: int) -> list[str]:
    listed = [f"- {item}" for item in items[:limit]]
    if len(items) > limit:
        listed.append(f"- …and {len(items) - limit} more (use `--json` for the full list)")
    return listed


def _reasons(reasons: tuple[str, ...]) -> str:
    shown = [
        reason if len(reason) <= MAX_REASON_CHARS else f"{reason[:MAX_REASON_CHARS].rstrip()}…"
        for reason in reasons[:MAX_UNCERTAINTY_REASONS]
    ]
    if len(reasons) > MAX_UNCERTAINTY_REASONS:
        shown.append(f"and {len(reasons) - MAX_UNCERTAINTY_REASONS} more")
    return "; ".join(shown)


def _action(action: Action | None) -> str:
    if action is None:
        return "None — no actionable repository work was found."
    refs = []
    if action.issue_number is not None:
        refs.append(f"issue #{action.issue_number}")
    if action.pull_request_number is not None:
        refs.append(f"PR #{action.pull_request_number}")
    suffix = f" ({', '.join(refs)})" if refs else ""
    evidence = f" Evidence: {', '.join(action.evidence)}." if action.evidence else ""
    return f"{action.kind}: {action.title}{suffix} — {action.reason}{evidence}"


def _next_issue(result: RecommendationResult, state: RepositoryState) -> str:
    if result.next_startable_issue is None:
        return "None"
    issue = next(issue for issue in state.issues if issue.number == result.next_startable_issue)
    return f"#{issue.number} {issue.title}"


def _candidate_lines(candidate: Candidate, title: str, position: int | None = None) -> list[str]:
    prefix = f"{position}." if position is not None else "-"
    evidence = (
        f"priority {candidate.priority}; phase {candidate.phase}; type {candidate.issue_type}; "
        f"quick win {'yes' if candidate.quick_win else 'no'}"
    )
    return [
        f"{prefix} #{candidate.issue_number} {title} [{evidence}]",
        f"   {candidate.rationale} → `{candidate.command}`",
    ]


def _classification_state(number: int, result: RecommendationResult) -> str:
    if number in result.classification.in_flight:
        return "in-flight"
    if number in result.classification.blocked:
        return "blocked"
    if number in result.classification.uncertain:
        return "uncertain"
    if number in result.classification.available:
        return "available"
    return "unknown"


def render_brief(result: RecommendationResult, state: RepositoryState) -> str:
    confidence = "complete" if result.inventory_complete else "incomplete"
    return "\n".join(
        (
            f"Project Next {result.contract_version} — brief",
            f"Top action: {_action(result.top_action)}",
            f"Next safe issue: {_next_issue(result, state)}",
            f"Inventory: {confidence}",
        )
    )


def render_compact(result: RecommendationResult, state: RepositoryState) -> str:
    issues = {issue.number: issue for issue in state.issues}
    lines = [
        f"## {result.repository} — Project Next {result.contract_version}",
        "",
        f"**Top action:** {_action(result.top_action)}",
        f"**Next safe issue:** {_next_issue(result, state)}",
        (
            f"**State:** {len(state.issues)} open | {len(result.classification.in_flight)} in-flight | "
            f"{len(result.classification.blocked)} blocked | {len(result.classification.uncertain)} uncertain | "
            f"inventory {'complete' if result.inventory_complete else 'incomplete'}"
        ),
    ]
    if result.next_startable_issue is not None:
        lines.extend(("", "### Ready to start (top 3)"))
        for position, candidate in enumerate(result.candidates[:3], start=1):
            lines.extend(_candidate_lines(candidate, issues[candidate.issue_number].title, position))
    else:
        lines.extend(("", "### Ready to start", "- None — a complete safe recommendation is unavailable."))

    critical_non_startable = tuple(
        number
        for number in result.backlog_tiers.critical
        if number not in result.classification.available
    )
    if critical_non_startable:
        lines.extend(("", "### Critical work (not startable)"))
        for number in critical_non_startable:
            lines.append(f"- #{number} {issues[number].title} — {_classification_state(number, result)}")
    if result.classification.in_flight:
        lines.extend(("", "### Active work (not startable)"))
        lines.extend(
            f"- #{number} {issues[number].title} — {', '.join(result.classification.in_flight_evidence[number])}"
            for number in result.classification.in_flight
        )
    if result.classification.blocked:
        lines.extend(("", "### Blocked (not startable)"))
        lines.extend(
            f"- #{number} {issues[number].title} — blocked by "
            + ", ".join(f"#{blocker}" for blocker in result.classification.blocked_by[number])
            for number in result.classification.blocked
        )
    if result.classification.uncertain:
        lines.extend(("", "### Uncertain (not startable)"))
        lines.extend(
            f"- #{number} {issues[number].title} — {_reasons(result.classification.uncertainty[number])}"
            for number in result.classification.uncertain
        )
    if result.warnings:
        lines.extend(("", "### Warnings"))
        lines.extend(_capped(result.warnings, MAX_LISTED_WARNINGS))
    return "\n".join(lines)


def _tier_issue_lines(
    numbers: tuple[int, ...], result: RecommendationResult, state: RepositoryState
) -> list[str]:
    issues = {issue.number: issue for issue in state.issues}
    candidates = {candidate.issue_number: candidate for candidate in result.candidates}
    lines: list[str] = []
    for number in numbers:
        state_name = _classification_state(number, result)
        suffix = ""
        if number in candidates and state_name == "available":
            suffix = f"; {candidates[number].rationale} → `{candidates[number].command}`"
        lines.append(f"- #{number} {issues[number].title} — {state_name}{suffix}")
    return lines or ["- none"]


def render_full(result: RecommendationResult, state: RepositoryState) -> str:
    summary = result.backlog_summary
    lines = [
        render_compact(result, state),
        "",
        "### Categorized backlog summary",
        (
            f"- {summary.open} open | {summary.critical} critical | {summary.bugs} bugs | "
            f"{summary.features} features | {summary.docs} docs | {summary.tech_debt} tech debt | "
            f"{summary.planning} planning | {summary.other} other"
        ),
        "",
        "### Tier 1 — Critical work",
        *_tier_issue_lines(result.backlog_tiers.critical, result, state),
        "",
        "### Tier 2 — Active work",
        *_tier_issue_lines(result.backlog_tiers.active, result, state),
        "",
        "### Blocked work (not actionable)",
        *_tier_issue_lines(result.backlog_tiers.blocked, result, state),
        "",
        "### Uncertain work (not actionable)",
        *_tier_issue_lines(result.backlog_tiers.uncertain, result, state),
        "",
        "### Tier 3 — Ready to start",
        *_tier_issue_lines(result.backlog_tiers.ready, result, state),
        "",
        "### Tier 3b — Pending specification sync",
    ]
    lines.extend(f"- {name}" for name in result.backlog_tiers.pending_spec_sync)
    if not result.backlog_tiers.pending_spec_sync:
        lines.append("- none")
    lines.extend(("", "### Tier 4 — Quick wins"))
    lines.extend(_tier_issue_lines(result.backlog_tiers.quick_wins, result, state))
    lines.extend(("", "### Tier 5 — Planning and discussion"))
    lines.extend(_tier_issue_lines(result.backlog_tiers.planning, result, state))

    lines.extend(("", "### Spec Kit readiness"))
    if result.spec_features:
        lines.extend(
            (
                "| Feature | spec.md | plan.md | tasks.md | Mapping | Recommended action |",
                "|---|---:|---:|---:|---|---|",
            )
        )
        lines.extend(
            f"| {feature.name} | {'yes' if feature.has_spec else 'no'} | "
            f"{'yes' if feature.has_plan else 'no'} | {'yes' if feature.has_tasks else 'no'} | "
            f"{feature.mapped_tasks}/{feature.total_tasks} ({feature.mapping_status}) | "
            f"{feature.recommended_action} |"
            for feature in result.spec_features
        )
    else:
        lines.append("- no Spec Kit features found")

    lines.extend(("", "### Pull requests"))
    lines.extend(
        f"- #{pr.number} {pr.title} — head {pr.head_ref}; checks {pr.checks_state}; "
        f"review {pr.review_decision or 'unknown'}; merge {pr.merge_state}"
        for pr in state.pull_requests
    )
    if not state.pull_requests:
        lines.append("- none")

    lines.extend(("", "### Worktree detail"))
    if result.worktree_details:
        lines.extend(
            (
                "| Path | Branch | Issue | State | Working tree | Recent commits |",
                "|---|---|---:|---|---|---|",
            )
        )
        for worktree in result.worktree_details:
            issue = f"#{worktree.issue_number}" if worktree.issue_number is not None else "—"
            commits = "<br>".join(worktree.recent_commits) or "none"
            if worktree.dirty:
                tree = "modified"
            elif worktree.untracked_only:
                tree = "untracked only"
            else:
                tree = "clean"
            lines.append(
                f"| {worktree.path} | {worktree.branch or '(detached)'} | {issue} | "
                f"{worktree.issue_state} | {tree} | {commits} |"
            )
    else:
        lines.append("- none")

    lines.extend(("", "### Cleanup guidance"))
    lines.extend(
        f"- {candidate.target_type} `{candidate.target}` ({candidate.branch or 'detached'}) — "
        f"{candidate.reason}. {candidate.action}."
        for candidate in result.cleanup_candidates
    )
    if not result.cleanup_candidates:
        lines.append("- none")
    return "\n".join(lines)


def render_result(result: RecommendationResult, state: RepositoryState, mode: str = "compact") -> str:
    if mode == "brief":
        return render_brief(result, state)
    if mode == "full":
        return render_full(result, state)
    if mode != "compact":
        raise ValueError(f"unknown project-next output mode: {mode}")
    return render_compact(result, state)
