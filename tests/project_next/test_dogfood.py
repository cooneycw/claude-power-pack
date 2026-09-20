from __future__ import annotations

from typing import Any

import pytest

from lib.project_next.models import RepositoryState
from lib.project_next.rank import recommend


@pytest.mark.parametrize("name", ["codex_power_pack_dogfood", "claude_power_pack_dogfood"])
def test_power_pack_dogfood_fixtures_select_expected_actions(project_next_scenarios: dict[str, Any], name: str) -> None:
    scenario = project_next_scenarios[name]
    result = recommend(RepositoryState.from_dict(scenario["state"]))
    expected = scenario["expected"]

    assert result.top_action is not None
    assert result.top_action.kind == expected["top_action"]
    assert result.top_action.issue_number == expected["top_issue"]
    assert result.next_startable_issue == expected["next_startable"]
    assert list(result.classification.in_flight) == expected["in_flight"]
    assert list(result.classification.blocked) == expected["blocked"]
    assert list(result.classification.available) == expected["available"]


def test_no_non_available_issue_leaks_into_startable_selection(project_next_scenarios: dict[str, Any]) -> None:
    for scenario in project_next_scenarios.values():
        result = recommend(RepositoryState.from_dict(scenario["state"]))
        if result.next_startable_issue is not None:
            assert result.next_startable_issue in result.classification.available
        if result.top_action is not None and result.top_action.kind == "start_issue":
            assert result.top_action.issue_number in result.classification.available


def test_a_backlog_with_no_blockers_always_yields_a_ready_recommendation(
    project_next_scenarios: dict[str, Any],
) -> None:
    """The enrichment work shipped reports that were shaped correctly but empty in practice."""
    unblocked = ("prose_is_not_a_dependency", "unlabeled_backlog", "markdown_dependency_forms")
    for name in unblocked:
        state = RepositoryState.from_dict(project_next_scenarios[name]["state"])
        result = recommend(state)

        assert result.classification.available, f"{name} classified every open issue as unstartable"
        assert result.next_startable_issue is not None, f"{name} produced no startable recommendation"
        assert result.candidates, f"{name} rendered no ranked candidates"


@pytest.mark.parametrize(
    "name",
    [
        "markdown_dependency_forms",
        "prose_is_not_a_dependency",
        "declared_blocker_without_a_reference",
        "spec_task_dependencies",
        "task_ids_resolved_from_issue_titles",
        "unlabeled_backlog",
        "untracked_only_worktree",
        "untracked_only_with_no_startable_work",
    ],
)
def test_real_world_scenarios_select_expected_actions(project_next_scenarios: dict[str, Any], name: str) -> None:
    scenario = project_next_scenarios[name]
    result = recommend(RepositoryState.from_dict(scenario["state"]))
    expected = scenario["expected"]

    assert (result.top_action.kind if result.top_action else None) == expected["top_action"]
    assert (result.top_action.issue_number if result.top_action else None) == expected["top_issue"]
    assert result.next_startable_issue == expected["next_startable"]
    assert list(result.classification.blocked) == expected["blocked"]
    assert list(result.classification.available) == expected["available"]
    assert list(result.classification.uncertain) == expected["uncertain"]
