"""Test-runner outcome parsing for the deterministic CI/CD runner.

A test step's success is decided by its process exit code, and every mainstream
test runner exits 0 when it ran nothing at all - pytest exits 0 when all of its
tests skipped. So the ``finish`` gate, whose whole contract is answering "is this
safe to merge?", reported an unqualified SUCCESS for a suite that executed none
of the tests that could have said no (issue #621, observed on flow:auto #65 in
agentic-poker: ``312 passed, 66 skipped`` where the 66 were the acceptance
tests).

This module turns a runner's summary line back into counts so the step result can
carry them. It is deliberately read-only and advisory: it changes what a step
REPORTS, never whether it passed. A summary it cannot recognize yields ``None``
and behaviour is unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class SuiteOutcome:
    """Counts parsed from a test runner's summary line."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    framework: str = "unknown"

    @property
    def executed(self) -> int:
        """Tests that actually ran (passed + failed + errored)."""
        return self.passed + self.failed + self.errors

    @property
    def nothing_ran(self) -> bool:
        """True when the suite reported a result without executing any test.

        This is the #621 case: a green exit code that proves nothing. It covers
        both "everything skipped" and pytest's "no tests ran" (which collects
        nothing at all, so even the skip count is zero).
        """
        return self.executed == 0

    def summary(self) -> str:
        """Human-readable count summary, e.g. ``312 passed, 66 skipped``."""
        parts = [f"{self.passed} passed"]
        if self.failed:
            parts.append(f"{self.failed} failed")
        if self.errors:
            parts.append(f"{self.errors} errors")
        parts.append(f"{self.skipped} skipped")
        return ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "executed": self.executed,
            "framework": self.framework,
        }


# pytest tail line: "==== 312 passed, 66 skipped, 1 warning in 55.69s ====",
# "= 5 failed, 3 passed in 1.20s =", "==== no tests ran in 0.01s ====". The
# duration suffix is what makes it a summary rather than an incidental line of
# test output that happens to contain the word "passed".
_PYTEST_TAIL = re.compile(r"\bin \d+(?:\.\d+)?\s*s(?:econds)?\b")
_PYTEST_NO_TESTS = re.compile(r"\bno tests ran\b", re.IGNORECASE)
_PYTEST_COUNT = re.compile(
    r"(\d+)\s+(passed|failed|skipped|error|errors|xfailed|xpassed)\b"
)

# jest / vitest: "Tests:       2 skipped, 10 passed, 12 total".
_JEST_LINE = re.compile(r"^\s*Tests:\s+(?P<counts>.+?)\s*$")
_JEST_COUNT = re.compile(r"(\d+)\s+(passed|failed|skipped|todo|pending)\b")

# stdlib unittest: "Ran 12 tests in 0.01s" then "OK (skipped=3)" / "FAILED
# (failures=2, skipped=1)". Counts are derived, since only the non-passing ones
# are itemized.
_UNITTEST_RAN = re.compile(r"^Ran (\d+) tests? in ")
_UNITTEST_VERDICT = re.compile(r"^(OK|FAILED)\b(?:\s*\((?P<detail>[^)]*)\))?")
_UNITTEST_DETAIL = re.compile(r"(failures|errors|skipped|expected failures)=(\d+)")


def parse_suite_outcome(text: str) -> Optional[SuiteOutcome]:
    """Parse a test runner's summary out of captured step output.

    Returns None when no recognizable summary is present - the caller then
    reports exactly what it reported before this module existed. The LAST
    matching summary wins, so a ``make test`` target that runs several suites
    reports its final one rather than an early partial.
    """
    if not text:
        return None
    lines = text.splitlines()
    # Order matters only in that each parser scans independently; the last
    # recognized summary across all of them (by line position) is returned.
    best: Optional[tuple[int, SuiteOutcome]] = None
    for idx, line in enumerate(lines):
        for parsed in (
            _parse_pytest_line(line),
            _parse_jest_line(line),
            _parse_unittest_line(line, lines, idx),
        ):
            if parsed is not None:
                best = (idx, parsed)
    return best[1] if best else None


def _parse_pytest_line(line: str) -> Optional[SuiteOutcome]:
    if not _PYTEST_TAIL.search(line):
        return None
    if _PYTEST_NO_TESTS.search(line):
        return SuiteOutcome(framework="pytest")
    counts = {name: int(num) for num, name in _PYTEST_COUNT.findall(line)}
    if not counts:
        return None
    errors = counts.get("error", 0) + counts.get("errors", 0)
    return SuiteOutcome(
        # xpassed tests executed and passed; xfailed executed and failed as
        # expected - both ran, which is the distinction #621 cares about.
        passed=counts.get("passed", 0) + counts.get("xpassed", 0),
        failed=counts.get("failed", 0) + counts.get("xfailed", 0),
        skipped=counts.get("skipped", 0),
        errors=errors,
        framework="pytest",
    )


def _parse_jest_line(line: str) -> Optional[SuiteOutcome]:
    match = _JEST_LINE.match(line)
    if not match:
        return None
    counts = {name: int(num) for num, name in _JEST_COUNT.findall(match.group("counts"))}
    if not counts:
        return None
    return SuiteOutcome(
        passed=counts.get("passed", 0),
        failed=counts.get("failed", 0),
        # jest reports never-run tests as "skipped" (describe.skip) and "todo";
        # both are unexecuted, which is the count that matters here.
        skipped=counts.get("skipped", 0) + counts.get("todo", 0) + counts.get("pending", 0),
        framework="jest",
    )


def _parse_unittest_line(line: str, lines: list[str], idx: int) -> Optional[SuiteOutcome]:
    """Parse an ``OK``/``FAILED`` verdict against the preceding ``Ran N tests``."""
    verdict = _UNITTEST_VERDICT.match(line)
    if not verdict:
        return None
    total = None
    for prev in reversed(lines[max(0, idx - 5): idx]):
        ran = _UNITTEST_RAN.match(prev)
        if ran:
            total = int(ran.group(1))
            break
    if total is None:
        return None
    detail = dict(
        (name, int(num))
        for name, num in _UNITTEST_DETAIL.findall(verdict.group("detail") or "")
    )
    failed = detail.get("failures", 0) + detail.get("expected failures", 0)
    errors = detail.get("errors", 0)
    skipped = detail.get("skipped", 0)
    return SuiteOutcome(
        passed=max(total - failed - errors - skipped, 0),
        failed=failed,
        skipped=skipped,
        errors=errors,
        framework="unittest",
    )
