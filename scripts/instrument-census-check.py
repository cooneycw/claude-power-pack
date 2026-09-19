#!/usr/bin/env python3
"""Derive ADR 0008's census MEMBERSHIP from `scripts/` (issue #1060).

ADR 0008 enumerates the instruments whose verdicts are consumed without being
re-derived - the ones its bound says need a committed negative control. That
table is the denominator `check-negative-controls.py` prints its coverage
against, and it is typed by hand.

WHAT WAS ALREADY FIXED, AND WHAT WAS NOT. Issue #1002 removed the hand-written
COUNT from the census note, on the correct grounds that "a count written in
prose is stale from the next append onward, which is the same
hand-maintained-number failure this ADR's own subject is about". The count is
now parsed from the table. The table's MEMBERSHIP is still appended by hand, and
nothing notices when it is not - so deriving the count made the omission harder
to see, not easier: `65` reads as "the census is current" when it only means
"the table has 65 rows".

THE DEMONSTRATED INSTANCE. `scripts/counter-model-receipt.py` was created on
2026-09-15 by `ffc315a` (#1001) and appeared in neither table. It is ADR 0007's
evidence artifact, and it has since produced #1047 (the implementer field is a
copied literal) and #1048 (13 of 13 reviewer fields identical). The one
instrument the enumeration missed is the one that shipped carrying the defect
the enumeration exists to prevent. That is not a coincidence worth hoping about
twice.

WHY AN ABSENT INSTRUMENT IS WORSE THAN AN UNCONTROLLED ONE. An enumerated row
with no control is VISIBLE: it is in the denominator, it is one of the `65 - 13`
that the coverage line is explicitly about, and anyone reading the ADR can see
it waiting. An instrument in neither table is in no count at all. It is not
reported as uncontrolled, it is not reported as excluded, and the only way to
find it is for someone to notice its absence from a document nobody reads
line-by-line.

WHAT THIS GATE ASKS, AND WHAT IT DELIBERATELY DOES NOT
------------------------------------------------------
It asks ONE question: *is every file in `scripts/` accounted for* - named by a
census row, or named by the exclusions table with a reason. It never asks
whether an accounted instrument HAS a control.

That boundary is the whole design. A gate that went red on "enumerated but
uncontrolled" would fail 54 rows the day it landed, and a gate that fails
everything on day one is switched off inside a week - which is the oscillation
ADR 0009 exists to predict, arriving as the remedy for the problem rather than
as the problem. The thing made loud here is NOBODY LOOKED. Not yet done stays
quiet, visible, and counted.

THE MATCHING RULE - FIRST BACKTICKED TOKEN, INSTRUMENT COLUMN
-------------------------------------------------------------
A census row is `| N | <instrument> | <verdict contract> | <consumer> | <class> |`
and the instrument is COLUMN 2. Three extraction rules were measured against
the real document before this one was chosen, and the two rejected ones are
recorded because each looks right until it is counted:

  every backticked token, whole row   13 unaccounted, 110 non-file subjects.
                                      Seven of the 13 were FALSE - the census
                                      names `branch-protection.sh check` and
                                      `codex-skill-sync.py --check`, so a
                                      whole-token compare misses the file. The
                                      110 is the verdict-contract and consumer
                                      columns bleeding in: `FLOW_CLAIM:`,
                                      `/flow:auto`, `ok`, `nothing`.

  every backticked token, column 2    7 unaccounted, 26 non-file subjects. The
                                      26 still carries flag and subcommand
                                      noise from multi-backtick cells
                                      (`--strict`, `deep`, `quick`, `resume`).

  FIRST backticked token, column 2    8 unaccounted, 14 non-file subjects.

The third is this file's rule, and it is the one `scripts-inventory-check.py`
already applies to headings, for the same reason stated there: "``## `alpha`
(calls `beta`)`` is a section about `alpha`", and letting an incidental mention
count "would let a neighbour's prose stand in as an undocumented script's
entry". Row 34 is ```eli5-vendor.py` (manifest; `eli5-core-drift.sh` ...)`` - a row
ABOUT the vendor script that mentions the drift script. Under the first-token
rule `eli5-core-drift.sh` reads UNACCOUNTED, and that is correct rather than a
false positive: if it is an instrument it is owed its own accounting, and if it
is not it is owed an exclusion line.

The head word of the token is taken, so `branch-protection.sh check` accounts
for `branch-protection.sh`. A subcommand narrows WHICH verdict the row is about;
it does not make the row about a different file.

THE COMPARE IS THE EXACT FILENAME, never the stem. An earlier cut also accepted
a match on `Path(name).stem`, which let `cpp-memory.py` be accounted for by the
exclusion naming the DIFFERENT file `cpp-memory` - a new instrument shipping
green under a neighbour's line, which is precisely what this gate exists to
stop. Found by the counter-model review (codex, gpt-6-astra) on this branch.
Measured before removing it: NO file in the real tree was accounted for by its
stem alone, so the fallback bought nothing and cost the distinction. The one
extensionless script, `cpp-memory`, matches by name because its name IS its stem.

THE EXCLUSIONS TABLE READS ALL ITS TOKENS, and that asymmetry is deliberate. Its
first column is a POPULATION - one cell lists fourteen installers and generators
- where the census's is a single subject. Reading only the first token there
would silently un-exclude thirteen of them.

BOTH DIRECTIONS, because a membership list lies in two ways
------------------------------------------------------------
  UNACCOUNTED  a file in `scripts/` named by neither table. The drift this
               issue is about.
  STALE        a subject naming neither a live file nor a declared external.
               What a row for a deleted script looks like. Without it the
               census keeps describing tooling that no longer exists, and the
               denominator silently inflates - which moves the coverage
               fraction in the flattering direction.

NON-FILE SUBJECTS ARE DECLARED IN THE DOCUMENT, not listed in here. Fourteen
census rows name things with no file under `scripts/` for a marker to live in -
`ruff`, `mypy`, `pytest`, `gitleaks`, `hadolint`, `make`, and the `lib.*` module
entry points. They are declared on an `instrument-census: external-subjects:`
marker inside the ADR, so the declaration sits beside what it governs and
travels with any tree this gate is pointed at.

That list NARROWS what is checked, so it is built to fail LOUDLY: a new external
subject is STALE until someone declares it. A list that narrows and fails quietly
is a list that erases its own findings.

Stdlib-only, git-free and offline, so `make verify` and the slim CI image give
the same verdict.

Usage:
    instrument-census-check.py [--root DIR]

Output: one `UNACCOUNTED:` / `STALE:` line per finding, provenance counts, then
a verdict line. Exit 0 when every file is accounted for and every subject
resolves, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: NEGATIVE-CONTROL: controls/instrument-census
#:
#: This gate lets work THROUGH - `make verify` and the CI `instrument-census-check`
#: step both read its green as "every instrument in this tree is accounted for",
#: and nothing downstream re-derives that. ADR 0008's bound therefore requires a
#: committed case (class G). The registration lives in THIS file because that is
#: what `check-negative-controls.py` enumerates: a control directory alone is
#: invisible to the battery, which then reports PASS over a register the new
#: control is not in.

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The census, relative to the tree being checked.
ADR_REL = "docs/decisions/0008-instrument-negative-control-bound.md"

#: The directory whose population the census must account for.
SCRIPTS_REL = "scripts"

#: A numbered census row. The leading integer is what distinguishes an
#: enumeration row from the header, the separator, and the three other tables in
#: the document - matching on "starts with a pipe" swept all of them in.
CENSUS_ROW_RE = re.compile(r"^\|\s*\d+\s*\|")

#: The exclusions table's heading. Its rows are a different shape from the
#: census's - population in column 1, reason in column 2, no row number - so it
#: is located by section rather than by row pattern.
EXCLUSIONS_HEADING_RE = re.compile(r"^#{2,}\s+Excluded,\s+with\s+the\s+reason\s*$")

#: A markdown table separator (`|---|---|`), which is not a row.
SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|?\s*$")

#: Subjects with no file under `scripts/`, declared inside the document:
#:
#:     <!-- instrument-census: external-subjects: ruff, mypy, pytest -->
#:
#: Read from the ADR rather than hardcoded here so the declaration lives beside
#: the table it describes. Several markers may appear; all are unioned.
DECLARE_RE = re.compile(
    r"<!--\s*instrument-census:\s*external-subjects:\s*(.*?)\s*-->",
    re.IGNORECASE | re.DOTALL,
)

#: An HTML comment is the document's author talking to the next editor, not the
#: document speaking. A row wrapped in `<!-- ... -->` does not render in the
#: census a reader sees, so reading it as a live row is a FALSE GREEN: comment
#: out row 73 and this gate still reports its subject accounted for while the
#: table no longer enumerates it. Found by the counter-model review (codex,
#: gpt-6-astra) on this branch.
#:
#: THE ORDER IS LOAD-BEARING and the sibling gate paid for it first: the
#: declaration marker below IS an HTML comment, so it must be read BEFORE
#: comments are stripped. Stripping first deletes the externals list and every
#: third-party subject reports STALE.
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

#: A fenced block is an EXAMPLE, not the document speaking. This gate is wrong in
#: both directions if it reads one: an illustrative census row accounts for a
#: script that has no real row (a false GREEN, the worst direction for a
#: membership check), and an illustrative subject naming no file reports STALE and
#: blocks every merge in the repository. Matched by character and length per
#: CommonMark, so the inner ``` of a ````-fenced example is not read as its close.
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*(.*)$")

BACKTICKED_RE = re.compile(r"`([^`]+)`")


def unfenced(text: str) -> str:
    """The document with every fenced example removed."""
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        marker = FENCE_RE.match(line)
        if fence is None:
            if marker:
                fence = marker.group(1)
            else:
                out.append(line)
            continue
        if (
            marker
            and marker.group(1)[0] == fence[0]
            and len(marker.group(1)) >= len(fence)
            and not marker.group(2).strip()
        ):
            fence = None
    return "\n".join(out)


def cells(line: str) -> list[str]:
    """The cells of a markdown table row, outer pipes stripped."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def subject_of(token: str) -> str:
    """The file a backticked token is about.

    The HEAD WORD, so `branch-protection.sh check` is about
    `branch-protection.sh`: a subcommand narrows which verdict the row covers, it
    does not make the row about some other file.
    """
    stripped = token.strip()
    return stripped.split()[0] if stripped else ""


