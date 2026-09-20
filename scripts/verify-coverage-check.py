#!/usr/bin/env python3
"""Account for every checker this repository owns, and make `verify` say what it skipped (issue #1028).

`make verify` is the aggregate local gate. It prints a green and says nothing
about the checks it never ran, so the green reads wider than it is - and a
reader who finds a checker in the tree reasonably infers the surface it covers
is being watched. Issue #1028 found four checkers in that state at once and
asked the same question of all four: *what gate consumes this, and what does a
green from `verify` claim about what it did NOT run?*

This gate answers the second half mechanically, and the first half by refusing
to let a checker exist without a declared answer.

WHAT IT DERIVES AND WHAT IT DEMANDS
-----------------------------------
Two populations, both derived from the tree - never from a list typed here:

  * every target in the `Makefile`;
  * every file in `scripts/`.

For targets, the class is DECLARED beside the target, on a directive the
Makefile carries:

    ## verify-coverage: excluded secret-scan - needs gitleaks on PATH; CI runs it

and the declaration is then CHECKED against the real prerequisite graph, in
both directions. A target declared `gate` that `verify` does not reach is a
red, and so is a `verify` prerequisite declared anything else. That is the
failure mode ADR 0008's own census row 40 names for `make verify` - "a sub-gate
silently dropped from the list, which no member row can see" - and it is the
one thing a member row cannot self-report.

For scripts, the class is DERIVED wherever the tree can answer:

  gate       a Makefile target invokes it and `verify` reaches that target
  excluded   a Makefile target invokes it and `verify` does not
  ci         no Makefile target invokes it, but a `.woodpecker.yml` step does

and only where the tree CANNOT answer - a script no build surface invokes at
all - must a human declare it, in `.claude/verify-coverage.json`:

  tested          its behaviour is driven by a module under `tests/`, so
                  `make test` - which IS in this gate - exercises it.
  runtime         consumed by a command, hook or sibling script at run time.
  not-a-checker   an installer, generator or helper that issues no verdict.

`tested` and `runtime` must name a `consumer` path, which this gate then opens
and greps: an excuse that names a file becomes a claim that can be false,
instead of a sentence that cannot.

`not-a-checker` IS THE HIDING PLACE, AND IT IS CROSS-CHECKED RATHER THAN
TRUSTED. It is the one class whose entries the closing report never mentions, so
a checker filed there disappears exactly the way the four #1028 subjects did.
The check is free, because the repository already maintains the answer: ADR
0008's census enumerates every instrument, its MEMBERSHIP is derived from
`scripts/` and gated by `make instrument-census-check`, and the extraction rule
is IMPORTED from that gate rather than re-implemented here - two copies of one
rule is how the documents would drift apart. A script the census calls an
instrument cannot be `not-a-checker` here, and the two files now have to agree.

THE MECHANISM FOR NEW CHECKERS IS THE SECOND POPULATION, NOT THE FIRST.
A framework that only classified Makefile targets would be satisfied by a
checker that never gets a target - which is not hypothetical: 56 of this
repository's 90 scripts have no target. `check-negative-controls.py` was one of
them until #1028 added `make negative-controls`, and it is one of that issue's
own four subjects: the register could be run only by someone who remembered the
script path and its `--strict`. So the population is `scripts/`, and a new file
there turns this gate red until it is accounted for. Adding a checker and
forgetting to wire it now costs a red, not a silence.

WHY `utility` CARRIES A TRIPWIRE
--------------------------------
`utility` is the class that says "this target is not a check", and it is
therefore the one place a checker could be parked where the report will never
mention it - the same wrong inference this gate exists to remove, reintroduced
one level up. So a `utility` recipe carrying a checking FLAG or SUBCOMMAND
(`--check`, `--strict`, `check`, `verify`, ...) is refused outright.

The rule matches flags and subcommands, never the invoked script's name:
`dependency-audit.py --capture` is a writer whose filename says "audit", and a
name-matching rule would force it into the report as a check that was not run,
which is a lie in the other direction. It is a TRIPWIRE, not a coverage
enumeration - it fires loudly on what it catches and claims nothing about what
it does not (`bootstrap-check.sh` invoked bare trips nothing here, and is
`excluded` on its own merits).

Stdlib-only, git-free and offline, so `make verify` and the slim CI image give
the same verdict.

Usage:
    verify-coverage-check.py [--root DIR] [--report]

`--report` prints, after the check passes, the closing summary `make verify`
ends on: every checker in this repository that this run did not examine, with
the reason each was left out. It runs the check first and refuses to print a
summary derived from an incomplete classification - a report is only worth the
enumeration behind it.

Output: one `UNACCOUNTED:` / `MISCLASSIFIED:` / `STALE:` / `UNDECLARED:` line
per finding, then a verdict line. Exit 0 when every target and every script is
accounted for, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

#: NEGATIVE-CONTROL: controls/verify-coverage
#:
#: This gate lets work THROUGH, and it is the aggregate one: `make verify`'s own
#: recipe reads its green as "every checker in this repository is accounted for,
#: and the closing report names the ones I skipped". Nothing downstream
#: re-derives that - the report IS the downstream consumer, and a blind version
#: prints a confident, well-formatted, short list.
#:
#: That is the sharpest reason this particular gate needs a committed case
#: rather than a clean-tree green: a report that under-names is indistinguishable
#: from a repository with less to name. The control's known-bad trees each hide
#: one checker in a different place - unclassified, misclassified against the
#: real prerequisite graph, and parked under `utility` - and the anchor is the
#: framing that only asks whether a `verify` target exists at all.

REPO_ROOT = Path(__file__).resolve().parents[1]

MAKEFILE_REL = "Makefile"
SCRIPTS_REL = "scripts"
CI_REL = ".woodpecker.yml"
DECL_REL = ".claude/verify-coverage.json"

#: The aggregate target whose prerequisite closure defines "examined".
VERIFY_TARGET = "verify"

TARGET_CLASSES = ("gate", "excluded", "utility")
SCRIPT_CLASSES = ("tested", "runtime", "not-a-checker")

#: Classes that must name the file that reads them. The named path is opened and
#: searched for the script's own name, so the entry is a claim rather than an
#: assertion - `STALE:` when the consumer is gone or has stopped mentioning it.
CONSUMER_REQUIRED = ("tested", "runtime")

#: ADR 0008's census, and the gate that derives its membership. The census
#: answers "is this an instrument"; this gate asks it rather than deciding again.
CENSUS_REL = "docs/decisions/0008-instrument-negative-control-bound.md"
CENSUS_GATE_REL = "scripts/instrument-census-check.py"

#: Where a `tested` consumer must live, and the target that runs them. `tested`
#: means "`make test` exercises this", so both halves are checked: the consumer
#: is a test module, and the runner is actually reachable from `verify`.
TESTS_REL = "tests"
TEST_TARGET = "test"

#: pytest's default collection patterns. A `tested` consumer must be a module
#: pytest would actually COLLECT - not merely a file that happens to live under
#: `tests/` (found by the #1028 counter-model review, pass 2). `tests/README.md`
#: passed the earlier rule the moment it mentioned a script's name, and the
#: report then counted that script as exercised by a suite that never loads it.
COLLECTED_TEST_RE = re.compile(r"(?:^|/)(?:test_[^/]+|[^/]+_test)\.py$")


def _is_collected_test(consumer: str) -> bool:
    return consumer.startswith(f"{TESTS_REL}/") and bool(
        COLLECTED_TEST_RE.search(consumer)
    )

#: `name:` at column 0, and NOT `name :=` (a variable) - the `(?!=)` is what
#: keeps `TOOLS_HARD := git python3 uv` out of the target population.
#:
#: DOTTED NAMES ARE MATCHED AND THEN SUBTRACTED, never excluded by the pattern
#: (found by the #1028 counter-model review). The first cut anchored on
#: `[A-Za-z]`, which kept `.PHONY` out - and also made a target literally named
#: `.my-check` invisible to the population, so it would be neither classified
#: nor reported. A rule that skips a whole namespace to avoid a handful of known
#: names is a rule that narrows silently: the exact shape this gate exists to
#: catch, in the gate itself.
#:
#: So the UNIVERSE is hardcoded (GNU make's special targets) and the MEMBERS are
#: derived. A dotted name that is not a make special is an ordinary target and
#: must be accounted for like any other.
#: SEVERAL TARGETS MAY SHARE ONE RULE - `a b:` declares both (found by the
#: #1028 counter-model review). Reading only the first name left the second in
#: no population at all: not classified, not reported, not counted.
#: A rule line is matched PERMISSIVELY and its names validated afterwards, so an
#: unsupported spelling becomes a FINDING rather than a silent omission (found by
#: the #1028 counter-model review, pass 2). The earlier pattern excluded `/`, a
#: leading `_` and a leading digit, so `security/check:` left the target count
#: unchanged while the verdict claimed every target was classified.
RULE_LINE_RE = re.compile(r"^([^\s:=#][^:=]*):(?!=)\s*(.*)$")

#: What an ordinary target name may look like. A name outside this is not
#: skipped - it is reported, which is the difference between a gate that narrows
#: and one that says it cannot answer (pattern rules like `%.o` land here).
TARGET_NAME_RE = re.compile(r"^\.?[A-Za-z0-9_][A-Za-z0-9_./-]*$")

#: GNU make's built-in special targets. Hardcoded deliberately - this is the
#: fixed universe, not a population derived from the tree - and a name outside it
#: is a real target however it is spelled.
MAKE_SPECIAL_TARGETS = frozenset({
    ".PHONY", ".SUFFIXES", ".DEFAULT", ".PRECIOUS", ".INTERMEDIATE", ".NOTINTERMEDIATE",
    ".SECONDARY", ".SECONDEXPANSION", ".DELETE_ON_ERROR", ".IGNORE", ".LOW_RESOLUTION_TIME",
    ".SILENT", ".EXPORT_ALL_VARIABLES", ".NOTPARALLEL", ".ONESHELL", ".POSIX",
    ".DEFAULT_GOAL", ".RECIPEPREFIX", ".MAKE", ".WAIT",
})

#: `## verify-coverage: <class> <target> - <reason>`. The target is NAMED rather
#: than inferred from position, so the directive survives being moved and a
#: comment block that drifts away from its recipe cannot silently re-point.
DIRECTIVE_RE = re.compile(
    r"^##\s*verify-coverage:\s*(\S+)\s+(\S+)\s*-\s*(.*?)\s*$"
)

#: A `scripts/<name>` invocation. Same shape the Codex bundler discovers, and
#: deliberately extension-bearing: the recipe calls the file, not its stem.
SCRIPT_REF_RE = re.compile(r"(?<![\w/-])scripts/([A-Za-z0-9._-]+)")

#: Checking flags and subcommands. Matched only against recipe text with the
#: invoked script paths removed, so a filename never decides the verdict.
#: A QUOTE IS NOT A DISGUISE. `sh scripts/beta-check.sh "--check"` is the same
#: invocation as the unquoted form, and requiring whitespace before the flag let
#: a quoted one slip a checker into `utility`, where the closing report never
#: names it (found by the #1028 counter-model review, pass 2). Printed text
#: cannot reach here any more - `_executable_recipe` drops whole printer
#: segments - so admitting quotes costs nothing and closes the gap.
SMELL_RE = re.compile(
    r"""(?:^|[\s"'])(?:--(?:check|strict|verify|lint|scan|drift|audit)\b"""
    r"""|(?:check|verify|lint)(?=[\s"']|$))"""
)


def _executable_recipe(text: str) -> str:
    """Recipe text with comments and quoted strings removed.

    WHAT A RECIPE SAYS IS NOT WHAT IT DOES, and reading the two as one moved
    this gate's verdict in BOTH directions (found by the #1028 counter-model
    review):

      * a recipe comment naming `scripts/x.sh` counted as an invocation, so
        deleting that script's declaration left the tree green - a checker
        dropped out of the accounting on the strength of a sentence;
      * `@echo "Run make verify before merging"` in a `utility` recipe tripped
        the checker tripwire on the word `verify`, a false red on a target that
        runs nothing at all. That direction is worse: this gate is a `make
        verify` prerequisite, so it would block every merge in the repository.

    THE DISCRIMINATION IS THE COMMAND, NOT THE QUOTES. Two earlier cuts of this
    got it wrong in opposite directions, and both were found rather than
    reasoned:

      * keeping everything let `# see scripts/x.sh` and
        `echo "scripts/x.sh explains why"` account for a checker nothing runs;
      * dropping every quoted run erased `workers="$(sh scripts/pytest-workers.sh)"`
        from `make test`, so the report called that helper "run only by CI, never
        locally" - and stayed green, because CI also runs it. It also erased
        `sh scripts/beta-check.sh "--check"`, letting a quoted flag hide a
        checker under `utility`.

    So a SEGMENT whose command is a printer (`echo`, `printf`, `:`) is dropped
    whole - its arguments are output, quoted or not - and every other segment is
    kept intact, quotes and command substitutions included. That is the actual
    difference between text a recipe prints and work a recipe does.
    """
    printers = {"echo", "printf", ":", "true", "false"}
    out: list[str] = []
    for raw in text.splitlines():
        if raw.lstrip("@-+ \t").startswith("#"):
            continue
        line = re.split(r"(?:^|\s)#", raw, maxsplit=1)[0]
        for segment in re.split(r";|&&|\|\|", line):
            words = segment.strip().lstrip("@-+ \t").split()
            if not words or words[0].lstrip("@-+") in printers:
                continue
            out.append(segment)
    return "\n".join(out)


def _prerequisites(text: str) -> list[str]:
    """A rule's prerequisite names, with make's comments removed.

    `verify: alpha-check # beta-check` runs ONLY alpha - make stops at the `#`.
    Splitting the raw text kept `beta-check` in the closure, so a gate commented
    out of the list still reported as examined. That is the precise failure this
    instrument exists to detect, and it was reachable in the instrument itself
    (found by the #1028 counter-model review, pass 2).
    """
    return re.split(r"(?:^|\s)#", text, maxsplit=1)[0].split()


def _strip_script_paths(text: str) -> str:
    """Recipe text with `scripts/<name>` tokens removed.

    The smell test asks what the recipe DOES, and a script's own name is not
    that. `dependency-audit.py --capture` writes a capture file; leaving the
    filename in would classify it as a check that `verify` skipped, which is a
    false entry in the one report this gate exists to keep honest.
    """
    return SCRIPT_REF_RE.sub(" ", text)


class Makefile:
    """The target graph, the recipes, and the `verify-coverage` directives."""

    def __init__(self, text: str) -> None:
        self.prereqs: dict[str, list[str]] = {}
        self.recipes: dict[str, list[str]] = {}
        self.order: list[str] = []
        self.directives: dict[str, tuple[str, str, int]] = {}
        self.duplicate_directives: list[tuple[str, int]] = []
        #: first target of a multi-target rule -> every target sharing its recipe
        self.shared: dict[str, list[str]] = {}
        #: (name, line) for rule names this parser cannot validate - reported
        self.unsupported: list[tuple[str, int]] = []
        self._parse(text)

    def _parse(self, text: str) -> None:
        current: str | None = None
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            directive = DIRECTIVE_RE.match(line)
            if directive:
                cls, target, reason = directive.groups()
                if target in self.directives:
                    self.duplicate_directives.append((target, i + 1))
                else:
                    self.directives[target] = (cls, reason, i + 1)
                i += 1
                continue
            if line.startswith("\t"):
                if current is not None:
                    self.recipes[current].append(line[1:])
                i += 1
                continue
            match = RULE_LINE_RE.match(line)
            if match:
                names, rest = match.groups()
                # A prerequisite list continued with trailing backslashes.
                while rest.endswith("\\") and i + 1 < len(lines):
                    i += 1
                    rest = rest[:-1] + " " + lines[i].strip()
                declared = [n for n in names.split() if n not in MAKE_SPECIAL_TARGETS]
                # A NAME THIS PARSER CANNOT VALIDATE IS REPORTED, NOT DROPPED.
                # Silently skipping an unrecognised spelling is how `security/check:`
                # and `%.o:` would leave the population while the verdict still
                # said "all Makefile targets are classified".
                unsupported = [n for n in declared if not TARGET_NAME_RE.match(n)]
                if unsupported:
                    self.unsupported.extend((n, i + 1) for n in unsupported)
                    declared = [n for n in declared if TARGET_NAME_RE.match(n)]
                if not declared:
                    # A directive to make (`.PHONY:`), not a target anyone runs.
                    current = None
                    i += 1
                    continue
                for name in declared:
                    if name not in self.prereqs:
                        self.order.append(name)
                        self.prereqs[name] = []
                        self.recipes[name] = []
                    self.prereqs[name].extend(_prerequisites(rest))
                # Every target of a multi-target rule shares its recipe.
                self.shared[declared[0]] = declared
                current = declared[0]
                i += 1
                continue
            if line.strip():
                current = None
            i += 1

    def closure(self, root: str) -> set[str]:
        """Every target `root` reaches, including itself."""
        seen: set[str] = set()
        stack = [root]
        while stack:
            name = stack.pop()
            if name in seen or name not in self.prereqs:
                continue
            seen.add(name)
            stack.extend(self.prereqs[name])
        return seen

    def recipe_text(self, target: str) -> str:
        """This target's recipe, including one it shares with siblings."""
        own = self.recipes.get(target, ())
        if own:
            return "\n".join(own)
        for first, group in self.shared.items():
            if target in group:
                return "\n".join(self.recipes.get(first, ()))
        return ""

    def scripts_invoked(self, target: str) -> set[str]:
        return set(SCRIPT_REF_RE.findall(_executable_recipe(self.recipe_text(target))))


def _ci_scripts(text: str) -> set[str]:
    """Scripts a `.woodpecker.yml` step RUNS - never one a comment discusses.

    The first cut grepped the whole file and reported four scripts as "run only
    by CI" that the pipeline merely talks ABOUT: `secret-scan-check.sh` is named
    in a comment explaining why gitleaks is staged, `classify-tool-risk.py` and
    `flow-wave-registry.sh` in comments about why a step is pinned. Every one of
    them was then counted as examined, which is the wrong direction for this
    gate to be wrong in - it makes an unrun checker look covered, the exact
    inference issue #1028 is about, produced by the fix for it.

    A pipeline this heavily commented is why: the comments are longer than the
    commands and name more scripts than the commands do.

    STRIPPING COMMENTS WAS NOT ENOUGH (found by the review's second pass): an
    `environment:` value, or any other uncommented field, still counted. So this
    reads ONLY the list items under a `commands:` key, and applies the same
    printer rule the Makefile recipes get - `- echo "scripts/ghost.sh"` is a
    step printing a name, not a step running it.
    """
    commands: list[str] = []
    in_commands = False
    key_indent = 0
    for raw in text.splitlines():
        line = raw.split("#", 1)[0] if raw.lstrip().startswith("#") else raw
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        if re.match(r"^commands:\s*$", stripped):
            in_commands, key_indent = True, indent
            continue
        if in_commands:
            # A list item deeper than the `commands:` key is one of its entries;
            # anything at or above that indent has ended the block.
            if stripped.startswith("- ") and indent > key_indent:
                commands.append(stripped[2:])
                continue
            in_commands = False
    return set(SCRIPT_REF_RE.findall(_executable_recipe("\n".join(commands))))


def _load_declarations(path: Path) -> tuple[dict[str, dict], list[str]]:
    """The hand-written accounting for scripts no build surface invokes."""
    if not path.is_file():
        return {}, [f"UNDECLARED: {DECL_REL} is missing - every script with no "
                    f"Makefile target or CI step needs its entry there"]
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return {}, [f"UNDECLARED: {DECL_REL} is unreadable ({exc})"]
    if not isinstance(data, dict) or not isinstance(data.get("scripts"), dict):
        return {}, [f"UNDECLARED: {DECL_REL} has no `scripts` object"]
    return data["scripts"], []


def census_instruments(root: Path) -> set[str] | None:
    """The scripts ADR 0008 enumerates as instruments, or None if unreadable.

    The extraction rule is IMPORTED from `instrument-census-check.py`, never
    re-implemented: that gate already owns "the first backticked token of column
    2, head word only", it is tested, and a second copy here would drift from it
    silently - leaving two documents that disagree about what an instrument is.

    None means UNREAD, not EMPTY. A tree without the census (every fixture, and
    any repository that has not adopted it) cannot answer the question, and an
    unanswered question must not read as "nothing is an instrument" - that is
    the blind-scan shape this whole file is about. Callers report it.
    """
    census = root / CENSUS_REL
    # THE RULE COMES FROM THIS CHECKOUT, THE DATA FROM THE TREE BEING CHECKED.
    # Loading the rule from `root` instead would execute the target tree's own
    # Python on every run - which `--root` points at fixtures and, in principle,
    # at any tree someone hands it. It is also wrong on the merits: "what counts
    # as an instrument" is this gate's rule, not something each tree redefines.
    gate = REPO_ROOT / CENSUS_GATE_REL
    if not census.is_file() or not gate.is_file():
        return None
    try:
        spec = spec_from_file_location("instrument_census_check", gate)
        if spec is None or spec.loader is None:
            return None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return set(module.census_subjects(census.read_text()))
    except Exception:  # noqa: BLE001 - any failure here is UNREAD, never EMPTY
        return None


def _script_population(scripts_dir: Path) -> list[str]:
    """Every file in `scripts/`. Directories (`__pycache__`) are not scripts."""
    if not scripts_dir.is_dir():
        return []
    return sorted(p.name for p in scripts_dir.iterdir() if p.is_file())


def run_check(root: Path, report: bool = False) -> int:
    findings: list[str] = []

    makefile_path = root / MAKEFILE_REL
    if not makefile_path.is_file():
        print(f"UNDECLARED: {MAKEFILE_REL} not found under {root}")
        print("verify-coverage-check: 1 finding(s).")
        return 1

    mk = Makefile(makefile_path.read_text())
    targets = set(mk.order)
    examined = mk.closure(VERIFY_TARGET) if VERIFY_TARGET in mk.prereqs else set()

    if VERIFY_TARGET not in mk.prereqs:
        findings.append(
            f"UNDECLARED: {MAKEFILE_REL} has no `{VERIFY_TARGET}` target, so "
            f"there is no aggregate whose coverage this gate can report"
        )

    for name, line_no in mk.unsupported:
        findings.append(
            f"UNDECLARED: {MAKEFILE_REL}:{line_no} declares `{name}`, a rule name "
            f"this gate cannot validate, so it is in NO population. Rename it to "
            f"an ordinary target name, or teach this gate the spelling - never "
            f"leave it unreported"
        )

    for target, line_no in mk.duplicate_directives:
        findings.append(
            f"STALE: {MAKEFILE_REL}:{line_no} is a second verify-coverage "
            f"directive for `{target}`; one target, one class"
        )

    # -- targets -----------------------------------------------------------
    for target, (cls, reason, line_no) in sorted(mk.directives.items()):
        if target not in targets:
            findings.append(
                f"STALE: {MAKEFILE_REL}:{line_no} classifies `{target}`, which "
                f"is not a target in this Makefile"
            )
            continue
        if cls not in TARGET_CLASSES:
            findings.append(
                f"MISCLASSIFIED: {MAKEFILE_REL}:{line_no} gives `{target}` the "
                f"unknown class `{cls}` (expected one of {', '.join(TARGET_CLASSES)})"
            )
            continue
        if not reason:
            findings.append(
                f"UNDECLARED: {MAKEFILE_REL}:{line_no} classifies `{target}` "
                f"`{cls}` with no reason after the `-`"
            )
        reaches = target in examined
        if cls == "gate" and not reaches:
            findings.append(
                f"MISCLASSIFIED: `{target}` is declared `gate` but `make "
                f"{VERIFY_TARGET}` does not reach it - the sub-gate-dropped-from-"
                f"the-list failure, which no member target can self-report"
            )
        if cls != "gate" and reaches:
            findings.append(
                f"MISCLASSIFIED: `{target}` is declared `{cls}` but `make "
                f"{VERIFY_TARGET}` DOES reach it, so the closing report names it "
                f"unexamined while it runs on every verify"
            )
        if cls == "utility":
            smell = SMELL_RE.search(
                _strip_script_paths(_executable_recipe(mk.recipe_text(target)))
            )
            if smell:
                findings.append(
                    f"MISCLASSIFIED: `{target}` is declared `utility` but its "
                    f"recipe runs `{smell.group(0).strip()}` - a checker parked "
                    f"where the closing report will never name it. Classify it "
                    f"`gate` or `excluded`"
                )

    for target in mk.order:
        if target not in mk.directives:
            findings.append(
                f"UNACCOUNTED: target `{target}` carries no `## verify-coverage:` "
                f"directive. Add `## verify-coverage: <{'|'.join(TARGET_CLASSES)}> "
                f"{target} - <reason>` beside it"
            )

    # -- scripts -----------------------------------------------------------
    scripts = _script_population(root / SCRIPTS_REL)
    by_target: dict[str, str] = {}
    for target in mk.order:
        for name in mk.scripts_invoked(target):
            # A script reached by any examined target is examined; otherwise the
            # first target that invokes it names it. `gate` wins over `excluded`
            # so a helper shared by both is not reported as skipped.
            if by_target.get(name) != "gate":
                by_target[name] = "gate" if target in examined else "excluded"

    ci_path = root / CI_REL
    ci_scripts = _ci_scripts(ci_path.read_text()) if ci_path.is_file() else set()

    declared, decl_errors = _load_declarations(root / DECL_REL)
    findings.extend(decl_errors)

    instruments = census_instruments(root)

    classified: dict[str, tuple[str, str]] = {}
    for name in scripts:
        if name in by_target:
            classified[name] = (by_target[name], "")
        elif name in ci_scripts:
            classified[name] = ("ci", "")
        elif name in declared:
            entry = declared[name]
            cls = entry.get("class", "") if isinstance(entry, dict) else ""
            reason = entry.get("reason", "") if isinstance(entry, dict) else ""
            if cls not in SCRIPT_CLASSES:
                findings.append(
                    f"MISCLASSIFIED: {DECL_REL} gives `{name}` the unknown class "
                    f"`{cls}` (expected one of {', '.join(SCRIPT_CLASSES)})"
                )
                continue
            if not reason:
                findings.append(
                    f"UNDECLARED: {DECL_REL} classifies `{name}` `{cls}` with no "
                    f"reason"
                )
            if cls == "not-a-checker" and instruments is not None and name in instruments:
                findings.append(
                    f"MISCLASSIFIED: {DECL_REL} calls `{name}` `not-a-checker`, "
                    f"but {CENSUS_REL} enumerates it as an instrument. "
                    f"`not-a-checker` is the one class the closing report never "
                    f"names, so a checker filed there disappears. Classify it "
                    f"`tested` or `runtime`, or take it out of the census"
                )
            if cls in CONSUMER_REQUIRED:
                consumer = entry.get("consumer", "")
                if not consumer:
                    findings.append(
                        f"UNDECLARED: {DECL_REL} classifies `{name}` `{cls}` "
                        f"with no `consumer` path. A `{cls}` entry names the "
                        f"surface that reads it, so the claim can be false"
                    )
                else:
                    target_path = root / consumer
                    if not target_path.is_file():
                        findings.append(
                            f"STALE: {DECL_REL} says `{name}` is consumed by "
                            f"`{consumer}`, which does not exist"
                        )
                    elif name not in target_path.read_text():
                        findings.append(
                            f"STALE: {DECL_REL} says `{name}` is consumed by "
                            f"`{consumer}`, which does not mention it"
                        )
                    elif cls == "tested" and not _is_collected_test(consumer):
                        # `tested` MEANS "the test runner exercises it", and the
                        # mention check alone could not tell that from `runtime`
                        # (found by the #1028 counter-model review): pointing a
                        # `tested` entry at a command document passed, and
                        # silently removed the script from the unexamined report.
                        findings.append(
                            f"MISCLASSIFIED: {DECL_REL} classifies `{name}` "
                            f"`tested` but its consumer `{consumer}` is not a "
                            f"module pytest would collect under {TESTS_REL}/. "
                            f"`tested` claims the test runner exercises it; a "
                            f"command document or a README is not that"
                        )
            classified[name] = (cls, reason)
        else:
            findings.append(
                f"UNACCOUNTED: `{SCRIPTS_REL}/{name}` is invoked by no Makefile "
                f"target and no {CI_REL} step, and has no entry in {DECL_REL}. A "
                f"checker nothing runs is the state issue #1028 is about"
            )

    for name in sorted(declared):
        if name not in scripts:
            findings.append(
                f"STALE: {DECL_REL} classifies `{name}`, which is not a file in "
                f"{SCRIPTS_REL}/"
            )
        elif name in by_target or name in ci_scripts:
            findings.append(
                f"STALE: {DECL_REL} classifies `{name}`, but a Makefile target or "
                f"{CI_REL} step already invokes it - the derived class is the "
                f"truth and the entry can only go stale against it"
            )

    # PROVENANCE ON EVERY VERDICT: an `ok` over 56 targets and an `ok` over a
    # two-target fixture are otherwise the same line.
    print(f"VERIFY_COVERAGE_TARGETS: {len(targets)}")
    print(f"VERIFY_COVERAGE_EXAMINED: {len(examined)}")
    print(f"VERIFY_COVERAGE_SCRIPTS: {len(scripts)}")
    # UNREAD IS NOT EMPTY. When the census cannot be read, the `not-a-checker`
    # cross-check did not run - and a line saying so is the difference between
    # "nothing was parked there" and "nobody looked".
    print(
        f"VERIFY_COVERAGE_CENSUS: "
        f"{'unread' if instruments is None else len(instruments)}"
    )

    if findings:
        for finding in findings:
            print(finding)
        print(
            f"verify-coverage-check: {len(findings)} finding(s). Every Makefile "
            f"target needs a `## verify-coverage:` directive, and every file in "
            f"{SCRIPTS_REL}/ needs a build surface that invokes it or an entry in "
            f"{DECL_REL}."
        )
        return 1

    print(
        f"verify-coverage-check: ok - all {len(targets)} Makefile target(s) are "
        f"classified against `make {VERIFY_TARGET}`, and all {len(scripts)} file(s) "
        f"in {SCRIPTS_REL}/ are accounted for."
    )

    if report:
        print_report(mk, classified, examined)
    return 0


def print_report(
    mk: Makefile,
    classified: dict[str, tuple[str, str]],
    examined: set[str],
) -> None:
    """The closing summary: what this `verify` did NOT examine, and why.

    Printed only after the check passes. A summary derived from an incomplete
    classification is the failure this whole gate exists to remove, so it is
    never printed beside a finding.
    """
    excluded = [
        (t, mk.directives[t][1])
        for t in mk.order
        if mk.directives.get(t, ("", "", 0))[0] == "excluded"
    ]
    ci_only = sorted(n for n, (c, _) in classified.items() if c == "ci")
    runtime = sorted(n for n, (c, _) in classified.items() if c == "runtime")

    gates = [t for t in mk.order if mk.directives.get(t, ("", "", 0))[0] == "gate"]
    tested = sorted(n for n, (c, _) in classified.items() if c == "tested")

    # `tested` IS A CLAIM ABOUT THE RUNNER, NOT ABOUT THE MODULE (found by the
    # #1028 counter-model review). Every one of these scripts counts as examined
    # only because `make test` is in this gate. Drop `test` from the prerequisite
    # list and 39 instruments become unexamined in the same instant - silently,
    # because each entry still names a real module that still mentions it. So the
    # report states the condition it depends on rather than assuming it.
    if TEST_TARGET not in examined and tested:
        print(
            f"  WARNING: {len(tested)} instrument(s) are recorded `tested`, but "
            f"`make {TEST_TARGET}` is NOT in this gate - nothing here exercised "
            f"them. They are unexamined:"
        )
        for name in tested:
            print(f"    {SCRIPTS_REL}/{name}")
        print("")
        tested = []

    print("")
    print(f"make {VERIFY_TARGET}: what this run did NOT examine")
    print("")
    # THE DENOMINATOR, BESIDE THE NUMERATOR. A list of what was skipped, printed
    # alone, reads as the whole picture; the same list under "18 of 33" reads as
    # a fraction a reader can weigh. This repository already learned that at
    # #979, on `check-negative-controls.py`'s own summary line.
    print(
        f"  examined: {len(gates)} check(s) in this gate, plus {len(tested)} "
        f"instrument(s) exercised through `make test`."
    )
    print("")
    if excluded:
        print(f"  {len(excluded)} check(s) this repository owns and this gate did not run:")
        for target, reason in excluded:
            print(f"    make {target} - {reason}")
    else:
        print("  every check with a Makefile target is in this gate.")
    if ci_only:
        print("")
        print(f"  {len(ci_only)} checker(s) run only by {CI_REL}, never locally:")
        for name in ci_only:
            print(f"    {SCRIPTS_REL}/{name}")
    if runtime:
        print("")
        print(
            f"  {len(runtime)} run-time instrument(s) are consumed by commands and "
            f"hooks rather than by any build gate; see {DECL_REL}."
        )
    print("")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(REPO_ROOT), help="tree to operate on")
    ap.add_argument(
        "--report",
        action="store_true",
        help="print the closing 'what verify did not examine' summary",
    )
    args = ap.parse_args(argv)
    return run_check(Path(args.root).resolve(), report=args.report)


if __name__ == "__main__":
    sys.exit(main())
