"""`/flow:finish`'s manual security scan must PASS or stop (issue #1760).

When the finish runner was unavailable, the document told the reader to run
the scan from `${HOME}/Projects/claude-power-pack` and, "if `lib/security` is
not available, skip this step (warn the user)". Where the checkout lives
elsewhere that command exits 2, so the scan was skipped before a commit and PR.

These tests RUN the document's own bash block. `uv` is a stub on PATH that
records its arguments and answers as told; the real scanner is not run, and
"the agent stops when the block exits non-zero" is not covered.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FINISH = REPO / ".claude" / "commands" / "flow" / "finish.md"
HELP = REPO / ".claude" / "commands" / "flow" / "help.md"
STEP = "### Step 2b: Run Security Quick Scan"
LOCATIONS = ("Projects/claude-power-pack", ".claude-power-pack")
#: The document's own list of places. The harness runs the block with `/opt`
#: pointed at a directory it owns, so a real `/opt/claude-power-pack` on the
#: host cannot answer for the fixture (counter-model review, #1760).
LOOP = "for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do"
FIXTURE_LOOP = 'for dir in ~/Projects/claude-power-pack "$FIXTURE_OPT" ~/.claude-power-pack; do'
OPT = "opt"  # `cpp_at=OPT` puts the checkout at the fixture-owned /opt stand-in

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")

UV_STUB = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$STUB_LOG"
[ -n "${STUB_GATE_VERDICT:-}" ] && echo "SECURITY_GATE: flow_finish $STUB_GATE_VERDICT (stub)"
exit "${STUB_GATE_EXIT:-0}"
"""


def _section() -> str:
    text = FINISH.read_text(encoding="utf-8")
    start = text.index(STEP)
    return text[start : text.index("\n### ", start + 1)]


def _block() -> str:
    found = re.findall(r"```bash\n(.*?)```", _section(), re.DOTALL)
    blocks = [b for b in found if "lib.security gate flow_finish" in b]
    assert len(blocks) == 1, "expected exactly one scan block in Step 2b"
    return blocks[0].replace(LOOP, FIXTURE_LOOP)


def _run(tmp_path: Path, *, cpp_at: str | None, gate_exit: int = 0, verdict: str | None = "PASS"):
    home, bin_dir, project = tmp_path / "home", tmp_path / "bin", tmp_path / "project"
    for directory in (home, bin_dir, project):
        directory.mkdir()
    fixture_opt = tmp_path / "fixture-opt" / "claude-power-pack"
    if cpp_at is not None:
        checkout = fixture_opt if cpp_at == OPT else home / cpp_at
        (checkout / "lib" / "security").mkdir(parents=True)
        (checkout / "lib" / "security" / "__init__.py").write_text("", encoding="utf-8")
    else:
        for place in (home / LOCATIONS[0], fixture_opt, home / LOCATIONS[1]):
            assert not place.exists(), "negative-fixture precondition: no checkout at any place the block looks"
    stub = bin_dir / "uv"
    stub.write_text(UV_STUB, encoding="utf-8")
    stub.chmod(0o755)
    log = tmp_path / "uv.log"
    env = {
        **os.environ,
        "HOME": str(home),
        "FIXTURE_OPT": str(fixture_opt),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "STUB_LOG": str(log),
        "STUB_GATE_EXIT": str(gate_exit),
        "STUB_GATE_VERDICT": verdict or "",
    }
    ran = subprocess.run(
        ["bash", "-c", _block() + "\necho REACHED-THE-NEXT-STEP\n"],
        cwd=project, env=env, capture_output=True, text=True, check=False,
    )
    calls = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
    return ran, calls


def test_with_no_checkout_the_scan_cannot_run_and_the_flow_stops(tmp_path: Path) -> None:
    ran, calls = _run(tmp_path, cpp_at=None)
    assert calls == [], "no scanner exists, so nothing may be called"
    assert ran.returncode != 0
    assert "REACHED-THE-NEXT-STEP" not in ran.stdout
    assert ran.stderr.startswith("STOP: no scanner in "), ran.stderr
    for location in ("~/Projects/claude-power-pack", "/opt/claude-power-pack", "~/.claude-power-pack"):
        assert location in ran.stderr, f"the stop message does not name {location}"


@pytest.mark.parametrize("cpp_at", [*LOCATIONS, OPT])
def test_a_passing_scan_runs_from_wherever_the_checkout_is_and_proceeds(tmp_path: Path, cpp_at: str) -> None:
    ran, calls = _run(tmp_path, cpp_at=cpp_at)
    assert ran.returncode == 0, ran.stderr
    assert "REACHED-THE-NEXT-STEP" in ran.stdout
    assert "SECURITY_GATE: flow_finish PASS" in ran.stdout, "the scan's own output must still be shown"
    where = "fixture-opt/claude-power-pack" if cpp_at == OPT else cpp_at
    assert len(calls) == 1 and f"/{where} " in calls[0] + " ", calls
    assert "lib.security gate flow_finish" in calls[0]


@pytest.mark.parametrize(
    ("gate_exit", "verdict"),
    [(1, "FAIL"), (0, None), (0, "FAIL"), (2, "UNKNOWN"), (2, None)],
)
def test_only_exit_0_WITH_the_pass_line_proceeds(tmp_path: Path, gate_exit: int, verdict: str | None) -> None:
    ran, calls = _run(tmp_path, cpp_at=LOCATIONS[0], gate_exit=gate_exit, verdict=verdict)
    assert len(calls) == 1
    assert ran.returncode != 0
    assert "REACHED-THE-NEXT-STEP" not in ran.stdout
    assert "STOP: scan did not pass" in ran.stderr


def test_neither_document_tells_the_reader_to_skip_the_scan() -> None:
    section = _section()
    assert "skip this step (warn the user)" not in section
    assert "${HOME}/Projects/claude-power-pack" not in section
    assert "Never skip it" in section
    policy = HELP.read_text(encoding="utf-8")
    assert "the gate is skipped" not in policy
    assert "the scan is never skipped" in policy


def test_the_block_looks_in_the_three_known_places_and_the_harness_owns_opt() -> None:
    """The isolation above only works while the block spells its search this
    way; if the document changes the loop, this says so instead of letting a
    real `/opt/claude-power-pack` on the host answer for the fixture."""
    found = re.findall(r"```bash\n(.*?)```", _section(), re.DOTALL)
    raw = [b for b in found if "lib.security gate flow_finish" in b]
    assert len(raw) == 1 and raw[0].count(LOOP) == 1
    assert "/opt/claude-power-pack;" not in _block() and '"$FIXTURE_OPT"' in _block()
