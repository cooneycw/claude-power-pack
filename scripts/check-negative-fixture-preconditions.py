#!/usr/bin/env python3
"""Gate the "a negative-condition fixture asserts its own precondition" directive (issue #697).

CLAUDE.md carries the rule:

    A fixture that creates a NEGATIVE condition by constructing an environment
    (rather than removing one named thing) MUST assert the precondition holds
    before exercising the code under test.

The failure it prevents (found in #695, PR #695): a test proving that
``cpp-commands-link.sh --check`` fails open when ``git`` is absent emptied
``PATH`` to create the absence. That removes ``git`` - and also ``ln``,
``mkdir``, ``readlink`` and ``bash``. The script then failed for reasons that
had nothing to do with git, and the assertions STILL PASSED: no advisory
printed, exit code unchanged. Those are exactly what a correct fail-open
produces.

That is the defect class this repo has spent its 2026-08-11 wave removing
(#673, #674, #677, #685, #698): a measurement whose broken version is
indistinguishable from its working version. A fail-open test is one of the few
kinds whose passing state carries almost no information on its own, so the
precondition assertion is not a nicety - it is the entire difference between
the test proving something and proving nothing.

The shipped fixture is the shape this gate looks for::

    assert shutil.which("git", path=str(stub_path)) is None, "fixture must lack git"

What counts as a negative-condition fixture
-------------------------------------------
A function that REPLACES ``PATH`` wholesale, where the new value does not
derive from the existing ``PATH``. Three syntactic shapes, all equally visible
to a parser:

- ``env["PATH"] = str(stub)`` / ``os.environ["PATH"] = ""`` - subscript assign
- ``monkeypatch.setenv("PATH", x)``
- ``subprocess.run(..., env={"PATH": str(stub)})`` - a DICT LITERAL carrying a
  ``PATH`` key, added for issue #933

Replacing the search path is how a test makes a *tool* absent, and these are
the shapes of "constructed absence" that are statically visible.

The dict literal was missing until #933 and is the reason this gate's success
message used to overclaim past its own stated scope. Six live sites used it,
two of them fail-open tests of the exact #695 class this gate was built from -
a blind spot inside the shape the gate already claimed to cover, not one of the
acknowledged out-of-scope shapes below.

What is deliberately NOT flagged
--------------------------------
The three shapes issue #697 names as safe, so the convention cannot be
over-applied:

- **A PATH prepend** - ``env["PATH"] = f"{bindir}:{env['PATH']}"`` ADDS a stub
  without removing anything, so there is no absence to assert.
- **``monkeypatch.delenv("X", raising=False)``** - removes exactly one named
  variable, deterministically. Direct removal needs no guard.
- **Outcome assertions** (``assert not path.exists()`` about what the code
  under test produced) - a different thing entirely from a fixture
  precondition.

Scope: this is a FLOOR, not proof of total coverage
---------------------------------------------------
The documented convention is broader than anything a parser can see: "a tool
absent, a path missing, a capability unavailable" has no single syntactic
shape. This gate covers the one shape that has actually failed, exactly as
``check-test-binary-guards.py`` (#602) covers the literal argv shape and says
so. Two known limits, both deliberate:

- the precondition assertion must live in the SAME function as the
  replacement; one lifted into a helper reads as missing here,
- assertion ORDER is not checked - presence is. A precondition asserted after
  the exercise still satisfies this gate, though not the directive's intent,
- only an assertion whose test CALLS ``which`` counts. ``assert not
  (bindir / "curl").exists()`` does not satisfy this gate, and deliberately so:
  a file that exists but is not executable, or a PATH assembled with the wrong
  separator, passes an existence check and fails a lookup. The gate wants the
  lookup.

Both limits are now STATED IN THE SUCCESS MESSAGE rather than only here (#933).
A scope that lives only in a docstring is a scope the reader of the green line
never sees.

Escape hatch: ``# negative-fixture: allow <reason>`` on the ``def`` line, the
assignment line, or the line above it.

Stdlib-only and binary-free by construction: it parses source text and never
executes anything, so it gives the same verdict in the slim CI image as on a
dev box.

Usage:
    python3 scripts/check-negative-fixture-preconditions.py       # scan tests/, exit 1 on findings
    python3 scripts/check-negative-fixture-preconditions.py --root DIR
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: sys.path is set EXPLICITLY rather than inherited: this gate runs as a CI step
#: AND under its own negative control, both with no virtualenv and no
#: PYTHONPATH, so an import that works from a dev shell would fail exactly where
#: the gate is load-bearing (the verify-coverage-check.py pattern).
#:
#: The import is MODULE-LEVEL, where issue #1169 had to defer `lib.cicd` inside
#: a function. The difference is the dependency, not the mechanism: `lib.cicd`
#: pulls pydantic, and the control image ships no third-party packages at all,
#: while `lib.sourcelines` imports nothing but `re`. Measured under both gates'
#: controls before choosing this form - see issue #1110.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.sourcelines import source_lines  # noqa: E402

#: The environment variable whose wholesale replacement constructs an absence.
#: Deliberately just PATH: replacing HOME or a config var wholesale is ordinary
#: test setup, not a constructed negative condition, and flagging it would be
#: exactly the over-application issue #697 warns against.
#: NEGATIVE-CONTROL: controls/check-negative-fixture-preconditions

TARGET_ENV_VAR = "PATH"

ALLOW_RE = re.compile(r"#\s*negative-fixture:\s*allow\b")

#: Calls that read an environment variable, for the "derives from the existing
#: PATH" test - ``env.get("PATH")``, ``os.getenv("PATH")``.
ENV_READ_FUNCS = frozenset({"get", "getenv"})


@dataclass(frozen=True)
class Finding:
    """One PATH-replacing fixture with no precondition assertion."""

    path: Path
    lineno: int
    func: str
    assign_lineno: int

    def render(self, root: Path) -> str:
        try:
            rel: Path | str = self.path.relative_to(root)
        except ValueError:  # pragma: no cover - defensive
            rel = self.path
        return (
            f"{rel}:{self.assign_lineno}: {self.func} replaces {TARGET_ENV_VAR} "
            f"wholesale with no precondition assertion"
        )


# --------------------------------------------------------------------------- #
# Small AST helpers
# --------------------------------------------------------------------------- #
def _dotted(node: ast.expr) -> str:
    """Render a Name/Attribute chain as a dotted string ("" if it is neither)."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def _literal_str(node: ast.expr | None) -> str | None:
    """A literal string constant, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _subscript_key(node: ast.Subscript) -> str | None:
    """The literal string key of ``x["key"]``, else None."""
    return _literal_str(node.slice)


def _reads_target_var(node: ast.expr) -> bool:
    """Does this expression read the EXISTING value of the target var?

    ``f"{stub}:{env['PATH']}"`` does - it is a prepend, which adds a stub
    without removing anything. ``str(stub_path)`` does not - it is a wholesale
    replacement, and that is the shape that constructs an absence.
    """
    for child in ast.walk(node):
        if isinstance(child, ast.Subscript) and _subscript_key(child) == TARGET_ENV_VAR:
            return True
        if isinstance(child, ast.Call) and child.args:
            name = _dotted(child.func).rsplit(".", 1)[-1]
            if name in ENV_READ_FUNCS and _literal_str(child.args[0]) == TARGET_ENV_VAR:
                return True
    return False


def _statement_sites(stmt: ast.stmt) -> list[int]:
    """EVERY line at which ``stmt`` replaces the target var wholesale.

    A list, not a single line (#933, found by review). `envs = [{"PATH": "/a"},
    {"PATH": "/b"}]` is one statement carrying two replacements; returning the
    first meant the denominator undercounted, and - worse - an ``allow`` comment
    on the first line could suppress the statement while the second replacement
    vanished from the population entirely.

    Covers both idioms in this suite:
      - ``env["PATH"] = <value>`` / ``os.environ["PATH"] = <value>``
      - ``monkeypatch.setenv("PATH", <value>)``
    """
    sites: list[int] = []

    if isinstance(stmt, ast.Assign):
        for target in stmt.targets:
            if isinstance(target, ast.Subscript) and _subscript_key(target) == TARGET_ENV_VAR:
                if not _reads_target_var(stmt.value):
                    sites.append(target.lineno)
        # No `return None` here. `env = {"PATH": str(stub)}` is an Assign whose
        # target is a plain Name, so an early return on this branch would skip
        # the dict-literal scan below for that statement.
        #
        # MEASURED CORRECTION (#933): restoring the early return changes no
        # verdict, because `_function_sites` walks with `ast.walk(func)` and a
        # FunctionDef IS an `ast.stmt` - so the function node itself reaches the
        # dict scan and finds every dict in the body anyway. A mutation proved
        # that; the first draft of this comment asserted the removal was
        # load-bearing and it is not. It stays out because relying on the
        # FunctionDef-as-statement coincidence is a worse thing to depend on
        # than an explicit fall-through, but the honest claim is redundancy,
        # not necessity.

    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        call = stmt.value
        if _dotted(call.func).rsplit(".", 1)[-1] == "setenv" and len(call.args) >= 2:
            if _literal_str(call.args[0]) == TARGET_ENV_VAR and not _reads_target_var(call.args[1]):
                sites.append(call.lineno)

    # A dict literal carrying PATH, in ANY statement shape - passed inline to
    # subprocess.run, assigned, returned. The derived test is the same one the
    # other shapes use, so `{"PATH": f"{stub}:{env['PATH']}"}` stays a prepend
    # and is still never flagged.
    for node in ast.walk(stmt):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            # `key is None` is the `{**base, ...}` unpacking entry, which has a
            # value and no key. It is not a PATH write in its own right - what
            # `base` contains is not statically knowable - so it is skipped, and
            # an explicit `"PATH":` entry in the same literal is still caught on
            # its own iteration. mypy found this: `_literal_str` tolerates None,
            # `key.lineno` does not.
            if key is None:
                continue
            if _literal_str(key) == TARGET_ENV_VAR and not _reads_target_var(value):
                sites.append(key.lineno)
    return sites


def _has_precondition_assert(func: ast.AST) -> bool:
    """An ``assert`` in this function proving the constructed absence.

    The canonical shape is ``assert shutil.which("git", path=...) is None``;
    any ``assert`` whose condition calls ``which`` counts, since that is the
    only way to interrogate a search path.
    """
    for child in ast.walk(func):
        if not isinstance(child, ast.Assert):
            continue
        for sub in ast.walk(child.test):
            if isinstance(sub, ast.Call) and _dotted(sub.func).rsplit(".", 1)[-1] == "which":
                return True
    return False


# --------------------------------------------------------------------------- #
# Per-module analysis
# --------------------------------------------------------------------------- #
FunctionDef = ast.FunctionDef | ast.AsyncFunctionDef


def _nested_function_linenos(func: FunctionDef) -> set[int]:
    """Line numbers belonging to functions nested inside ``func``.

    A replacement inside a nested helper is attributed to that helper when it
    is visited in its own right, so the outer function must not double-report
    it.
    """
    lines: set[int] = set()
    for child in ast.walk(func):
        if child is func or not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(child):
            if hasattr(node, "lineno"):
                lines.add(node.lineno)
    return lines


def _function_sites(func: FunctionDef, allow_lines: set[int]) -> list[int]:
    """Every wholesale replacement line in ``func`` - the inspected population.

    Split out of ``_check_function`` (#933) so the count the success message
    reports and the findings it reports come from ONE walk. A second traversal
    written to produce the denominator would be a second population to keep in
    sync, which is the #840 lesson one level up: the number would drift from the
    verdict and both would stay green.
    """
    if func.lineno in allow_lines:
        return []

    nested = _nested_function_linenos(func)

    # Pass 1: every replacement line, BEFORE any exclusion. The allow-hatch
    # below needs to know whether the preceding line is itself a replacement,
    # which cannot be decided while still discovering them.
    raw: list[int] = []
    for stmt in ast.walk(func):
        if not isinstance(stmt, ast.stmt):
            continue
        for lineno in _statement_sites(stmt):
            if lineno in nested:
                continue
            if lineno not in raw:
                raw.append(lineno)

    # Pass 2: apply the escape hatch.
    sites: list[int] = []
    for lineno in raw:
        if lineno in allow_lines:
            continue
        # `# negative-fixture: allow` is also honoured on the line ABOVE, so the
        # comment can sit on its own line. That allowance must NOT fire when the
        # line above is another replacement (#933, found by review): an allow on
        # one site was silently deleting its NEIGHBOUR from the population - not
        # merely unreporting it, but removing it from the denominator, so the
        # gate printed "0 replacements" for a file holding two. A hatch that
        # suppresses a site nobody exempted is the overclaim this change exists
        # to remove, arriving through the exemption mechanism instead.
        if (lineno - 1) in allow_lines and (lineno - 1) not in raw:
            continue
        sites.append(lineno)
    return sorted(sites)


