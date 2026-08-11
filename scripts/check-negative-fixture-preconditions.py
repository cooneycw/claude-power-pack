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
A function that REPLACES ``PATH`` wholesale - ``env["PATH"] = str(stub)``,
``os.environ["PATH"] = ""``, ``monkeypatch.setenv("PATH", x)`` - where the new
value does not derive from the existing ``PATH``. Replacing the search path is
how a test makes a *tool* absent, and it is the one shape of "constructed
absence" that is statically visible.

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
  the exercise still satisfies this gate, though not the directive's intent.

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

#: The environment variable whose wholesale replacement constructs an absence.
#: Deliberately just PATH: replacing HOME or a config var wholesale is ordinary
#: test setup, not a constructed negative condition, and flagging it would be
#: exactly the over-application issue #697 warns against.
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


def _replacement_lineno(stmt: ast.stmt) -> int | None:
    """The line at which ``stmt`` replaces the target var wholesale, else None.

    Covers both idioms in this suite:
      - ``env["PATH"] = <value>`` / ``os.environ["PATH"] = <value>``
      - ``monkeypatch.setenv("PATH", <value>)``
    """
    if isinstance(stmt, ast.Assign):
        for target in stmt.targets:
            if isinstance(target, ast.Subscript) and _subscript_key(target) == TARGET_ENV_VAR:
                if not _reads_target_var(stmt.value):
                    return target.lineno
        return None

    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        call = stmt.value
        if _dotted(call.func).rsplit(".", 1)[-1] == "setenv" and len(call.args) >= 2:
            if _literal_str(call.args[0]) == TARGET_ENV_VAR and not _reads_target_var(call.args[1]):
                return call.lineno
    return None


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


def _check_function(path: Path, func: FunctionDef, allow_lines: set[int]) -> Finding | None:
    if func.lineno in allow_lines:
        return None

    nested = _nested_function_linenos(func)
    for stmt in ast.walk(func):
        if not isinstance(stmt, ast.stmt):
            continue
        lineno = _replacement_lineno(stmt)
        if lineno is None or lineno in nested:
            continue
        if lineno in allow_lines or (lineno - 1) in allow_lines:
            continue
        if _has_precondition_assert(func):
            return None
        return Finding(path=path, lineno=func.lineno, func=func.name, assign_lineno=lineno)
    return None


def _check_module(path: Path, source: str) -> list[Finding]:
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover - a broken test file is pytest's problem
        return []

    allow_lines = {
        i for i, line in enumerate(source.splitlines(), start=1) if ALLOW_RE.search(line)
    }

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            finding = _check_function(path, node, allow_lines)
            if finding is not None:
                findings.append(finding)
    return findings


def check_paths(paths: list[Path]) -> list[Finding]:
    """Check the given test modules; returns findings sorted by location."""
    findings: list[Finding] = []
    for path in sorted(paths):
        findings.extend(_check_module(path, path.read_text(encoding="utf-8")))
    return sorted(findings, key=lambda f: (str(f.path), f.assign_lineno))


def check_tree(tests_dir: Path) -> list[Finding]:
    """Check every ``test_*.py`` (and ``conftest.py``) under ``tests_dir``."""
    paths = [p for p in tests_dir.rglob("*.py") if p.name.startswith(("test_", "conftest"))]
    return check_paths(paths)


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
        print(f"negative-fixture: no tests/ directory under {root}", file=sys.stderr)
        return 0

    findings = check_tree(tests_dir)
    if not findings:
        print("negative-fixture: ok - every constructed absence asserts its precondition")
        return 0

    print(f"negative-fixture: {len(findings)} unasserted precondition(s)\n")
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
