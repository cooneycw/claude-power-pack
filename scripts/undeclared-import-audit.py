#!/usr/bin/env python3
"""Refuse an import that no dependency metadata declares (issue #1041).

`scripts/dependency-audit.py` asks OSV about what `uv.lock` PINS. A module that
the code imports directly and that nothing declares is never queried, so it
cannot appear in any advisory row however vulnerable it is - and a scan that
never looked prints the same clean line as one that looked and found nothing.
That blind spot is stated in `docs/security/dependency-advisory-dispositions.md`;
this gate is the instrument that closes it.

WHAT WAS MEASURED, AND WHY THE ISSUE UNDERCOUNTED IT. #1041 was filed against a
single instance - `scrape_reddit.py:11` doing `import requests` with only
`types-requests`, the type STUBS, in the lock. Run over the tree, the same
question returned three module-level instances and nine guarded ones, in six
distinct packages, several of them inside `lib/creds/` - this repository's own
credential retrieval and secrets UI. One was found by reading the issue; the
other eleven were found by building the instrument. That asymmetry is the
argument for the instrument.

---------------------------------------------------------------------------
The question this gate asks, and the one it deliberately does not
---------------------------------------------------------------------------
It asks: does a MODULE-LEVEL, UNGUARDED import name resolve to a distribution
that `pyproject.toml` declares?

It does NOT ask about an import that cannot reach an importer, and there are
exactly three of those:

  - inside a function body (a lazy import, e.g. `lib/creds/ui/app.py`'s
    `_import_deps()`),
  - inside a `try:` whose handler catches `ImportError` (the documented
    `BOTO3_AVAILABLE` / `_HAVE_PSYCOPG` pattern),
  - inside the body of `if TYPE_CHECKING:`, which never executes.

EVERYTHING ELSE EXECUTES, and the first cut of this gate got nine of those wrong -
found by the counter-model review, not by the author. A `finally:`, a `try`'s
`else:`, an `except ImportError:` handler's own body (the guard protects the name
in the `try`, not the fallback that runs when it fails), a module-level `with`,
`for` or `while` body, a class body, the `else:` of an `if TYPE_CHECKING:`, and
the body of `if not TYPE_CHECKING:` all run during import, and all nine were
reported clean. Two of them were one mistake twice: the TYPE_CHECKING exemption
was decided by searching the test expression for the NAME, so `not TYPE_CHECKING`
matched it. An `if` whose condition this gate cannot classify fails CLOSED - both
branches are treated as executing - because a condition it cannot read is one
whose branches might run.

That boundary is a DECISION, not an oversight, and #1041 resolved the other half
rather than leaving it to this gate: the six packages behind those nine sites -
boto3, botocore, python-dotenv, psycopg, fastapi, uvicorn - are now declared as
`[project.optional-dependencies]` extras, so they are in `uv.lock` and under the
advisory scan while still being installed by nobody. Guarded is not the same as
declared; the guard stops a crash, and declaring stops the blindness. Had they
been left undeclared, this gate would have been green over them, which is the
reason the boundary is written here rather than assumed.

WHAT THIS GATE CANNOT SEE, said so that its green is not read as more than it
is: a dynamic `importlib.import_module(name)` or a `__import__` call, since
neither is a syntactic import; and a package whose distribution is declared but
whose CODE is never reached. Both are outside what a static import scan can
answer, and neither is quietly counted as clean - the success line reports the
population it examined so the claim is bounded by construction.

---------------------------------------------------------------------------
Resolution reads COMMITTED METADATA ONLY - never the ambient environment
---------------------------------------------------------------------------
`importlib.metadata.packages_distributions()` would map import names to
distributions exactly, and it is not used. It reads what happens to be INSTALLED,
so the gate's verdict would depend on the machine: green on a developer box that
has boto3 for unrelated reasons, red in CI. Issue #1044 closed precisely that
failure one gate over ("stop the pip-audit adapter passing on a skip or an
ambient scan"). So resolution is:

  1. the import name, PEP-503-normalized, equals a declared distribution name;
  2. or IMPORT_ALIASES maps it to one (the naming irregularities: `yaml` ships
     as `pyyaml`, `dotenv` as `python-dotenv`);
  3. otherwise it is a FINDING.

Step 3 is fail-CLOSED on purpose. A package this repository adds whose import
name differs from its distribution name, and for which nobody adds an alias,
goes RED with a message naming the alias to add - it does not pass quietly. A
table that fails open would reintroduce the blindness the gate exists to remove.

THE STUB TRAP IS THE REASON NORMALIZATION IS EXACT AND NOT A SUBSTRING MATCH.
`types-requests` CONTAINS "requests"; a gate that asked "does this name appear in
the dependency list" would have reported #1041's own tree clean. That is not
hypothetical - it is the registered anchor, and `bad-stub-only-declaration` is
the case it misses.

---------------------------------------------------------------------------
The ledger, and why it has a stale direction
---------------------------------------------------------------------------
A file genuinely meant for a system interpreter is recorded in
`.undeclared-import-allow`, one line per (path, import name), tracked, counted,
and printed on every run. `woodpecker/bootstrap-secrets.py` is the live instance:
it is run by hand on the Woodpecker host (`tests/test_bootstrap.py` gives its
remediation as `python woodpecker/bootstrap-secrets.py`), not from the project
environment.

An entry that accounts for NOTHING is a finding too (`UNDECLARED-IMPORT-STALE`,
exit 1). Without that direction a line outlives the import it records and becomes
a permanent blindfold nobody re-reads - the same two-sided property
`.bandit-audit-allow` carries, and the reason neither is a `--skip`.

KNOWN BLIND SPOT, bounded rather than widened: a line is (path, name), so it
accepts that import in that file however many times it appears. Line numbers are
invalidated by every edit above them, and a ledger that reddens on unrelated
edits gets switched off (ADR 0009). Whether an accepted site is still the same
site is answered by review of the diff that moves it.

Usage:
    undeclared-import-audit.py [--root DIR] [--allow-file PATH] [--selftest]
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

#: NEGATIVE-CONTROL: controls/undeclared-import-audit
#:     Registered per ADR 0008. This gate LETS WORK THROUGH: `make verify` and
#:     the CI `undeclared-import-audit` step both read its green as "no
#:     module-level import in this tree is undeclared", and nothing downstream
#:     re-derives that. A blind version prints the identical clean line over the
#:     pre-#1041 tree, where three files imported three undeclared packages and
#:     had done since the initial commit.
#:
#:     The registered anchor is the SUBSTRING matcher - the plausible first cut,
#:     not a strawman - which reports #1041's own tree clean because
#:     `types-requests` contains "requests".

#: Directories whose Python is deliberately outside the population. A DENY list,
#: never an allow list of roots: a new top-level directory is therefore SCANNED
#: rather than silently skipped, which is the fail-closed direction. Every entry
#: is printed on every run, so narrowing is a visible decision.
PRUNE = (
    # A separate subproject with its own pyproject/lock; its imports are declared
    # against that metadata, not this one. Excluded from mypy for the same reason.
    "mcp-second-opinion",
    # Negative-control fixtures and frozen anchors (issue #924). Cases here are
    # DELIBERATELY undeclared - that is what they test - and an anchor must stay
    # byte-identical to the artifact it vendors.
    "controls",
    # Byte-identical generated copies of scripts/*.py (issue #555); scanning them
    # re-scans the originals and doubles every finding.
    "codex/skills",
    # Paired base/head fixture trees for the #953 prototype, same situation.
    "docs/research/forced-claim-prototype-2026-09-15/cases",
    # Never source; present in a working tree, absent from a clone.
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
)

#: Import name -> distribution name, for the cases where they differ. SMALL and
#: auditable by construction: a name missing from here does not pass, it REDS
#: with the alias to add (see the module docstring).
IMPORT_ALIASES = {
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
}

#: Directory name conventionally inserted onto `sys.path` by the module that
#: uses it. `tests/fixtures/delivery_pilots/pilots/*/check_*.py` does exactly
#: that before importing `retry` / `slugify`, which are local files - so without
#: this the gate would report two findings that are not imports of anything
#: third-party at all.
SYS_PATH_DIR = "src"

FINDING = "UNDECLARED-IMPORT:"
STALE = "UNDECLARED-IMPORT-STALE:"
UNKNOWN = "UNDECLARED-IMPORT-UNKNOWN:"

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_UNKNOWN = 2


class Unknown(Exception):
    """The gate could not establish its answer. Never the same as 'clean'."""


@dataclass(frozen=True)
class Import:
    path: str
    line: int
    name: str


@dataclass(frozen=True)
class AllowLine:
    raw: str
    lineno: int
    path: str
    name: str


def normalize(name: str) -> str:
    """PEP 503 name normalization, applied to both sides of every comparison."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def requirement_name(spec: str) -> str:
    """The distribution name out of a requirement string, without a parser dep."""
    return normalize(re.split(r"[<>=!~\[;\s]", spec, maxsplit=1)[0])


