"""Regression tests for the opt-in session-open pending-retro reminder (issue #530).

`scripts/hook-pending-retro.sh` is a SessionStart hook that SURFACES pending retro
material (friction signals + uncodified learnings) and points at
`/self-improvement:retro`. It never codifies and never blocks. These tests pin:
per-class counts and the one-line format, the actionable-vs-permission-prompt
split (so the bulk census records do not read as alarm), uncodified
(`Status: proposed`) learnings counted from the sibling ledger, hard silence when
nothing is pending / the buffer is absent, and that the hook is read-only.

Since issue #622 the same hook carries a SECOND, independent advisory: the
installed-vs-checkout command drift reported by the sibling
`scripts/install-drift.sh`. The tests below drive the retro half with that half
suppressed (`CPP_HOOK_SKIP_INSTALL_DRIFT`) so the two never mask each other, and
pin the wiring of the drift half separately - including that a missing or failing
install-drift.sh leaves the hook silent and successful.

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
        env={
            "CPP_FRICTION_LOG": str(buffer),
            "PATH": os.environ.get("PATH", ""),
            # Isolate the retro half: the drift half reads the real HOME and
            # would otherwise make these assertions depend on how stale the
            # developer's own plugin install happens to be.
            "CPP_HOOK_SKIP_INSTALL_DRIFT": "1",
        },
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


# --- The install-drift advisory (issue #622) --------------------------------
# Wired through a STUB sibling: the hook resolves install-drift.sh next to its
# own realpath, so copying the hook into a tmp dir lets these tests pin the
# wiring (does the line surface? does a failure stay silent?) without depending
# on the state of the box's real plugin install, which test_install_drift.py
# already covers on hermetic trees.


def _staged_hook(tmp_path: Path, drift_body: str | None) -> Path:
    stage = tmp_path / "scripts"
    stage.mkdir(parents=True, exist_ok=True)
    hook = stage / "hook-pending-retro.sh"
    shutil.copy(HOOK, hook)
    if drift_body is not None:
        drift = stage / "install-drift.sh"
        drift.write_text(drift_body, encoding="utf-8")
        drift.chmod(0o755)
    return hook


def _run_staged(hook: Path, buffer: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(hook)],
        env={"CPP_FRICTION_LOG": str(buffer), "PATH": os.environ.get("PATH", "")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )


DRIFT_LINE = "CPP install: 15 commit(s) behind checkout - run /cpp:update"
STUB_DRIFT = f'#!/usr/bin/env bash\necho "{DRIFT_LINE}"\nexit 0\n'


def test_drift_line_surfaces_with_no_retro_material(tmp_path: Path):
    # The case that matters most: a clean box with nothing pending is exactly
    # where a week-old command surface goes unnoticed. Gating the drift line on
    # retro material would hide it there.
    hook = _staged_hook(tmp_path, STUB_DRIFT)
    r = _run_staged(hook, tmp_path / "absent.jsonl")
    assert r.returncode == 0
    assert r.stdout.strip() == DRIFT_LINE
    assert "CPP retro" not in r.stdout


def test_both_advisories_surface_together(tmp_path: Path):
    hook = _staged_hook(tmp_path, STUB_DRIFT)
    buf = tmp_path / "friction.jsonl"
    _write(buf, REC["gate"])
    out = _run_staged(hook, buf).stdout.splitlines()
    assert len(out) == 2, out
    assert out[0].startswith("CPP retro:")
    assert out[1] == DRIFT_LINE


def test_absent_install_drift_script_is_silent(tmp_path: Path):
    hook = _staged_hook(tmp_path, None)
    r = _run_staged(hook, tmp_path / "absent.jsonl")
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_failing_install_drift_never_fails_or_noises_the_session(tmp_path: Path):
    hook = _staged_hook(
        tmp_path, "#!/usr/bin/env bash\necho boom >&2\nexit 3\n"
    )
    buf = tmp_path / "friction.jsonl"
    _write(buf, REC["gate"])
    r = _run_staged(hook, buf)
    assert r.returncode == 0, "a hook that errors is worse than a hook that is silent"
    assert "boom" not in r.stdout
    assert "boom" not in r.stderr
    assert r.stdout.strip().startswith("CPP retro:")


def test_skip_env_suppresses_only_the_drift_half(tmp_path: Path):
    hook = _staged_hook(tmp_path, STUB_DRIFT)
    buf = tmp_path / "friction.jsonl"
    _write(buf, REC["gate"])
    r = subprocess.run(
        ["bash", str(hook)],
        env={
            "CPP_FRICTION_LOG": str(buf),
            "PATH": os.environ.get("PATH", ""),
            "CPP_HOOK_SKIP_INSTALL_DRIFT": "1",
        },
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert DRIFT_LINE not in r.stdout
    assert "CPP retro:" in r.stdout


def test_not_registered_in_shipped_hooks_json():
    # Opt-in integrity (the whole point): the reminder must NOT live in the
    # shipped .claude/hooks.json, which /cpp:init copies into user projects -
    # that would turn it on for everyone by default. It is registered only via
    # the user-confirmed (default N) settings.json path in /cpp:init|update.
    hooks = (ROOT / ".claude" / "hooks.json").read_text(encoding="utf-8")
    assert "hook-pending-retro" not in hooks, (
        "hook-pending-retro must stay opt-in: never in the shipped .claude/hooks.json"
    )
