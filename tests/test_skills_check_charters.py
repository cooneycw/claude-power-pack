"""A `charters/` tree is never counted as a topic skill (issue #1838).

`charters/<family>/<command>/CHARTER.md` holds a slash command's charter at the
repository root. `skills-check.py` counts packages under `.claude/skills/`, so a
charter must leave that count unchanged. The paired control plants a real
package and shows the count is able to move, so the unchanged count is evidence.
"""

from __future__ import annotations

from pathlib import Path

from tests.test_skills_check import _write_skill, skills_check

CHARTER = (
    "---\ncontract: flow-auto\nsubject: .claude/commands/flow/auto.md\n---\n\nProse.\n"
)


def _count(root: Path) -> int:
    report = skills_check.check_repository(root, root / "no-managed-installs")
    assert report.ok, [finding.render(root) for finding in report.findings]
    return report.canonical_checked


def test_a_planted_charters_tree_is_not_counted_as_a_skill(tmp_path):
    _write_skill(tmp_path, "sample")
    before = _count(tmp_path)
    assert before == 1
    charter = tmp_path / "charters" / "flow" / "auto" / "CHARTER.md"
    charter.parent.mkdir(parents=True)
    charter.write_text(CHARTER)
    (tmp_path / "charters" / "README.md").write_text("# Charters\n")
    assert charter.is_file()
    assert _count(tmp_path) == before


def test_control_a_planted_skill_package_is_counted(tmp_path):
    """Negative control: the count this file relies on does move when a real
    package appears, so an unchanged count above is not a blind instrument."""
    _write_skill(tmp_path, "sample")
    before = _count(tmp_path)
    _write_skill(tmp_path, "second")
    assert _count(tmp_path) == before + 1
