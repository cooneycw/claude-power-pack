"""Per-stage coverage evidence for the gates that are not test steps (issue #1027).

A step's exit code says the tool did not error. It does not say the tool looked
at anything. ``ruff check .`` on a tree with no Python files prints a warning to
stderr, ``All checks passed!`` to stdout, and exits 0 - so a stage that examined
nothing is byte-identical, at the exit code and in ``step_details``, to one that
examined five hundred files and found them clean.

``outcomes.py`` already closed this hole for the ``test`` step: a suite that
executed nothing carries counts saying so, and the runner warns (issue #621).
The other three gates in the ``finish`` plan - ``lint``, ``typecheck`` and
``security_scan`` - emitted ``{id, status}`` and nothing else, so the standing
"grade per-stage, not the rollup" procedure was unfalsifiable for three stages
out of four. This module is the same idea for those: turn whatever the tool said
about its own coverage back into a number the step result can carry.

Three states, and the third is the point:

``covered``   the tool stated how many units it examined, and it was not zero.
``zero``      the tool stated, positively, that it examined nothing.
``unknown``   nothing recognizable was said either way.

Only ``zero`` is a warning. ``unknown`` is recorded and reported but never
stops a gate, and that bound is deliberate - the same one ``runner.py`` already
draws for an unparseable test summary. Warning on ``unknown`` would fire on
every Go, Rust or shell lint harness CPP cannot parse, on every run, which is
how a warning stops being read. Recording it still fixes the reported defect:
a reader can SEE the stage is unproven instead of reading ``status: "success"``
as clean.

Like ``outcomes.py`` this is read-only and advisory: it changes what a step
REPORTS, never whether it passed.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Optional

#: The stage stated a non-zero count of units examined.
COVERED = "covered"
#: The stage stated that it examined nothing at all.
ZERO = "zero"
#: Nothing recognizable was said about coverage either way.
UNKNOWN = "unknown"

#: The measurement covers the WHOLE stage - what the stage examined is what this
#: number counts. True of ruff and mypy, where one tool is the stage.
SCOPE_STAGE = "stage"
#: The measurement covers ONE COMPONENT of a multi-check stage (issue #1027,
#: cross-model review). `security_scan` runs several checks - secrets, gitignore,
#: file permissions, tracked .env files, debug flags - and only the secrets
#: scanner reports a file count. Reading that one number as the stage's coverage
#: says "this gate proved nothing" about a run in which the gitignore and
#: permissions checks examined their subjects and passed on the evidence. The
#: number is real; the scope of the conclusion drawn from it was not, so the
#: scope travels WITH the number and the warning prose branches on it.
SCOPE_COMPONENT = "component"


@dataclass(frozen=True)
class StageCoverage:
    """What a non-test stage said about how much it examined."""

    state: str = UNKNOWN
    #: Units examined, when the tool stated a number. ``None`` under
    #: ``unknown`` - deliberately not 0, which is a MEASUREMENT and would make
    #: "said nothing" indistinguishable from "said none".
    units: Optional[int] = None
    #: What the tool counts, for the report: "source file", "module".
    unit_name: str = "unit"
    tool: str = "unknown"
    #: Whether this number measures the whole stage or one component of it.
    #: A component measurement can say "the secrets scan examined nothing"; it
    #: cannot say "security_scan proved nothing", because the stage's other
    #: checks have their own inputs and this number never looked at them.
    scope: str = SCOPE_STAGE
    #: What the measurement is OF, when it is narrower than the stage.
    component: str = ""
    #: The literal line the verdict was read from, so a reader can audit the
    #: parse instead of trusting it.
    evidence: str = ""
    #: How many separate coverage statements were found, and how many of them
    #: reported zero. The direct analogue of ``SuiteOutcome.invocations`` /
    #: ``empty_invocations`` (kyle issue #838): a step whose command runs the
    #: tool more than once can have one invocation examine nothing while the
    #: TOTAL looks healthy, so a sum alone re-hides exactly what this module
    #: exists to surface.
    invocations: int = 0
    empty_invocations: int = 0
    #: Which streams carried a statement (issue #952's idiom). Both streams are
    #: ALWAYS examined, so a stream missing here was read and said nothing - it
    #: was not skipped.
    streams: tuple[str, ...] = ()

    @property
    def examined_nothing(self) -> bool:
        """True when the stage positively reported examining nothing."""
        return self.state == ZERO

    @property
    def any_invocation_empty(self) -> bool:
        """True when some invocation examined nothing, even if others did."""
        return self.empty_invocations > 0

    @property
    def stated(self) -> bool:
        """True when the tool said anything measurable about its coverage."""
        return self.state in (COVERED, ZERO)

    def summary(self) -> str:
        """Human-readable coverage, e.g. ``examined 47 source files``."""
        if self.state == UNKNOWN:
            return "coverage not stated by this tool"
        plural = "" if self.units == 1 else "s"
        subject = f"the {self.component} " if self.component else ""
        if self.state == ZERO:
            return f"{subject}examined NO {self.unit_name}{plural}".lstrip()
        return f"{subject}examined {self.units} {self.unit_name}{plural}".lstrip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "units": self.units,
            "unit_name": self.unit_name,
            "tool": self.tool,
            "scope": self.scope,
            "component": self.component,
            "evidence": self.evidence,
            "invocations": self.invocations,
            "empty_invocations": self.empty_invocations,
            "streams": list(self.streams),
        }


# ruff: MEASURED, and the measurement is mostly bad news. Recorded here because
# the next reader will otherwise assume `lint` is covered, which it is not.
#
#   - ruff never states a positive count. `--statistics` on a clean tree prints
#     nothing (ruff 0.15.4), so `lint` can reach `zero` or `unknown` and never
#     `covered`.
#   - the "no Python files" warning below is SUPPRESSED when a pyproject.toml
#     is present - measured across four tree shapes, and it holds whether or
#     not the file has a [tool.ruff] section. Every real Python project has a
#     pyproject.toml, so in the population this gate actually runs against,
#     this pattern does not fire. It fires for a tree with no pyproject (a
#     scripts-only repo), which is why it is kept: it is correct when it
#     appears and costs nothing.
#
# So `lint` coverage is, in practice, `unknown`. That is a WEAKER outcome than
# this module achieves for typecheck and security_scan, and it is stated rather
# than implied: "unknown" still fixes the reported defect for lint (a reader
# sees an unproven stage instead of a bare `status: "success"`), but nobody
# should cite a green lint stage as evidence that it examined anything.
#
# Getting a real number would mean measuring the stage's INPUT rather than
# parsing its output - counting the files the gate's scope contains - which is
# a different design than this module and is filed separately rather than
# half-built here.
_RUFF_NO_FILES = re.compile(
    r"^\s*warning:\s*No Python files found under the given path", re.IGNORECASE
)

# mypy states its denominator on BOTH verdicts, which makes `typecheck` the one
# stage here with reliable POSITIVE coverage:
#   "Success: no issues found in 47 source files"
#   "Found 3 errors in 2 files (checked 47 source files)"
#
# The zero case was probed and NOT reached: mypy with nothing to check exits 2
# ("There are no .py[i] files in directory '.'"), both on an empty tree and on
# one whose files are all excluded - a hard failure, not a false green, so the
# gate already stops. The `(\d+)` below therefore matches 0 defensively rather
# than because a run was observed producing it. Said plainly so the zero branch
# is not later cited as a tested path: what is demonstrated for mypy is the
# positive count, and that is enough - a stage reporting "examined 47 source
# files" is the assertion this module exists to add.
_MYPY_CLEAN = re.compile(r"\bno issues found in (\d+) source files?\b", re.IGNORECASE)
_MYPY_CHECKED = re.compile(r"\bchecked (\d+) source files?\b", re.IGNORECASE)

# CPP's own security gate line (issue #1027). `blocked=`/`warned=` are FINDINGS
# and say nothing about coverage - a clean scan of 575 files and a scan of none
# both report 0 - so the line also carries `scanned=`.
#
# `scanned=unknown` is matched by neither pattern, which is the intended
# outcome: the line is recognized, no number is claimed, and the stage reports
# `unknown` rather than a fabricated zero.
_SECURITY_GATE = re.compile(r"^\s*SECURITY_GATE:\s")
_SECURITY_SCANNED = re.compile(r"\bsecrets-scanned=(\d+)\b")


def parse_stage_coverage(text: str, stream: str = "") -> Optional[StageCoverage]:
    """Parse coverage statements out of one captured stream.

    Returns ``None`` when nothing recognizable is present, so a caller reports
    exactly what it reported before this module existed.

    Every recognized statement is aggregated, not just the last - the reasoning
    ``outcomes.py`` records for the same choice applies unchanged here: a step
    whose command runs the tool over two disjoint paths produces one statement
    per run, and keeping the last would discard the other.
    """
    if not text:
        return None
    parsed: list[StageCoverage] = []
    for line in text.splitlines():
        for candidate in (
            _parse_ruff_line(line),
            _parse_mypy_line(line),
            _parse_security_line(line),
        ):
            if candidate is not None:
                parsed.append(candidate)
    if not parsed:
        return None
    aggregated = _aggregate(parsed)
    # Attribution happens here because this is the only layer that knows which
    # stream the text came from.
    return replace(aggregated, streams=(stream,)) if stream else aggregated


def merge_stream_coverage(
    coverages: list[Optional[StageCoverage]],
) -> Optional[StageCoverage]:
    """Merge the coverage parsed from a step's DIFFERENT streams.

    A line echoed to BOTH streams is counted once; a line repeated WITHIN one
    stream is counted every time. The distinction is the whole difficulty, and
    a single global "have I seen this string" set gets it wrong in a way that
    is easy to miss (cross-model review, second pass): two mypy runs over
    separate 47-file packages print the identical summary twice on stdout, and
    with such a set the merged result reported 47 units and one invocation
    whenever the other stream happened to carry anything - so a step's measured
    coverage changed because an UNRELATED stream had output. Echo suppression
    is therefore done occurrence-for-occurrence against the first stream, not
    by flattening every line to a set.

    ``zero`` from ANY stream survives the merge, because that is the whole
    signal: ruff prints its "no files" warning to stderr and its cheerful
    ``All checks passed!`` to stdout, so the stream that proves the stage
    no-opped is exactly the one a stdout-only reader would miss.
    """
    present = [coverage for coverage in coverages if coverage is not None]
    if not present:
        return None
    if len(present) == 1:
        return present[0]

    streams: list[str] = []
    for coverage in present:
        for name in coverage.streams:
            if name not in streams:
                streams.append(name)

    per_stream = [
        [line for line in coverage.evidence.splitlines() if line.strip()]
        for coverage in present
    ]
    kept: list[str] = list(per_stream[0])
    base = Counter(per_stream[0])
    for lines in per_stream[1:]:
        remaining = Counter(base)
        for line in lines:
            if remaining[line] > 0:
                # This occurrence matches one the first stream already carried:
                # a tee'd echo, not a second invocation.
                remaining[line] -= 1
                continue
            kept.append(line)

    records = [r for r in (_parse_evidence_line(line) for line in kept) if r is not None]
    if not records:
        # Nothing re-parsed cleanly; fall back to the richest single stream
        # rather than inventing a merged number.
        richest = max(present, key=lambda c: (c.stated, c.invocations))
        return replace(richest, streams=tuple(streams))

    return replace(_aggregate(records), streams=tuple(streams))


def _parse_evidence_line(line: str) -> Optional[StageCoverage]:
    for candidate in (
        _parse_ruff_line(line),
        _parse_mypy_line(line),
        _parse_security_line(line),
    ):
        if candidate is not None:
            return candidate
    return None


def _aggregate(coverages: list[StageCoverage]) -> StageCoverage:
    """Sum several coverage statements from ONE stream into one.

    A single statement passes through with its count untouched; it simply
    reports ``invocations=1``, and ``empty_invocations=1`` when it is the
    "examined nothing" case this module exists for.
    """
    stated = [c for c in coverages if c.units is not None]
    units_total = sum(c.units or 0 for c in stated)
    empty = sum(1 for c in coverages if c.units == 0 or c.state == ZERO)
    tools = {c.tool for c in coverages}
    unit_names = {c.unit_name for c in coverages if c.stated}
    if empty > 0 and (not stated or units_total == 0):
        state = ZERO
    elif stated:
        state = COVERED
    else:
        state = UNKNOWN
    # A stage measurement plus a component measurement is a STAGE measurement
    # only if every part agreed it was one. Mixing them and keeping "stage"
    # would let one narrow number widen itself by being aggregated with a broad
    # one, which is the overclaim this field exists to stop.
    scopes = {c.scope for c in coverages if c.stated}
    # Attribution is keyed on the (tool, component) IDENTITY, and an EMPTY
    # component is one of those identities rather than an abstention
    # (cross-model review, second pass). Collecting only non-empty components
    # meant mypy's `47 source files` aggregated with `secrets-scanned=0` left
    # exactly one named component standing, and the summary read "the secrets
    # scan examined 47 source files" - 47 files the secrets scan never opened,
    # attributed to it because the only other measurement declined to name
    # itself. A mixed aggregate names no component, so it can still report a
    # number and can no longer say whose.
    identities = {(c.tool, c.component) for c in coverages if c.stated}
    if len(identities) == 1:
        agg_tool, agg_component = identities.pop()
    else:
        agg_tool, agg_component = "mixed", ""
    return StageCoverage(
        state=state,
        units=units_total if stated else None,
        unit_name=unit_names.pop() if len(unit_names) == 1 else "unit",
        tool=agg_tool if stated else (coverages[-1].tool if len(tools) == 1 else "mixed"),
        scope=SCOPE_COMPONENT if SCOPE_COMPONENT in scopes else SCOPE_STAGE,
        component=agg_component,
        evidence="\n".join(c.evidence for c in coverages if c.evidence),
        invocations=len(coverages),
        empty_invocations=empty,
        streams=(),
    )


def _parse_ruff_line(line: str) -> Optional[StageCoverage]:
    if not _RUFF_NO_FILES.search(line):
        return None
    return StageCoverage(
        state=ZERO,
        units=0,
        unit_name="Python file",
        tool="ruff",
        evidence=line.strip(),
        invocations=1,
        empty_invocations=1,
    )


def _parse_mypy_line(line: str) -> Optional[StageCoverage]:
    match = _MYPY_CLEAN.search(line) or _MYPY_CHECKED.search(line)
    if not match:
        return None
    units = int(match.group(1))
    return StageCoverage(
        state=ZERO if units == 0 else COVERED,
        units=units,
        unit_name="source file",
        tool="mypy",
        evidence=line.strip(),
        invocations=1,
        empty_invocations=1 if units == 0 else 0,
    )


def _parse_security_line(line: str) -> Optional[StageCoverage]:
    """Parse CPP's own ``SECURITY_GATE:`` summary line.

    Only ``scanned=`` is read. The line also carries ``skipped-checks=``, which
    is deliberately NOT graded on: a check whose subject is absent (no ``.env``
    file to inspect) skips as its correct outcome, so treating that as a
    coverage hole would warn on healthy repos.

    ``scanned=unknown`` returns ``None`` - the stage then reports ``unknown``,
    which is the honest answer, rather than a zero nobody measured.
    """
    if not _SECURITY_GATE.search(line):
        return None
    scanned = _SECURITY_SCANNED.search(line)
    if scanned is None:
        return None
    units = int(scanned.group(1))
    return StageCoverage(
        state=ZERO if units == 0 else COVERED,
        units=units,
        unit_name="source file",
        tool="security-gate",
        # `scanned=` is the SECRETS scanner's file count, and the security stage
        # runs more than the secrets scanner. Declared narrow at the source so
        # no consumer has to know which of the stage's checks the number came
        # from in order to avoid overclaiming with it.
        scope=SCOPE_COMPONENT,
        component="secrets scan",
        evidence=line.strip(),
        invocations=1,
        empty_invocations=1 if units == 0 else 0,
    )