def table_text(text: str) -> str:
    """The document's own table rows - fenced examples, then HTML comments, removed.

    Declarations are read from `unfenced` instead, because the marker is itself a
    comment. Both readers strip fences first, so a fenced example can neither
    account for a script nor widen the externals list.
    """
    return COMMENT_RE.sub("", unfenced(text))


def census_subjects(text: str) -> list[str]:
    """One subject per numbered census row: the FIRST backticked token of column 2.

    Only the first - see the module docstring. A row that mentions a second
    script in passing is a row about the first one.
    """
    subjects: list[str] = []
    for line in table_text(text).splitlines():
        if not CENSUS_ROW_RE.match(line):
            continue
        row = cells(line)
        if len(row) < 2:
            continue
        tokens = BACKTICKED_RE.findall(row[1])
        if not tokens:
            continue
        subject = subject_of(tokens[0])
        if subject:
            subjects.append(subject)
    return subjects


def exclusion_subjects(text: str) -> tuple[list[str], bool]:
    """Every backticked subject in the exclusions table's first column.

    Returns `(subjects, found)`. ALL tokens, not just the first: that column
    holds a POPULATION - one cell names fourteen installers and generators -
    where a census cell names one instrument.

    `found` is returned rather than inferred from an empty list because the two
    need opposite responses. A missing section means this gate cannot see the
    exclusions at all and every legitimately-excluded file would report
    UNACCOUNTED; that is a broken read, not a finding.
    """
    subjects: list[str] = []
    found = False
    in_section = False
    for line in table_text(text).splitlines():
        if EXCLUSIONS_HEADING_RE.match(line):
            in_section = True
            found = True
            continue
        if in_section and line.startswith("#"):
            in_section = False
            continue
        if not in_section or not line.startswith("|") or SEPARATOR_RE.match(line):
            continue
        row = cells(line)
        if not row:
            continue
        for token in BACKTICKED_RE.findall(row[0]):
            subject = subject_of(token)
            if subject:
                subjects.append(subject)
    return subjects, found


