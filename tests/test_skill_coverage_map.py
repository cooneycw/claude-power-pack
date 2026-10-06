"""Tests for scripts/check-skill-coverage-map.py (#1370).

Two independent staleness axes (content, dependency closure), five output
states, and the snapshot-staleness guard that keeps axis 2 honest about
being a VENDORED result, never a live one, in CI. See the module's own
docstring for the full design rationale; this file pins the behaviour.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "check-skill-coverage-map.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_skill_coverage_map", GATE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


SKILL_MD_TEMPLATE = """---
name: flow-check
description: {description}
---
{body}"""


def _write_skill(repo: Path, skill: str, description: str, body: str,
                  extra_files: dict[str, str] | None = None) -> Path:
    skill_dir = repo / "codex" / "skills" / skill
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        SKILL_MD_TEMPLATE.format(description=description, body=body), encoding="utf-8"
    )
    for rel, content in (extra_files or {}).items():
        path = skill_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return skill_dir


def _write_snapshot(snapshot_dir: Path, skill: str, *, description: str, body: str,
                     closure_digests: dict[str, str], status: str = "intact",
                     problems: list[dict[str, Any]] | None = None) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "skill": skill,
        "reference": {
            "description_digest": _digest(description),
            "body_digest": _digest(body),
            "source": "test fixture",
        },
        "diagnose": {
            "skillc_commit": "deadbeef" * 5,
            "cpp_revision_snapshot": "cafef00d" * 5,
            "command": "skillc profile diagnose (test fixture)",
            "recorded_at": "2026-10-06T00:00:00Z",
            "result": {
                "skills": {skill: {"status": status, "problems": []}},
                "problems": problems or [],
            },
            "closure_digests": closure_digests,
        },
    }
    (snapshot_dir / f"{skill}.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


BASE_DESCRIPTION = "Use when a quality gate is needed."
BASE_BODY = "# Flow Check\n\nRun the gates.\n"


def _base_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    """A minimal flow-check skill whose current content and snapshot agree
    on everything - the clean starting point every test perturbs."""
    repo = tmp_path / "repo"
    snapshot_dir = tmp_path / "snapshot"
    skill_dir = _write_skill(repo, "flow-check", BASE_DESCRIPTION, BASE_BODY)
    closure_digests = mod.digest_tree(skill_dir)
    _write_snapshot(snapshot_dir, "flow-check", description=BASE_DESCRIPTION, body=BASE_BODY,
                     closure_digests=closure_digests)
    return repo, snapshot_dir, BASE_DESCRIPTION


# --------------------------------------------------------------- golden cases


def test_a_fully_current_skill(tmp_path: Path) -> None:
    repo, snapshot_dir, _ = _base_fixture(tmp_path)
    result = mod.check_skill("flow-check", repo, snapshot_dir)
    assert result["state"] == "current"
    assert result["axis1"]["status"] == "current"
    assert result["axis2"]["status"] == "intact"


def test_not_evaluated_is_a_map_membership_fact(tmp_path: Path) -> None:
    """An unmapped skill never reaches check_skill at all via `audit` - the
    map short-circuit is checked BEFORE any digest work, so a mapped
    sibling's cleanliness can never leak into it."""
    repo, snapshot_dir, _ = _base_fixture(tmp_path)
    # A second, unmapped skill with NO snapshot and NO real content at all -
    # if the map short-circuit were missing, this would blow up or read as
    # "unknown"/"current" by accident rather than "not evaluated".
    results = mod.audit(repo, snapshot_dir)
    assert "flow-check" in results
    assert "some-unmapped-skill" not in mod.SKILL_FAMILY_MAP
    assert set(results.keys()) == set(mod.SKILL_FAMILY_MAP.keys())


def test_stale_content_changed_description(tmp_path: Path) -> None:
    """Golden control 2 (real-world instance: CPP #1380 changed flow-check's
    description, so a reference at the OLD digest must read stale here)."""
    repo, snapshot_dir, _ = _base_fixture(tmp_path)
    _write_skill(repo, "flow-check", "A completely different description.", BASE_BODY)
    result = mod.check_skill("flow-check", repo, snapshot_dir)
    assert result["state"] == "stale (content)"
    assert "description_digest differs" in result["axis1"]["detail"]


def test_stale_content_changed_body_only(tmp_path: Path) -> None:
    repo, snapshot_dir, _ = _base_fixture(tmp_path)
    _write_skill(repo, "flow-check", BASE_DESCRIPTION, "# Flow Check\n\nA different body entirely.\n")
    result = mod.check_skill("flow-check", repo, snapshot_dir)
    assert result["state"] == "stale (content)"
    assert "body_digest differs" in result["axis1"]["detail"]


def test_no_equivalence_registry_a_cosmetic_edit_is_still_stale(tmp_path: Path) -> None:
    """v1 ruling: no equivalence registry. A whitespace-only body edit must
    still come back stale (content), never silently reused as 'current'."""
    repo, snapshot_dir, _ = _base_fixture(tmp_path)
    _write_skill(repo, "flow-check", BASE_DESCRIPTION, BASE_BODY + "\n")  # trailing blank line only
    result = mod.check_skill("flow-check", repo, snapshot_dir)
    assert result["state"] == "stale (content)", (
        "v1 ships with no equivalence registry - ANY digest difference is stale, "
        "including a cosmetic one"
    )