def declared_distributions(root: Path) -> set[str]:
    """Every distribution `pyproject.toml` declares - runtime AND every extra.

    An extra counts as declared. That is the whole mechanism #1041 used to close
    the guarded half: `uv` resolves every extra into `uv.lock`, so an extra is
    under the advisory scan even though `uv sync --extra dev` installs none of it.
    """
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        raise Unknown(f"{pyproject} is not present, so nothing declares anything - this run examined nothing")
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise Unknown(f"{pyproject} could not be parsed ({exc}), so the declared set is unknown") from exc

    project = data.get("project", {})
    names = {requirement_name(spec) for spec in project.get("dependencies", [])}
    for extra in project.get("optional-dependencies", {}).values():
        names |= {requirement_name(spec) for spec in extra}
    return {n for n in names if n}


def discover(root: Path) -> tuple[list[Path], list[str]]:
    """Every `.py` under `root`, walking with the declared prune list.

    Derived, never globbed, and never enumerated from a hardcoded root list: a
    directory added tomorrow is in the population by default.

    Returns the files and the virtual-environment directories that were pruned by
    marker, so the count can print rather than the exclusion being silent.
    """
    found: list[Path] = []
    environments: list[str] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError as exc:
            # os.walk swallows this and omits the subtree, which is a short
            # population wearing a clean verdict (the #962 lesson, one gate over).
            raise Unknown(f"{current} could not be read ({exc}), so the population is incomplete") from exc
        for entry in entries:
            if entry.is_symlink():
                continue
            rel = entry.relative_to(root).as_posix()
            if entry.is_dir():
                if rel in PRUNE or entry.name in PRUNE:
                    continue
                # A virtual environment is recognized by its MARKER, not by
                # guessing its name (counter-model review). `.venv` and `venv` are
                # two spellings out of many - `env`, `ENV`, `.direnv` - and an
                # environment that slipped the name list put its whole
                # site-packages tree into the population, so an installed
                # neighbour's imports would red this project against this
                # project's metadata and `make verify` would depend on what
                # someone had installed next door.
                if (entry / "pyvenv.cfg").is_file() or entry.name == "site-packages":
                    environments.append(rel)
                    continue
                stack.append(entry)
            elif entry.suffix == ".py":
                found.append(entry)
    return sorted(found), sorted(environments)


