"""`pytest-parallel-differential.py`'s verdicts, including the ones a control cannot express.

`controls/pytest-parallel-differential/` registers the GOOD/BAD discrimination and
proves it against a blind anchor. It cannot cover UNKNOWN: the harness's
`cases[].expect` takes only GOOD or BAD, deliberately - "I expect this gate to
fall over" is not a property anyone should be able to register.

So the third verdict lives here, and it is the one that matters most for this
instrument. Two EMPTY reports have identical node-id sets and agree perfectly;
that is the most flattering wrong answer available, and it is what a broken
extraction produces. A differential that answered "no differences" to a pair it
could not read would be a blind instrument reporting on blindness.

The red cases below were proposed by the counter-model reviewer (#1086,
gpt-6-astra) and are registered here rather than noted, per ADR 0008.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "pytest-parallel-differential.py"
CASES = ROOT / "controls" / "pytest-parallel-differential" / "cases"


def _suite(rows: str, tests: int, failures: int = 0) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<testsuites>\n'
        f'  <testsuite name="pytest" errors="0" failures="{failures}" skipped="0" '
        f'tests="{tests}" time="1.0">\n{rows}  </testsuite>\n</testsuites>\n'
    )


def _case(anyhow: str) -> str:
    return f'    <testcase classname="tests.test_a" name="{anyhow}" time="0.01"/>\n'


def _run(serial: Path, parallel: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), "--serial", str(serial), "--parallel", str(parallel)],
        capture_output=True, text=True, timeout=60,
    )


def _pair(tmp_path: Path, serial_text: str, parallel_text: str) -> tuple[Path, Path]:
    s, p = tmp_path / "serial.xml", tmp_path / "parallel.xml"
    s.write_text(serial_text, encoding="utf-8")
    p.write_text(parallel_text, encoding="utf-8")
    return s, p


# --------------------------------------------------------------------------- #
# UNKNOWN - never a pass
# --------------------------------------------------------------------------- #
def test_two_empty_reports_are_UNKNOWN_not_agreement(tmp_path: Path) -> None:
    """The headline case. Empty and empty agree on every node they both carry."""
    empty = _suite("", 0)
    result = _run(*_pair(tmp_path, empty, empty))
    assert result.returncode == 2, (
        f"two zero-case reports did not report UNKNOWN (exit {result.returncode}). "
        f"They have identical node-id sets and zero verdict changes, so a "
        f"differential that reads them structurally reports perfect agreement "
        f"about nothing.\n{result.stdout}\n{result.stderr}"
    )
    assert "DIFFERENTIAL-UNKNOWN" in result.stderr
    assert "not a pass" in result.stderr


def test_a_malformed_report_is_UNKNOWN(tmp_path: Path) -> None:
    result = _run(*_pair(tmp_path, "<testsuites><not-closed>", _suite(_case("test_a"), 1)))
    assert result.returncode == 2, result.stdout
    assert "DIFFERENTIAL-UNKNOWN" in result.stderr


def test_a_missing_report_is_UNKNOWN(tmp_path: Path) -> None:
    serial, parallel = _pair(tmp_path, _suite(_case("test_a"), 1), _suite(_case("test_a"), 1))
    parallel.unlink()
    result = _run(serial, parallel)
    assert result.returncode == 2, result.stdout
    assert "DIFFERENTIAL-UNKNOWN" in result.stderr


def test_duplicate_node_ids_are_UNKNOWN(tmp_path: Path) -> None:
    """A node id that appears twice is not an identity.

    Without this the second occurrence silently overwrites the first, and every
    comparison over that report is between sets that do not mean what they say.
    """
    dupe = _suite(_case("test_a") + _case("test_a"), 2)
    result = _run(*_pair(tmp_path, dupe, dupe))
    assert result.returncode == 2, result.stdout
    assert "twice" in result.stderr


# --------------------------------------------------------------------------- #
# The three decided verdicts, over the committed control fixtures
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("case", "expected_exit", "marker"),
    [
        ("bad-substituted-node", 1, "MEMBERSHIP FLOOR: VIOLATED"),
        ("bad-dangerous-flip", 1, "BLOCKS - 1 test(s) fail serially"),
        ("good-matched", 0, "VERDICT: no dangerous-direction changes"),
    ],
)
def test_the_committed_control_cases_from_this_side_too(
    case: str, expected_exit: int, marker: str
) -> None:
    """The same fixtures the register drives, asserted with their MESSAGES.

    The control harness decides a case from the exit code plus a `detect_signal`
    regex. This pins the specific sentence each case should produce, so a gate
    that started reporting every disagreement as the same undifferentiated BLOCKS
    would still satisfy the register and fail here.
    """
    result = subprocess.run(
        [sys.executable, str(GATE), "--pair", str(CASES / case)],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == expected_exit, result.stdout
    assert marker in result.stdout, result.stdout


def test_a_pass_to_fail_change_is_QUARANTINE_and_still_non_zero(tmp_path: Path) -> None:
    """The direction people want to wave through.

    Passing serially and failing in parallel is a flake to triage, not agreement.
    Reporting it as agreement because it is the "safe" direction would be the same
    overclaim as missing the dangerous one, pointed somewhere comfortable.
    """
    serial = _suite(_case("test_a") + _case("test_b"), 2)
    parallel = _suite(
        _case("test_a")
        + '    <testcase classname="tests.test_a" name="test_b" time="0.01">'
        '<failure message="boom">AssertionError</failure></testcase>\n',
        2, failures=1,
    )
    result = _run(*_pair(tmp_path, serial, parallel))
    assert result.returncode == 1, result.stdout
    assert "QUARANTINE" in result.stdout
    assert "BLOCKS" not in result.stdout, (
        "a non-dangerous change was reported as BLOCKS, which loses the "
        "distinction between 'triage this flake' and 'do not ship this'"
    )