def _check_function(path: Path, func: FunctionDef, allow_lines: set[int]) -> Finding | None:
    sites = _function_sites(func, allow_lines)
    if not sites:
        return None
    if _has_precondition_assert(func):
        return None
    return Finding(path=path, lineno=func.lineno, func=func.name, assign_lineno=sites[0])


@dataclass(frozen=True)
class Survey:
    """What the gate INSPECTED, alongside what it found (issue #933).

    The success message used to read "every constructed absence asserts its
    precondition". "Every" is a claim about a class; this gate inspects three
    syntactic shapes of one of them. A reader had no way to tell a green that
    means "I looked at eight sites and all eight assert" from a green that
    means "I could not see any of them", and those are different facts -
    detector-contracts.md question 1, on this gate's own output.

    So the denominator ships with the verdict. Counted from the same walk that
    produces the findings, never a second traversal.
    """

    files_scanned: int
    sites: int
    unasserted_sites: int
    files_with_sites: int
    findings: list[Finding]


#: What this gate cannot see. Named in the OUTPUT, not only in the docstring:
#: a scope that lives only in the source is a scope the reader of the green
#: line never encounters.
NOT_INSPECTED = (
    "absences built by chmod, a stub's exit status, a container image or "
    "import patching; an assertion lifted into a fixture; assertion ORDER; "
    "WHICH path an assertion covers - one `which` assert clears every "
    "replacement in its function; and two replacements on ONE source line "
    "count as one, because a site is identified by its line"
)


