from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "check-claude-md-behavior.py"
SPEC = importlib.util.spec_from_file_location("check_claude_md_behavior", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
behavior = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = behavior
SPEC.loader.exec_module(behavior)


def _write_fixture(root: Path, *, needle: str = "never output secrets", retirements: object = None) -> None:
    fixture = root / behavior.FIXTURE
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        json.dumps(
            {
                "version": behavior.FIXTURE_VERSION,
                "obligations": [{"slug": "never-output-secrets", "needle": needle}],
                "retirements": {} if retirements is None else retirements,
            }
        ),
        encoding="utf-8",
    )


def test_obligation_can_move_to_docs(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("Read docs on demand.", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "safety.md").write_text("Never output secrets in responses.", encoding="utf-8")
    _write_fixture(tmp_path)

    assert behavior.check_tree(tmp_path) == []


def test_missing_obligation_fails(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("Short routing file.", encoding="utf-8")
    _write_fixture(tmp_path)
    assert "never output secrets" not in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8").casefold()

    findings = behavior.check_tree(tmp_path)

    assert [(finding.kind, finding.detail) for finding in findings] == [
        ("missing-obligation", "never-output-secrets: expected findable text 'never output secrets'")
    ]


def test_named_retirement_allowlist_permits_deliberate_removal(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("Short routing file.", encoding="utf-8")
    _write_fixture(
        tmp_path,
        retirements={"never-output-secrets": "superseded by platform-level response redaction"},
    )
    assert "never output secrets" not in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8").casefold()

    assert behavior.check_tree(tmp_path) == []


def test_bare_retirement_without_reason_fails(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("Short routing file.", encoding="utf-8")
    _write_fixture(tmp_path, retirements={"never-output-secrets": ""})

    findings = behavior.check_tree(tmp_path)

    assert findings[0].kind == "invalid-fixture"
    assert "requires a named reason" in findings[0].detail


def test_duplicated_normative_lifecycle_policy_in_skill_fails_locality_check(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("Never output secrets.", encoding="utf-8")
    _write_fixture(tmp_path)
    skill = tmp_path / ".claude" / "commands" / "flow" / "finish.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "# Finish\n\n| Knowledge in the completed spec | Durable home |\n|---|---|\n| behavior | tests |\n",
        encoding="utf-8",
    )
    assert behavior.NORMATIVE_TABLE_MARKER in skill.read_text(encoding="utf-8")

    findings = behavior.check_tree(tmp_path)

    assert [(finding.kind, finding.detail) for finding in findings] == [
        ("duplicated-lifecycle-policy", ".claude/commands/flow/finish.md")
    ]


def test_non_boundary_skill_cannot_link_canonical_lifecycle_reference(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("Never output secrets.", encoding="utf-8")
    _write_fixture(tmp_path)
    skill = tmp_path / ".claude" / "commands" / "security" / "scan.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("See docs/agents/knowledge-lifecycle.md.\n", encoding="utf-8")
    assert skill.relative_to(tmp_path).as_posix() not in behavior.LIFECYCLE_BOUNDARY_FILES

    findings = behavior.check_tree(tmp_path)

    assert [(finding.kind, finding.detail) for finding in findings] == [
        ("non-boundary-lifecycle-pointer", ".claude/commands/security/scan.md")
    ]