def provided_module_names(root: Path, files: list[Path]) -> tuple[set[str], dict[str, set[str]]]:
    """Module names this repository itself provides, so they are not third-party.

    Two sources, both derived, and they have DIFFERENT SCOPES - which is the
    correction the counter-model review forced:

      - ROOT-LEVEL names are global. `[tool.pytest.ini_options] pythonpath`
        declares the repository root as a `sys.path` entry, so every top-level
        package and module at the root is importable by its own name from
        anywhere in the tree.
      - A `src/` directory - the conventional `sys.path.insert` target - is
        scoped to its OWNER, the directory holding it. Only files under that
        owner can reach it, which is what `sys.path.insert(0, HERE / "src")`
        actually means.

    The first cut got both halves wrong and in the same direction, toward silence.
    It made every `src/` stem first-party EVERYWHERE, so
    `tests/fixtures/delivery_pilots/pilots/pilot-a-approach/src/retry.py`
    suppressed an unrelated production `import retry` anywhere in the repository.
    And it tested `path.parts`, the ABSOLUTE path, so a checkout living under any
    directory named `src` - `/home/user/src/claude-power-pack` - turned every
    Python file's stem into a global exemption and the verdict became a property
    of where the repository happened to sit on disk.

    The bound that REMAINS, stated rather than hoped about: a root-level file named
    `X.py` makes `import X` resolve as first-party anywhere, because
    `pythonpath = ["."]` genuinely makes that true. A file named `requests.py` at
    the root would therefore mask the finding this gate exists to raise - which is
    why the registered cases plant their known-bad import under a name no
    repository file provides.
    """
    global_names: set[str] = set()
    for entry in root.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            global_names.add(entry.name)
        elif entry.suffix == ".py":
            global_names.add(entry.stem)

    scoped: dict[str, set[str]] = {}
    for path in files:
        parts = path.relative_to(root).parts
        if SYS_PATH_DIR not in parts[:-1]:
            continue
        index = parts.index(SYS_PATH_DIR)
        owner = "/".join(parts[:index])
        below = parts[index + 1:]
        # The importable name is the IMMEDIATE child of the source root - a module
        # file's stem, or a package DIRECTORY's name. Collecting every descendant's
        # stem was wrong in both directions (counter-model re-review):
        # `tool/src/acme/requests.py` is `acme.requests`, so recording `requests`
        # masked an unrelated `import requests`; and `tool/src/acme/__init__.py`
        # recorded `__init__`, so a legitimate `import acme` was reported undeclared.
        scoped.setdefault(owner, set()).add(below[0][:-3] if len(below) == 1 else below[0])
    return global_names, scoped