def _check_module(path: Path, source: str) -> list[Finding]:
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover - a broken test file is pytest's problem
        return []

    allow_lines = {
        i for i, line in enumerate(source_lines(source), start=1) if ALLOW_RE.search(line)
    }

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            finding = _check_function(path, node, allow_lines)
            if finding is not None:
                findings.append(finding)
    return findings


def survey_paths(paths: list[Path]) -> Survey:
    """Findings AND the population they were drawn from, from one traversal."""
    findings: list[Finding] = []
    sites = 0
    unasserted = 0
    files_with_sites = 0
    for path in sorted(paths):
        source = path.read_text(encoding="utf-8")
        findings.extend(_check_module(path, source))

        tree = ast.parse(source)
        allow_lines = {
            i for i, line in enumerate(source_lines(source), start=1) if ALLOW_RE.search(line)
        }
        module_sites = 0
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            func_sites = _function_sites(node, allow_lines)
            module_sites += len(func_sites)
            # The numerator must be in the same UNIT as the denominator (#933,
            # found by review). `len(findings)` counts FUNCTIONS - one finding
            # per function however many replacements it holds - so "1 of 2" was
            # reported for a function whose two replacements BOTH lacked an
            # assertion. A ratio whose halves count different things is a
            # specific, checkable-looking number that is wrong.
            if func_sites and not _has_precondition_assert(node):
                unasserted += len(func_sites)
        sites += module_sites
        if module_sites:
            files_with_sites += 1

    return Survey(
        files_scanned=len(paths),
        sites=sites,
        unasserted_sites=unasserted,
        files_with_sites=files_with_sites,
        findings=sorted(findings, key=lambda f: (str(f.path), f.assign_lineno)),
    )


