"""Tests for lib/cicd/outcomes.py - test-runner summary parsing (issue #621).

A test step's exit code cannot distinguish "312 tests passed" from "312 tests
were skipped", because pytest exits 0 for both. These tests pin the parser that
recovers the counts, and the deliberate blind spots: a step that is not a test
step, and output with no recognizable summary, must yield None so the runner
reports exactly what it reported before.
"""

from __future__ import annotations

import pytest

from lib.cicd.outcomes import (
    SuiteOutcome,
    parse_failed_node_ids,
    parse_suite_outcome,
)
from lib.cicd.steps import ShellStep, StepDef


class TestFailedNodeIds:
    def test_realistic_short_summary(self) -> None:
        text = """================ short test summary info =================
FAILED tests/test_x.py::test_y - AssertionError: expected 1
FAILED tests/test_x.py::TestC::test_z[param-1]
  ERROR tests/test_w.py::test_v - fixture 'db' not found
================ 2 failed, 1 error in 0.42s =================
"""
        assert parse_failed_node_ids(text) == [
            "tests/test_x.py::test_y",
            "tests/test_x.py::TestC::test_z[param-1]",
            "tests/test_w.py::test_v",
        ]

    def test_reason_suffix_is_stripped_and_duplicates_preserve_order(self) -> None:
        text = """FAILED tests/a.py::test_one - AssertionError: first
ERROR tests/b.py::TestB::test_two[param] - RuntimeError
FAILED tests/a.py::test_one - AssertionError: repeated
"""
        assert parse_failed_node_ids(text) == [
            "tests/a.py::test_one",
            "tests/b.py::TestB::test_two[param]",
        ]

    def test_bare_error_line_yields_nothing(self) -> None:
        assert parse_failed_node_ids("ERROR at setup of test_x\n") == []

    def test_empty_string_yields_nothing(self) -> None:
        assert parse_failed_node_ids("") == []

    def test_prose_is_not_a_summary_line(self) -> None:
        assert parse_failed_node_ids("The request failed tests/a.py::test_one\n") == []


class TestPytestParsing:
    def test_passed_and_skipped(self) -> None:
        # The line from the run that produced issue #621.
        out = parse_suite_outcome(
            "======= 312 passed, 66 skipped, 1 warning in 55.69s ======="
        )
        assert out is not None
        assert out.framework == "pytest"
        assert out.passed == 312
        assert out.skipped == 66
        assert out.executed == 312
        assert not out.nothing_ran
        assert out.summary() == "312 passed, 66 skipped"

    def test_everything_skipped_is_nothing_ran(self) -> None:
        out = parse_suite_outcome("========== 66 skipped in 0.42s ==========")
        assert out is not None
        assert out.passed == 0
        assert out.skipped == 66
        assert out.nothing_ran
        assert out.summary() == "0 passed, 66 skipped"

    def test_no_tests_ran(self) -> None:
        out = parse_suite_outcome("=========== no tests ran in 0.01s ===========")
        assert out is not None
        assert out.framework == "pytest"
        assert out.nothing_ran
        assert out.skipped == 0

    def test_failures_and_errors(self) -> None:
        out = parse_suite_outcome("=== 2 failed, 8 passed, 1 error in 3.20s ===")
        assert out is not None
        assert out.failed == 2
        assert out.passed == 8
        assert out.errors == 1
        assert out.executed == 11
        assert not out.nothing_ran

    def test_xfail_and_xpass_count_as_executed(self) -> None:
        out = parse_suite_outcome("== 5 passed, 1 xfailed, 1 xpassed in 1.00s ==")
        assert out is not None
        assert out.passed == 6  # 5 passed + 1 xpassed
        assert out.failed == 1  # xfailed ran and failed as expected
        assert not out.nothing_ran

    def test_summaries_from_two_suites_are_summed(self) -> None:
        """CONTRACT CHANGE (kyle issue #838). This test previously asserted
        the opposite - "a `make test` target that runs two suites reports the
        final one" - and that was the defect, pinned as intent: kyle's target
        runs pytest twice, so a gate over 4,153 tests reported 103.

        The old docstring in outcomes.py defended last-wins against "an early
        partial", which is a different scenario from the one this test used.
        Where a partial genuinely occurs - the #769 failed-id re-run - it runs
        as a separate `step.execute` with its own output, so it is never in
        the same text and cannot be double-counted by summing here.
        """
        text = "\n".join(
            [
                "=== 10 passed in 1.00s ===",
                "running the second suite",
                "=== 4 passed, 2 skipped in 2.00s ===",
            ]
        )
        out = parse_suite_outcome(text)
        assert out is not None
        assert out.passed == 14
        assert out.skipped == 2
        assert out.invocations == 2

    def test_summary_embedded_in_full_output(self) -> None:
        text = (
            "uv run pytest\n"
            "tests/test_a.py ..s                                    [ 60%]\n"
            "tests/test_b.py ss                                     [100%]\n"
            "\n"
            "================== 2 passed, 3 skipped in 0.31s ==================\n"
        )
        out = parse_suite_outcome(text)
        assert out is not None
        assert (out.passed, out.skipped) == (2, 3)