def mutates_sys_path(tree: ast.Module) -> bool:
    """Does this module manipulate `sys.path`?

    The evidence a `src/` exemption requires (counter-model re-review). Scoping the
    exemption to a subtree narrowed the leak but did not close it: every file under
    an owner inherited its names whether or not anything put that directory on the
    path, so `tool/src/requests.py` beside a plain `import requests` in
    `tool/check.py` was still exempt with no `sys.path` insertion anywhere. A file
    that never touches `sys.path` cannot reach a directory that is not on it.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "path":
            if isinstance(node.value, ast.Name) and node.value.id == "sys":
                return True
        if isinstance(node, ast.ImportFrom) and node.module == "sys":
            if any(alias.name == "path" for alias in node.names):
                return True
    return False


def reachable(
    rel_path: str,
    name: str,
    global_names: set[str],
    scoped: dict[str, set[str]],
    sys_path_aware: bool,
) -> bool:
    """Is `name` provided to the file at `rel_path` by this repository itself?

    A root-level name is global, because `pythonpath = ["."]` genuinely makes it
    so. A `src/` name is granted only to a file that both lives under the owner
    AND manipulates `sys.path` itself - the two conditions together are what
    `sys.path.insert(0, HERE / "src")` actually means.
    """
    if name in global_names:
        return True
    if not sys_path_aware:
        return False
    parts = rel_path.split("/")[:-1]
    for depth in range(len(parts), -1, -1):
        if name in scoped.get("/".join(parts[:depth]), ()):
            return True
    return False


#: `ast.TryStar` is 3.11+; the project floor is 3.11, but resolving it here keeps
#: the tuple honest rather than assuming the attribute exists.
TRY_NODES = tuple(n for n in (ast.Try, getattr(ast, "TryStar", None)) if n is not None)

#: Compound statements whose body RUNS where the statement sits. A module-level
#: `with`, `for`, `while` or `class` body executes during import exactly as a bare
#: statement does - the first cut treated all four as deferred, and a planted
#: `import requests` in any of them was reported clean (counter-model review).
BODY_EXECUTES = (ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While, ast.ClassDef)


def _is_type_checking(node: ast.expr) -> bool:
    """`TYPE_CHECKING` or `<mod>.TYPE_CHECKING`, as the WHOLE test - not anywhere in it.

    The distinction is the bug this replaced. The first cut asked whether the name
    appeared anywhere under the test, so `if not TYPE_CHECKING:` matched and its
    body - which DOES execute - was exempted.
    """
    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    return isinstance(node, ast.Attribute) and node.attr == "TYPE_CHECKING"


def _type_checking_split(test: ast.expr, executing: bool) -> tuple[bool, bool]:
    """(does the body execute, does the else execute) for an `if` at import time.

    Only two shapes are recognized, and everything else FAILS CLOSED to "both
    execute". A test this function cannot read is a test whose branches might run,
    and an unreadable condition must not become an exemption.
    """
    if _is_type_checking(test):
        return False, executing
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) and _is_type_checking(test.operand):
        return executing, False
    return executing, executing


class ImportCollector:
    """Separate imports that RUN on import from imports that cannot.

    `hard` is what an importer executes; `deferred` is what it cannot reach - a
    function body, a `try:` guarded by an `ImportError` handler, an `if
    TYPE_CHECKING:` body. Everything else executes, including the parts the first
    cut got wrong: a `finally:`, a `try`'s `else:`, an exception handler's own
    body, a module-level `with`/`for`/`while`, a class body, and the `else:` of an
    `if TYPE_CHECKING:`.

    An `except ImportError:` handler's body is HARD on purpose. It is the fallback
    that runs when the guarded import fails, so an undeclared import there is an
    undeclared import that executes; the guard protects the name in the `try`, not
    the one in the handler.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.hard: list[Import] = []
        self.deferred: list[Import] = []

    def collect(self, tree: ast.Module) -> None:
        for stmt in tree.body:
            self._walk(stmt, executing=True)

    def _walk(self, stmt: ast.stmt, executing: bool) -> None:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            self._record(stmt, self.hard if executing else self.deferred)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in stmt.body:
                self._walk(inner, executing=False)
        elif isinstance(stmt, TRY_NODES):
            guarded = self._catches_import_error(stmt)
            for inner in stmt.body:
                self._walk(inner, executing and not guarded)
            for handler in stmt.handlers:
                for inner in handler.body:
                    self._walk(inner, executing)
            for inner in list(stmt.orelse) + list(stmt.finalbody):
                self._walk(inner, executing)
        elif isinstance(stmt, ast.If):
            body_exec, else_exec = _type_checking_split(stmt.test, executing)
            for inner in stmt.body:
                self._walk(inner, body_exec)
            for inner in stmt.orelse:
                self._walk(inner, else_exec)
        elif isinstance(stmt, BODY_EXECUTES):
            for inner in list(stmt.body) + list(getattr(stmt, "orelse", [])):
                self._walk(inner, executing)
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                for inner in case.body:
                    self._walk(inner, executing)

    def _record(self, node: ast.AST, bucket: list[Import]) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                bucket.append(Import(self.path, node.lineno, alias.name.split(".")[0]))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            bucket.append(Import(self.path, node.lineno, node.module.split(".")[0]))

    @staticmethod
    def _catches_import_error(stmt: ast.stmt) -> bool:
        for handler in getattr(stmt, "handlers", []):
            if handler.type is None:
                return True
            for node in ast.walk(handler.type):
                if isinstance(node, ast.Name) and node.id in {"ImportError", "ModuleNotFoundError", "Exception"}:
                    return True
        return False


