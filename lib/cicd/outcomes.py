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
from dataclasses import dataclass, replace
from typing import Any, Optional


@dataclass(frozen=True)
class SuiteOutcome:
    """Counts parsed from a test runner's summary line."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    framework: str = "unknown"
    # How many summaries were aggregated into these counts, and how many of
    # them executed nothing (kyle issue #838). A step whose command runs the
    # runner more than once - `make test` invoking pytest for two disjoint
    # suites - produces one summary per invocation, and the TOTAL can look
    # healthy while one invocation collected zero. Summing without these would
    # report an honest number and leave #621's guard exactly as blind as the
    # last-wins behaviour did.
    invocations: int = 1
    empty_invocations: int = 0
    # WHICH streams carried a summary (issue #939/#952). A verdict
    # without its denominator cannot be audited: `3 passed` read from stdout
    # alone and `3 passed` read from both streams are different claims, and
    # before #939 the parser could not tell them apart because it stopped at
    # the first stream that said anything.
    #
    # Deliberately NOT the same question as `invocations`, which counts how
    # many times the RUNNER ran. One invocation echoed to both streams sums to
    # `invocations=2` with `summary_streams=("stdout", "stderr")`; two genuinely
    # disjoint invocations split across the streams produce the same pair. The
    # counts alone cannot separate those, so recording the streams is what
    # leaves the shape legible to a reader instead of merely trusted.
    #
    # NAMED FOR WHAT IT HOLDS. `_parse_tests` always EXAMINES both streams, so
    # a stream missing here was read and carried no recognizable summary - it
    # was not skipped. An earlier name, `streams_read`, said the other thing
    # and would have let a reader conclude the parser had gone back to
    # examining one stream, which is the exact misreading #939 exists to end.
    # The denominator is therefore "both, always"; this field is which of them
    # spoke, and the pair is what separates "nothing there" from "did not
    # look" (#952).
    summary_streams: tuple[str, ...] = ()

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

    @property
    def any_invocation_empty(self) -> bool:
        """True when some invocation executed nothing, even if others did.

        ``nothing_ran`` asks about the total, which is the right question for
        a single invocation and the wrong one for several: two suites where
        the first collects zero and the second passes 102 total 102, so the
        total ran something and the #621 warning stays silent about a half of
        the gate that proved nothing (kyle issue #838).
        """
        return self.empty_invocations > 0

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
            "invocations": self.invocations,
            "empty_invocations": self.empty_invocations,
            "summary_streams": list(self.summary_streams),
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

# Pytest's short-summary ids make a first-attempt flake nameable and countable
# in the #769 report. They are NOT the selection mechanism: ``--last-failed``
# narrows the re-run from pytest's own cache, so this best-effort parse is never
# load-bearing for whether the gate is correct.
# The node id runs to the ` - <reason>` separator pytest prints in its short
# summary, NOT to the first whitespace: a parametrized id may contain spaces
# (`test_v[hello world]`), and `\S+` cut it at the space, so two DIFFERENT
# parametrized failures collapsed onto one truncated id. That was cosmetic while
# ids only labelled a re-run; it became a wrong verdict once the #915 retry
# compares failed sets by membership - a false "reproduced" with no newly
# appeared failure recorded. Lazy up to the FIRST ` - `; an id whose own
# parameter text contains ` - ` is re-joined by the bracket check below.
_PYTEST_FAILED_NODE_ID = re.compile(
    r"^\s*(?:FAILED|ERROR)\s+(.+?)(?:\s+-\s.*)?$", re.MULTILINE
)


def parse_failed_node_ids(text: str) -> list[str]:
    """Return pytest FAILED/ERROR node ids in first-seen order."""
    if not text:
        return []

    ids: list[str] = []
    seen: set[str] = set()
    for match in _PYTEST_FAILED_NODE_ID.finditer(text):
        node_id = match.group(1).strip()
        # A parameter id containing ` - ` was split by the lazy separator match;
        # an unclosed `[` says so, and the rest of the line up to its `]` is the
        # remainder of the id, not the reason.
        if "[" in node_id and "]" not in node_id:
            rest = match.group(0)[match.end(1) - match.start(0):]
            close = rest.find("]")
            if close != -1:
                node_id = (node_id + rest[: close + 1]).strip()
        if ("::" not in node_id and not node_id.endswith(".py")) or node_id in seen:
            continue
        seen.add(node_id)
        ids.append(node_id)
    return ids


def parse_suite_outcome(text: str, stream: str = "") -> Optional[SuiteOutcome]:
    """Parse a test runner's summary out of captured step output.

    Returns None when no recognizable summary is present - the caller then
    reports exactly what it reported before this module existed.

    EVERY recognized summary is aggregated, not just the last one. This used
    to keep the last, reasoning that a target running several suites should
    report its final one "rather than an early partial" - which is right for a
    partial or a re-run of a subset, and wrong for two DISJOINT suites, a
    shape that reasoning did not cover. kyle's ``make test`` runs pytest twice
    (non-Playwright, then Playwright), so a gate over 4,153 executed tests
    reported 103 and discarded 97.5% of the run (kyle issue #838).

    The #769 failed-id re-run is unaffected: it runs as a SEPARATE
    ``step.execute`` with its own captured output, so it is never in the same
    text as the run it re-runs and cannot be double-counted here.
    """
    if not text:
        return None
    lines = text.splitlines()
    # Each parser scans independently; per line the last recognized summary
    # wins, which preserves the previous precedence for a single summary.
    parsed: list[SuiteOutcome] = []
    for idx, line in enumerate(lines):
        found: Optional[SuiteOutcome] = None
        for candidate in (
            _parse_pytest_line(line),
            _parse_jest_line(line),
            _parse_unittest_line(line, lines, idx),
        ):
            if candidate is not None:
                found = candidate
        if found is not None:
            parsed.append(found)
    if not parsed:
        return None
    outcome = _aggregate(parsed)
    # Attribution happens here rather than inside `_aggregate` because this is
    # the only layer that knows which stream the text came from; everything
    # `_aggregate` sees is already from one stream.
    return replace(outcome, summary_streams=(stream,)) if stream else outcome


def _aggregate(outcomes: list[SuiteOutcome]) -> SuiteOutcome:
    """Sum several summaries into one, keeping how many ran nothing.

    A single summary passes through with its counts untouched; it simply
    reports ``invocations=1``, and ``empty_invocations=1`` when it is #621's
    original "exited 0 having executed nothing" case.
    """
    frameworks = {outcome.framework for outcome in outcomes}
    return SuiteOutcome(
        passed=sum(outcome.passed for outcome in outcomes),
        failed=sum(outcome.failed for outcome in outcomes),
        skipped=sum(outcome.skipped for outcome in outcomes),
        errors=sum(outcome.errors for outcome in outcomes),
        # One framework per step is the norm; "mixed" is honest rather than
        # silently attributing a jest run's tests to pytest.
        framework=outcomes[-1].framework if len(frameworks) == 1 else "mixed",
        invocations=len(outcomes),
        empty_invocations=sum(1 for outcome in outcomes if outcome.nothing_ran),
    )


def merge_stream_outcomes(
    outcomes: list[Optional[SuiteOutcome]],
) -> Optional[SuiteOutcome]:
    """Merge summaries parsed from the DIFFERENT streams of one step (issue #939).

    The rule is the one `_aggregate` already applies within a stream: sum. The
    parser used to read ``parse(output) or parse(error)``, which scanned the
    second stream only when the first returned ``None`` - so whichever stream
    spoke first silently won, and a passing or empty stdout summary hid the
    failures reported on stderr. Answering "several summaries in one stream"
    and "several summaries across two streams" by different rules would leave
    a caller unable to predict which it was getting.

    The rejected alternative was "prefer whichever stream reports failures".
    It makes precedence depend on the VALUE parsed rather than on provenance,
    so it cannot be stated as a rule about streams at all - only about
    outcomes - and it silently discards the other stream's passed count. A
    gate that wants pessimism should apply it at the gate, where it is visible
    and reviewable, not inside the thing reporting the facts.

    `invocations` is SUMMED rather than recomputed: each input has already
    aggregated its own stream, so it carries a real count of runner
    invocations. Recounting here (``len(present)``) would silently replace
    "how many times the runner ran" with "how many streams spoke" and discard
    kyle #838's field, which #621's guard reads.
    """
    present = [outcome for outcome in outcomes if outcome is not None]
    if not present:
        return None
    if len(present) == 1:
        return present[0]

    streams: list[str] = []
    for outcome in present:
        for name in outcome.summary_streams:
            if name not in streams:
                streams.append(name)

    frameworks = {outcome.framework for outcome in present}
    return SuiteOutcome(
        passed=sum(outcome.passed for outcome in present),
        failed=sum(outcome.failed for outcome in present),
        skipped=sum(outcome.skipped for outcome in present),
        errors=sum(outcome.errors for outcome in present),
        framework=present[-1].framework if len(frameworks) == 1 else "mixed",
        invocations=sum(outcome.invocations for outcome in present),
        empty_invocations=sum(outcome.empty_invocations for outcome in present),
        summary_streams=tuple(streams),
    )


# Signatures of a SUPPORTED runner that are not its summary (issue #977). They
# answer one narrow question for output that yielded no summary: "did a runner
# CPP parses produce this?" A yes is the per-run alarm - a supported parser was
# pointed at its own runner's output and came back empty. A no is NOT "this
# runner is unsupported": that is a declared decision (`unsupported_runner`),
# and output matching none of these is only UNCLASSIFIABLE, an unmeasured fact.
#
# Kept deliberately narrow, because recognising a runner is itself parsing.
# Undeclared, both causes are UNKNOWN and both warn, so a misclassification
# there changes the DETAIL wording and never the verdict.
#
# Against a DECLARATION it is not wording: a signature overrides the declaration
# and turns a quiet run into a warning. So each signature says whether it is
# CORROBORATED - a line that runner's own framing prints and a foreign harness
# has no reason to - and only those may override. `PASS src/app.test.ts` is
# jest's per-file line, but any shell harness can print exactly that, so it
# names jest in DETAIL and never out-votes a declaration (counter-model review).
_RUNNER_SIGNATURES: tuple[tuple[str, re.Pattern[str], bool], ...] = (
    ("pytest", re.compile(r"^=+ test session starts =+\s*$"), True),
    # The WHOLE line, end-anchored: pytest prints `collected 3 items` or
    # `collected 5 items / 2 deselected / 3 selected` and nothing after it, so a
    # prefix match let application output such as `collected 3 items from
    # queue` out-vote a declaration (counter-model review, pass 2).
    (
        "pytest",
        re.compile(
            r"^collected \d+ items?(?: / \d+ (?:deselected|selected|errors?|skipped))*\s*$"
        ),
        True,
    ),
    ("jest", re.compile(r"^\s*Test Suites:\s+\d+"), True),
    ("jest", re.compile(r"^\s*(?:PASS|FAIL)\s+\S+\.(?:[cm]?[jt]sx?)\b"), False),
    ("unittest", _UNITTEST_RAN, True),
)


def classify_unparsed(
    text: str, corroborated_only: bool = False
) -> Optional[tuple[str, str]]:
    """Name the supported runner whose output this is, when no summary parsed.

    Returns ``(framework, evidence_line)`` for the first line carrying a
    supported runner's signature, or ``None`` when the output matches none -
    which means UNCLASSIFIABLE, never "unsupported" (issue #977's ruling:
    unsupported is declared, not inferred).

    ``corroborated_only`` restricts the match to signatures strong enough to
    override a declaration; see ``_RUNNER_SIGNATURES``.

    Only meaningful for text ``parse_suite_outcome`` already returned ``None``
    for; on parseable text it would name a runner whose summary WAS read.
    """
    if not text:
        return None
    for line in text.splitlines():
        for framework, pattern, corroborated in _RUNNER_SIGNATURES:
            if corroborated_only and not corroborated:
                continue
            if pattern.search(line):
                return framework, line.strip()
    return None


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
