#!/usr/bin/env python3
"""Gate the "guard tests that shell out to a real binary" directive (issue #602).

CLAUDE.md carries the rule:

    A test that shells out to a real binary (`git`, `docker`, `gitleaks`) MUST
    guard with `@pytest.mark.skipif(shutil.which("<tool>") is None, ...)`.

The Woodpecker ``validate`` container (``uv:python3.11-bookworm-slim``) ships
none of those binaries, so an unguarded test does not fail politely - it raises
``FileNotFoundError`` and turns the pipeline red. The rule has now been forgotten
three times (#451, #489, #577), and it is structurally invisible locally: the dev
box HAS git, so ``make verify`` can never reproduce the failure. A directive that
has failed three times is not a directive problem, it is a missing gate.

This is that gate. It walks ``tests/`` with ``ast`` and reports any ``test_``
function that reaches a guarded binary without a matching ``shutil.which`` guard.

What counts as shelling out
---------------------------
A ``subprocess.run/Popen/call/check_call/check_output`` (or ``os.system`` /
``os.popen``) whose command is statically resolvable to a guarded binary:

- a list/tuple argv whose first element is a literal ``"git"`` / ``"docker"`` /
  ``"gitleaks"`` (the #577 shape),
- a literal command string (``shell=True``, ``os.system``, or an f-string) whose
  first token is one of them.

Both the DIRECT shape and the INDIRECT one are covered: a test that calls a
module-level helper which shells out is flagged too, transitively - several
existing CPP tests are written that way.

A fully dynamic argv (``subprocess.run(cmd)`` where ``cmd`` is built at runtime)
is deliberately NOT resolved. This gate targets the literal shape that has
actually failed three times, not every conceivable one; it is a floor, not proof
of total coverage.

What counts as a guard
----------------------
Any of these, on the test itself, its class, or the module (``pytestmark``):

- ``@pytest.mark.skipif(shutil.which("git") is None, ...)``
- ``@requires_git`` where ``requires_git = pytest.mark.skipif(shutil.which(...))``
  is assigned at module level (CPP's prevailing idiom),
- an in-body ``if shutil.which("bash") is None: pytest.skip(...)``.

Escape hatch: ``# binary-guard: allow <reason>`` on the call line or the ``def``
line suppresses a finding, for the rare intentional case.

Stdlib-only and binary-free by construction: it parses source text and never
executes anything, so it runs in the slim CI image - and, unlike the failure it
guards, it reproduces identically on a dev box.

Usage:
    python3 scripts/check-test-binary-guards.py           # scan tests/, exit 1 on findings
    python3 scripts/check-test-binary-guards.py --root DIR
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: Binaries absent from the CI ``validate`` image. ``bash`` is deliberately NOT
#: here - the image ships it, and including it would flag most of the suite.
GUARDED_BINARIES = frozenset({"git", "docker", "gitleaks"})

SUBPROCESS_FUNCS = frozenset({"run", "Popen", "call", "check_call", "check_output"})
OS_SHELL_FUNCS = frozenset({"system", "popen"})

ALLOW_RE = re.compile(r"#\s*binary-guard:\s*allow\b")


@dataclass(frozen=True)
class Finding:
    """One unguarded test."""

    path: Path
    lineno: int
    test: str
    binaries: tuple[str, ...]
    indirect_via: str | None

    def render(self, root: Path) -> str:
        try:
            rel: Path | str = self.path.relative_to(root)
        except ValueError:  # pragma: no cover - defensive
            rel = self.path
        tools = ", ".join(self.binaries)
        how = f" (via helper {self.indirect_via}())" if self.indirect_via else ""
        return (
            f"{rel}:{self.lineno}: {self.test} shells out to {tools}{how} "
            f"with no shutil.which() guard"
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


def _first_token_binary(command: str) -> str | None:
    """The binary a literal command string invokes, if it is a guarded one."""
    tokens = command.strip().split()
    if not tokens:
        return None
    name = tokens[0].rsplit("/", 1)[-1]
    return name if name in GUARDED_BINARIES else None


def _literal_str(node: ast.expr) -> str | None:
    """A literal string, including the constant prefix of an f-string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr) and node.values:
        head = node.values[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            return head.value
    return None


class _ShellOutFinder(ast.NodeVisitor):
    """Collect the guarded binaries a subtree statically invokes."""

    def __init__(self, subprocess_aliases: set[str], os_aliases: set[str]) -> None:
        self.subprocess_aliases = subprocess_aliases
        self.os_aliases = os_aliases
        self.binaries: set[str] = set()
        self.linenos: set[int] = set()

    def visit_Call(self, node: ast.Call) -> None:
        binary = self._binary_for(node)
        if binary is not None:
            self.binaries.add(binary)
            self.linenos.add(node.lineno)
        self.generic_visit(node)

    def _binary_for(self, node: ast.Call) -> str | None:
        if not node.args:
            return None
        kind = self._callee_kind(node.func)
        if kind is None:
            return None
        first = node.args[0]

        if kind == "os":
            literal = _literal_str(first)
            return _first_token_binary(literal) if literal is not None else None

        # subprocess: an argv sequence, or a command string.
        if isinstance(first, (ast.List, ast.Tuple)):
            if not first.elts:
                return None
            head = _literal_str(first.elts[0])
            if head is None:
                return None
            name = head.rsplit("/", 1)[-1]
            return name if name in GUARDED_BINARIES else None

        literal = _literal_str(first)
        return _first_token_binary(literal) if literal is not None else None

    def _callee_kind(self, func: ast.expr) -> str | None:
        """"subprocess", "os", or None - which family this callee belongs to."""
        dotted = _dotted(func)
        if not dotted:
            return None
        if "." in dotted:
            module, _, attr = dotted.rpartition(".")
            base = module.rsplit(".", 1)[-1]
            if base in self.subprocess_aliases and attr in SUBPROCESS_FUNCS:
                return "subprocess"
            if base in self.os_aliases and attr in OS_SHELL_FUNCS:
                return "os"
            return None
        # A bare name only counts when it was imported from subprocess/os.
        if dotted in self.subprocess_aliases and dotted in SUBPROCESS_FUNCS:
            return "subprocess"
        if dotted in self.os_aliases and dotted in OS_SHELL_FUNCS:
            return "os"
        return None


def _which_binaries(node: ast.AST) -> set[str]:
    """Guarded binaries named by ``shutil.which("x")`` calls inside a subtree."""
    found: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        dotted = _dotted(child.func)
        if dotted.rsplit(".", 1)[-1] != "which" or not child.args:
            continue
        literal = _literal_str(child.args[0])
        if literal is not None and literal in GUARDED_BINARIES:
            found.add(literal)
    return found


def _called_names(node: ast.AST) -> set[str]:
    """Bare function names called inside a subtree (``_git(...)`` -> ``_git``)."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            names.add(child.func.id)
    return names


# --------------------------------------------------------------------------- #
# Per-module analysis
# --------------------------------------------------------------------------- #
FunctionDef = ast.FunctionDef | ast.AsyncFunctionDef


class _ModuleAnalysis:
    """Everything the check needs to know about one test module."""

    def __init__(self, tree: ast.Module, source: str) -> None:
        self.tree = tree
        self.allow_lines = {
            i for i, line in enumerate(source.splitlines(), start=1) if ALLOW_RE.search(line)
        }
        self.subprocess_aliases, self.os_aliases = self._imports()
        self.skip_aliases = self._skip_aliases()
        self.module_guard = self._module_guard()
        self.helper_binaries = self._helper_binaries()

    # -- imports ----------------------------------------------------------- #
    def _imports(self) -> tuple[set[str], set[str]]:
        subprocess_aliases = {"subprocess"}
        os_aliases = {"os"}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "subprocess":
                        subprocess_aliases.add(alias.asname or "subprocess")
                    elif alias.name == "os":
                        os_aliases.add(alias.asname or "os")
            elif isinstance(node, ast.ImportFrom):
                if node.module == "subprocess":
                    subprocess_aliases.update(a.asname or a.name for a in node.names)
                elif node.module == "os":
                    os_aliases.update(a.asname or a.name for a in node.names)
        return subprocess_aliases, os_aliases

    # -- guards ------------------------------------------------------------ #
    def _skip_aliases(self) -> dict[str, set[str]]:
        """Module-level ``requires_git = pytest.mark.skipif(shutil.which(...))``."""
        aliases: dict[str, set[str]] = {}
        for node in self.tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            if not _dotted(node.value.func).endswith("skipif"):
                continue
            binaries = _which_binaries(node.value)
            if not binaries:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    aliases[target.id] = binaries
        return aliases

    def _decorator_guard(self, decorators: list[ast.expr]) -> set[str]:
        guarded: set[str] = set()
        for dec in decorators:
            guarded |= self._expr_guard(dec)
        return guarded

    def _expr_guard(self, node: ast.expr) -> set[str]:
        if isinstance(node, ast.Name):
            return set(self.skip_aliases.get(node.id, ()))
        if isinstance(node, (ast.List, ast.Tuple)):
            guarded: set[str] = set()
            for elt in node.elts:
                guarded |= self._expr_guard(elt)
            return guarded
        if isinstance(node, ast.Call):
            dotted = _dotted(node.func)
            if dotted.rsplit(".", 1)[-1] in {"skipif", "skip"}:
                return _which_binaries(node)
            # e.g. `requires_git(reason=...)` - alias reused as a factory.
            if isinstance(node.func, ast.Name):
                return set(self.skip_aliases.get(node.func.id, ()))
        return set()

    def _module_guard(self) -> set[str]:
        """``pytestmark = requires_git`` (or a list of markers) at module level."""
        guarded: set[str] = set()
        for node in self.tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
            ):
                guarded |= self._expr_guard(node.value)
        return guarded

    def _body_guard(self, func: FunctionDef) -> set[str]:
        """An in-body ``if shutil.which("x") is None: pytest.skip(...)``."""
        skips = any(
            isinstance(child, ast.Call) and _dotted(child.func).rsplit(".", 1)[-1] == "skip"
            for child in ast.walk(func)
        )
        return _which_binaries(func) if skips else set()

    # -- shell-outs -------------------------------------------------------- #
    def _shell_out(self, node: ast.AST) -> _ShellOutFinder:
        finder = _ShellOutFinder(self.subprocess_aliases, self.os_aliases)
        finder.visit(node)
        return finder

    def _helper_binaries(self) -> dict[str, set[str]]:
        """Module-level helpers that reach a guarded binary, transitively.

        The indirect shape the issue calls out: a ``test_`` that never names
        ``git`` itself but calls ``_git()``, which does.
        """
        helpers: dict[str, FunctionDef] = {
            node.name: node
            for node in self.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("test_")
        }
        direct = {name: self._shell_out(node).binaries for name, node in helpers.items()}
        calls = {name: _called_names(node) & helpers.keys() for name, node in helpers.items()}

        # Fixpoint: propagate along the call graph until nothing new appears.
        changed = True
        while changed:
            changed = False
            for name, callees in calls.items():
                for callee in callees:
                    new = direct[callee] - direct[name]
                    if new:
                        direct[name] |= new
                        changed = True
        return {name: bins for name, bins in direct.items() if bins}


def _check_module(path: Path, source: str) -> list[Finding]:
    tree = ast.parse(source, filename=str(path))
    analysis = _ModuleAnalysis(tree, source)
    findings: list[Finding] = []

    def visit(node: ast.AST, class_guard: set[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, class_guard | analysis._decorator_guard(child.decorator_list))
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name.startswith("test_"):
                    finding = _check_test(path, analysis, child, class_guard)
                    if finding is not None:
                        findings.append(finding)
            # Nested defs inside a test are part of that test's subtree already.

    visit(tree, set())
    return findings


def _check_test(
    path: Path,
    analysis: _ModuleAnalysis,
    func: FunctionDef,
    class_guard: set[str],
) -> Finding | None:
    direct = analysis._shell_out(func)
    needed = set(direct.binaries)
    indirect_via: str | None = None
    for name in sorted(_called_names(func)):
        helper = analysis.helper_binaries.get(name)
        if helper:
            if indirect_via is None:
                indirect_via = name
            needed |= helper
    if not needed:
        return None

    # A `# binary-guard: allow <reason>` on any shell-out line, or on the def.
    # For the indirect shape there is no call line to annotate, so the def line
    # is the escape.
    allow_lines = analysis.allow_lines
    if func.lineno in allow_lines or any(line in allow_lines for line in direct.linenos):
        return None

    guarded = (
        class_guard
        | analysis.module_guard
        | analysis._decorator_guard(func.decorator_list)
        | analysis._body_guard(func)
    )
    missing = needed - guarded
    if not missing:
        return None
    return Finding(
        path=path,
        lineno=func.lineno,
        test=func.name,
        binaries=tuple(sorted(missing)),
        indirect_via=indirect_via if not direct.binaries else None,
    )


def check_paths(paths: list[Path]) -> list[Finding]:
    """Check the given test modules; returns findings sorted by location."""
    findings: list[Finding] = []
    for path in sorted(paths):
        findings.extend(_check_module(path, path.read_text(encoding="utf-8")))
    return sorted(findings, key=lambda f: (str(f.path), f.lineno))


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
        print(f"binary-guards: no tests/ directory under {root}", file=sys.stderr)
        return 0

    findings = check_tree(tests_dir)
    if not findings:
        print("binary-guards: ok - every shelling-out test is guarded")
        return 0

    print(f"binary-guards: {len(findings)} unguarded test(s)\n")
    for finding in findings:
        print(f"  {finding.render(root)}")
    print(
        "\nAdd a guard (CLAUDE.md core directive, issue #602):\n"
        '    requires_git = pytest.mark.skipif(\n'
        '        shutil.which("git") is None, reason="git absent in the CI validate image"\n'
        "    )\n"
        "    @requires_git\n"
        "    def test_...\n"
        "Intentional exception: append `# binary-guard: allow <reason>` to the def line."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