def read_allow(allow_file: Path) -> list[AllowLine]:
    """Parse the ledger. Whole-line comments only, for the reason #962 records:
    `#` opens a comment and also opens every issue reference on a record."""
    if not allow_file.is_file():
        return []
    try:
        text = allow_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise Unknown(f"{allow_file} could not be read ({exc}), so accepted entries are unknown") from exc

    lines: list[AllowLine] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 3 or parts[0] != "allow":
            raise Unknown(f"{allow_file}:{lineno} is not `allow <path> <import-name> <issue>`: {stripped!r}")
        lines.append(AllowLine(raw=stripped, lineno=lineno, path=parts[1], name=parts[2]))
    return lines


def audit(root: Path, allow_file: Path) -> tuple[int, list[str]]:
    """Return (exit code, report lines)."""
    root = root.resolve()
    declared = declared_distributions(root)
    files, environments = discover(root)
    if not files:
        raise Unknown(f"no Python file was found under {root} - a zero-file population proves nothing")

    global_names, scoped_names = provided_module_names(root, files)
    stdlib = set(sys.stdlib_module_names)
    allow = read_allow(allow_file)

    findings: list[Import] = []
    deferred_names: set[str] = set()
    examined_names: set[str] = set()

    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, SyntaxError, ValueError) as exc:
            # "could not read it" and "it is clean" are different facts.
            raise Unknown(f"{rel} could not be parsed ({exc}), so its imports are unknown") from exc

        collector = ImportCollector(rel)
        collector.collect(tree)
        sys_path_aware = mutates_sys_path(tree)
        for imp in collector.deferred:
            if imp.name not in stdlib and not reachable(rel, imp.name, global_names, scoped_names, sys_path_aware):
                deferred_names.add(imp.name)
        for imp in collector.hard:
            if imp.name in stdlib or reachable(rel, imp.name, global_names, scoped_names, sys_path_aware):
                continue
            examined_names.add(imp.name)
            distribution = IMPORT_ALIASES.get(imp.name, imp.name)
            if normalize(distribution) not in declared:
                findings.append(imp)

    accepted: set[tuple[str, str]] = set()
    report: list[str] = []
    allowed_pairs = {(a.path, a.name): a for a in allow}
    gating: list[Import] = []
    for imp in findings:
        key = (imp.path, imp.name)
        if key in allowed_pairs:
            accepted.add(key)
        else:
            gating.append(imp)

    for imp in gating:
        distribution = IMPORT_ALIASES.get(imp.name, imp.name)
        hint = "" if distribution == imp.name else f" (distribution `{distribution}`)"
        report.append(
            f"{FINDING} {imp.path}:{imp.line} imports `{imp.name}`{hint}, which no "
            f"`pyproject.toml` dependency or extra declares"
        )

    stale = [a for a in allow if (a.path, a.name) not in accepted]
    for entry in stale:
        report.append(
            f"{STALE} {allow_file.name}:{entry.lineno} accepts `{entry.name}` in {entry.path}, "
            f"which is not an undeclared module-level import in this tree - the entry accounts for nothing"
        )

    prunes = ", ".join(PRUNE[:4]) + ", ..."
    summary = (
        f"undeclared-import-audit: {'ok - ' if not report else ''}"
        f"{len(files)} file(s) examined under {root.name}/ (pruned: {prunes}; "
        f"{len(environments)} virtual environment(s) by marker), "
        f"{len(examined_names)} distinct module-level third-party import name(s), "
        f"{len(gating)} undeclared, {len(accepted)} accepted, {len(stale)} stale allow line(s); "
        f"{len(deferred_names)} guarded/deferred name(s) are outside this gate's question"
    )
    report.append(summary)
    return (EXIT_FINDING if gating or stale else EXIT_OK), report


