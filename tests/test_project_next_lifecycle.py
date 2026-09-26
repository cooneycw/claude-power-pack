"""CPP relationship, Wayfinder, and spec-lifecycle extension fixtures."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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


# #1035 negative controls: each route or state is paired with the input that must
# produce the other answer.


def test_a_wayfinder_label_never_emits_a_flow_auto_route_and_an_unlabelled_issue_still_does(tmp_path: Path) -> None:
    state = _state(
        issues=[
            {"number": 876, "title": "Chart a wayfinder map: CPP resilience", "labels": ["wayfinder:map"]},
            {"number": 900, "title": "Ordinary work"},
        ]
    )
    result = project_next.recommend(state)
    wayfinder_map, payload = project_next.read_wayfinder_map(tmp_path)
    routes = project_next.planning_routes(tmp_path, state, payload)
    extensions = project_next.CppExtensions((), (), routes, (), wayfinder_map=wayfinder_map)

    assert [route.issue_number for route in routes] == [876]
    assert routes[0].artifact == "label:wayfinder:map"
    for mode in ("compact", "full"):
        rendered = project_next.render_cpp(result, state, mode, extensions)
        assert "$flow-auto 876" not in rendered
        assert "$flow-auto 900" in rendered


def test_the_map_reads_absent_only_when_it_is_absent_and_unreadable_when_it_is_malformed(tmp_path: Path) -> None:
    absent, payload = project_next.read_wayfinder_map(tmp_path)
    assert (absent.state, payload) == ("absent", None)

    map_path = tmp_path / ".claude" / "wayfinder-map.json"
    map_path.parent.mkdir(parents=True)
    map_path.write_text("{not json", encoding="utf-8")
    unreadable, payload = project_next.read_wayfinder_map(tmp_path)
    assert (unreadable.state, unreadable.path, payload) == ("unreadable", str(map_path), None)

    map_path.write_text(json.dumps({"state": "cleared", "decisions": []}), encoding="utf-8")
    read, payload = project_next.read_wayfinder_map(tmp_path)
    assert (read.state, read.detail) == ("read", "state: cleared")
    assert payload == {"state": "cleared", "decisions": []}


def test_a_worktree_that_cannot_name_its_primary_says_unreadable_not_absent(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {tmp_path / 'missing' / '.git' / 'worktrees' / 'wt'}\n", encoding="utf-8")

    observed, _ = project_next.read_wayfinder_map(worktree)

    assert observed.state == "unreadable"
    assert "primary checkout" in observed.detail


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "init.defaultBranch=main", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git to build a linked worktree")
def test_a_linked_worktree_reads_the_primary_checkouts_untracked_map(tmp_path: Path) -> None:
    primary = tmp_path / "repo"
    primary.mkdir()
    _git(primary, "init")
    _git(primary, "commit", "--allow-empty", "-m", "base")
    _git(primary, "worktree", "add", "-b", "issue-1-x", str(tmp_path / "repo-issue-1-x"))
    worktree = tmp_path / "repo-issue-1-x"

    # Genuinely absent everywhere: the worktree must say absent, having checked both.
    absent, _ = project_next.read_wayfinder_map(worktree)
    assert absent.state == "absent"
    assert str(primary / ".claude" / "wayfinder-map.json") in absent.detail

    # Untracked in the primary only - the shape a gitignored map always has.
    map_path = primary / ".claude" / "wayfinder-map.json"
    map_path.parent.mkdir()
    map_path.write_text(
        json.dumps({"state": "awaiting-decisions", "decisions": [{"decision_id": "D001", "status": "open"}]}),
        encoding="utf-8",
    )
    assert not (worktree / ".claude" / "wayfinder-map.json").exists()

    read, payload = project_next.read_wayfinder_map(worktree)
    state = _state(issues=[{"number": 7, "title": "D001 choose the identity provider"}])
    assert (read.state, read.path) == ("read", str(map_path))
    assert any(route.issue_number == 7 for route in project_next.planning_routes(worktree, state, payload))


def _native_state(*issues: dict[str, object]) -> tuple[object, list[dict[str, object]]]:
    state = _state(issues=list(issues))
    # Native rows present but carrying no edges, so every parsed reference is text-only.
    rows = [{"number": issue["number"], "blockedBy": [], "blocking": [], "subIssues": []} for issue in issues]
    return state, rows


def test_a_text_dependency_on_closed_issues_is_satisfied_not_uncertain() -> None:
    state, rows = _native_state({"number": 6, "title": "Build on the baseline", "body": "Depends on: #4, #5."})

    normalized, _ = project_next.normalize_relationships(state, rows)
    result = project_next.recommend(normalized)

    assert result.classification.available == (6,)
    assert result.classification.uncertainty == {}


def test_a_text_dependency_on_an_open_issue_stays_uncertain_and_names_it() -> None:
    state, rows = _native_state(
        {"number": 6, "title": "Build on the baseline", "body": "Depends on: #7."},
        {"number": 7, "title": "Baseline", "body": "Depends on: None"},
    )

    normalized, _ = project_next.normalize_relationships(state, rows)
    result = project_next.recommend(normalized)

    assert result.classification.uncertain == (6,)
    assert result.classification.available == (7,)
    reasons = " ".join(result.classification.uncertainty[6])
    assert "#7" in reasons
    assert "names no issue" not in reasons


def test_json_gives_a_labelled_seed_the_planning_route_not_flow_auto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = tmp_path / "state.json"
    fixture.write_text(
        json.dumps(
            {
                "repository": "example/project",
                "default_branch": "main",
                "collected_at": "2026-09-26T00:00:00Z",
                "issues": [
                    {"number": 876, "title": "Chart a map", "labels": ["wayfinder:map"]},
                    {"number": 900, "title": "Ordinary work"},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert project_next.main([str(tmp_path), "--input", str(fixture), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    commands = {candidate["issue_number"]: candidate["command"] for candidate in payload["candidates"]}

    assert "$flow-auto" not in commands[876]
    assert commands[876].startswith("/project:init")
    assert commands[900] == "$flow-auto 900"


def test_routing_one_issue_never_rewrites_a_neighbour_whose_number_it_prefixes() -> None:
    routes = (project_next.PlanningRoute(87, "label:wayfinder:map", "/project:init", "seed"),)
    text = "→ `$flow-auto 87`\n→ `$flow-auto 876`\n$flow-auto 87"

    rendered = project_next._apply_route_rendering(text, routes)

    assert "`$flow-auto 876`" in rendered
    assert "$flow-auto 87`" not in rendered
    assert rendered.count("/project:init") == 2


def test_a_permission_denied_map_path_reads_unreadable_rather_than_crashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_exists = Path.exists

    def denied(self: Path, *args: object, **kwargs: object) -> bool:
        if self.name == "wayfinder-map.json":
            raise PermissionError(13, "Permission denied", str(self))
        return real_exists(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "exists", denied)
    observed, payload = project_next.read_wayfinder_map(tmp_path)

    assert (observed.state, payload) == ("unreadable", None)
    assert "Permission denied" in observed.detail
