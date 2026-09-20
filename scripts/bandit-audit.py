#!/usr/bin/env python3
"""Run Python static security analysis over `lib/` and `scripts/` (issue #962).

CPP ran no Python SAST at all. `grep -rn "bandit" Makefile .woodpecker.yml
pyproject.toml` returned nothing, across 113 tracked Python files - while
`lib/security/` is this repository's own deterministic secret and policy scanner
and `lib/creds/` handles credential retrieval and injection. A repository
shipping security tooling that runs no static analysis over that tooling is the
gap worth closing, independent of what the scan finds.

---------------------------------------------------------------------------
THE INHERITED SKIP LIST, RE-DECIDED - which is the whole of issue #962
---------------------------------------------------------------------------
codex-power-pack already runs bandit, and its Makefile carries the exclusions:

    bandit -r lib scripts -ll --quiet --skip B104,B108,B310,B602

Copying that line is the tempting move and it is measurably the wrong one here.
B602 is `subprocess` with `shell=True` and B108 is an insecure temp-file path -
both are exactly what a repository of shell-out helpers and deploy locks does
constantly, so the inherited suppression silences the findings most likely to be
REAL in this tree. Measured on adoption: of 11 MEDIUM-or-worse findings, that
skip list removes 10 and reports 1.

So the skip list is EMPTY, and the mechanism is different rather than merely
shorter. A `--skip` turns a rule off across the whole tree, forever, invisibly.
This gate records the accepted residual ONE LINE PER (file, rule) in
`.bandit-audit-allow`, with the count and the issue tracking it - so a NEW
`shell=True` in a file that already has one is a finding, a new one in a fresh
file is a finding, and a recorded one that gets FIXED turns the gate red until
its line comes out. A blanket skip can do none of those three.

WHAT THE COUNT DOES NOT ESTABLISH, and the claim is bounded rather than widened
(counter-model review, codex). A line matches on (file, rule, COUNT), so it is a
BASELINE, not a per-site identity: fix one accepted `shell=True` in a file and
introduce a different one in the same file, and the count is unchanged and the
gate stays green. The REPLACEMENT is invisible to it. That is deliberate rather
than unnoticed - the alternatives are a line number, which every edit above it
invalidates, or a snippet hash, which every reformat invalidates, and a ledger
that reddens on unrelated edits is a ledger somebody switches off (ADR 0009).
The larger question - is this still the same accepted site - is answered by
review of the diff that moved it and by #1113's disposition, not here. Pinned as
a known blind spot by
`tests/test_bandit_audit.py::test_a_same_count_site_replacement_is_a_known_blind_spot`,
so the bound is a committed fact rather than a sentence in a comment.

TWO INLINE BYPASSES OF THAT LEDGER ARE REFUSED, and they are DIFFERENT
CHANNELS reported in DIFFERENT FIELDS - which the first cut of this file got
wrong, and which is worth writing down because the two look identical in source.
Measured on bandit 1.9.4:

    input                       results   metrics.nosec   metrics.skipped_tests
    ------------------------    -------   -------------   ---------------------
    eval(input())               B307      0               0
    eval(input())  # nosec      (none)    1               0
    eval(input())  # nosec B307 (none)    0               1

  * a BARE `# nosec` suppresses every rule on the line and increments `nosec`.
  * a RULE-SCOPED `# nosec B307` suppresses that rule and increments
    `skipped_tests` - NOT `nosec`. A gate reading only `nosec` misses it
    entirely, which is what the first cut did.

Both are read, per file, so the finding names where to look.

WHAT `skipped_tests` IS NOT, corrected after measurement (counter-model review,
codex). The first cut read that field as "a `--skip`/`-s` reached the tool" and
said so in its own message. It does not: with `--skip B307` the report carries
`skipped_tests=0` and simply omits the finding. A guard reading it for that
purpose is blind to the exact thing this issue is about, and the registered case
that "proved" it modelled a report bandit never emits - a fixture built to the
author's belief rather than to the tool.

So the CLI-flag question is answered where it can actually fail, in two places
that are not string checks:

  * THE FLAGS ARE SHARED. `BANDIT_FLAGS` below is the single list used by the
    real scan AND by `--selftest`, and the selftest runs from the same cwd
    against a fixture holding a B307 it must report. A suppression flag added
    to that list reddens the selftest before the audit runs - but only for the
    rule the fixture exercises: `--skip B104` would pass the selftest, because
    nothing in that fixture is a B104 (counter-model review pass 2). The
    behavioural half is a spot check on ONE rule, and saying so is the point.
  * SO THE ARGV IS PINNED EXACTLY. `tests/test_bandit_audit.py` asserts
    `BANDIT_FLAGS` equals a literal tuple, which no spelling of a new flag can
    slip past - `--skip=B104` and `-sB104` both defeated a token test, measured
    - and additionally rejects any suppression OPTION by normalized name, so
    the pin cannot be updated into a hole. The Makefile and pipeline are
    checked too, on bandit's own lines rather than on any `--skip` anywhere.

Ambient CONFIG FILES were checked and are not a route on this version: a
`.bandit` at the repository root and a `pyproject.toml [tool.bandit]` section
both had NO effect on the scan (measured 2026-09-20 - bandit needs an explicit
`-c`/`--configfile`, which this gate never passes and the argv assertion
forbids). That is a version-dependent fact rather than a guarantee, so it is
recorded with its date rather than asserted as a property.

---------------------------------------------------------------------------
The shape, inherited rather than invented (ADR 0008, "Adopting a third-party
linter as an instrument")
---------------------------------------------------------------------------
`shellcheck` (#960) settled this shape and the ADR states outright that
`pip-audit` (#961) and `bandit` (#962) take it:

DERIVE THE POPULATION, NEVER GLOB IT. The scan ROOTS are hardcoded so the
enumeration cannot silently narrow itself; the MEMBERS under them are derived by
walking with a declared prune list, and the run reports `source=walk`.

PRINT THE DENOMINATOR ON EVERY RUN, INCLUDING THE CLEAN ONE. `0 findings` means
nothing beside an unstated number of files. A zero-file population is UNKNOWN.

A MISSING BINARY IS UNKNOWN AND EXITS NON-ZERO, NEVER A PASS. So is a file the
tool could not parse. The tempting `command -v bandit || exit 0` goes green on
every machine that lacks the tool.

SUPPRESSIONS ARE VISIBLE OR THEY DO NOT HAPPEN. `.bandit-audit-allow` is tracked
and its counts print on every run, clean ones included.

EXCLUDING A FIXTURE DIRECTORY IS NOT SUPPRESSING A CHECK. Nothing under
`controls/` is scanned by the live path: those trees hold deliberately-bad
inputs that the control itself feeds this gate with `--from-capture`.

---------------------------------------------------------------------------
WHAT THIS GATE DOES NOT CLAIM, stated rather than left to be discovered
---------------------------------------------------------------------------
The population is `lib/` and `scripts/` - issue #962's scope. `tests/`,
`extras/` and the generated `codex/skills/` copies are OUTSIDE it (the two
root-level `*reddit*.py` scripts this paragraph used to name were deleted by
#1041, which corrected the same sentence in docs/scripts.md and not this one),
and the roots print on every run so the claim is bounded rather than silently
narrow. Widening is a decision, not an
omission to be quietly fixed: measured 2026-09-20, bandit over `tests/` reports
9,400 findings, 8,618 of them B101 `assert_used` - which is a description of a
test suite, not a finding about one.

The gate is severity-thresholded at MEDIUM. The LOW band is COUNTED and PRINTED
on every run rather than discarded, so "below the gate" never reads as "not
examined".

AND, SINCE #1114, THE BAND IS ALSO ENUMERATED BY RULE CLASS, because the total
alone could not say the one thing that matters about it. Every LOW rule class
this tree contains was read at the #1114 disposition and each carries a
`reviewed-low <test-id> <issue>` record in `.bandit-audit-allow`, backed by
docs/decisions/0010-bandit-low-band-disposition.md. A LOW finding whose rule
class has NO such record is reported and reddens the gate - not because LOW
gates (it does not, and the threshold is untouched), but because an UNREAD rule
class is a different fact from a read one, and a single integer cannot hold
both. On adoption of this rule the tree's unreviewed count was 0: all 135
findings fall in the 7 reviewed classes, so this gates nothing that existed
when it landed and fires only on a pattern nobody has looked at yet.

THAT IS THE OPPOSITE OF THE `--skip` #962 REJECTED, and the difference is worth
being exact about, because the two would sit in the same file. A `--skip`
REMOVES a distinction the tool could draw; a `reviewed-low` record ADDS one the
gate could not. It suppresses nothing - the LOW band was already below the
threshold - and it cannot suppress anything, because a record's only effect is
to mark its class as read. The reversal trigger for the redden-on-unreviewed
half is recorded in ADR 0010 beside the decision, per ADR 0009.

---------------------------------------------------------------------------
Three inputs, because the control has to run where the harness runs (ADR 0008)
---------------------------------------------------------------------------
LIVE (default)   walk the roots, run bandit, adjudicate. Needs the `bandit`
                 binary, which `uv sync --extra dev` provides.

--from-capture   replay a committed capture of bandit's own JSON. Stdlib only,
                 offline, no bandit binary - so it gives the SAME verdict in the
                 slim CI image, on a dev box with nothing installed, and inside
                 `check-negative-controls.py`, whose `negative-controls` step
                 runs a bare `python3` with no `uv sync`. This is what the
                 registered control exercises. The precedent is
                 `controls/dependency-audit`, which replays pip-audit captures,
                 and `controls/check-oscillation`, which feeds its detector
                 committed `git log` captures because git is absent from the CI
                 image.

--selftest       the live path against two committed fixture trees: one holding
                 a pattern bandit must report at the gated severity, one clean.
                 This is the half `--from-capture` cannot cover - that bandit is
                 actually invoked, and invoked against the files we meant. The
                 CI step runs it BEFORE the real audit, so no clean verdict is
                 issued by a scan that was never shown able to find something.

Neither alone is enough, and saying which one covers which half is the point.

Usage:
    bandit-audit.py [--root DIR] [--allow-file PATH]
    bandit-audit.py --from-capture FILE [--allow-file PATH]
    bandit-audit.py --capture FILE [--root DIR]
    bandit-audit.py --selftest [--root DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

#: NEGATIVE-CONTROL: controls/bandit-audit
#:     Registered per issue #962, under ADR 0008's bound: this is a gate that
#:     lets work THROUGH. `make verify` and the CI `bandit-audit` step read its
#:     green as "no unaccounted MEDIUM+ security finding in lib/ or scripts/",
#:     and nothing downstream re-derives that.
#:
#:     THE ANCHOR IS CxPP's OWN ONE-LINER - `-ll --skip B104,B108,B310,B602`,
#:     no allowlist - because that is the blind implementation this issue
#:     exists to reject, not a strawman written to fail. It misses every
#:     known-bad case here and agrees on the known-good one, so the control's
#:     demonstration IS the issue's thesis rather than an illustration of it.
#:
#:     The registered cases are OFFLINE captures, deliberately. The
#:     `negative-controls` CI step runs a bare `python3` with no `uv sync`, so
#:     a control whose invocation needed the bandit binary would report
#:     UNSIGNALLED there - an environment failure wearing the diagnosis "the
#:     gate stopped discriminating". What the offline cases do NOT establish -
#:     that bandit is invoked, and against the files we meant - is established
#:     by `--selftest` in the CI step instead. Both halves, each where it can
#:     actually run.

SUMMARY = "bandit-audit"
FINDING = "BANDIT-FINDING"
STALE = "BANDIT-STALE"
SUPPRESSION = "BANDIT-SUPPRESSION"
UNKNOWN = "BANDIT-UNKNOWN"
SELFTEST = "BANDIT-SELFTEST"
#: A LOW-band rule class no `reviewed-low` record accounts for (issue #1114).
#: Its own marker rather than a `FINDING`, because the two say different things
#: and a reader acts on them differently: a FINDING is an unaccounted security
#: finding at the gated severity, this is an UNREAD rule class below it. The
#: registered control's `detect_signal` matches both.
LOW_UNREVIEWED = "BANDIT-LOW-UNREVIEWED"
#: A `reviewed-low` record that matched nothing this run. Deliberately NOT in
#: `detect_signal` and deliberately not a finding - see `adjudicate`.
LOW_NOTE = "BANDIT-LOW-NOTE"

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_UNKNOWN = 2

ALLOW_FILE = ".bandit-audit-allow"
CAPTURE_SCHEMA = 1

#: THE UNIVERSE, HARDCODED so the enumeration cannot silently narrow itself
#: (ADR 0008's own phrasing for its census). The MEMBERS under these roots are
#: derived by walking; only the roots are written down, and they are printed on
#: every run so a reader is never told a verdict without being told its subject.
SCAN_ROOTS = ("lib", "scripts")

#: Directories the walk never descends into, and the reason each is here.
#: Excluding a fixture DIRECTORY is not suppressing a check (ADR 0008).
PRUNE = {
    "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".venv", "venv",
}

#: The gated band. LOW is counted and printed, never discarded - see the header.
GATED_SEVERITIES = ("MEDIUM", "HIGH")

#: THE ONE FLAG LIST, shared by the real scan and by `--selftest`, and that
#: sharing is a control rather than tidiness. A suppression flag added here
#: takes effect in BOTH, so the selftest's known-bad fixture stops reporting and
#: the run goes red before the audit is reached. Two separate lists would let a
#: `--skip` be added to the audit while the positive control kept passing, which
#: is precisely the shape this gate exists to refuse.
#:
#: No `-ll`: the severity threshold is applied in-process so the LOW band can be
#: COUNTED instead of vanishing. No `-s`/`--skip`, no `-t`/`--tests`, no
#: `-c`/`--configfile` - see the header. `--exit-zero` because bandit exits 1
#: for findings and 2 for a usage error, so reading the verdict off the exit
#: code would make "found something" and "I was invoked wrong" the same fact;
#: the REPORT is the evidence.
BANDIT_FLAGS = ("-f", "json", "-q", "--exit-zero")

#: bandit resolves a whole tree quickly, but a wedged subprocess must not hold
#: a CI step open until the pipeline's own timeout.
BANDIT_TIMEOUT = 600


class Unknown(Exception):
    """This run could not look. Never a pass, and never printed as one."""


@dataclass(frozen=True)
class Finding:
    path: str
    test_id: str
    severity: str
    line: int
    text: str


@dataclass
class AllowEntry:
    path: str
    test_id: str
    count: int
    issue: str
    source_line: int
    matched: int = 0


@dataclass
class ReviewedLow:
    """One LOW-band rule class that has been READ, and the issue that read it.

    THIS IS NOT A SUPPRESSION, and the distinction is the whole of issue #1114.
    An `AllowEntry` accepts findings that WOULD otherwise gate; a record here
    accepts nothing, because the LOW band is already below the threshold and
    gates nothing to begin with. What it does is the opposite of a `--skip`: it
    ADDS a distinction this gate could not previously draw - between a rule
    class somebody read and dispositioned, and one that has never been looked
    at. Before it, both were a single number.
    """

    test_id: str
    issue: str
    source_line: int
    matched: int = 0


@dataclass
class Ledger:
    """Everything `.bandit-audit-allow` declares, in its two record types."""

    findings: list[AllowEntry]
    reviewed_low: list[ReviewedLow]


# --------------------------------------------------------------------------- #
# The allowlist
# --------------------------------------------------------------------------- #

def parse_allow(path: Path) -> Ledger:
    """Read `.bandit-audit-allow`, or an empty ledger when it is absent.

    An ABSENT file is legitimately empty - a tree with no accepted residual -
    and is not UNKNOWN. An UNREADABLE or MALFORMED one is UNKNOWN: a suppression
    ledger that could not be read leaves every finding's disposition undecided,
    and guessing "nothing is suppressed" would redden a tree that is correctly
    accounted for while guessing the opposite would hide everything.

    TWO RECORD TYPES, AND THEY DO DIFFERENT THINGS (issue #1114):

        finding <path> <test-id> <count> <issue>    accepts GATED findings
        reviewed-low <test-id> <issue>              declares a LOW rule class READ

    An UNRECOGNISED first field is UNKNOWN rather than ignored, which is what
    makes the second type safe to add: a typo cannot degrade into a silently
    skipped line, and a `reviewed-low` record whose rule id is misspelled cannot
    open a hole either - the class it was meant to cover simply stays
    unreviewed and the gate reddens, while the misspelled record matches
    nothing and is named in a NOTE. Both halves of a typo are visible.
    """
    if not path.exists():
        return Ledger([], [])
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise Unknown(f"allowlist {path} is unreadable: {exc}") from exc

    entries: list[AllowEntry] = []
    reviewed: list[ReviewedLow] = []
    seen: dict[tuple[str, str], int] = {}
    seen_low: dict[str, int] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        # WHOLE-LINE COMMENTS ONLY, and a trailing one is a parse error rather
        # than a stripped suffix. `#` is the comment character AND the first
        # character of every issue reference this file exists to carry, so
        # `line.split("#")[0]` would silently eat the `#1113` off every record.
        # The sibling gate learned this the expensive way (#961).
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "reviewed-low":
            if len(parts) != 3:
                raise Unknown(
                    f"allowlist {path} line {number} is not a record this gate understands: "
                    f"{raw.strip()!r} (expected `reviewed-low <test-id> <issue>`)"
                )
            _, test_id, issue = parts
            # ONE LINE PER RULE CLASS, for the reason the finding records give:
            # a duplicate is how a second, differently-reasoned disposition gets
            # appended beside the first instead of replacing it, leaving two
            # issue references for one decision and no way to tell which is live.
            if test_id in seen_low:
                raise Unknown(
                    f"allowlist {path} line {number} repeats reviewed-low {test_id}, already "
                    f"recorded on line {seen_low[test_id]} - one line per rule class, so a "
                    "disposition is revised by editing the record rather than by appending "
                    "beside it"
                )
            seen_low[test_id] = number
            reviewed.append(ReviewedLow(test_id, issue, number))
            continue
        if len(parts) != 5 or parts[0] != "finding":
            raise Unknown(
                f"allowlist {path} line {number} is not a record this gate understands: "
                f"{raw.strip()!r} (expected `finding <path> <test-id> <count> <issue>` "
                "or `reviewed-low <test-id> <issue>`)"
            )
        _, file_path, test_id, count_text, issue = parts
        if not count_text.isdigit() or int(count_text) < 1:
            raise Unknown(
                f"allowlist {path} line {number} declares count {count_text!r}, "
                "which is not a positive integer - a line accepting zero findings "
                "accepts nothing and would read as suppression"
            )
        # A SECOND LINE FOR THE SAME (file, rule) IS UNKNOWN, NOT ADDITIVE.
        # Two lines summing to the observed count and one line naming it are
        # indistinguishable in the verdict, but they are not the same record:
        # a duplicate is how a count gets raised without the original line's
        # issue reference being revisited. Refusing the ambiguity is cheaper
        # than choosing a reading of it.
        key = (file_path, test_id)
        if key in seen:
            raise Unknown(
                f"allowlist {path} line {number} repeats {file_path} {test_id}, already "
                f"recorded on line {seen[key]} - one line per (file, rule), so a count "
                "is raised by editing the record rather than by appending beside it"
            )
        seen[key] = number
        entries.append(AllowEntry(file_path, test_id, int(count_text), issue, number))
    return Ledger(entries, reviewed)


# --------------------------------------------------------------------------- #
# Reading bandit's own report
# --------------------------------------------------------------------------- #

def _all_findings(report: dict, examined: set[str]) -> list[Finding]:
    """Every finding in one bandit JSON report, at every severity.

    `examined` is the population this run enumerated. A finding whose file is
    outside it means the report does not describe the tree we asked about -
    a capture recorded against a different root, or a walk and a scan that
    disagree - so it is UNKNOWN rather than a finding, because attributing it
    would be attributing it to a file nobody looked at.

    ONE VALIDATED PASS, TWO BANDS. The gated and below-threshold views are
    filters of this list rather than two traversals, so the validation above
    cannot come to apply to one band and not the other - which is how a report
    gets validated for the findings that gate and trusted blindly for the ones
    that only get counted.
    """
    results = report.get("results")
    if not isinstance(results, list):
        raise Unknown("bandit report carries no `results` list")

    found: list[Finding] = []
    for raw in results:
        if not isinstance(raw, dict):
            raise Unknown("bandit report carries a result that is not an object")
        path = normalize_path(str(raw.get("filename", "")))
        test_id = str(raw.get("test_id", "")).strip()
        severity = str(raw.get("issue_severity", "")).strip().upper()
        if not path or not test_id or not severity:
            raise Unknown(
                "bandit report carries a result with no filename, test_id or severity"
            )
        if path not in examined:
            raise Unknown(
                f"bandit reported on {path}, which is not in the population this run "
                f"enumerated ({len(examined)} file(s)) - the report and the walk "
                "disagree about what was scanned"
            )
        found.append(Finding(
            path=path,
            test_id=test_id,
            severity=severity,
            line=int(raw.get("line_number", 0) or 0),
            text=str(raw.get("issue_text", "")).strip(),
        ))
    return sorted(found, key=lambda f: (f.path, f.test_id, f.line))


def findings_from_report(report: dict, examined: set[str]) -> list[Finding]:
    """Every GATED finding in one bandit JSON report."""
    return [f for f in _all_findings(report, examined) if f.severity in GATED_SEVERITIES]


def below_threshold_findings(report: dict, examined: set[str]) -> list[Finding]:
    """Every finding this run saw BELOW the gated band.

    Counted and printed rather than dropped: "below the gate" and "not
    examined" are the two states the denominator exists to keep apart, and a
    threshold with no count behind it reads as the second.

    RETURNED AS FINDINGS RATHER THAN AS A NUMBER (issue #1114). A single total
    keeps those two states apart and nothing else: it cannot tell the seven
    rule classes somebody read from an eighth that arrived last week, because
    both are increments of the same integer. The rule classes are what a reader
    dispositions, so they are what this returns.
    """
    return [f for f in _all_findings(report, examined) if f.severity not in GATED_SEVERITIES]


def coverage(report: dict, expected: set[str]) -> tuple[set[str], list[str]]:
    """`(files bandit actually examined, per-file scan errors)`.

    TWO CHECKS, NOT ONE, and the second is the one that is easy to miss. A file
    bandit cannot parse still appears in `metrics` with a `loc` count - measured
    directly: a file containing `def broken(:` produced
    `metrics["probe/c.py"] = {"loc": 1, ...}` and an entry in `errors`. So
    membership in `metrics` says a file was READ, not that it was ANALYSED, and
    a report whose `errors` list is non-empty has silently skipped part of its
    own population while printing a clean `results`. That is the same shape as
    pip-audit's `skip_reason` one gate over (#961), where a single skipped
    dependency produced `ok - 1 package(s), 0 findings`.
    """
    metrics = report.get("metrics")
    if not isinstance(metrics, dict):
        raise Unknown("bandit report carries no `metrics` object")
    seen = {normalize_path(k) for k in metrics if k != "_totals"}
    errors = report.get("errors")
    if not isinstance(errors, list):
        raise Unknown("bandit report carries no `errors` list")
    messages = [
        f"{normalize_path(str(e.get('filename', '<unnamed>')))}: {e.get('reason', 'no reason given')}"
        for e in errors if isinstance(e, dict)
    ]
    missing = sorted(expected - seen)
    if missing:
        shown = missing[:5]
        raise Unknown(
            f"{len(missing)} enumerated file(s) do not appear in bandit's own metrics, so "
            "this run examined less than it was asked to: " + ", ".join(shown)
            + ("..." if len(missing) > len(shown) else "")
        )
    if messages:
        raise Unknown(
            f"bandit could not analyse {len(messages)} file(s), which therefore report no "
            "findings for a reason that is not cleanliness: " + "; ".join(messages)
        )
    return seen, messages


def totals(report: dict) -> dict:
    metrics = report.get("metrics")
    if not isinstance(metrics, dict):
        raise Unknown("bandit report carries no `metrics` object")
    tot = metrics.get("_totals")
    if not isinstance(tot, dict):
        raise Unknown("bandit report carries no `metrics._totals` object")
    return tot


def inline_suppressions(report: dict) -> list[tuple[str, str, int]]:
    """`[(file, kind, count)]` for every inline suppression bandit recorded.

    THE LEDGER'S BYPASS, CLOSED IN BOTH ITS FORMS. `.bandit-audit-allow` is
    tracked, counted and printed on every run; a `# nosec` comment is none of
    those - it deletes the finding from the report before this gate sees it.

    TWO FIELDS, NOT ONE, and the first cut read only the first (counter-model
    review, codex). Measured on bandit 1.9.4:

        eval(input())  # nosec        -> metrics.nosec = 1, skipped_tests = 0
        eval(input())  # nosec B307   -> metrics.nosec = 0, skipped_tests = 1

    The two comments are a character apart in source and land in different
    fields, so reading `nosec` alone leaves the rule-scoped form - the one a
    careful author is MORE likely to write, since it suppresses less - entirely
    invisible. Both are read, per file, so a finding names where to look rather
    than only that something happened somewhere.
    """
    metrics = report.get("metrics", {})
    found: list[tuple[str, str, int]] = []
    for name, per_file in sorted(metrics.items()):
        if name == "_totals" or not isinstance(per_file, dict):
            continue
        if per_file.get("nosec"):
            found.append((normalize_path(name), "bare `# nosec`", int(per_file["nosec"])))
        if per_file.get("skipped_tests"):
            found.append((normalize_path(name), "rule-scoped `# nosec <ID>`",
                          int(per_file["skipped_tests"])))
    return found


def normalize_path(raw: str) -> str:
    """A report path as the walk spells it: relative, forward slashes, no `./`."""
    text = raw.replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text


# --------------------------------------------------------------------------- #
# The live path
# --------------------------------------------------------------------------- #

def resolve_bandit(root: Path | None = None) -> list[str]:
    """The argv prefix that runs bandit, or UNKNOWN.

    `bandit` on PATH first, which is what `uv run --extra dev` provides and what
    the Makefile target and the CI step both arrange - so the version is the one
    `uv.lock` pins and the verdict does not depend on which box ran it. The
    project venv is tried next for a caller who invoked this with a bare
    `python3` after a sync. `uvx` is the last resort and is NOT silent about
    itself: it resolves whatever PyPI serves today, which is the version skew
    the lock exists to remove.

    EVERY PATH RETURNED IS ABSOLUTE (counter-model review, codex). The venv
    fallback returned a RELATIVE `.venv/bin/bandit`, and every subprocess this
    module launches sets its own `cwd` - so on a box with bandit only in the
    project venv, `python3 scripts/bandit-audit.py --selftest` died with
    `FileNotFoundError: '.venv/bin/bandit'` and reported UNKNOWN. Reproduced
    before the fix; a relative argv[0] is resolved against the CHILD's cwd, not
    the parent's.
    """
    direct = shutil.which("bandit")
    if direct:
        return [str(Path(direct).resolve())]
    venv = (root or Path.cwd()) / ".venv" / "bin" / "bandit"
    if venv.is_file() and os.access(venv, os.X_OK):
        return [str(venv.resolve())]
    uvx = shutil.which("uvx")
    if uvx:
        uvx = str(Path(uvx).resolve())
        print(
            f"{SUMMARY}: NOTE - bandit is not on PATH and no project venv holds it, so this "
            "run uses `uvx bandit`, whose version is whatever PyPI serves rather than the "
            "one uv.lock pins. Run `uv sync --extra dev` for the pinned tool.",
            file=sys.stderr,
        )
        return [uvx, "bandit"]
    raise Unknown(
        "bandit is not on PATH, not in .venv/bin, and `uvx` is not available to run it - "
        "this run examined nothing. Run `uv sync --extra dev`."
    )


def discover(root: Path) -> list[str]:
    """Every `.py` file under the declared roots, by walking with a prune list.

    AN ENUMERATION THAT FAILS PARTWAY MUST NOT YIELD A SHORT LIST AND A CLEAN
    VERDICT (counter-model review pass 2, codex). `os.walk` swallows every
    directory-read error by default and simply omits the subtree - so an
    unreadable `lib/security/` took the population from 113 files to 94 and the
    audit still printed `ok`, exit 0. The coverage check downstream compares
    bandit's report against THIS list, so it agrees with an enumeration that was
    already incomplete and cannot see the gap. Reproduced before the fix.

    `onerror` makes the failure loud, and a DECLARED ROOT that is absent or
    unreadable is refused outright for the same reason: "the root is not there"
    and "the root is clean" are not the same fact, and only one of them is a
    verdict this gate may print.
    """
    found: list[str] = []
    for name in SCAN_ROOTS:
        base = root / name
        if not base.is_dir():
            raise Unknown(
                f"declared scan root {name}/ is not a directory under {root} - this run "
                "examined less than it was asked to, which is not the same as finding nothing"
            )

        def fail(exc: OSError) -> None:
            raise Unknown(
                f"could not enumerate {getattr(exc, 'filename', '<unknown>')}: {exc} - "
                "the file list is incomplete, so a clean verdict would be about a "
                "population this run never established"
            )

        for dirpath, dirnames, filenames in os.walk(base, onerror=fail):
            dirnames[:] = sorted(d for d in dirnames if d not in PRUNE)
            for filename in sorted(filenames):
                if filename.endswith(".py"):
                    whole = Path(dirpath) / filename
                    found.append(whole.relative_to(root).as_posix())
    return sorted(found)


def scan(root: Path, prefix: list[str], targets: list[str]) -> dict:
    """bandit's raw JSON report over EXACTLY the paths named in `targets`.

    THE ENUMERATED FILES ARE PASSED EXPLICITLY, not `-r lib scripts` (counter-
    model review, codex). `discover()` prunes `.venv`, `venv` and the cache
    directories; bandit's own `-r` recursion does not, so the two traversals
    disagreed the moment anything created a virtualenv under a scanned root.
    Measured: `lib/.venv/site-packages/dep.py` appeared in the report and not in
    the population, and the gate correctly - but uselessly - reported UNKNOWN
    because a neighbour's installed dependency had changed. Handing bandit the
    file list makes the two populations identical BY CONSTRUCTION, so there is
    no second exclusion list to keep in sync with the first.
    """
    cmd = [*prefix, *BANDIT_FLAGS, *targets]
    try:
        proc = subprocess.run(
            cmd, cwd=root, capture_output=True, text=True,
            timeout=BANDIT_TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise Unknown(f"bandit timed out after {BANDIT_TIMEOUT}s under {root}") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise Unknown(f"bandit could not be run: {exc}") from exc
    try:
        return json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        tail = (proc.stderr or "").strip().splitlines()
        raise Unknown(
            f"bandit returned no usable report (exit {proc.returncode}): "
            f"{tail[-1] if tail else 'no diagnostic'} - this run examined nothing"
        ) from exc


def collect_live(root: Path) -> dict:
    """`{files, report}` for the declared roots of this tree."""
    files = discover(root)
    if not files:
        raise Unknown(
            f"no .py file found under {'/, '.join(SCAN_ROOTS)}/ in {root} - "
            "a zero-file population is not a clean one"
        )
    report = scan(root, resolve_bandit(root), files)
    return {"roots": list(SCAN_ROOTS), "files": files, "report": report}


# --------------------------------------------------------------------------- #
# The capture
# --------------------------------------------------------------------------- #

def read_capture(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Unknown(f"capture {path} is unreadable: {exc}") from exc
    if payload.get("schema") != CAPTURE_SCHEMA:
        raise Unknown(f"capture {path} declares schema {payload.get('schema')!r}, not {CAPTURE_SCHEMA}")
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise Unknown(f"capture {path} names no files - a zero-file population is not a clean one")
    if not isinstance(payload.get("report"), dict):
        raise Unknown(f"capture {path} carries no `report` object")
    roots = payload.get("roots")
    if not isinstance(roots, list) or not roots:
        raise Unknown(f"capture {path} names no roots, so its verdict has no stated subject")
    return {
        "roots": [str(r) for r in roots],
        "files": [normalize_path(str(f)) for f in files],
        "report": payload["report"],
    }


def write_capture(path: Path, collected: dict) -> None:
    payload = {"schema": CAPTURE_SCHEMA, **collected}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# The verdict
# --------------------------------------------------------------------------- #

def adjudicate(collected: dict, allow: Ledger, source: str) -> tuple[list[str], int]:
    """Print the report, return `(finding lines, exit code)`.

    Every gated finding is one of two: SUPPRESSED (an allowlist line for its
    file and rule still has room in its count) or GATING (nothing accounts for
    it). Plus STALE: an allowlist line whose count is higher than what this run
    reported, including the zero case where the finding is gone entirely.

    And, below the threshold, one further distinction (issue #1114): a rule
    class somebody READ against a `reviewed-low` record, versus one that has
    never been looked at. That is not a severity decision - the LOW band's
    severity is still below the gate and no LOW finding gates because of its
    severity - it is a REVIEW decision, and it is the only one of the two that
    a count can never carry.
    """
    files = set(collected["files"])
    report = collected["report"]
    roots = ", ".join(collected["roots"])

    coverage(report, files)
    tot = totals(report)

    found = findings_from_report(report, files)
    observed = Counter((f.path, f.test_id) for f in found)
    index = {(e.path, e.test_id): e for e in allow.findings}

    lines: list[str] = []

    # AN INVISIBLE SUPPRESSION IS A FINDING, and it is checked before the
    # findings themselves: a `# nosec` deletes its result from the report, so
    # anything downstream of here is already reasoning about a report someone
    # edited from inside the source tree.
    for path, kind, count in inline_suppressions(report):
        lines.append(
            f"{SUPPRESSION}: {path} carries {count} {kind}, which removes a finding from the "
            f"report before this gate sees it. Delete the comment and record the finding in "
            f"{ALLOW_FILE}, where it is tracked, counted and printed on every run."
        )

    for finding in found:
        entry = index.get((finding.path, finding.test_id))
        if entry is not None and entry.matched < entry.count:
            entry.matched += 1
            continue
        if entry is not None:
            entry.matched += 1
            continue
        lines.append(
            f"{FINDING}: {finding.path}:{finding.line} {finding.test_id} "
            f"({finding.severity}) - {finding.text}. No {ALLOW_FILE} line accounts for it. "
            f"Fix it, or record it with the issue tracking it."
        )

    # THE EXCESS IS REPORTED PER (file, rule), NOT PER FINDING, because a count
    # that moved from 1 to 2 is one fact and printing it twice reads as two.
    for (path, test_id), count in sorted(observed.items()):
        entry = index.get((path, test_id))
        if entry is None or count <= entry.count:
            continue
        lines.append(
            f"{FINDING}: {path} {test_id} reported {count} time(s), but {ALLOW_FILE} "
            f"line {entry.source_line} accepts {entry.count} ({entry.issue}). "
            f"{count - entry.count} new site(s) - fix them, or raise the count with a reason."
        )

    # A LINE THAT ACCOUNTS FOR LESS THAN IT CLAIMS IS STALE, and this is the
    # direction that keeps the residual honest. Without it a suppression
    # outlives the finding it records and becomes a permanent blindfold nobody
    # re-reads. The zero case and the shortfall case are the same rule and get
    # different sentences, because "it is gone" and "there are fewer now" send a
    # reader to different places.
    stale: list[AllowEntry] = []
    for entry in allow.findings:
        seen_count = observed.get((entry.path, entry.test_id), 0)
        if seen_count >= entry.count:
            continue
        stale.append(entry)
        if seen_count == 0:
            why = (
                "which this run did not report at all"
                if entry.path in files
                else "whose file is not in the population this run examined"
            )
            lines.append(
                f"{STALE}: {ALLOW_FILE} line {entry.source_line} accepts {entry.count} "
                f"{entry.test_id} finding(s) in {entry.path} ({entry.issue}), {why} - "
                "remove the line."
            )
        else:
            lines.append(
                f"{STALE}: {ALLOW_FILE} line {entry.source_line} accepts {entry.count} "
                f"{entry.test_id} finding(s) in {entry.path} ({entry.issue}), but this run "
                f"reported {seen_count} - lower the count to {seen_count}."
            )

    # ------------------------------------------------------------------- #
    # The band below the threshold - issue #1114
    # ------------------------------------------------------------------- #
    # A LOW finding NEVER gates because of its severity; that is the #962
    # threshold decision and this does not touch it. What gates here is the
    # absence of a REVIEW: a rule class nobody has read yet, which the total
    # alone cannot express, because an eighth class and a fifty-eighth finding
    # of the first class move the same integer by one.
    low = below_threshold_findings(report, files)
    low_by_rule = Counter(f.test_id for f in low)
    reviewed_index = {r.test_id: r for r in allow.reviewed_low}
    for test_id, count in sorted(low_by_rule.items()):
        record = reviewed_index.get(test_id)
        if record is not None:
            record.matched += count
            continue
        where = sorted({f.path for f in low if f.test_id == test_id})
        shown = ", ".join(where[:3]) + ("..." if len(where) > 3 else "")
        lines.append(
            f"{LOW_UNREVIEWED}: {test_id} reported {count} time(s) in {len(where)} file(s) "
            f"below severity>={GATED_SEVERITIES[0]} ({shown}), and no {ALLOW_FILE} "
            f"`reviewed-low` record accounts for that rule class. Below the gate is not "
            f"the same as read: disposition it (see docs/decisions/"
            f"0010-bandit-low-band-disposition.md), then record it - or fix the sites."
        )

    # A RECORD THAT MATCHED NOTHING IS A NOTE, NOT A FINDING, and the asymmetry
    # with the STALE rule above is deliberate rather than an oversight. A stale
    # `finding` line is a SUPPRESSION outliving its finding - a blindfold, so it
    # reddens. A `reviewed-low` record suppresses nothing, so one whose class has
    # left the tree hides nothing; reddening for it would mean deleting the last
    # `import subprocess` in a file turns the build red, which is precisely the
    # "reddens on unrelated edits, so somebody switches it off" failure ADR 0009
    # names. Pinned by tests/test_bandit_audit.py rather than left to this
    # comment.
    for record in sorted(allow.reviewed_low, key=lambda r: r.source_line):
        if record.matched:
            continue
        print(
            f"{LOW_NOTE}: {ALLOW_FILE} line {record.source_line} records {record.test_id} as a "
            f"reviewed LOW rule class ({record.issue}), and this run reported none. Harmless - "
            "it suppresses nothing - but the record now accounts for nothing and can be removed.",
            file=sys.stderr,
        )

    gating = sum(1 for line in lines if line.startswith(FINDING))
    unreviewed = sum(1 for line in lines if line.startswith(LOW_UNREVIEWED))
    suppressed = sum(min(e.matched, e.count) for e in allow.findings)
    loc = int(tot.get("loc") or 0)

    residual = (
        f", {suppressed} accepted ({', '.join(sorted({e.issue for e in allow.findings}))})"
        if allow.findings else ""
    )
    verdict = "ok - " if not lines else ""
    # BOTH NUMBERS, because either alone is the claim this gate must not make.
    # "135 below threshold" says how much is down there and nothing about
    # whether anyone looked; "7 reviewed" over an unstated population says
    # everything was read without saying how much there was. Printed together
    # they are checkable against each other, and a gap between them is already
    # explained by the LOW-UNREVIEWED lines above.
    print(
        f"{SUMMARY}: {verdict}{len(files)} file(s) examined under {roots} "
        f"(source={source}), {loc} loc, {gating} gating finding(s) at "
        f"severity>={GATED_SEVERITIES[0]}, {len(stale)} stale allowlist line(s), "
        f"{len(low)} below threshold in {len(low_by_rule)} rule class(es), "
        f"{len(low_by_rule) - unreviewed} reviewed (#1114){residual}"
    )
    if low:
        print(
            f"{SUMMARY}: below-threshold band by rule - "
            + ", ".join(f"{rule} x{count}" for rule, count in low_by_rule.most_common())
        )
    return lines, EXIT_FINDING if lines else EXIT_OK


# --------------------------------------------------------------------------- #
# The live positive control
# --------------------------------------------------------------------------- #

def selftest(root: Path) -> int:
    """Prove the LIVE path can still find something, before any clean verdict.

    `--from-capture` cannot establish this: it replays a report rather than
    producing one, so it is silent on whether bandit is invoked at all and on
    whether it is invoked against the files we meant. A clean run of a scan that
    cannot see is indistinguishable from a clean tree, so the CI step runs this
    FIRST and the real audit only afterwards.
    """
    live = root / "controls" / "bandit-audit" / "live"
    bad = live / "bad-known-finding"
    good = live / "good-clean"
    for path in (bad, good):
        if not path.is_dir():
            print(f"{UNKNOWN}: selftest fixture {path} is absent - this run proved nothing",
                  file=sys.stderr)
            return EXIT_UNKNOWN

    prefix = resolve_bandit(root)
    verdicts: dict[str, tuple[dict, list[str]]] = {}
    for path in (bad, good):
        # THE SAME FLAGS AND THE SAME CWD AS THE REAL SCAN, deliberately
        # (counter-model review, codex). `BANDIT_FLAGS` is one list and `scan()`
        # is one function, so a suppression flag added for the audit is added
        # here too - and this fixture's B307 then stops being reported, which
        # turns the selftest red BEFORE the audit runs. Running the fixture
        # under its own cwd and its own hand-written flags is what would let the
        # audit be quietly narrowed while its positive control kept passing.
        expected = sorted(f.relative_to(root).as_posix() for f in sorted(path.rglob("*.py")))
        if not expected:
            print(f"{UNKNOWN}: selftest fixture {path.relative_to(root)} holds no .py file",
                  file=sys.stderr)
            return EXIT_UNKNOWN
        try:
            report = scan(root, prefix, expected)
        except Unknown as exc:
            print(f"{UNKNOWN}: selftest fixture {path.relative_to(root)} - {exc}", file=sys.stderr)
            return EXIT_UNKNOWN
        # EXAMINED, BEFORE ADJUDICATED - the positive control's own positive
        # control. Reading findings alone cannot separate "scanned the clean
        # fixture and found nothing" from "scanned nothing": a bandit returning
        # `{"results": []}` for an empty scan passes a naive selftest and prints
        # its success message, which is the defect this whole file exists to
        # prevent sitting inside the thing built to prevent it. The sibling gate
        # found this one in review (#961); it is not re-found here, it is
        # inherited.
        try:
            coverage(report, set(expected))
        except Unknown as exc:
            print(f"{UNKNOWN}: selftest fixture {path.relative_to(root)} - {exc}", file=sys.stderr)
            return EXIT_UNKNOWN
        gated = [
            r for r in report.get("results", []) or []
            if str(r.get("issue_severity", "")).upper() in GATED_SEVERITIES
        ]
        verdicts[path.name] = (report, sorted({str(r.get("test_id")) for r in gated}))

    bad_ids = verdicts["bad-known-finding"][1]
    good_ids = verdicts["good-clean"][1]

    problems: list[str] = []
    if not bad_ids:
        problems.append(
            f"the known-bad fixture {bad.relative_to(root)} reported NOTHING at "
            f"severity>={GATED_SEVERITIES[0]}, so a clean verdict from this run would say "
            "nothing about the tree"
        )
    if good_ids:
        problems.append(
            f"the clean fixture {good.relative_to(root)} reported {', '.join(good_ids)} - "
            "until it is clean, this gate cannot show it is not wedged at 'fail'"
        )
    if problems:
        for problem in problems:
            print(f"{SELFTEST}: {problem}", file=sys.stderr)
        print(f"{SELFTEST}: failed")
        return EXIT_FINDING
    print(
        f"{SELFTEST}: ok - the live path reported {', '.join(bad_ids)} on the known-bad "
        "fixture and nothing on the clean one"
    )
    return EXIT_OK


# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="tree to scan (default: the current directory)")
    parser.add_argument("--allow-file", default=None,
                        help=f"suppression ledger (default: <root>/{ALLOW_FILE})")
    parser.add_argument("--from-capture", default=None, metavar="FILE",
                        help="replay a committed capture instead of running bandit (offline)")
    parser.add_argument("--capture", default=None, metavar="FILE",
                        help="write this run's raw bandit report to FILE")
    parser.add_argument("--selftest", action="store_true",
                        help="prove the live path can report a known finding, and not a clean tree")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    allow_path = Path(args.allow_file) if args.allow_file else root / ALLOW_FILE

    try:
        if args.selftest:
            return selftest(root)
        if args.from_capture:
            collected, source = read_capture(Path(args.from_capture)), "capture"
        else:
            collected, source = collect_live(root), "walk"
        if args.capture:
            write_capture(Path(args.capture), collected)
        allow = parse_allow(allow_path)
        lines, code = adjudicate(collected, allow, source)
    except Unknown as exc:
        # Printed alone, and never alongside a summary line: a run that could not
        # look must not also emit a sentence shaped like a verdict about the tree.
        print(f"{UNKNOWN}: {exc}", file=sys.stderr)
        return EXIT_UNKNOWN
    for line in lines:
        print(line, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
