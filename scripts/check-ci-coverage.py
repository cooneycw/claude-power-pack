#!/usr/bin/env python3
"""Every `make verify` gate declares whether CI runs it, and the claim is checked (issue #1146).

`make verify` chains 27 gates. The pipeline ran 16 of them. Nothing in the tree
recorded which 11 were missing, so a gate could be wired into `verify` and never
into CI, and the only messenger was a red `main` in front of whoever pulled
next. That is not hypothetical: #1144 merged green over `claude-md-behavior-check`
- in `make verify`, absent from `.woodpecker.yml` - and `main` was red from the
moment it landed.

The accounting that failed was an ABSENCE read as fine. So the remedy is not a
second registry listing which gates CI runs; a registry drifts from the pipeline
exactly the way the pipeline drifted from the Makefile. The remedy is a
DECLARATION beside each gate, and a check that reads BOTH SIDES of it.

WHAT IT DERIVES
---------------
Three populations, all read from the tree, none typed here:

  * `verify`'s prerequisites, from the `verify:` rule in the `Makefile`;
  * the step names in `.woodpecker.yml`;
  * the `ci:` clause of each `## verify-coverage:` directive.

and it refuses three ways:

  UNDECLARED    a `verify` prerequisite with no `ci:` clause at all.
  MALFORMED     a clause that is not exactly `ci: runs <step>` or
                `ci: excluded <reason>`.
  ABSENT-STEP   a gate declaring `ci: runs <step>` for a step `.woodpecker.yml`
                does not have.
  ORPHANED-CLAUSE
                a `## ci: ...` line written outside a directive, where it reads
                as a declaration to a human and is invisible to this gate.

A DECLARATION IS A CLAIM, WHICH IS WHY THE STEP SIDE IS READ. `ci: runs foo`
with no `foo` step is the same silence this gate exists to end, written down in
a more convincing font: the Makefile now asserts coverage that does not exist,
and a reader who checked the annotation instead of the pipeline would come away
more confident and equally wrong. Deleting a step is the ordinary way this
happens, and nothing else in the tree notices.

THE SHAPE IS STRICT; THE VOCABULARY IS OPEN
-------------------------------------------
`ci: excluded <reason>` takes any reason - `needs-git`, `host-state`, a
sentence. Nobody can enumerate in advance why a gate cannot run in a slim
container, and a closed list would push the next real reason into the nearest
wrong word.

The SHAPE is the opposite. `ci: run validate` is a typo, and a lenient parser
that accepted it would turn "an unrecognised reason still passes" - which is
correct - into "a malformed declaration still passes", which is the defect
wearing the feature's clothes. `ci: excluded` with no reason is the same thing:
an empty reason is not an open-vocabulary reason, it is a missing argument. Both
are committed bad cases.

THE DECLARATION BINDS BY NAME, NOT BY POSITION
----------------------------------------------
`## verify-coverage:` directives NAME their target - a decision
`verify-coverage-check.py` made and documented, so a comment block that drifts
away from its recipe cannot silently re-point at the target below it. This gate
inherits that binding rather than re-deriving one, and
`bad-declaration-bound-to-a-ghost-target` is the case that proves it: an
annotation carrying a perfectly valid `ci: runs` sits directly above an
undeclared gate, and a positional reader scores that tree clean.

WHY A SIBLING OF `verify-coverage-check.py` AND NOT A BRANCH INSIDE IT
----------------------------------------------------------------------
That gate's verdict already stands for two populations at once - every Makefile
target is classified, and every file in `scripts/` is accounted for - and its
own docstring calls it "a TRIPWIRE, not a coverage enumeration". This is a third
pair (`verify` prerequisites x pipeline steps) and it IS a coverage enumeration:
per-prerequisite, exhaustive, and green only when every member is dispositioned.
Folding it in would make one green stand for two unrelated claims, which is the
reading failure #1146 is about, one level up.

What is NOT duplicated is the parsing. The `Makefile` reader is IMPORTED from
that gate, never re-implemented: two parsers of one format drift, and the
drift would be invisible - both would still print a green. The same import
discipline that gate applies to the census extraction rule.

The two also cover each other's blind side. A gate dropped OUT of the `verify:`
list disappears from this gate's population entirely - it has no prerequisite
left to be undeclared - and `verify-coverage-check` is what reds on it, because
the target is still declared `gate` and `verify` no longer reaches it.

AN EMPTY POPULATION IS `UNKNOWN`, NEVER `ok`
--------------------------------------------
This check exists because an absence read as fine, and a derivation that returns
zero members is an absence. Two ways that happens with nobody editing this file:
the `verify:` rule is reformatted past the continuation join, or `.woodpecker.yml`
is converted to the list form (`- name: validate`) that this reader does not
speak. The second reds loudly on its own - every `ci: runs` becomes an
ABSENT-STEP - but the first would go green over nothing at all. So zero
prerequisites and zero steps each exit 2 naming the population that came back
empty, and the `ok` line states its counts so a reader can see the population
the green rests on.

Stdlib-only, git-free and offline: it opens two repo-relative files, so `make
verify` and the slim CI image give the same verdict. Which is also why this gate
runs in CI and declares `ci: runs ci-coverage-check` on itself - a check that
audits "does the pipeline run what `verify` runs" and is itself absent from the
pipeline is the class it audits.

Usage:
    python3 scripts/check-ci-coverage.py [--root DIR]

Exit: 0 clean, 1 findings, 2 a population it could not derive.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

MAKEFILE_REL = "Makefile"
CI_REL = ".woodpecker.yml"

#: The aggregate whose prerequisites are the population.
VERIFY_TARGET = "verify"

#: The Makefile reader lives in the sibling gate, and is IMPORTED rather than
#: copied. Both gates read the same `verify:` rule and the same
#: `## verify-coverage:` directives; a second parser here would drift from that
#: one silently, and two green gates disagreeing about what the Makefile says is
#: worse than one. The RULE comes from THIS checkout, the DATA from the tree
#: being checked - `--root` points at fixture trees, and loading the parser from
#: there would execute the inspected tree's own Python.

#: NEGATIVE-CONTROL: controls/ci-coverage

#: The `ci:` clause marker. Anchored on a start, whitespace or `;` so a word
#: ending in `ci` cannot open a declaration, and the LAST occurrence wins - the
#: clause is written at the end of the directive's reason.
CI_MARKER_RE = re.compile(r"(?:^|[;\s])ci:\s*")

#: `runs <step>`. One token, because a step name is one token; `runs validate
#: and shellcheck` is not two declarations, it is a sentence where a declaration
#: should be.
RUNS_RE = re.compile(r"^runs\s+([A-Za-z0-9_][A-Za-z0-9_.-]*)$")

#: `excluded <reason>`. The reason is free text and must be NON-EMPTY: an
#: absent reason is a missing argument, not an open-vocabulary one.
EXCLUDED_RE = re.compile(r"^excluded\s+(\S.*)$")

#: A COMMENT LINE THAT OPENS WITH `ci:` AND IS NOT PART OF A DIRECTIVE.
#:
#: This is the notation reintroducing the defect it was written to remove
#: (found when #1071 and #1146 met at merge). A worker who had not seen the
#: inline form wrote the clause on its own line:
#:
#:     ## verify-coverage: gate agents-md-budget-check - stays inside its budget
#:     ## ci: runs agents-md-budget-check
#:
#: which READS AS A DECLARATION TO A HUMAN AND IS INVISIBLE TO THIS GATE - a
#: declaration nothing consumes, which is the whole of #1146 one level in. Left
#: to surface as `UNDECLARED` it is worse than silence: the remedy line says
#: "say `ci: runs <step>`" to someone looking straight at a line reading
#: `## ci: runs agents-md-budget-check`, and from where they sit that is
#: indistinguishable from a broken gate.
#:
#: ANCHORED ON THE LINE START, because prose about the notation is ordinary and
#: must not red. The Makefile's own explanation of this gate contains
#: "`ci: runs <step>` is a claim" mid-sentence; the good case carries a line of
#: the same shape so the discrimination is committed rather than asserted.
#: Within a Makefile comment, an opening `ci:` is RESERVED for the clause.
ORPHANED_CLAUSE_RE = re.compile(r"^##\s*ci:\s*(\S.*)$")

#: A step name in the mapping form `.woodpecker.yml` uses: a key two columns
#: deeper than the `steps:` key that opened the block. The list form
#: (`- name: validate`) is deliberately NOT read - see the empty-population
#: note in the module docstring. It does not silently return fewer steps; it
#: returns none, and none is `UNKNOWN`.
STEP_KEY_RE = re.compile(r"^(\s*)([A-Za-z0-9_][A-Za-z0-9_.-]*):\s*$")

STEPS_KEY = "steps:"


class Unknown(Exception):
    """A population this gate could not derive. Never a verdict about the tree."""


def _load_makefile(root: Path):
    """`(parsed Makefile, its text)` from ONE read of `root`'s Makefile.

    The text comes back with the parse because two reads of one file are two
    facts about two moments. This tree is a shared checkout that other sessions
    edit, and the orphaned-clause scan reports LINE NUMBERS - a second read
    would let a verdict cite a line from a file the populations did not come
    from.
    """
    # IMPORTED, NOT LOADED BY PATH (issue #1162). This used to
    # `spec_from_file_location` its way into `scripts/verify-coverage-check.py`
    # to borrow the class defined there - so this gate's parser was a private
    # detail of a sibling gate, and a rename or a refactor over there broke it
    # here with an `Unknown` that named a file rather than a cause. The reader
    # is a module now and this is an ordinary import.
    #
    # sys.path is set EXPLICITLY: this runs as a CI step with no virtualenv.
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        import lib.cicd.makefile_declaration as _declaration
        from lib.cicd.makefile_declaration import Makefile
    except ImportError as exc:  # pragma: no cover - reported, never guessed at
        raise Unknown(
            f"the Makefile declaration reader could not be imported ({exc}), so "
            "no population can be derived - this is UNKNOWN, not clean"
        ) from exc

    # ANCHORED, NOT INFERRED (issue #1162, counter-model review). `lib` is a
    # PEP 420 namespace package, so a foreign REGULAR `lib` anywhere on
    # sys.path is preferred over this checkout's portion even with REPO_ROOT at
    # position 0 - and it would answer this gate's population question with
    # someone else's parser. A different question is not a narrower answer.
    reader_file = Path(getattr(_declaration, "__file__", "") or "").resolve()
    if REPO_ROOT not in reader_file.parents:
        raise Unknown(
            f"the Makefile declaration reader resolved to "
            f"{reader_file or 'an unknown location'}, outside {REPO_ROOT} - "
            f"another `lib` package is shadowing this checkout's"
        )

    makefile_path = root / MAKEFILE_REL
    if not makefile_path.is_file():
        raise Unknown(f"{MAKEFILE_REL} is missing, so no `{VERIFY_TARGET}:` "
                      f"prerequisite could be derived")
    try:
        text = makefile_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise Unknown(f"{MAKEFILE_REL} is unreadable ({exc})") from exc
    return Makefile(text), text


def verify_prerequisites(mk) -> list[str]:
    """`verify`'s direct prerequisites, in Makefile order, de-duplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for name in mk.prereqs.get(VERIFY_TARGET, ()):
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def ci_steps(text: str) -> list[str]:
    """Step NAMES from a `.woodpecker.yml` in the mapping form.

    Names, not the scripts they run: the declaration this gate checks names a
    step, and the question `ci: runs validate` asks is whether a step called
    `validate` exists - not whether some step happens to invoke a matching
    script. `validate` runs `ruff`, `mypy` and `pytest` and invokes none of the
    three Makefile targets by name, which is exactly why the declaration names
    the step and this reader answers in the same currency.
    """
    names: list[str] = []
    in_steps = False
    key_indent = 0
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if raw.strip() == STEPS_KEY:
            in_steps, key_indent = True, indent
            continue
        if not in_steps:
            continue
        if indent <= key_indent:
            # Anything at or above the `steps:` key's indent has closed it.
            in_steps = False
            continue
        match = STEP_KEY_RE.match(raw)
        if match and len(match.group(1)) == key_indent + 2:
            names.append(match.group(2))
    return names