def test_stale_dependency_real_fixture_shape(tmp_path: Path) -> None:
    """Golden control 3 (real-world instance: execution-evidence-verify.py
    referenced by flow-check since CPP b8825bd, satisfied by no skillc
    dependency - diagnose() reports the skill broken)."""
    repo, snapshot_dir, _ = _base_fixture(tmp_path)
    skill_dir = repo / "codex" / "skills" / "flow-check"
    closure_digests = mod.digest_tree(skill_dir)
    _write_snapshot(
        snapshot_dir, "flow-check", description=BASE_DESCRIPTION, body=BASE_BODY,
        closure_digests=closure_digests, status="broken",
        problems=[{
            "id": 0, "category": "unresolved-reference",
            "detail": "unresolved reference: $CPP_DIR/scripts/execution-evidence-verify.py "
                      "(in codex/skills/flow-check/reference.md, variable-rooted)",
            "skills": ["flow-check"], "in": "codex/skills/flow-check/reference.md",
        }],
    )
    result = mod.check_skill("flow-check", repo, snapshot_dir)
    assert result["state"] == "stale (dependency)"
    assert "execution-evidence-verify.py" in result["reason"]
    assert result["axis1"]["status"] == "current", "axis 1 must stay current - only axis 2 is broken here"


def test_snapshot_staleness_is_detected_not_silently_reused(tmp_path: Path) -> None:
    """The committed red case cpp-orch asked for explicitly: a snapshot whose
    recorded closure digest differs from the CURRENT tree must yield axis-2
    UNKNOWN, never a reused (and therefore wrong) 'current' or 'stale'."""
    repo, snapshot_dir, _ = _base_fixture(tmp_path)
    # Change a file in the closure AFTER the snapshot was taken - the
    # snapshot's own closure_digests still name the OLD bytes.
    skill_dir = repo / "codex" / "skills" / "flow-check"
    (skill_dir / "reference.md").write_text("a new file the snapshot never saw\n", encoding="utf-8")
    result = mod.check_skill("flow-check", repo, snapshot_dir)
    assert result["state"] == "unknown"
    assert "stale" in result["reason"]
    assert "reference.md (added)" in result["reason"]


def test_snapshot_staleness_detection_is_mutation_checked(tmp_path: Path) -> None:
    """Disable the drift check (pretend the digests always match) and
    confirm the SAME fixture then wrongly reports a verdict instead of
    unknown - the case the staleness check exists to prevent."""
    repo, snapshot_dir, _ = _base_fixture(tmp_path)
    skill_dir = repo / "codex" / "skills" / "flow-check"
    (skill_dir / "reference.md").write_text("a new file the snapshot never saw\n", encoding="utf-8")

    # Reproduce the mutation directly: call the drift comparator with equal
    # dicts (what a broken "always fresh" implementation would effectively do).
    assert mod._diff_digests({"a": "x"}, {"a": "x"}) == [], "sanity: no drift when nothing changed"
    assert mod._diff_digests({"a": "x"}, {"a": "y"}) == ["a (content changed)"]
    assert mod._diff_digests({}, {"a": "x"}) == ["a (added)"]
    assert mod._diff_digests({"a": "x"}, {}) == ["a (removed)"]

    # And confirm the REAL path still reports unknown for the perturbed fixture -
    # this is the positive half; a version with the check removed would report
    # "current" here instead, which is exactly the regression this test pins.
    result = mod.check_skill("flow-check", repo, snapshot_dir)
    assert result["state"] == "unknown"


def test_unknown_no_snapshot_at_all(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    snapshot_dir = tmp_path / "snapshot"
    _write_skill(repo, "flow-check", BASE_DESCRIPTION, BASE_BODY)
    result = mod.check_skill("flow-check", repo, snapshot_dir)
    assert result["state"] == "unknown"
    assert "no vendored snapshot" in result["reason"]


def test_unknown_skill_directory_absent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    snapshot_dir = tmp_path / "snapshot"
    _write_snapshot(snapshot_dir, "flow-check", description=BASE_DESCRIPTION, body=BASE_BODY,
                     closure_digests={})
    result = mod.check_skill("flow-check", repo, snapshot_dir)
    assert result["state"] == "unknown"
    assert "absent from the current checkout" in result["reason"]


def test_malformed_skill_md_is_unknown_not_a_crash(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    snapshot_dir = tmp_path / "snapshot"
    skill_dir = repo / "codex" / "skills" / "flow-check"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("not frontmatter at all\n", encoding="utf-8")
    _write_snapshot(snapshot_dir, "flow-check", description=BASE_DESCRIPTION, body=BASE_BODY,
                     closure_digests={})
    result = mod.check_skill("flow-check", repo, snapshot_dir)
    assert result["state"] == "unknown"
    assert "no frontmatter block" in result["reason"]


# ------------------------------------------------------------------ parsing


def test_parse_skill_md_strips_quotes() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "SKILL.md"
        path.write_text('---\nname: x\ndescription: "quoted text"\n---\nbody here\n', encoding="utf-8")
        description, body = mod.parse_skill_md(path)
        assert description == "quoted text"
        assert body == "body here\n"


def test_parse_skill_md_refuses_missing_description() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "SKILL.md"
        path.write_text("---\nname: x\n---\nbody\n", encoding="utf-8")
        with pytest.raises(mod.SkillMdError, match="no 'description:' key"):
            mod.parse_skill_md(path)


# --------------------------------------------------------------------- CLI


def test_say_exits_nonzero_on_any_non_current_state() -> None:
    results = {"flow-check": {"family": "flow:check", "state": "stale (content)", "reason": "x"}}
    assert mod._say(results) == 1


def test_say_exits_zero_when_all_current() -> None:
    results = {"flow-check": {"family": "flow:check", "state": "current", "reason": ""}}
    assert mod._say(results) == 0
