"""Behavioral tests for project-init destination routing and Wayfinder handoff."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project-init.py"

SPEC = importlib.util.spec_from_file_location("project_init_wayfinder", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
project_init = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = project_init
SPEC.loader.exec_module(project_init)

PROJECT_NAME = "destination-app"
DESTINATION = "Give support teams a reliable customer escalation console"
FOG_AUTH = "Which authentication constraints apply?"
CREATED_AT = "2026-08-16T12:00:00+00:00"
RESOLVED_AT = "2026-08-16T13:00:00+00:00"
CLEARED_AT = "2026-08-16T14:00:00+00:00"


def make_decision(
    decision_id: str,
    question: str,
    kind: str = "research",
    *,
    status: str = "open",
    blocked_by: list[str] | None = None,
    resolves: str | None = None,
    resolution: str | None = None,
    resolved_at: str | None = None,
) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "question": question,
        "kind": kind,
        "status": status,
        "blocked_by": blocked_by or [],
        "resolves": resolves,
        "resolution": resolution,
        "resolved_at": resolved_at,
    }


def create_map(
    tmp_path: Path,
    decisions: list[dict[str, Any]],
    *,
    fog: list[str] | None = None,
) -> Any:
    return project_init.create_wayfinder_map(
        PROJECT_NAME,
        DESTINATION,
        decisions,
        fog if fog is not None else [FOG_AUTH],
        ["Billing workflow"],
        approved=True,
        target_dir=tmp_path / PROJECT_NAME,
        now=CREATED_AT,
    )


def test_given_well_scoped_cli_clear_single_session_creates_no_map_or_planning_issues(
    tmp_path: Path,
) -> None:
    """Scenario 1: clear one-session work proceeds without planning artifacts."""
    target = tmp_path / "well-scoped-cli"
    assert not target.exists(), "negative fixture precondition: no project artifacts exist"

    route = project_init.classify_route("clear", "one")

    assert route == project_init.ROUTE_SCAFFOLD
    assert not project_init.default_wayfinder_map_path(target).exists()
    assert not (target / ".specify").exists()


def test_given_large_settled_application_clear_multiple_creates_spec_tasks_without_wayfinder(
    tmp_path: Path,
) -> None:
    """Scenario 2: clear multi-session work routes to spec/tasks, not decision tickets."""
    target = tmp_path / "settled-application"
    assert not target.exists(), "negative fixture precondition: no Wayfinder map exists"

    route = project_init.classify_route("clear", "multiple")

    assert route == project_init.ROUTE_SPEC_AND_TASKS
    assert route != project_init.ROUTE_OFFER_WAYFINDER
    assert not project_init.default_wayfinder_map_path(target).exists()


def test_given_large_unclear_idea_approved_wayfinder_records_awaiting_decisions(
    tmp_path: Path,
) -> None:
    """Scenario 3: approved unclear multi-session work persists a resumable map."""
    target = tmp_path / PROJECT_NAME
    map_path = project_init.default_wayfinder_map_path(target)
    assert not map_path.exists(), "negative fixture precondition: map creation starts fresh"
    assert project_init.classify_route("unclear", "multiple") == project_init.ROUTE_OFFER_WAYFINDER

    wayfinder_map = create_map(
        tmp_path,
        [make_decision("D001", "Which identity provider meets the customer's constraints?")],
    )

    assert wayfinder_map.state == "awaiting-decisions"
    persisted = json.loads(map_path.read_text(encoding="utf-8"))
    assert persisted["state"] == "awaiting-decisions"
    assert persisted["destination"] == DESTINATION
    assert persisted["fog"] == [FOG_AUTH]
    assert "frontier" not in persisted
    resumed = project_init.resume_wayfinder_map(target, project_name=PROJECT_NAME)
    assert resumed == wayfinder_map
    assert [decision.decision_id for decision in resumed.frontier] == ["D001"]


def test_given_cleared_wayfinder_map_handoff_records_active_lifecycle_and_decision_links(
    tmp_path: Path,
) -> None:
    """Scenario 4: a cleared map proposes an active spec linked to its evidence."""
    target = tmp_path / PROJECT_NAME
    map_path = project_init.default_wayfinder_map_path(target)
    wayfinder_map = create_map(
        tmp_path,
        [
            make_decision("D001", "Which identity provider satisfies the customer's constraints?"),
            make_decision(
                "D002",
                "Confirm the client's SOC2 requirement before choosing an auth provider",
                "task",
                blocked_by=["D001"],
                resolves=FOG_AUTH,
            ),
        ],
    )
    wayfinder_map = project_init.resolve_wayfinder_decision(
        wayfinder_map,
        "D001",
        "Use the customer's existing enterprise identity provider.",
        now=RESOLVED_AT,
    )
    wayfinder_map = project_init.resolve_wayfinder_decision(
        wayfinder_map,
        "D002",
        "SOC2 evidence is required before launch.",
        now=RESOLVED_AT,
    )
    assert all(decision.status == "resolved" for decision in wayfinder_map.decisions)

    cleared = project_init.mark_wayfinder_map_cleared(wayfinder_map, now=CLEARED_AT)
    project_init.save_wayfinder_map(cleared, map_path)
    proposed = project_init.clear_map(cleared, spec_name="customer-escalation-console")

    assert cleared.state == "cleared"
    assert project_init.resume_wayfinder_map(target, project_name=PROJECT_NAME) == cleared
    assert proposed.path == ".specify/specs/customer-escalation-console/spec.md"
    assert "lifecycle: active" in proposed.content
    assert "transitional: true" in proposed.content
    assert 'originating_map: ".claude/wayfinder-map.json"' in proposed.content
    assert cleared.fingerprint in proposed.content
    assert "D001" in proposed.content and "D002" in proposed.content
    assert "Use the customer's existing enterprise identity provider." in proposed.content
    assert "SOC2 evidence is required before launch." in proposed.content
    assert "lifecycle: graduated" not in proposed.content
    assert "lifecycle: stale" not in proposed.content
    assert "lifecycle: retained" not in proposed.content


@pytest.mark.parametrize(
    ("clarity", "session_count", "expected"),
    [
        ("clear", "one", "scaffold"),
        ("clear", "multiple", "spec-and-implementation-tasks"),
        ("unclear", "one", "clarify-and-reclassify"),
        ("unclear", "multiple", "offer-wayfinder"),
    ],
)
def test_route_classifier_pins_all_four_truth_table_rows(
    clarity: str,
    session_count: str,
    expected: str,
) -> None:
    assert project_init.classify_route(clarity, session_count) == expected


def test_wayfinder_opening_check_with_no_fog_skips_map_and_routes_to_spec(tmp_path: Path) -> None:
    target = tmp_path / PROJECT_NAME
    map_path = project_init.default_wayfinder_map_path(target)
    fog: list[str] = []
    assert not fog, "negative fixture precondition: opening inventory contains no fog"
    assert not map_path.exists(), "negative fixture precondition: no map exists before routing"

    route = project_init.classify_route_with_fog("unclear", "multiple", fog)

    assert route == project_init.ROUTE_SPEC_AND_TASKS
    assert not map_path.exists()


def test_map_creation_without_explicit_approval_is_refused_before_persistence(tmp_path: Path) -> None:
    target = tmp_path / PROJECT_NAME
    map_path = project_init.default_wayfinder_map_path(target)
    approved = False
    assert approved is False, "negative fixture precondition: approval is absent"
    assert not map_path.exists(), "negative fixture precondition: map does not already exist"

    with pytest.raises(project_init.WayfinderValidationError, match="approved=True"):
        project_init.create_wayfinder_map(
            PROJECT_NAME,
            DESTINATION,
            [make_decision("D001", "Which identity provider should the product use?")],
            [FOG_AUTH],
            approved=approved,
            target_dir=target,
        )

    assert not map_path.exists()


def test_map_creation_with_no_fog_is_refused_in_favor_of_escape_route(tmp_path: Path) -> None:
    target = tmp_path / PROJECT_NAME
    map_path = project_init.default_wayfinder_map_path(target)
    fog: list[str] = []
    assert not fog, "negative fixture precondition: no fog exists to justify a map"
    assert not map_path.exists(), "negative fixture precondition: no map exists"

    with pytest.raises(project_init.WayfinderValidationError, match="no-fog route"):
        project_init.create_wayfinder_map(
            PROJECT_NAME,
            DESTINATION,
            [make_decision("D001", "Which identity provider should the product use?")],
            fog,
            approved=True,
            target_dir=target,
        )

    assert not map_path.exists()


def test_frontier_is_computed_from_open_questions_and_unresolved_blockers(tmp_path: Path) -> None:
    wayfinder_map = create_map(
        tmp_path,
        [
            make_decision("D001", "Which identity provider should the product use?"),
            make_decision(
                "D002",
                "How should tenant identity map to the selected provider?",
                blocked_by=["D001"],
            ),
            make_decision(
                "D003",
                "What audit evidence must the authentication path retain?",
                blocked_by=["D002"],
            ),
        ],
    )

    assert [decision.decision_id for decision in wayfinder_map.frontier] == ["D001"]
    assert "frontier" not in wayfinder_map.to_dict()

    after_first = project_init.resolve_wayfinder_decision(
        wayfinder_map,
        "D001",
        "Use the enterprise identity provider.",
        now=RESOLVED_AT,
    )
    assert [decision.decision_id for decision in after_first.frontier] == ["D002"]


def test_dangling_blocked_by_reference_is_refused(tmp_path: Path) -> None:
    missing = "D999"
    decisions = [
        make_decision(
            "D001",
            "Which identity provider should the product use?",
            blocked_by=[missing],
        )
    ]
    assert missing not in {decision["decision_id"] for decision in decisions}, (
        "negative fixture precondition: blocker reference is dangling"
    )

    with pytest.raises(project_init.WayfinderValidationError, match="dangling blocked_by"):
        create_map(tmp_path, decisions)


def test_task_kind_without_resolves_target_is_refused(tmp_path: Path) -> None:
    decision = make_decision(
        "D001",
        "Confirm the client's SOC2 requirement before choosing an auth provider",
        "task",
    )
    assert decision["kind"] == "task" and decision["resolves"] is None, (
        "negative fixture precondition: task has no resolves target"
    )

    with pytest.raises(project_init.WayfinderValidationError, match="requires a resolves target"):
        create_map(tmp_path, [decision])


def test_task_kind_with_dangling_resolves_target_is_refused(tmp_path: Path) -> None:
    missing = "Unknown fog"
    decision = make_decision(
        "D001",
        "Confirm the client's SOC2 requirement before choosing an auth provider",
        "task",
        resolves=missing,
    )
    assert missing != FOG_AUTH, "negative fixture precondition: resolves target is not known fog"
    assert missing != decision["decision_id"], (
        "negative fixture precondition: resolves target is not a known decision"
    )

    with pytest.raises(project_init.WayfinderValidationError, match="dangling resolves"):
        create_map(tmp_path, [decision])


def test_mislabeled_task_build_login_page_without_resolves_is_refused(tmp_path: Path) -> None:
    decision = make_decision("D001", "Build the login page", "task")
    question = str(decision["question"])
    assert question.lower().startswith("build ") and "?" not in question, (
        "negative fixture precondition: item has the named build-X shape"
    )
    assert decision["resolves"] is None, (
        "negative fixture precondition: mislabeled task also lacks a resolves target"
    )

    with pytest.raises(project_init.WayfinderValidationError, match="implementation imperative"):
        create_map(tmp_path, [decision])


def test_mislabeled_task_build_login_page_with_resolves_is_still_refused(tmp_path: Path) -> None:
    decision = make_decision("D001", "Build the login page", "task", resolves=FOG_AUTH)
    question = str(decision["question"])
    assert question.lower().startswith("build ") and "?" not in question, (
        "negative fixture precondition: item has the named build-X shape"
    )
    assert decision["resolves"] == FOG_AUTH, (
        "negative fixture precondition: referential axis is valid"
    )

    with pytest.raises(project_init.WayfinderValidationError, match="implementation imperative"):
        create_map(tmp_path, [decision])


def test_build_x_content_is_refused_regardless_of_non_task_kind(tmp_path: Path) -> None:
    decision = make_decision("D001", "Implement the identity provider", "research")
    question = str(decision["question"])
    assert decision["kind"] != "task", "negative fixture precondition: item is not task-kind"
    assert question.lower().startswith("implement ") and "?" not in question, (
        "negative fixture precondition: item is an implementation imperative"
    )

    with pytest.raises(project_init.WayfinderValidationError, match="implementation imperative"):
        create_map(tmp_path, [decision])


def test_genuine_decision_blocking_task_with_named_fog_target_is_accepted(tmp_path: Path) -> None:
    decision = make_decision(
        "D001",
        "Confirm the client's SOC2 requirement before choosing an auth provider",
        "task",
        resolves=FOG_AUTH,
    )
    assert decision["kind"] == "task" and decision["resolves"] == FOG_AUTH
    assert FOG_AUTH in [FOG_AUTH], "positive fixture precondition: resolves target is known fog"

    wayfinder_map = create_map(tmp_path, [decision])

    assert wayfinder_map.decisions[0].kind == "task"
    assert wayfinder_map.decisions[0].resolves == FOG_AUTH


def test_interrogative_build_word_question_is_accepted(tmp_path: Path) -> None:
    question = "Should we build or buy the authentication adapter?"
    assert question.startswith("Should") and "?" in question

    wayfinder_map = create_map(tmp_path, [make_decision("D001", question, "prototype")])

    assert wayfinder_map.decisions[0].question == question


def test_resume_refuses_schema_version_mismatch_loudly_and_distinctly(tmp_path: Path) -> None:
    target = tmp_path / PROJECT_NAME
    create_map(tmp_path, [make_decision("D001", "Which identity provider should the product use?")])
    map_path = project_init.default_wayfinder_map_path(target)
    raw = json.loads(map_path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == project_init.WAYFINDER_SCHEMA_VERSION, (
        "negative fixture precondition: persisted schema initially matches"
    )
    raw["schema_version"] = project_init.WAYFINDER_SCHEMA_VERSION + 1
    map_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(project_init.WayfinderStateError) as caught:
        project_init.resume_wayfinder_map(target, project_name=PROJECT_NAME)

    assert "schema_version mismatch" in str(caught.value)
    assert "fingerprint mismatch" not in str(caught.value)


def test_resume_refuses_fingerprint_mismatch_loudly_and_distinctly(tmp_path: Path) -> None:
    target = tmp_path / PROJECT_NAME
    create_map(tmp_path, [make_decision("D001", "Which identity provider should the product use?")])
    map_path = project_init.default_wayfinder_map_path(target)
    raw = json.loads(map_path.read_text(encoding="utf-8"))
    assert raw["fingerprint"], "negative fixture precondition: persisted fingerprint exists"
    assert raw["schema_version"] == project_init.WAYFINDER_SCHEMA_VERSION
    raw["fingerprint"] = "wrong-fingerprint"
    map_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(project_init.WayfinderStateError) as caught:
        project_init.resume_wayfinder_map(target, project_name=PROJECT_NAME)

    assert "fingerprint mismatch" in str(caught.value)
    assert "schema_version mismatch" not in str(caught.value)


def test_resume_with_different_destination_refuses_immutable_origin_fingerprint(tmp_path: Path) -> None:
    target = tmp_path / PROJECT_NAME
    create_map(tmp_path, [make_decision("D001", "Which identity provider should the product use?")])
    changed_destination = "A materially different destination"
    assert changed_destination != DESTINATION, (
        "negative fixture precondition: caller changed the immutable destination"
    )

    with pytest.raises(project_init.WayfinderStateError, match="fingerprint mismatch"):
        project_init.resume_wayfinder_map(
            target,
            project_name=PROJECT_NAME,
            destination=changed_destination,
        )


def test_clear_map_refuses_while_any_decision_is_unresolved(tmp_path: Path) -> None:
    wayfinder_map = create_map(
        tmp_path,
        [make_decision("D001", "Which identity provider should the product use?")],
    )
    assert any(decision.status != "resolved" for decision in wayfinder_map.decisions), (
        "negative fixture precondition: at least one decision is unresolved"
    )

    with pytest.raises(project_init.WayfinderStateError, match="remain unresolved"):
        project_init.clear_map(wayfinder_map)


def test_resolved_map_handoff_is_deterministic_and_contains_no_production_command(
    tmp_path: Path,
) -> None:
    wayfinder_map = create_map(
        tmp_path,
        [make_decision("D001", "Which identity provider should the product use?")],
    )
    resolved = project_init.resolve_wayfinder_decision(
        wayfinder_map,
        "D001",
        "Use the existing enterprise identity provider.",
        now=RESOLVED_AT,
    )
    cleared = project_init.mark_wayfinder_map_cleared(resolved, now=CLEARED_AT)

    first = project_init.clear_map(cleared)
    second = project_init.clear_map(cleared)

    assert first == second
    assert isinstance(first, project_init.PlannedWrite)
    assert "gh issue create" not in first.content
    assert "gh pr create" not in first.content
    assert "flow:auto" not in first.content

