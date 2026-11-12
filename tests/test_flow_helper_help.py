"""`--help` prints the WHOLE header of flow-start-resolve.sh (issue #1713).

It printed a hard-coded line range (`2,80p` of a 147-line header), so the help
stopped mid-header and would have gone on shrinking, relatively, with every
header edit. It now prints to the end of the header comment, the way
flow-ci-status.sh does since #1653.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")

# gate-lib.sh has the same hard-coded range, but its check runner is pinned
# byte-for-byte by a control anchor (tests/test_gate_lib.py), so it is not
# changed here; it is recorded with the other scripts that share the pattern.
CASES = [
    ("scripts/flow-start-resolve.sh", ["bash"]),
]


def _header(script: Path) -> list[str]:
    """The header comment: from line 2 to the line before the first blank line."""
    lines = script.read_text(encoding="utf-8").splitlines()
    end = next(i for i, line in enumerate(lines[1:], 1) if line == "")
    return lines[1:end]


def _help(script: Path, shell: list[str]) -> str:
    proc = subprocess.run([*shell, str(script), "--help"], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


@pytest.mark.parametrize(("rel", "shell"), CASES)
def test_help_reaches_the_last_line_of_the_header(rel, shell):
    script = ROOT / rel
    header = _header(script)
    assert len(header) > 40, f"precondition: {rel} has a long header ({len(header)} lines)"
    out = _help(script, shell)
    last = header[-1].lstrip("#").strip()
    assert last and last in out, f"--help of {rel} stops before the header's last line: {last!r}"
    assert len(out.splitlines()) >= len(header)


@pytest.mark.parametrize(("rel", "shell"), CASES)
def test_help_follows_the_header_when_it_grows(rel, shell, tmp_path):
    """The red case for a line range: add a header line and it must be printed."""
    script = ROOT / rel
    lines = script.read_text(encoding="utf-8").splitlines(keepends=True)
    end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "")
    marker = "# A-NEW-HEADER-LINE-ADDED-AT-THE-END\n"
    copy = tmp_path / script.name
    copy.write_text("".join(lines[:end] + [marker] + lines[end:]), encoding="utf-8")
    assert "A-NEW-HEADER-LINE-ADDED-AT-THE-END" in _help(copy, shell)
