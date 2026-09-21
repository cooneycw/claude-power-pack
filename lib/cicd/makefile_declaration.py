r"""The DECLARATION reader for a Makefile: what the file SAYS, as written.

WHY THIS MODULE EXISTS (issue #1162). This repository had THREE readers of a
Makefile and needed two. The split that matters is the question asked, not the
implementation:

  DECLARATION - what does the file declare, including a prerequisite a
      conditional currently disables? `verify-coverage-check` and
      `check-ci-coverage` ask this: their subject is what somebody has
      DISPOSITIONED against the pipeline, so a rule that exists but does not
      currently run still belongs in the population. This module.

  EXECUTION - what will make ACTUALLY run, here, now? `lib/cicd/steps.py`
      asks this by running `make -p -n` behind a positive grammar (#1165),
      because a textual reader cannot evaluate `ifeq` and answering the
      execution question from text is how a broken gate passed as `subsumed`.

The third reader was `lib/cicd/makefile.py::parse_makefile`, which asked the
DECLARATION question with a parser that stopped at the first physical line of a
rule: it returned 9 of this repository's 29 `verify` prerequisites, the ninth a
literal backslash, and told authors of a `deploy: build \` rule that they had no
quality prerequisites when the next line declared `test lint`. It is an adapter
over this module now. A third textual parser "fixed for continuations" would
only diverge again on the next shape nobody listed.

MOVED VERBATIM from `scripts/verify-coverage-check.py`, which had grown the
careful version: it joins continuations, strips make's comments (`verify: alpha
# beta` runs only alpha), keeps per-target recipes, understands multi-target
rules, and - the part that makes it an instrument rather than a parser -
REPORTS names it cannot validate in `unsupported` instead of dropping them.
Silently skipping an unrecognised spelling is how a target leaves the
population while the verdict still says everything was classified.

STDLIB ONLY, and that is a constraint not a preference: both consuming scripts
run in CI steps with no virtualenv, and `lib.cicd` must import without pydantic
(#1163) or the negative-controls battery cannot reach any control that touches
it.
"""

from __future__ import annotations

import re

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
        #: `.PHONY` and friends: the names a SPECIAL target declares. Kept
        #: rather than discarded (issue #1162, counter-model review) - the
        #: rule loop drops special targets from `declared` so they never become
        #: targets in their own right, which is right, but it also threw away
        #: WHAT THEY SAID. `lib/cicd/makefile.py` publishes `is_phony` on every
        #: target and had been reading it from its own parser; against this
        #: reader every target silently became non-phony.
        self.special: dict[str, list[str]] = {}
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
                    # A directive to make (`.PHONY:`), not a target anyone runs -
                    # but WHAT IT DECLARES is recorded before moving on.
                    for special in names.split():
                        if special in MAKE_SPECIAL_TARGETS:
                            self.special.setdefault(special, []).extend(
                                _prerequisites(rest)
                            )
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