class TestJestParsing:
    def test_tests_line(self) -> None:
        out = parse_suite_outcome(
            "Test Suites: 3 passed, 3 total\n"
            "Tests:       2 skipped, 10 passed, 12 total\n"
            "Time:        4.2 s\n"
        )
        assert out is not None
        assert out.framework == "jest"
        assert out.passed == 10
        assert out.skipped == 2
        assert not out.nothing_ran

    def test_all_skipped(self) -> None:
        out = parse_suite_outcome("Tests:       12 skipped, 12 total\n")
        assert out is not None
        assert out.nothing_ran
        assert out.skipped == 12

    def test_todo_counts_as_unexecuted(self) -> None:
        out = parse_suite_outcome("Tests:       1 todo, 4 passed, 5 total\n")
        assert out is not None
        assert out.skipped == 1
        assert out.passed == 4


class TestUnittestParsing:
    def test_ok_with_skips(self) -> None:
        out = parse_suite_outcome("Ran 12 tests in 0.03s\n\nOK (skipped=3)\n")
        assert out is not None
        assert out.framework == "unittest"
        assert out.passed == 9
        assert out.skipped == 3
        assert not out.nothing_ran

    def test_everything_skipped(self) -> None:
        out = parse_suite_outcome("Ran 5 tests in 0.01s\n\nOK (skipped=5)\n")
        assert out is not None
        assert out.nothing_ran

    def test_failed_verdict(self) -> None:
        out = parse_suite_outcome(
            "Ran 10 tests in 0.10s\n\nFAILED (failures=2, skipped=1)\n"
        )
        assert out is not None
        assert out.failed == 2
        assert out.skipped == 1
        assert out.passed == 7

    def test_verdict_without_ran_line_is_ignored(self) -> None:
        # A bare "OK" in arbitrary output is not a test summary.
        assert parse_suite_outcome("OK\n") is None


class TestNonSummaries:
    @pytest.mark.parametrize(
        "text",
        [
            "",
            "All checks passed!\n",  # ruff
            "Success: no issues found in 120 source files\n",  # mypy
            "Compiled 3 files in 0.5s\n",
            "3 files reformatted in 1.2s\n",
            "12 vulnerabilities passed the allowlist\n",  # no duration -> not a summary
        ],
    )
    def test_unrecognized_output_yields_none(self, text: str) -> None:
        assert parse_suite_outcome(text) is None


class TestStepGating:
    """The parse only fires for steps that name a test runner."""

    @pytest.mark.parametrize(
        "step_id,command",
        [
            ("test", "make test"),
            ("test-pg", "make test-pg"),
            ("unit_tests", "uv run pytest"),
            ("suite", "npx jest --ci"),
            ("check", "uv run vitest run"),
        ],
    )
    def test_recognized_test_steps(self, step_id: str, command: str) -> None:
        assert ShellStep(StepDef(id=step_id, command=command)).is_test_step()

    @pytest.mark.parametrize(
        "step_id,command",
        [
            ("lint", "make lint"),
            ("typecheck", "make typecheck"),
            ("security_scan", "python3 -m lib.security gate flow_finish"),
            ("deploy", "make deploy"),
            ("latest", "make build-latest"),  # "latest" is not "test"
        ],
    )
    def test_non_test_steps(self, step_id: str, command: str) -> None:
        assert not ShellStep(StepDef(id=step_id, command=command)).is_test_step()

    def test_path_in_command_matches_by_design(self) -> None:
        """An absolute path is scanned like any other command text (#621, #704).

        This is a characterization test, not a wish: #621 wants a `make test`
        recipe recognized even under an unhelpful step id, which means scanning
        the whole command, which in turn means a path carrying "test"/"pytest"
        matches too. Narrowing the pattern to dodge paths would weaken the
        detection it exists for, so the trade-off is pinned here - a future
        narrowing has to be a deliberate act that turns this red rather than a
        silent drift.

        The cost lands on FIXTURES, which is how it was found (#704): a step
        command built from `sys.executable` inherits the checkout path, so every
        flow worktree whose branch slug contained "test" reclassified a `lint`
        step as a test step and went red. Both poisoned shapes below are real -
        a flow worktree path, and anything under pytest's own `tmp_path` root.
        """
        worktree = '"/home/u/cpp-issue-704-test-workers-cap/.venv/bin/python3" capture_env.py'
        pytest_tmp = '"/tmp/pytest-of-u/pytest-3/plain0/interp" capture_env.py'

        assert ShellStep(StepDef(id="lint", command=worktree)).is_test_step()
        assert ShellStep(StepDef(id="lint", command=pytest_tmp)).is_test_step()
        # The shape a fixture must use instead: a relative name, no path, and no
        # mention of PYTEST_WORKERS (which matches on "pytest" as well).
        assert not ShellStep(StepDef(id="lint", command="./interp capture_env.py")).is_test_step()

    def test_non_test_step_never_parses_counts(self) -> None:
        step = ShellStep(StepDef(id="lint", command="make lint"))
        assert step._parse_tests("== 1 passed, 9 skipped in 1.0s ==", "") is None

    def test_test_step_parses_from_stderr_too(self) -> None:
        step = ShellStep(StepDef(id="test", command="make test"))
        outcome = step._parse_tests("", "== 1 passed, 9 skipped in 1.0s ==")
        assert outcome == SuiteOutcome(passed=1, skipped=9, framework="pytest")