def selftest(repo_root: Path) -> int:
    """Prove the scan can SEE before any clean verdict is issued.

    A broken scan's zeros look exactly like real ones, so this points the real code
    path at two committed trees - one holding an undeclared module-level import it
    must report, one clean it must not - and fails if either answer is wrong.

    IT ASSERTS THE SIGNAL, NOT THE EXIT CODE, and the difference is a real defect
    the counter-model review found in the first cut. Reading only the exit code, a
    bad fixture whose planted import had stopped being detected but whose ledger
    had gone stale still exited 1, and this printed "reported the planted import" -
    an unrelated failure standing in for the detection, which is precisely the
    substitution `UNSIGNALLED` exists to refuse one harness over.

    It is the LIVE half; `controls/undeclared-import-audit` proves the adjudication
    on committed cases. Neither is sufficient alone.
    """
    live = repo_root / "controls" / "undeclared-import-audit" / "live"
    #: (fixture, expected exit, the (line prefix, substring) ONE finding must carry)
    expectations: tuple[tuple[Path, int, tuple[str, str] | None], ...] = (
        (live / "bad-undeclared", EXIT_FINDING, (f"{FINDING} scraper.py:", "`requests`")),
        (live / "good-clean", EXIT_OK, None),
    )
    for case, want, required in expectations:
        if not case.is_dir():
            print(f"{UNKNOWN} selftest fixture {case} is missing, so the scan was never shown able to see")
            return EXIT_UNKNOWN
        try:
            got, lines = audit(case, case / ".undeclared-import-allow")
        except Unknown as exc:
            print(f"{UNKNOWN} selftest on {case.name}: {exc}")
            return EXIT_UNKNOWN
        if got != want:
            print(f"{UNKNOWN} selftest on {case.name}: expected exit {want}, got {got}")
            for line in lines:
                print(f"  {line}")
            return EXIT_UNKNOWN
        if required is not None:
            prefix, substring = required
            # ONE LINE must carry BOTH the path and the name. Searching the joined
            # report for each independently let two unrelated lines supply one
            # half each - a `scraper.py` finding about some other package plus a
            # stale ledger entry mentioning `requests` scored as the planted
            # detection (counter-model re-review). That is the same substitution
            # this selftest was hardened against one pass earlier, one level down.
            if not any(line.startswith(prefix) and substring in line for line in lines):
                print(
                    f"{UNKNOWN} selftest on {case.name}: exited {got} with no single finding carrying both "
                    f"{prefix!r} and {substring!r} - the expected detection was replaced by some other failure"
                )
                for line in lines:
                    print(f"  {line}")
                return EXIT_UNKNOWN
        elif any(line.startswith(FINDING) for line in lines):
            print(f"{UNKNOWN} selftest on {case.name}: reported a finding on the tree it must stay silent on")
            return EXIT_UNKNOWN
    print("undeclared-import-audit: selftest ok - reported the planted import and stayed silent on the clean tree")
    return EXIT_OK


def repo_root_of(path: Path) -> Path:
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="tree to audit (default: the current directory)")
    parser.add_argument("--allow-file", default=None, help="ledger path (default: <root>/.undeclared-import-allow)")
    parser.add_argument("--selftest", action="store_true", help="run the live positive control and exit")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest(repo_root_of(Path(__file__).resolve().parent))

    root = Path(args.root)
    allow_file = Path(args.allow_file) if args.allow_file else root / ".undeclared-import-allow"
    try:
        code, report = audit(root, allow_file)
    except Unknown as exc:
        print(f"{UNKNOWN} {exc}")
        return EXIT_UNKNOWN
    for line in report:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
