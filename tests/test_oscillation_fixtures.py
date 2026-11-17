"""The committed check-oscillation control cases are NUL-free UTF-8 (#1860).

Kept OUT of tests/test_oscillation_control.py on purpose: that module skips
whole when git is absent from the fixture PATH, which is the CI image, and this
check reads two committed files and needs no git at all. Inside that module it
would be inert in exactly the place the cases are consumed.

Why the property matters: GitHub GraphQL `Blob.text`, the only file transport
on a network that blocks git smart-HTTP, returns a NUL-bearing file as text
with each NUL rewritten to the literal `^@`. The control would then read input
CI never saw, with no error anywhere.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "controls" / "check-oscillation" / "cases"


def _logs() -> list[Path]:
    found = sorted(CASES.glob("*/history.log"))
    # Precondition: an empty glob would make the test below pass vacuously.
    assert len(found) >= 2, f"expected the BAD and GOOD captures under {CASES}, found {found}"
    return found


@pytest.mark.parametrize("log", _logs(), ids=lambda p: p.parent.name)
def test_committed_case_is_NUL_free_utf8(log: Path) -> None:
    raw = log.read_bytes()
    assert b"\x00" not in raw, f"{log.relative_to(ROOT)} carries a NUL byte"
    raw.decode("utf-8")


def _gate():
    spec = importlib.util.spec_from_file_location(
        "check_oscillation_fx", ROOT / "scripts" / "check-oscillation.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("sep", ["\v", "\f", "\x1c", "\x1e", "\x85", "\u2028"])
def test_a_diff_line_cannot_impersonate_a_commit_header(sep: str) -> None:
    """A printable marker is unambiguous only on git's own LF boundaries (#1860).

    `str.splitlines()` also breaks on VT, FF, the C0 separators, NEL and the
    Unicode separators. A committed line holding one of those and then the
    marker text became a fake header that reset the current file and dropped
    the reversal after it. The NUL format was immune, because a NUL-bearing file
    is binary to git and never reaches a text hunk. Parser-level, so no git.
    """
    gate = _gate()
    bad = (ROOT / "controls/check-oscillation/cases/bad-reversed/history.log").read_text(encoding="utf-8")
    injected = f"+note{sep}{gate.COMMIT_MARKER}{'0' * 40} fake\n+timeout = 60\n"
    assert "+timeout = 60\n" in bad, "the BAD case no longer has the line this injects before"
    poisoned = bad.replace("+timeout = 60\n", injected, 1)
    assert poisoned != bad, "precondition: the injection did not apply"
    clean, _ = gate.parse_log(bad)
    moves, _ = gate.parse_log(poisoned)
    assert gate.find_oscillations(gate.parse_log(bad)[0], gate.DEFAULT_WINDOW), "precondition: BAD case reports"
    assert [(m.path, m.key, m.before, m.after) for m in moves] == \
           [(m.path, m.key, m.before, m.after) for m in clean], f"separator {sep!r} split a diff line"


def test_a_lone_CR_cannot_impersonate_a_header_through_the_CLI(  # binary-guard: allow --from-log never runs git
    tmp_path: Path,
) -> None:
    """The pass-2 counter-model finding on #1860, through the real --from-log path.

    A parser-level test cannot see this: `Path.read_text()` converts a lone CR
    into LF BEFORE the parser runs, so `+note\\rOSCILLATION-COMMIT ...` became a
    fake header on the way in and the BAD case reported `none`, exit 0.
    """
    gate = _gate()
    bad = (ROOT / "controls/check-oscillation/cases/bad-reversed/history.log").read_bytes()
    injected = b"+note\r" + gate.COMMIT_MARKER.encode() + b"0" * 40 + b" fake\n+timeout = 60\n"
    poisoned = bad.replace(b"+timeout = 60\n", injected, 1)
    assert poisoned != bad and b"\r" + gate.COMMIT_MARKER.encode() in poisoned, "precondition: no lone CR injected"
    log = tmp_path / "poisoned.log"
    log.write_bytes(poisoned)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-oscillation.py"), "--from-log", str(log), "--exit-on-finding"],
        capture_output=True, text=True,
    )
    assert "OSCILLATION_FINDING: knob.conf:timeout" in proc.stdout, proc.stdout
    assert "OSCILLATION_COMMITS: 3" in proc.stdout, f"a fake header was counted:\n{proc.stdout}"
    assert proc.returncode == 1, proc.stdout
