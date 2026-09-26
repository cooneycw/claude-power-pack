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


# Negative controls for #1035. Each marker is paired with the input that must still
# go the other way, because an exclusion that silently matches nothing renders
# identically to a working one.


def _inbox_state(inbox_labels: tuple[str, ...], **extra: Any) -> RepositoryState:
    return RepositoryState(
        repository="example/inbox",
        default_branch="main",
        collected_at="2026-09-26T00:00:00Z",
        issues=(
            # Old and unlabelled-by-priority: exactly the tuple the fallback ranks first.
            Issue(864, "Nit Store", labels=inbox_labels, updated_at="2026-01-01T00:00:00Z"),
            Issue(900, "Ordinary work", labels=("enhancement",), updated_at="2026-09-25T00:00:00Z"),
        ),
        **extra,
    )


def test_a_marked_inbox_is_never_available_nor_the_next_startable_issue() -> None:
    from lib.project_next.rank import recommend
    from lib.project_next.render import render_result

    state = _inbox_state(("evergreen",))
    result = recommend(state)

    assert result.classification.non_startable == (864,)
    assert result.classification.non_startable_evidence == {864: ("label:evergreen",)}
    assert 864 not in result.classification.available
    assert 864 not in result.ranked_available
    assert all(candidate.issue_number != 864 for candidate in result.candidates)
    assert result.next_startable_issue == 900
    assert "$flow-auto 864" not in render_result(result, state, "compact")


def test_the_same_inbox_without_the_marker_is_still_ranked_first() -> None:
    from lib.project_next.rank import recommend

    result = recommend(_inbox_state(()))

    assert result.classification.non_startable == ()
    assert result.next_startable_issue == 864


def test_the_marker_is_matched_after_label_normalization_and_is_configurable() -> None:
    from lib.project_next.config import ProjectNextConfig
    from lib.project_next.rank import recommend

    assert recommend(_inbox_state(("Not Startable",))).classification.non_startable == (864,)
    custom = ProjectNextConfig.from_dict({"non_startable_labels": ["standing:inbox"]})
    assert recommend(_inbox_state(("standing-inbox",)), custom).classification.non_startable == (864,)
    assert recommend(_inbox_state(("evergreen",)), custom).next_startable_issue == 864


def test_in_flight_work_outranks_the_marker() -> None:
    from lib.project_next.models import Worktree

    state = _inbox_state(("evergreen",), worktrees=(Worktree("/wt", "issue-864-triage"),))
    result = classify_repository(state, ("evergreen",))

    assert result.in_flight == (864,)
    assert result.non_startable == ()


def test_a_marked_issue_with_unresolved_dependency_prose_is_non_startable_not_uncertain() -> None:
    state = RepositoryState(
        repository="example/inbox",
        default_branch="main",
        collected_at="2026-09-26T00:00:00Z",
        issues=(Issue(871, "Evergreen re-check", body="Blocked by: an owner decision", labels=("evergreen",)),),
    )
    result = classify_repository(state, ("evergreen",))

    assert result.non_startable == (871,)
    assert result.uncertain == ()


@pytest.mark.parametrize(
    "negation",
    ["None", "none; can start from the baseline", "N/A", "nothing", "—", "-", "None within the wave. Related: #861"],
)
def test_depends_on_none_declares_no_dependency(negation: str) -> None:
    state = RepositoryState(
        repository="example/deps",
        default_branch="main",
        collected_at="2026-09-26T00:00:00Z",
        issues=(Issue(2, "Baseline item", body=f"**Depends on:** {negation}"),),
    )
    result = classify_repository(state)

    assert result.available == (2,)
    assert result.uncertainty == {}


@pytest.mark.parametrize(
    "text", ["the owner's ruling", "- see the tracking thread", "-12", "nothing but #12", "none except T004"]
)
def test_depends_on_something_unresolvable_is_still_uncertain(text: str) -> None:
    state = RepositoryState(
        repository="example/deps",
        default_branch="main",
        collected_at="2026-09-26T00:00:00Z",
        issues=(Issue(3, "Waits on a person", body=f"**Depends on:** {text}"),),
    )

    assert classify_repository(state).uncertain == (3,)
