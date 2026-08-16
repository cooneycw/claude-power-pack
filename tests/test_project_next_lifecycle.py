"""CPP relationship, Wayfinder, and spec-lifecycle extension fixtures."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project-next.py"
SPEC = importlib.util.spec_from_file_location("cpp_project_next", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
project_next = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = project_next
SPEC.loader.exec_module(project_next)


def _state(**overrides: object) -> object:
    data = {
        "repository": "example/project",
        "default_branch": "main",
        "collected_at": "2026-08-16T12:00:00Z",
    }
    data.update(overrides)
    return project_next.RepositoryState.from_dict(data)


def test_native_relationships_are_confirmed_and_text_only_fallback_is_uncertain() -> None:
    state = _state(
        issues=[
            {"number": 1, "title": "Native child", "body": "Blocked by #2"},
            {"number": 2, "title": "Foundation", "assignees": ["owner"]},
            {"number": 3, "title": "Text child", "body": "Depends on #2"},
        ]
    )
    rows = [
        {"number": 1, "blockedBy": [{"number": 2}], "parent": {"number": 9}},
        {"number": 2, "blocking": [{"number": 1}], "subIssues": [{"number": 1}]},
        {"number": 3, "blockedBy": [], "blocking": [], "subIssues": []},
    ]

    normalized, relationships = project_next.normalize_relationships(state, rows)
    result = project_next.recommend(normalized)

    assert result.classification.blocked == (1,)
    assert result.classification.uncertain == (3,)
    assert normalized.issues[1].assignees == ("owner",)
    assert project_next.Relationship(1, 2, "blocked_by", "github-native", "confirmed") in relationships
    assert project_next.Relationship(3, 2, "blocked_by", "documented-text", "uncertain") in relationships
    assert project_next.Relationship(1, 9, "parent", "github-native", "confirmed") in relationships
    assert project_next.Relationship(2, 1, "sub_issue", "github-native", "confirmed") in relationships


def test_active_graduated_stale_and_retained_share_one_lifecycle_decision(tmp_path: Path) -> None:
    specs = tmp_path / ".specify" / "specs"
    for slug in ("active-feature", "stale-feature", "retained-contract"):
        path = specs / slug
        path.mkdir(parents=True)
        (path / "spec.md").write_text(f"# {slug}\n", encoding="utf-8")
    ledger_path = tmp_path / ".specify" / "graduation-ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                "version": 1,
                "specs": [
                    {
                        "spec_slug": "graduated-feature",
                        "state": "graduated",
                        "evidence_url": "https://github.com/example/project/pull/10",
                        "recorded_at": "2026-08-15",
                    },
                    {
                        "spec_slug": "retained-contract",
                        "state": "retained",
                        "owner": "protocol-team",
                        "evidence_url": "https://github.com/example/project/issues/11",
                        "recorded_at": "2026-08-15",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    state = _state(
        issues=[{"number": 20, "title": "Still open"}],
        spec_features=[
            {"name": slug, "path": f".specify/specs/{slug}", "has_spec": True}
            for slug in ("active-feature", "stale-feature", "retained-contract")
        ],
        spec_tasks=[
            {
                "task_id": "T001",
                "title": "Contradictory task",
                "feature": "stale-feature",
                "source": ".specify/specs/stale-feature/tasks.md",
                "issue_numbers": [20],
                "mapping_status": "mapped",
                "mapping_state": "CLOSED",
            }
        ],
    )
    result = project_next.recommend(state)

    lifecycle, warnings = project_next.classify_spec_lifecycle(tmp_path, state, result)
    by_slug = {item.spec_slug: item for item in lifecycle}

    assert by_slug["active-feature"].state == "active"
    assert by_slug["graduated-feature"].state == "graduated"
    assert not by_slug["graduated-feature"].present
    assert by_slug["stale-feature"].state == "stale"
    assert "marked CLOSED" in by_slug["stale-feature"].reason
    assert by_slug["retained-contract"].state == "retained"
    assert by_slug["retained-contract"].owner == "protocol-team"
    assert not any("graduated-feature" in warning for warning in warnings)

    extensions = project_next.CppExtensions((), lifecycle, (), warnings)
    for mode in ("brief", "compact", "full"):
        rendered = project_next.render_cpp(result, state, mode, extensions)
        for lifecycle_state in ("active", "graduated", "stale", "retained"):
            assert lifecycle_state in rendered


def test_missing_file_warning_applies_to_active_not_graduated(tmp_path: Path) -> None:
    ledger = tmp_path / ".specify" / "graduation-ledger.json"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        json.dumps(
            {
                "version": 1,
                "specs": [
                    {
                        "spec_slug": "gone-on-purpose",
                        "state": "graduated",
                        "evidence_url": "https://github.com/example/project/pull/5",
                        "recorded_at": "2026-08-15",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    state = _state(
        spec_features=[
            {"name": "missing-active", "path": ".specify/specs/missing-active", "has_spec": False},
            {
                "name": "gone-on-purpose",
                "path": ".specify/specs/gone-on-purpose",
                "has_spec": False,
                "has_tasks": True,
                "recommended_action": "create spec.md",
            },
        ]
    )

    normalized = project_next.normalize_graduated_specs(tmp_path, state)
    result = project_next.recommend(normalized)
    _, warnings = project_next.classify_spec_lifecycle(tmp_path, normalized, result)

    assert any("missing-active" in warning for warning in warnings)
    assert not any("gone-on-purpose" in warning for warning in warnings)
    assert "gone-on-purpose" not in result.backlog_tiers.pending_spec_sync
    assert all(feature.name != "gone-on-purpose" for feature in result.spec_features)


def test_wayfinder_decision_ticket_routes_to_planning_in_every_mode(tmp_path: Path) -> None:
    map_path = tmp_path / ".claude" / "wayfinder-map.json"
    map_path.parent.mkdir(parents=True)
    map_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "state": "awaiting-decisions",
                "decisions": [{"decision_id": "D001", "status": "open"}],
            }
        ),
        encoding="utf-8",
    )
    state = _state(issues=[{"number": 7, "title": "D001 choose the identity provider", "labels": ["planning"]}])
    result = project_next.recommend(state)
    routes = project_next.planning_routes(tmp_path, state)
    extensions = project_next.CppExtensions((), (), routes, ())

    assert any(route.issue_number == 7 and route.action == "/project:init" for route in routes)
    for mode in ("brief", "compact", "full"):
        rendered = project_next.render_cpp(result, state, mode, extensions)
        assert "/project:init" in rendered
        assert "$flow-auto 7" not in rendered
        assert "never `flow:auto`" in rendered


def test_graduation_ledger_without_a_version_field_is_rejected_loudly(tmp_path: Path) -> None:
    # The ledger is a human-written, git-tracked interface #724 (T006's
    # graduation gate) is expected to write to - a missing/mismatched version
    # must be a visible warning, never a silent no-op that hides real entries.
    ledger = tmp_path / ".specify" / "graduation-ledger.json"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        json.dumps(
            {
                "specs": [
                    {
                        "spec_slug": "unversioned-entry",
                        "state": "graduated",
                        "evidence_url": "https://github.com/example/project/pull/1",
                        "recorded_at": "2026-08-15",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    ledger_data, warnings = project_next._load_graduation_ledger(tmp_path)

    assert ledger_data == {}
    assert any("version" in warning for warning in warnings)
    assert not any("unversioned-entry" in warning for warning in warnings)