def orphaned_clauses(text: str) -> list[tuple[int, str]]:
    """`(line number, text)` for every `ci:` clause written outside a directive.

    A `## verify-coverage:` line carries its clause in the reason and is matched
    by `DIRECTIVE_RE`, never here: this pattern requires `ci:` to be the first
    token after the comment marker, which a directive line cannot be.
    """
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = ORPHANED_CLAUSE_RE.match(line)
        if match:
            found.append((number, match.group(1).strip()))
    return found


def parse_declaration(reason: str) -> tuple[str, str] | None:
    """`("runs", step)`, `("excluded", reason)`, `("malformed", text)`, or None.

    None means no `ci:` clause was written at all. `malformed` means one was and
    it does not parse - reported rather than ignored, because a typo'd
    declaration is an author who believes the gate is dispositioned.
    """
    markers = list(CI_MARKER_RE.finditer(reason))
    if not markers:
        return None
    tail = reason[markers[-1].end():].strip()
    runs = RUNS_RE.match(tail)
    if runs:
        return ("runs", runs.group(1))
    excluded = EXCLUDED_RE.match(tail)
    if excluded:
        return ("excluded", excluded.group(1).strip())
    return ("malformed", tail)


def run_check(root: Path) -> int:
    try:
        mk, makefile_text = _load_makefile(root)
        prerequisites = verify_prerequisites(mk)
        if not prerequisites:
            raise Unknown(
                f"derived 0 prerequisites from `{VERIFY_TARGET}:` in "
                f"{MAKEFILE_REL} - the population is empty, so a clean verdict "
                f"would rest on nothing"
            )
        ci_path = root / CI_REL
        if not ci_path.is_file():
            raise Unknown(f"{CI_REL} is missing, so no pipeline step could be derived")
        try:
            steps = ci_steps(ci_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            raise Unknown(f"{CI_REL} is unreadable ({exc})") from exc
        if not steps:
            raise Unknown(
                f"derived 0 steps from {CI_REL} - the population is empty, so "
                f"every `ci: runs` claim would be unchecked against nothing"
            )
    except Unknown as exc:
        print(f"check-ci-coverage: UNKNOWN - {exc}")
        return 2

    step_names = set(steps)
    findings: list[str] = []
    runs = 0
    excluded = 0

    # Reported FIRST, because it is the cause and the `UNDECLARED` beside it is
    # the symptom. A reader who meets the symptom alone goes looking for a gate
    # bug. It contributes NOTHING to the counts below: an orphaned clause is not
    # a declaration, which is the finding.
    for number, clause in orphaned_clauses(makefile_text):
        findings.append(
            f"ORPHANED-CLAUSE: {MAKEFILE_REL}:{number} reads `## ci: {clause}` on "
            f"its own line, where nothing consumes it - the clause belongs on the "
            f"`## verify-coverage:` directive itself, after the reason: "
            f"`## verify-coverage: gate <target> - <reason>; ci: {clause}`"
        )

    for target in prerequisites:
        directive = mk.directives.get(target)
        declaration = parse_declaration(directive[1]) if directive else None
        if declaration is None:
            findings.append(
                f"UNDECLARED: `{target}` is a `{VERIFY_TARGET}` prerequisite with "
                f"no `ci:` clause on its `## verify-coverage:` directive - say "
                f"`ci: runs <step>` or `ci: excluded <reason>`"
            )
            continue
        kind, value = declaration
        if kind == "malformed":
            findings.append(
                f"MALFORMED: `{target}` declares `ci: {value}`, which is neither "
                f"`ci: runs <step>` nor `ci: excluded <reason>` - the reason "
                f"vocabulary is open, the shape is not"
            )
            continue
        if kind == "excluded":
            excluded += 1
            continue
        runs += 1
        if value not in step_names:
            findings.append(
                f"ABSENT-STEP: `{target}` declares `ci: runs {value}`, and "
                f"{CI_REL} has no step named `{value}` - the declaration claims "
                f"a coverage the pipeline does not provide"
            )

    print(f"CI_COVERAGE_PREREQUISITES: {len(prerequisites)}")
    print(f"CI_COVERAGE_STEPS: {len(steps)}")

    if findings:
        for finding in findings:
            print(finding)
        print(f"check-ci-coverage: FAIL - {len(findings)} finding(s)")
        return 1

    print(
        f"check-ci-coverage: ok - {len(prerequisites)} `{VERIFY_TARGET}` "
        f"prerequisite(s) dispositioned against {len(steps)} pipeline step(s): "
        f"{runs} run in CI, {excluded} excluded"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(REPO_ROOT), help="tree to operate on")
    args = ap.parse_args(argv)
    return run_check(Path(args.root).resolve())


if __name__ == "__main__":
    sys.exit(main())
