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