class TestMultipleInvocationsInOneStep:
    """A step whose command runs pytest more than once (kyle issue #838).

    `make test` in kyle runs two disjoint pytest invocations - non-Playwright,
    then Playwright - inside one Make target. The parser kept only the last
    summary, so a gate over 4,153 executed tests reported 103: the Playwright
    half, with the other 97.5% silently discarded.

    The existing last-wins behaviour is NOT an oversight, it is scoped. Its
    comment reasons about "an early partial", and for a partial or a re-run of
    a subset last-wins is correct - summing those would double-count. Two
    DISJOINT suites is a shape that reasoning did not cover.

    The #769 failed-id re-run stays correct for the same reason it always was:
    it happens in a SEPARATE `step.execute` with its own captured output
    (`runner.py`), so aggregating within one output cannot absorb it.
    """

    TWO_SUITES = """Running non-Playwright tests...
============ 4051 passed, 1 skipped, 954 warnings in 284.73s (0:04:44) ============
Running Playwright tests...
============ 102 passed, 1 xpassed in 156.66s (0:02:36) ============
"""

    ONE_INVOCATION_RAN_NOTHING = """Running non-Playwright tests...
============ no tests ran in 0.31s ============
Running Playwright tests...
============ 102 passed in 156.66s ============
"""

    def test_disjoint_suites_are_summed_not_replaced(self) -> None:
        outcome = parse_suite_outcome(self.TWO_SUITES)

        assert outcome is not None
        # 4051 + 102 + 1 xpassed: xpassed executed and passed (#621's rule).
        assert outcome.passed == 4154
        assert outcome.skipped == 1
        assert outcome.executed == 4154
        assert outcome.invocations == 2

    def test_an_empty_invocation_is_reported_even_when_the_total_is_healthy(
        self,
    ) -> None:
        """THE criterion for kyle #838, and the reason summing is not enough.

        One invocation collects nothing, the other passes 102. The TOTAL ran
        something, so `nothing_ran` is False and the #621 warning does not
        fire - which is exactly the blindness that issue exists to prevent,
        surviving inside the aggregate that was supposed to fix it.

        This test fails against a correctly-summing implementation, not only
        against the old last-wins one. That is deliberate: aggregation alone
        would report the honest total, pass a test asserting the honest total,
        look complete, and leave the guard as blind as it is today.
        """
        outcome = parse_suite_outcome(self.ONE_INVOCATION_RAN_NOTHING)

        assert outcome is not None
        assert outcome.executed == 102
        assert outcome.nothing_ran is False
        assert outcome.invocations == 2
        assert outcome.empty_invocations == 1
        assert outcome.any_invocation_empty is True

    def test_a_single_invocation_is_unchanged(self) -> None:
        """The overwhelmingly common shape must be untouched."""
        outcome = parse_suite_outcome("==== 312 passed, 66 skipped in 55.69s ====")

        assert outcome is not None
        assert outcome.passed == 312
        assert outcome.invocations == 1
        assert outcome.empty_invocations == 0
        assert outcome.any_invocation_empty is False

    def test_a_lone_empty_invocation_still_reads_as_nothing_ran(self) -> None:
        """#621's original case keeps its original answer."""
        outcome = parse_suite_outcome("==== no tests ran in 0.01s ====")

        assert outcome is not None
        assert outcome.nothing_ran is True
        assert outcome.invocations == 1
        assert outcome.empty_invocations == 1


class TestVerdictIsIndependentOfCounts:
    """The blast-radius guarantee, demonstrated rather than asserted in prose.

    This module's contract is that it "changes what a step REPORTS, never
    whether it passed". CPP is the tooling every session's gate runs through,
    so the question a reviewer actually needs answered is whether a parsing
    change can turn a red green. It cannot: status comes from the exit code
    and nothing else, and these pin that for the multi-invocation output whose
    parsing this change alters.
    """

    TWO_SUITES = (
        "printf '%s\\n' "
        "'==== 4051 passed in 284.73s ====' "
        "'==== 102 passed in 156.66s ===='; exit "
    )

    def test_zero_exit_is_success_with_counts_parsed(self) -> None:
        step = ShellStep(StepDef(id="test", command=self.TWO_SUITES + "0"))

        result = step.execute({"project_root": "/tmp"})

        assert result.success
        assert result.tests is not None
        assert result.tests.passed == 4153

    def test_nonzero_exit_is_failure_with_the_same_counts_parsed(self) -> None:
        """Same output, same counts, opposite verdict - decided by exit code."""
        step = ShellStep(StepDef(id="test", command=self.TWO_SUITES + "1"))

        result = step.execute({"project_root": "/tmp"})

        assert not result.success
        assert result.tests is not None
        assert result.tests.passed == 4153
