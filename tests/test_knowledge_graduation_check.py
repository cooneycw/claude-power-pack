from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "knowledge-graduation-check.py"
SPEC = importlib.util.spec_from_file_location("knowledge_graduation_check", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
graduation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = graduation
SPEC.loader.exec_module(graduation)


def _project(tmp_path: Path, *, independent_value: str = "none", state: str = "graduated") -> tuple[Path, Path]:
    spec_dir = tmp_path / ".specify" / "specs" / "feature"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text(
        """# Feature

## User Stories

### US1

**Acceptance Criteria:**
- [x] The command writes a deterministic result.
- [x] Deferred work is tracked explicitly.
""",
        encoding="utf-8",
    )
    (spec_dir / "tasks.md").write_text(
        """# Tasks

- [x] T001 Implement the command
- [x] **T002** Add regression tests
""",
        encoding="utf-8",
    )
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_feature.py").write_text("def test_value(): pass\n", encoding="utf-8")
    mapping = {
        "version": 1,
        "spec_slug": "feature",
        "state": state,
        "independent_value": independent_value,
        "acceptance_criteria": [
            {
                "criterion": "The command writes a deterministic result.",
                "durable_home": "code-tests",
                "artifacts": ["scripts/feature.py", "tests/test_feature.py"],
            },
            {
                "criterion": "Deferred work is tracked explicitly.",
                "durable_home": "issue-or-rejection",
                "artifacts": ["https://github.com/owner/repo/issues/8"],
            },
        ],
        "tasks": [
            {
                "task_id": "T001",
                "resolution": "closed-issue",
                "evidence_url": "https://github.com/owner/repo/issues/1",
            },
            {
                "task_id": "T002",
                "resolution": "closed-issue",
                "evidence_url": "https://github.com/owner/repo/issues/2",
            },
        ],
    }
    if state == "retained":
        mapping["owner"] = "platform-team"
    mapping_path = spec_dir / "graduation.json"
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    return spec_dir, mapping_path


def _run(tmp_path: Path, spec_dir: Path, mapping_path: Path) -> dict[str, str]:
    return graduation.graduate(
        tmp_path,
        spec_dir,
        mapping_path,
        "https://github.com/owner/repo/pull/123",
        "2026-08-16",
    )


def test_success_writes_ledger_accepted_by_project_next_reader(tmp_path: Path) -> None:
    spec_dir, mapping_path = _project(tmp_path)

    entry = _run(tmp_path, spec_dir, mapping_path)

    assert entry == {
        "spec_slug": "feature",
        "state": "graduated",
        "evidence_url": "https://github.com/owner/repo/pull/123",
        "recorded_at": "2026-08-16",
    }
    project_next_spec = importlib.util.spec_from_file_location(
        "project_next_for_graduation", ROOT / "scripts/project-next.py"
    )
    assert project_next_spec is not None and project_next_spec.loader is not None
    project_next = importlib.util.module_from_spec(project_next_spec)
    sys.modules[project_next_spec.name] = project_next
    project_next_spec.loader.exec_module(project_next)
    ledger, warnings = project_next._load_graduation_ledger(tmp_path)
    assert warnings == []
    assert ledger["feature"]["state"] == "graduated"
    state = project_next.RepositoryState.from_dict(
        {
            "repository": "owner/repo",
            "default_branch": "main",
            "collected_at": "2026-08-16T12:00:00Z",
            "spec_features": [
                {
                    "name": "feature",
                    "path": ".specify/specs/feature",
                    "has_spec": False,
                    "has_tasks": True,
                    "recommended_action": "create spec.md",
                }
            ],
        }
    )
    normalized = project_next.normalize_graduated_specs(tmp_path, state)
    result = project_next.recommend(normalized)
    lifecycle, lifecycle_warnings = project_next.classify_spec_lifecycle(tmp_path, normalized, result)
    assert lifecycle[0].state == "graduated"
    assert not any("feature" in warning for warning in lifecycle_warnings)
    assert "feature" not in result.backlog_tiers.pending_spec_sync


def test_unmapped_acceptance_criterion_fails_graduation(tmp_path: Path) -> None:
    spec_dir, mapping_path = _project(tmp_path)
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    mapping["acceptance_criteria"].pop()
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    assert len(mapping["acceptance_criteria"]) < len(graduation.parse_acceptance_criteria(spec_dir / "spec.md"))

    with pytest.raises(graduation.GraduationError, match="unmapped acceptance criterion: Deferred work"):
        _run(tmp_path, spec_dir, mapping_path)

    assert not (tmp_path / graduation.GRADUATION_LEDGER).exists()


def test_regulatory_contract_proposed_for_deletion_fails_graduation(tmp_path: Path) -> None:
    spec_dir, mapping_path = _project(tmp_path, independent_value="regulatory", state="graduated")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    assert mapping["independent_value"] == "regulatory" and mapping["state"] == "graduated"

    with pytest.raises(graduation.GraduationError, match="regulatory spec cannot be graduated"):
        _run(tmp_path, spec_dir, mapping_path)

    assert not (tmp_path / graduation.GRADUATION_LEDGER).exists()


def test_retained_contract_requires_and_records_named_owner(tmp_path: Path) -> None:
    spec_dir, mapping_path = _project(tmp_path, independent_value="cross-team", state="retained")

    entry = _run(tmp_path, spec_dir, mapping_path)

    assert entry["state"] == "retained"
    assert entry["owner"] == "platform-team"


def test_retained_contract_without_owner_fails_closed(tmp_path: Path) -> None:
    spec_dir, mapping_path = _project(tmp_path, independent_value="contractual", state="retained")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    del mapping["owner"]
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    assert "owner" not in mapping, "fixture must omit the retained owner"

    with pytest.raises(graduation.GraduationError, match="retained spec requires a non-empty owner"):
        _run(tmp_path, spec_dir, mapping_path)


def test_unresolved_task_fails_closed(tmp_path: Path) -> None:
    spec_dir, mapping_path = _project(tmp_path)
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    mapping["tasks"].pop()
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    assert len(mapping["tasks"]) < len(graduation.parse_tasks(spec_dir / "tasks.md"))

    with pytest.raises(graduation.GraduationError, match="unresolved task: T002"):
        _run(tmp_path, spec_dir, mapping_path)


def test_missing_mapped_artifact_fails_closed(tmp_path: Path) -> None:
    spec_dir, mapping_path = _project(tmp_path)
    missing = tmp_path / "tests" / "test_feature.py"
    missing.unlink()
    assert not missing.exists(), "fixture artifact must be absent"

    with pytest.raises(graduation.GraduationError, match="maps to missing artifact"):
        _run(tmp_path, spec_dir, mapping_path)


def test_ledger_version_constant_matches_project_next_reader() -> None:
    tree = ast.parse((ROOT / "scripts" / "project-next.py").read_text(encoding="utf-8"))
    reader_version = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "GRADUATION_LEDGER_VERSION"
            for target in node.targets
        ):
            reader_version = ast.literal_eval(node.value)
            break

    assert reader_version == graduation.GRADUATION_LEDGER_VERSION
