"""Per-stage coverage evidence for non-test gates (issue #1027).

The defect these pin: `lint`, `typecheck` and `security_scan` emitted
`{id, status}` and nothing else, so `status: "success"` was returned both by a
stage that examined the whole tree and by one that examined nothing. Only the
`test` step carried the "it ran and was not empty" assertion.

The parser inputs below are REAL tool output, captured by running the tools
rather than written from memory - a fixture invented to match the parser tests
the author's belief about the format, not the format.
"""

from __future__ import annotations

import pytest

from lib.cicd.coverage import (
    COVERED,
    UNKNOWN,
    ZERO,
    StageCoverage,
    merge_stream_coverage,
    parse_stage_coverage,
)

# Captured from `uv run --extra dev ruff check <dir>` / `mypy` / `python -m
# lib.security gate flow_finish` on this host (ruff 0.15.4).
RUFF_NO_FILES = "warning: No Python files found under the given path(s)\n"
RUFF_CLEAN = "All checks passed!\n"
MYPY_CLEAN = "Success: no issues found in 47 source files\n"
MYPY_ERRORS = "Found 3 errors in 2 files (checked 47 source files)\n"
SECURITY_COVERED = (
    "SECURITY_GATE: flow_finish PASS (blocked=0 warned=0; "
    "scanned=575 skipped-checks=0; blocks-on=CRITICAL warns-on=HIGH)\n"
)
SECURITY_ZERO = (
    "SECURITY_GATE: flow_finish PASS (blocked=0 warned=0; "
    "scanned=0 skipped-checks=3; blocks-on=CRITICAL warns-on=HIGH)\n"
)
SECURITY_UNKNOWN = (
    "SECURITY_GATE: flow_finish PASS (blocked=0 warned=0; "
    "scanned=unknown skipped-checks=0; blocks-on=CRITICAL warns-on=HIGH)\n"
)


class TestZeroIsDistinguishableFromClean:
    """The issue's own red case, at the parser.

    "a stage configured to match zero files must report a zero-coverage marker
    rather than status: success. A clean stage must not."

    Both halves are asserted. The second is the one that catches a blind
    instrument: a detector that reported `zero` for everything would pass the
    first test alone and be worse than no detector at all.
    """

    def test_ruff_reports_zero_when_it_found_no_files(self) -> None:
        cov = parse_stage_coverage(RUFF_NO_FILES, "stderr")
        assert cov is not None
        assert cov.state == ZERO
        assert cov.examined_nothing is True
        assert cov.units == 0

    def test_security_reports_zero_when_it_scanned_nothing(self) -> None:
        cov = parse_stage_coverage(SECURITY_ZERO, "stdout")
        assert cov is not None
        assert cov.state == ZERO
        assert cov.examined_nothing is True

    def test_a_covered_stage_does_not_report_zero(self) -> None:
        for text in (MYPY_CLEAN, MYPY_ERRORS, SECURITY_COVERED):
            cov = parse_stage_coverage(text, "stdout")
            assert cov is not None, text
            assert cov.state == COVERED, text
            assert cov.examined_nothing is False, text
            assert (cov.units or 0) > 0, text


class TestUnknownIsNotClean:
    """Silence must read as UNKNOWN and must NOT reach the gate as a warning.

    Both directions matter. Reporting `unknown` is what fixes the defect for a
    tool that states nothing; NOT warning on it is what keeps the warning
    readable, since every lint harness CPP cannot parse would otherwise warn on
    every run.
    """

    def test_ruff_clean_output_states_nothing(self) -> None:
        # ruff prints no count on the clean path, so there is nothing to parse.
        assert parse_stage_coverage(RUFF_CLEAN, "stdout") is None

    def test_scanned_unknown_is_not_read_as_zero(self) -> None:
        # The line IS recognized; the number is absent. A fabricated 0 here
        # would invent a zero-coverage warning nobody measured.
        assert parse_stage_coverage(SECURITY_UNKNOWN, "stdout") is None

    def test_default_state_is_unknown_and_not_stated(self) -> None:
        cov = StageCoverage()
        assert cov.state == UNKNOWN
        assert cov.stated is False
        assert cov.examined_nothing is False
        assert cov.units is None, "None, not 0: 'said nothing' is not 'said none'"


class TestBothStreamsAreRead:
    """ruff's zero evidence is on stderr and its cheerful line on stdout."""

    def test_zero_on_stderr_survives_a_clean_stdout(self) -> None:
        # THE REAL SHAPE: this is exactly what `ruff check <empty dir>` emits.
        # A stdout-only parse sees "All checks passed!" and reports a clean
        # stage, which is the false green the whole issue is about.
        cov = merge_stream_coverage(
            [
                parse_stage_coverage(RUFF_CLEAN, "stdout"),
                parse_stage_coverage(RUFF_NO_FILES, "stderr"),
            ]
        )
        assert cov is not None
        assert cov.state == ZERO
        assert cov.streams == ("stderr",)

    def test_an_echoed_line_is_counted_once(self) -> None:
        # A `make` recipe or wrapper that tees puts the SAME line on both
        # streams. Summing would report 94 files examined where 47 were.
        cov = merge_stream_coverage(
            [
                parse_stage_coverage(MYPY_CLEAN, "stdout"),
                parse_stage_coverage(MYPY_CLEAN, "stderr"),
            ]
        )
        assert cov is not None
        assert cov.units == 47, "deduplicated on the evidence line, not summed"
        assert cov.invocations == 1
        assert set(cov.streams) == {"stdout", "stderr"}


class TestAnEmptyInvocationSurvivesAHealthyTotal:
    """kyle #838's shape, for coverage instead of test counts.

    A stage whose command runs the tool twice can have one run examine nothing
    while the TOTAL looks healthy. Summing alone makes the number honest and
    re-hides exactly what this module exists to surface.
    """

    def test_one_empty_run_is_reported_beside_a_healthy_total(self) -> None:
        text = (
            "Success: no issues found in 0 source files\n"
            "Success: no issues found in 20 source files\n"
        )
        cov = parse_stage_coverage(text, "stdout")
        assert cov is not None
        assert cov.units == 20
        assert cov.state == COVERED, "the total really did examine something"
        assert cov.invocations == 2
        assert cov.empty_invocations == 1
        assert cov.any_invocation_empty is True


class TestEvidenceIsCarried:
    """A verdict a reader cannot audit is one they have to trust."""

    @pytest.mark.parametrize(
        ("text", "tool"),
        [
            (RUFF_NO_FILES, "ruff"),
            (MYPY_CLEAN, "mypy"),
            (SECURITY_COVERED, "security-gate"),
        ],
    )
    def test_the_parsed_line_is_kept(self, text: str, tool: str) -> None:
        cov = parse_stage_coverage(text, "stdout")
        assert cov is not None
        assert cov.tool == tool
        assert cov.evidence == text.strip()
        assert cov.to_dict()["evidence"] == text.strip()


class TestSkippedChecksIsNotGradedOn:
    """`skipped-checks=` rides the same line and must not drive the verdict.

    A check whose subject is absent (no .env file to inspect) skips as its
    CORRECT outcome. Grading on it would fire on healthy repos, which is how a
    warning stops being read.
    """

    def test_a_covered_scan_with_skipped_checks_is_not_zero(self) -> None:
        line = (
            "SECURITY_GATE: flow_finish PASS (blocked=0 warned=0; "
            "scanned=575 skipped-checks=4; blocks-on=CRITICAL warns-on=HIGH)\n"
        )
        cov = parse_stage_coverage(line, "stdout")
        assert cov is not None
        assert cov.state == COVERED
        assert cov.examined_nothing is False
