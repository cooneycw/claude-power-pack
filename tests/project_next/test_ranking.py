from __future__ import annotations

from typing import Any

from lib.project_next.models import Issue, RepositoryState, SpecTask, Worktree
from lib.project_next.rank import recommend


def test_ranking_uses_critical_priority_phase_type_staleness_and_number() -> None:
    state = RepositoryState(
        repository="example/ranking",
        default_branch="main",
        collected_at="2026-08-06T00:00:00Z",
        issues=(
            Issue(9, "Wave 2 docs", labels=("p1", "documentation"), updated_at="2026-08-05T00:00:00Z"),
            Issue(8, "Wave 1 feature", labels=("p1",), updated_at="2026-08-05T00:00:00Z"),
            Issue(7, "Wave 9 security", labels=("security",), updated_at="2026-08-05T00:00:00Z"),
            Issue(6, "Wave 1 old task", labels=("p1", "task"), updated_at="2025-01-01T00:00:00Z"),
            Issue(5, "Wave 1 old task", labels=("p1", "task"), updated_at="2025-01-01T00:00:00Z"),
        ),
    )

    assert recommend(state).ranked_available == (7, 5, 6, 8, 9)


def test_repeated_ranking_is_byte_stable(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["dependency_chain"]["state"])

    assert recommend(state).to_dict() == recommend(state).to_dict()


def test_incomplete_inventory_never_selects_next_startable(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["incomplete_inventory"]["state"])
    result = recommend(state)

    assert result.top_action is not None and result.top_action.kind == "resolve_inventory"
    assert result.next_startable_issue is None


def test_stale_mapping_is_repaired_before_spec_synchronization() -> None:
    state = RepositoryState(
        repository="example/repo",
        default_branch="main",
        collected_at="2026-08-06T00:00:00Z",
        spec_tasks=(
            SpecTask(
                "T001",
                "Mapped incorrectly",
                "feature",
                ".specify/specs/feature/tasks.md",
                mapping_status="stale",
                stable_identity="spec-sync:v1:wrong/repo:path:stage-1",
            ),
        ),
    )

    result = recommend(state)

    assert result.top_action is not None
    assert result.top_action.kind == "resolve_spec_mapping"
    assert result.next_startable_issue is None


def test_missing_mapping_recommends_spec_sync_group() -> None:
    state = RepositoryState(
        repository="example/repo",
        default_branch="main",
        collected_at="2026-08-06T00:00:00Z",
        spec_tasks=(
            SpecTask(
                "T001",
                "Ready to sync",
                "feature",
                ".specify/specs/feature/tasks.md",
                group_id="stage-1",
                mapping_status="missing",
            ),
        ),
    )

    result = recommend(state)

    assert result.top_action is not None
    assert result.top_action.kind == "sync_spec"
    assert "stage-1" in result.top_action.title


def test_operational_report_keeps_critical_blocked_work_out_of_startable_tiers(
    project_next_scenarios: dict[str, Any],
) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["operational_report"]["state"])

    result = recommend(state)

    assert [candidate.issue_number for candidate in result.candidates] == [3, 4, 5]
    assert result.candidates[0].priority == "high (p1)"
    assert result.candidates[0].phase == "wave/phase 1"
    assert result.candidates[0].command == "$flow-auto 3"
    assert result.backlog_tiers.critical == (1,)
    assert result.backlog_tiers.active == (2,)
    assert result.backlog_tiers.ready == (3,)
    assert result.backlog_tiers.quick_wins == (4,)
    assert result.backlog_tiers.planning == (5,)
    assert result.backlog_tiers.uncertain == (6,)
    assert 1 not in {candidate.issue_number for candidate in result.candidates}


def test_incomplete_inventory_exposes_no_startable_candidates_or_tiers(
    project_next_scenarios: dict[str, Any],
) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["incomplete_inventory"]["state"])

    result = recommend(state)

    assert result.candidates == ()
    assert result.backlog_tiers.ready == ()
    assert result.backlog_tiers.quick_wins == ()
    assert result.backlog_tiers.planning == ()


def test_worktree_report_maps_active_work_and_marks_only_unmapped_cleanup(
    project_next_scenarios: dict[str, Any],
) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["operational_report"]["state"])

    result = recommend(state)

    details = {worktree.branch: worktree for worktree in result.worktree_details}
    assert details["issue-2-active-foundation"].issue_state == "in-flight"
    assert details["issue-2-active-foundation"].recent_commits == ("bbb active work", "aaa main commit")
    assert details["issue-99-old-work"].cleanup_recommended is True
    assert {(item.target_type, item.target) for item in result.cleanup_candidates} == {
        ("worktree", "/repo-issue-99"),
        ("remote branch", "origin/issue-88-abandoned"),
    }


def test_dirty_unmapped_worktree_cleanup_requires_inspection() -> None:
    state = RepositoryState(
        repository="example/repo",
        default_branch="main",
        collected_at="2026-08-07T13:00:00Z",
        worktrees=(Worktree("/repo-topic", "topic", dirty=True),),
    )

    candidate = recommend(state).cleanup_candidates[0]

    assert candidate.action == "Inspect uncommitted changes; do not remove automatically"


def test_unmatched_label_vocabulary_is_reported_instead_of_passing_issue_order_as_rank(
    project_next_scenarios: dict[str, Any],
) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["unlabeled_backlog"]["state"])

    result = recommend(state)

    assert result.warnings[0].startswith("no issue label matches the configured")
    assert ".project-next.json" in result.warnings[0]


def test_recognised_label_vocabulary_raises_no_warning(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["operational_report"]["state"])

    assert not any(warning.startswith("no issue label matches") for warning in recommend(state).warnings)


def test_label_separators_are_normalized_before_matching() -> None:
    state = RepositoryState(
        repository="example/labels",
        default_branch="main",
        collected_at="2026-08-07T13:00:00Z",
        issues=(
            Issue(1, "Spelled with a colon", labels=("Priority: High",)),
            Issue(2, "Spelled with a slash", labels=("priority/medium",)),
        ),
    )

    result = recommend(state)

    assert result.ranked_available == (1, 2)
    assert result.candidates[0].priority == "high (priority-high)"


def test_untracked_files_alone_never_outrank_a_startable_issue(
    project_next_scenarios: dict[str, Any],
) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["untracked_only_worktree"]["state"])

    result = recommend(state)

    assert result.top_action is not None
    assert result.top_action.kind == "start_issue"
    assert result.top_action.issue_number == 90


def test_untracked_files_surface_once_nothing_else_is_actionable(
    project_next_scenarios: dict[str, Any],
) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["untracked_only_with_no_startable_work"]["state"])

    result = recommend(state)

    assert result.top_action is not None
    assert result.top_action.kind == "review_untracked"
    assert result.worktree_details[0].untracked_only is True


def test_tracked_modifications_still_outrank_new_work() -> None:
    state = RepositoryState(
        repository="example/dirty",
        default_branch="main",
        collected_at="2026-08-07T13:00:00Z",
        issues=(Issue(90, "Ready work", labels=("task",)),),
        worktrees=(Worktree("/repo", "main", dirty=True),),
    )

    result = recommend(state)

    assert result.top_action is not None
    assert result.top_action.kind == "continue_work"
