"""Pins for /cpp:init and /cpp:update ignoring friction capture (issue #1498).

/flow:auto's friction capture (scripts/friction-log.sh) writes into a
project's own .claude/friction.jsonl and .claude/friction/ - the same
directory CPP's own .gitignore (:288-289) already excludes. Neither /cpp:init
nor /cpp:update added those entries to a CONSUMER project's .gitignore before
this issue: /cpp:init added only settings.local.json, and /cpp:update had no
.gitignore step of its own at all.

Both blocks below are extracted directly from their command documents and run
under bash, the same pattern test_mcp_json_override.py uses for /cpp:init's
step 3c and /cpp:update's step 6b.0.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

FRICTION_LINES = (".claude/friction.jsonl", ".claude/friction/")


def _init_friction_block() -> str:
    text = (ROOT / ".claude/commands/cpp/init.md").read_text()
    section = text[text.index("Add `.claude/friction.jsonl`") :]
    start = section.index("```bash\n") + len("```bash\n")
    return section[start : section.index("\n```", start)]


def _update_friction_block() -> str:
    text = (ROOT / ".claude/commands/cpp/update.md").read_text()
    section = text[text.index("#### 6b.1: Friction Capture .gitignore") :]
    start = section.index("```bash\n") + len("```bash\n")
    return section[start : section.index("\n```", start)]


_needs_bash = pytest.mark.skipif(
    __import__("shutil").which("bash") is None, reason="needs bash"
)


def _run(block: str, tmp_path: Path) -> str:
    out = subprocess.run(
        ["bash", "-c", block], cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    return out.stdout + out.stderr


@_needs_bash
@pytest.mark.parametrize("extractor", [_init_friction_block, _update_friction_block])
def test_friction_lines_added_when_absent(tmp_path: Path, extractor) -> None:
    (tmp_path / ".gitignore").write_text("node_modules/\n")
    out = _run(extractor(), tmp_path)
    contents = (tmp_path / ".gitignore").read_text()
    for line in FRICTION_LINES:
        assert line in contents, contents
        assert f"✓ Added {line} to .gitignore" in out, out


@_needs_bash
@pytest.mark.parametrize("extractor", [_init_friction_block, _update_friction_block])
def test_friction_lines_not_duplicated_when_already_present(tmp_path: Path, extractor) -> None:
    (tmp_path / ".gitignore").write_text("\n".join(FRICTION_LINES) + "\n")
    _run(extractor(), tmp_path)
    contents = (tmp_path / ".gitignore").read_text()
    for line in FRICTION_LINES:
        assert contents.count(line) == 1, contents


@_needs_bash
@pytest.mark.parametrize("extractor", [_init_friction_block, _update_friction_block])
def test_no_gitignore_is_left_alone(tmp_path: Path, extractor) -> None:
    out = _run(extractor(), tmp_path)
    assert not (tmp_path / ".gitignore").exists()
    assert out == ""


@_needs_bash
@pytest.mark.parametrize("extractor", [_init_friction_block, _update_friction_block])
def test_one_missing_line_adds_only_that_one(tmp_path: Path, extractor) -> None:
    (tmp_path / ".gitignore").write_text(".claude/friction.jsonl\n")
    _run(extractor(), tmp_path)
    contents = (tmp_path / ".gitignore").read_text()
    assert contents.count(".claude/friction.jsonl") == 1, contents
    assert ".claude/friction/" in contents, contents


# Codex cross-model review (issue #1498): a substring match (plain `grep -qF`)
# reads a COMMENTED-OUT entry, or a LONGER neighbouring path that merely
# contains the pattern, as "already present" and skips the real line - which
# leaves friction files genuinely unignored while the step reports nothing to
# do. The fix is `grep -qxF`: a complete, literal line only.
@_needs_bash
@pytest.mark.parametrize("extractor", [_init_friction_block, _update_friction_block])
def test_a_commented_out_entry_is_not_mistaken_for_present(tmp_path: Path, extractor) -> None:
    (tmp_path / ".gitignore").write_text(
        "# .claude/friction.jsonl\n# .claude/friction/\n"
    )
    _run(extractor(), tmp_path)
    contents = (tmp_path / ".gitignore").read_text()
    for line in FRICTION_LINES:
        assert any(entry == line for entry in contents.splitlines()), contents


@_needs_bash
@pytest.mark.parametrize("extractor", [_init_friction_block, _update_friction_block])
def test_a_longer_neighbouring_path_is_not_mistaken_for_present(tmp_path: Path, extractor) -> None:
    (tmp_path / ".gitignore").write_text(
        ".claude/friction.jsonl.backup\n.claude/friction/old\n"
    )
    _run(extractor(), tmp_path)
    contents = (tmp_path / ".gitignore").read_text()
    for line in FRICTION_LINES:
        assert any(entry == line for entry in contents.splitlines()), contents
