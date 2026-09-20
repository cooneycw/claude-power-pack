from __future__ import annotations

from typing import Any

import pytest

from lib.project_next.classify import classify_repository
from lib.project_next.models import Issue, RepositoryState


@pytest.mark.parametrize(
    "name",
    [
        "active_pr_and_safe_issue",
        "dependency_chain",
        "dependency_cycle",
        "ambiguous_dependency",
        "incomplete_inventory",
        "markdown_dependency_forms",
        "prose_is_not_a_dependency",
        "declared_blocker_without_a_reference",
        "spec_task_dependencies",
        "task_ids_resolved_from_issue_titles",
        "unlabeled_backlog",
    ],
)
def test_fixture_classification_is_exact(project_next_scenarios: dict[str, Any], name: str) -> None:
    scenario = project_next_scenarios[name]
    result = classify_repository(RepositoryState.from_dict(scenario["state"]))
    expected = scenario["expected"]

    assert list(result.in_flight) == expected["in_flight"]
    assert list(result.blocked) == expected["blocked"]
    assert list(result.available) == expected["available"]
    assert list(result.uncertain) == expected["uncertain"]

    all_sets = [set(result.in_flight), set(result.blocked), set(result.available), set(result.uncertain)]
    assert sum(len(values) for values in all_sets) == len(set().union(*all_sets))


def test_dependency_chain_records_transitive_blockers(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["dependency_chain"]["state"])
    result = classify_repository(state)

    assert result.blocked_by[10] == (11, 12)
    assert result.blocked_by[11] == (12,)


def test_cycles_are_blocked_not_startable(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["dependency_cycle"]["state"])
    result = classify_repository(state)

    assert result.blocked_by == {20: (21,), 21: (20,)}
    assert result.available == ()


def test_markdown_and_range_dependency_forms_are_parsed(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["markdown_dependency_forms"]["state"])
    result = classify_repository(state)

    assert result.dependency_map[50] == (51, 52, 53)


def test_prose_sequencing_never_creates_uncertainty(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["prose_is_not_a_dependency"]["state"])
    result = classify_repository(state)

    assert result.uncertainty == {}
    assert result.dependency_map == {60: (), 61: ()}


def test_declared_blocker_without_a_reference_stays_uncertain(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["declared_blocker_without_a_reference"]["state"])
    result = classify_repository(state)

    assert "names no issue or spec task" in result.uncertainty[70][0]


def test_spec_task_dependencies_resolve_through_the_issue_sync_ledger(
    project_next_scenarios: dict[str, Any],
) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["spec_task_dependencies"]["state"])
    result = classify_repository(state)

    assert result.dependency_map[14] == (13,)
    assert result.uncertainty == {}


def test_task_ids_resolve_from_issue_titles_when_no_ledger_exists(
    project_next_scenarios: dict[str, Any],
) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["task_ids_resolved_from_issue_titles"]["state"])
    result = classify_repository(state)

    assert result.dependency_map[371] == (368,)


def test_unresolved_task_reference_is_satisfied_when_the_inventory_is_complete() -> None:
    state = RepositoryState(
        repository="example/repo",
        default_branch="main",
        collected_at="2026-08-07T13:00:00Z",
        issues=(Issue(1, "Consumer", body="**Depends on:** T-CV01"),),
    )

    result = classify_repository(state)

    assert result.available == (1,)
    assert result.uncertainty == {}


def test_unresolved_task_reference_is_uncertain_when_the_inventory_is_incomplete() -> None:
    state = RepositoryState(
        repository="example/repo",
        default_branch="main",
        collected_at="2026-08-07T13:00:00Z",
        inventory_complete=False,
        issues=(Issue(1, "Consumer", body="**Depends on:** T-CV01"),),
    )

    result = classify_repository(state)

    assert result.uncertain == (1,)
    assert "T-CV01" in result.uncertainty[1][0]


def test_code_blocks_never_declare_dependencies(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["claude_power_pack_dogfood"]["state"])
    result = classify_repository(state)

    assert result.dependency_map[701] == ()