def declared_externals(text: str) -> set[str]:
    """Subjects the document declares have no file under `scripts/`."""
    declared: set[str] = set()
    for match in DECLARE_RE.finditer(unfenced(text)):
        for name in match.group(1).replace("\n", " ").split(","):
            cleaned = name.strip().strip("`")
            if cleaned:
                declared.add(cleaned)
    return declared


def script_files(root: Path) -> dict[str, str]:
    """Every regular file directly under `scripts/`, mapped name -> name.

    DERIVED FROM THE TREE, never from a list in here: a gate that hardcodes the
    population it is checking has the very bug it exists to catch. Directories
    are skipped - `__pycache__` is not an instrument.
    """
    scripts_dir = root / SCRIPTS_REL
    return {path.name: path.name for path in sorted(scripts_dir.iterdir()) if path.is_file()}


def run_check(root: Path) -> int:
    adr = root / ADR_REL
    scripts_dir = root / SCRIPTS_REL

    if not scripts_dir.is_dir():
        print(f"instrument-census-check: no {SCRIPTS_REL}/ under {root}; nothing compared.")
        return 1
    if not adr.is_file():
        print(f"UNACCOUNTED: {ADR_REL} does not exist under {root}")
        print("instrument-census-check: the census itself is absent; nothing compared.")
        return 1

    text = adr.read_text(encoding="utf-8")
    files = script_files(root)

    if not files:
        # A population of zero makes every assertion below vacuously true and
        # prints a clean verdict over an unexamined tree - the blind-instrument
        # shape this repository refuses to ship. See docs/agents/detector-contracts.md.
        print(f"instrument-census-check: {SCRIPTS_REL}/ holds no files; nothing compared.")
        return 1

    census = census_subjects(text)
    if not census:
        # Same reasoning in the other direction: no rows parsed means the
        # extractor is broken or the table moved, and EVERY file would then
        # report UNACCOUNTED. That is a broken read presented as 73 findings.
        print(f"instrument-census-check: {ADR_REL} parsed to 0 census rows; nothing compared.")
        return 1

    exclusions, exclusions_found = exclusion_subjects(text)
    if not exclusions_found:
        print(f"instrument-census-check: {ADR_REL} has no 'Excluded, with the reason' section; nothing compared.")
        return 1

    externals = declared_externals(text)
    subjects = set(census) | set(exclusions)

    findings = 0

    for name in sorted(files):
        if name in subjects:
            continue
        print(
            f"UNACCOUNTED: {SCRIPTS_REL}/{name} is named by no census row and no "
            f"exclusion in {ADR_REL}"
        )
        findings += 1

    for subject in dict.fromkeys(census + exclusions):
        if subject in files or subject in externals:
            continue
        print(
            f"STALE: {ADR_REL} subject `{subject}` names no file in {SCRIPTS_REL}/ "
            f"and is not declared an external subject"
        )
        findings += 1

    # PROVENANCE ON EVERY VERDICT: an `ok` over a 73-file tree and an `ok` over a
    # 2-file fixture are otherwise the same line, and a verdict cannot be read
    # against what produced it.
    print(f"INSTRUMENT_CENSUS_EXAMINED: {len(files)}")
    print(f"INSTRUMENT_CENSUS_ROWS: {len(census)}")
    print(f"INSTRUMENT_CENSUS_EXCLUSIONS: {len(set(exclusions))}")
    print(f"INSTRUMENT_CENSUS_EXTERNALS: {len(externals)}")

    if findings:
        print(
            f"instrument-census-check: {findings} finding(s). Add a census row for "
            f"the instrument, an exclusion line with its reason, or declare an "
            f"external subject on the `instrument-census: external-subjects:` marker."
        )
        return 1

    print(
        f"instrument-census-check: ok - all {len(files)} file(s) in {SCRIPTS_REL}/ "
        f"are accounted for by {ADR_REL}, and every subject resolves."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("mode", nargs="?", default="check", choices=["check"])
    ap.add_argument("--root", default=str(REPO_ROOT), help="tree to operate on")
    args = ap.parse_args(argv)
    return run_check(Path(args.root).resolve())


if __name__ == "__main__":
    sys.exit(main())
