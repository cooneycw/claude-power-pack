"""Regression tests for the opt-in session-open pending-retro reminder (issue #530).

`scripts/hook-pending-retro.sh` is a SessionStart hook that SURFACES pending retro
material (friction signals + uncodified learnings) and points at
`/self-improvement:retro`. It never codifies and never blocks. These tests pin:
per-class counts and the one-line format, the actionable-vs-permission-prompt
split (so the bulk census records do not read as alarm), uncodified
(`Status: proposed`) learnings counted from the sibling ledger, hard silence when
nothing is pending / the buffer is absent, and that the hook is read-only.

Pure-filesystem: the hook is driven with a `CPP_FRICTION_LOG` override, so no git
subprocess is needed and this runs in the git-less CI `validate` container (only
bash is required).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts" / "hook-pending-retro.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)

REC = {
    "gate": '{"class":"gate-failure","signal":"x"}',
    "red": '{"class":"red-output","signal":"y"}',
    "manual": '{"class":"manual-intervention","signal":"z"}',
    "census": '{"class":"permission-prompt","signal":"w"}',
}


def _run(buffer: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(HOOK)],
        env={"CPP_FRICTION_LOG": str(buffer), "PATH": os.environ.get("PATH", "")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )


def _write(path: Path, *records: str) -> None:
    path.write_text("".join(r + "\n" for r in records), encoding="utf-8")


def test_absent_buffer_is_silent(tmp_path: Path):
    r = _run(tmp_path / "does-not-exist.jsonl")
    assert r.returncode == 0
    assert r.stdout.strip() == "", "no buffer -> no output"


def test_empty_buffer_is_silent(tmp_path: Path):
    buf = tmp_path / "friction.jsonl"
    buf.write_text("", encoding="utf-8")
    r = _run(buf)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_counts_actionable_and_census_split(tmp_path: Path):
    buf = tmp_path / "friction.jsonl"
    _write(buf, REC["gate"], REC["manual"], REC["red"], REC["census"], REC["census"])
    r = _run(buf)
    assert r.returncode == 0
    out = r.stdout.strip()
    assert "3 actionable" in out, out  # gate + manual + red
    assert "2 permission-prompt" in out, out
    assert "/self-improvement:retro" in out
    # actionable is listed before the census breakdown
    assert out.index("actionable") < out.index("permission-prompt")


def test_census_only_still_surfaced(tmp_path: Path):
    buf = tmp_path / "friction.jsonl"
    _write(buf, REC["census"], REC["census"], REC["census"])
    out = _run(buf).stdout
    assert "3 permission-prompt" in out
    assert "actionable" not in out  # no actionable segment when the count is zero


def test_proposed_learnings_counted_from_sibling_ledger(tmp_path: Path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    buf = claude / "friction.jsonl"
    _write(buf, REC["red"])
    (claude / "learnings.md").write_text(
        "## a\n- Status: proposed\n\n## b\n- Status: applied\n\n## c\n- Status: proposed\n",
        encoding="utf-8",
    )
    out = _run(buf).stdout
    assert "1 actionable" in out
    assert "2 uncodified learning(s)" in out


def test_no_uncodified_clause_when_none_proposed(tmp_path: Path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    buf = claude / "friction.jsonl"
    _write(buf, REC["gate"])
    (claude / "learnings.md").write_text("## a\n- Status: applied\n", encoding="utf-8")
    out = _run(buf).stdout
    assert "1 actionable" in out
    assert "uncodified" not in out


def test_hook_is_read_only(tmp_path: Path):
    buf = tmp_path / "friction.jsonl"
    _write(buf, REC["census"])
    before = buf.read_text(encoding="utf-8")
    _run(buf)
    assert buf.read_text(encoding="utf-8") == before, "the hook must never write"


def test_not_registered_in_shipped_hooks_json():
    # Opt-in integrity (the whole point): the reminder must NOT live in the
    # shipped .claude/hooks.json, which /cpp:init copies into user projects -
    # that would turn it on for everyone by default. It is registered only via
    # the user-confirmed (default N) settings.json path in /cpp:init|update.
    hooks = (ROOT / ".claude" / "hooks.json").read_text(encoding="utf-8")
    assert "hook-pending-retro" not in hooks, (
        "hook-pending-retro must stay opt-in: never in the shipped .claude/hooks.json"
    )