def check_paths(paths: list[Path]) -> list[Finding]:
    """Check the given test modules; returns findings sorted by location."""
    return survey_paths(paths).findings


def test_files(tests_dir: Path) -> list[Path]:
    """The modules this gate scans - the single definition of its population.

    Issue #840: main()'s empty-scan check and check_tree()'s self-check caller
    (tests/test_negative_fixture_preconditions.py:102) both need this exact
    set, and a second copy of the glob is a second population to keep in sync -
    change what counts as a test file in one and the gate scans a different set
    than the repo's own self-check asserts against, both staying green.
    """
    return [p for p in tests_dir.rglob("*.py") if p.name.startswith(("test_", "conftest"))]


def check_tree(tests_dir: Path) -> list[Finding]:
    """Check every ``test_*.py`` (and ``conftest.py``) under ``tests_dir``."""
    return check_paths(test_files(tests_dir))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repo root (default: the checkout this script lives in)",
    )
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        print(f"negative-fixture: no tests/ directory under {root} - nothing was scanned")
        return 1

    # Keyed on files scanned, not directory existence (issue #840): a tests/
    # that exists but holds no test_*.py/conftest.py is the same "examined
    # nothing" condition as a missing directory, and un-keyed on it the "ok"
    # message below would claim every precondition is asserted for a
    # population of zero - a false clean bill of health, not merely a missed
    # report.
    paths = test_files(tests_dir)
    if not paths:
        print(f"negative-fixture: tests/ under {root} contains no test files - nothing was scanned")
        return 1

    survey = survey_paths(paths)
    findings = survey.findings
    if not findings:
        # The denominator, not a quantifier (#933, the #952 form). "every" was a
        # claim about a class this gate inspects three syntactic shapes of; a
        # reader could not tell "eight sites, all assert" from "I saw none".
        # "assert their precondition" was itself an overclaim (#933, found by
        # review). The gate knows only that the ENCLOSING FUNCTION contains a
        # `which` assertion; it does not check that the assertion covers the
        # path this replacement built. Two replacements and one assertion read
        # as both asserted. So the message says what was actually established.
        print(
            f"negative-fixture: ok - {survey.sites} wholesale {TARGET_ENV_VAR} "
            f"replacement(s) in {survey.files_with_sites} of {survey.files_scanned} "
            f"test file(s) are in functions that assert a precondition"
        )
        print(f"  not inspected: {NOT_INSPECTED}")
        return 0

    print(
        f"negative-fixture: {survey.unasserted_sites} of {survey.sites} wholesale "
        f"{TARGET_ENV_VAR} replacement(s) lack a precondition assertion, in "
        f"{len(findings)} function(s) "
        f"({survey.files_scanned} test file(s) scanned)\n"
    )
    for finding in findings:
        print(f"  {finding.render(root)}")
    print(
        "\nAssert the absence you built (CLAUDE.md core directive, issue #697):\n"
        '    assert shutil.which("git", path=str(stub_path)) is None, "fixture must lack git"\n'
        "\nA fail-open test's success assertions - nothing printed, exit code\n"
        "unchanged - are also what a completely broken fixture produces. The\n"
        "precondition guard is what separates them, and it costs one line.\n"
        "Intentional exception: append `# negative-fixture: allow <reason>`."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
