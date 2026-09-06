#!/usr/bin/env python3
"""Gate the "guard tests that shell out to a real binary" directive (issue #602).

CLAUDE.md carries the rule:

    A test that shells out to a real binary (`git`, `docker`, `gitleaks`, `jq`) MUST
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
  first token is one of them,
- an argv that runs a REPO SHELL SCRIPT which itself calls a guarded binary -
  ``subprocess.run(["bash", str(CAP), "list", "--json"])`` where
  ``flow-driver-capability.sh`` builds its JSON with ``jq`` (the #783 shape;
  see "One hop through a shell script" below).

Both the DIRECT shape and the INDIRECT one are covered: a test that calls a
module-level helper which shells out is flagged too, transitively - several
existing CPP tests are written that way. The script hop composes with it, so a
``_run()`` wrapper that invokes a jq-using script flags its callers as well.

One hop through a shell script
------------------------------
``bash`` is deliberately NOT a guarded binary - the CI image ships it - so
``["bash", SCRIPT, ...]`` used to pass the gate no matter what SCRIPT ran. On
#783 that cost a red pipeline. The gate now follows exactly ONE more hop, and
only when it is as statically resolvable as everything else here:

- argv[0] must be ``bash`` or ``sh`` (an absolute path such as ``/bin/bash``
  is fine; its basename is what is matched),
- the first non-flag argument must resolve to a real file at check time, from
  the source text alone: a module-level ``Path`` constant
  (``ROOT = Path(__file__).resolve().parents[1]`` then
  ``CAP = ROOT / "scripts" / "flow-driver-capability.sh"`` - CPP's prevailing
  idiom), the same expression written inline, or a literal path,
- that file is then read and scanned for the guarded binaries it HARD-REQUIRES,
  with comments stripped (see below).

The scan is one level deep and text-only: a script that sources or execs a
SECOND script is not followed.

What "hard-requires" means, and why it is not just "mentions"
------------------------------------------------------------
Scanning for any mention of a binary is useless here: measured on this repo it
produced 266 findings, ~250 of them from scripts that run perfectly well without
the tool. A test does not go red because a script *mentions* ``git`` - it goes
red because the script cannot do its job without it. So a binary counts only when
BOTH of these hold:

1. **The script does not declare that it degrades.** A ``command -v <bin>``
   (or ``type``/``hash``) preflight whose failure branch does not ``exit`` -
   ``command -v git >/dev/null 2>&1 || return 0`` in ``cpp-commands-link.sh``,
   ``|| return 1`` in ``gh-pr-merge.sh`` - is the script author stating in code
   that absence is survivable. That declaration is believed, and the binary is
   dropped for that script. A preflight that DOES ``exit`` (``branch-protection.sh``,
   ``flow-wave-lexicon.sh``, and ``flow-driver-capability.sh``'s own #783 fix) is
   the opposite declaration and keeps the binary.
2. **At least one use is not fail-soft.** A use at command position whose command
   carries a ``||`` fallback, or which sits in an ``if``/``elif``/``while``/
   ``until`` condition or behind ``!``, cannot turn the script red on its own -
   ``git rev-parse --git-common-dir 2>/dev/null || printf ''`` is fine without
   git. A bare ``BRANCH=$(jq -r '.branch' "$CONFIG")`` is not.

Both exclusions err toward silence, which is the same direction every other
judgement in this file errs. This is deliberately NOT a shell dataflow analyser:
it reads text, and a script that reaches a binary in a way these two rules cannot
see is a false negative the gate accepts.

Comment stripping means ``# needs jq`` is never a match; command position means a
``"jq"`` inside a string list and ``gh --jq`` are not either, while ``| jq -r .x``
and ``$(git rev-parse)`` are.

A fully dynamic argv (``subprocess.run(cmd)`` where ``cmd`` is built at runtime)
is deliberately NOT resolved, and neither is the script hop's argument when it is
a local variable, a ``bash -c`` command string, or a path that names no real
file. This gate targets the literal shapes that have actually failed, not every
conceivable one; it is a floor, not proof of total coverage. Widening the hop -
inferring a script's transitive tool needs, or resolving runtime argv - is
deliberately out of scope, because a guess that cries wolf costs more than the
false negative it removes.

What counts as a guard
----------------------
Any of these, on the test itself, its class, or the module (``pytestmark``):

- ``@pytest.mark.skipif(shutil.which("git") is None, ...)``
- ``@requires_git`` where ``requires_git = pytest.mark.skipif(shutil.which(...))``
  is assigned at module level (CPP's prevailing idiom),
- an in-body ``if shutil.which("bash") is None: pytest.skip(...)``.

Escape hatch: ``# binary-guard: allow <reason>`` on the call line or the ``def``
line suppresses a finding, for the rare intentional case - including the script
hop, where a script's ``jq`` path is genuinely unreachable from the test.

Stdlib-only and binary-free by construction: it parses source text and reads
shell scripts, but never executes anything, so it runs in the slim CI image -
and, unlike the failure it guards, it reproduces identically on a dev box.

Usage:
    python3 scripts/check-test-binary-guards.py           # scan tests/, exit 1 on findings
    python3 scripts/check-test-binary-guards.py --root DIR
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: Binaries absent from the CI ``validate`` image. ``bash`` is deliberately NOT
#: here - the image ships it, and including it would flag most of the suite.
#: ``jq`` joined the set after issue #716/#717's own CI run reproduced the
#: exact failure mode this gate exists for: `uv:python3.11-bookworm-slim`
#: ships none of `git`/`docker`/`gitleaks`/`curl`/`jq`, and this dev box has
#: `jq` installed, so an unguarded `jq` test is invisible locally and red only
#: in CI - structurally the same trap #602 already covers for the other three.
#: Since issue #789 the gate no longer stops at a LITERAL `["jq", ...]` argv: it
#: follows one static hop through `subprocess.run(["bash", SCRIPT])` and scans
#: SCRIPT for these binaries, which is the transitive case #716/#717 documented
#: as a known blind spot and #783 then walked straight into. What still needs a
#: hand-added skipif is what the hop cannot statically resolve - a runtime-built
#: argv, a `bash -c` command string, a script path held in a local variable, or
#: a binary reached through a SECOND script the first one sources.
GUARDED_BINARIES = frozenset({"git", "docker", "gitleaks", "jq"})

SUBPROCESS_FUNCS = frozenset({"run", "Popen", "call", "check_call", "check_output"})
OS_SHELL_FUNCS = frozenset({"system", "popen"})

#: argv[0] values that mean "the next non-flag argument is a script to run".
SHELL_RUNNERS = frozenset({"bash", "sh"})

#: Shell flags whose argument is a command string, not a script path - the hop
#: cannot resolve those, so it stops rather than guessing.
SHELL_STDIN_FLAGS = frozenset({"-c", "-s"})

ALLOW_RE = re.compile(r"#\s*binary-guard:\s*allow\b")

#: A ``#`` comment: at line start, or preceded by whitespace. ``$#`` and ``s/#//``
#: keep their ``#`` because neither is preceded by whitespace.
SHELL_COMMENT_RE = re.compile(r"(?:^|(?<=\s))#.*$", re.MULTILINE)

#: A guarded binary at COMMAND POSITION inside a shell script: line start, or
#: after a separator that begins a new command. This is what keeps ``gh --jq``,
#: ``"jq"`` inside a string list, ``$GIT_DIR`` and ``.git/config`` from matching.
#: ``anchor`` and ``bang`` are captured because a use in an ``if`` condition or
#: behind ``!`` is fail-soft - its failure is the point, not an error.
SHELL_BINARY_RE = re.compile(
    r"(?:^|[\n;&|(`{]|\$\(|&&|\|\||\b(?P<anchor>then|do|else|elif|if|while|until)\b)"
    r"[ \t]*(?P<bang>!\s*)?(?:sudo\s+)?"
    r"(?P<bin>" + "|".join(sorted(GUARDED_BINARIES, key=len, reverse=True)) + r")\b"
)

#: Anchors that put the following command in a CONDITION rather than a step.
CONDITION_ANCHORS = frozenset({"if", "elif", "while", "until"})

#: ``command -v jq`` / ``type jq`` / ``hash jq`` - a preflight, not a use. Whether
#: its failure branch exits decides if the script declares the binary mandatory.
PREFLIGHT_RE = re.compile(
    r"(?:command\s+-v|type\s+-P|hash|\btype)\s+"
    r"(?P<bin>" + "|".join(sorted(GUARDED_BINARIES, key=len, reverse=True)) + r")\b"
)

#: How far to look for the end of a preflight's failure branch.
PREFLIGHT_WINDOW = 12
BRANCH_END_RE = re.compile(r"\s*(fi|\}|esac)\b")
EXIT_RE = re.compile(r"\bexit\b")

#: A command whose stderr is thrown away is one whose failure the author expects
#: and handles downstream - ``SHA="$(git rev-parse HEAD 2>/dev/null)"`` followed
#: by an emptiness test. You do not silence a command you cannot do without.
STDERR_SILENCED_RE = re.compile(r"2>\s*/dev/null|2>&-|&>\s*/dev/null|>&\s*/dev/null")

#: Scanned shell scripts, keyed by (path, mtime, size) so an edited script is
#: re-read rather than served stale within one process.
_SCRIPT_SCAN_CACHE: dict[tuple[str, int, int], frozenset[str]] = {}


@dataclass(frozen=True)
class Finding:
    """One unguarded test."""

    path: Path
    lineno: int
    test: str
    binaries: tuple[str, ...]
    indirect_via: str | None
    via_scripts: tuple[Path, ...] = field(default=())

    def render(self, root: Path) -> str:
        tools = ", ".join(self.binaries)
        if self.via_scripts:
            scripts = ", ".join(_relative(p, root) for p in self.via_scripts)
            how = f" (via script {scripts})"
        elif self.indirect_via:
            how = f" (via helper {self.indirect_via}())"
        else:
            how = ""
        return (
            f"{_relative(self.path, root)}:{self.lineno}: {self.test} shells out to {tools}{how} "
            f"with no shutil.which() guard"
        )


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:  # pragma: no cover - defensive
        return str(path)


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


def _const_str(node: ast.expr) -> str | None:
    """A plain string constant - no f-string prefix guessing, for path building."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


# --------------------------------------------------------------------------- #
# The one static hop: bash SCRIPT -> the binaries SCRIPT calls
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _ScriptUse:
    """One command-position use of a guarded binary inside a shell script."""

    binary: str
    indent: int
    failsoft: bool


def _logical_command(lines: list[str], index: int) -> tuple[str, int]:
    """The whole backslash-continued command containing ``lines[index]``, and its indent."""
    start = index
    while start > 0 and lines[start - 1].rstrip().endswith("\\"):
        start -= 1
    end = index
    while end + 1 < len(lines) and lines[end].rstrip().endswith("\\"):
        end += 1
    head = lines[start]
    return "\n".join(lines[start : end + 1]), len(head) - len(head.lstrip())


def _failure_branch(lines: list[str], index: int) -> str:
    """The text a preflight runs when the binary is missing."""
    line = lines[index]
    _, separator, remainder = line.partition("||")
    if separator and "{" not in remainder:
        return remainder  # the whole failure branch is on this line
    collected = [line]
    for follower in lines[index + 1 : index + 1 + PREFLIGHT_WINDOW]:
        if not follower.strip():
            break
        collected.append(follower)
        if BRANCH_END_RE.match(follower):
            break
    return "\n".join(collected)


def _preflight_declarations(lines: list[str]) -> tuple[set[str], set[str]]:
    """What a script's own ``command -v`` preflights declare about each binary.

    Returns ``(degrades, scoped)``:

    - ``degrades`` - a preflight whose failure branch does not ``exit``
      (``command -v git >/dev/null 2>&1 || return 0``). The author is stating in
      code that absence is survivable, and the gate believes it.
    - ``scoped`` - every preflight for that binary exits, but all of them are
      NESTED inside a branch or function, so the requirement belongs to one path
      (``flow-driver-capability.sh``: "``--json`` is the ONLY path that needs
      jq"). Tracing which tests take that path is beyond a text scan, so only
      TOP-LEVEL uses of such a binary count.

    A top-level exiting preflight is neither: it declares the whole script
    unusable without the binary, and every use counts.
    """
    degrades: set[str] = set()
    top_level: set[str] = set()
    nested: set[str] = set()
    for index, line in enumerate(lines):
        for match in PREFLIGHT_RE.finditer(line):
            binary = match.group("bin")
            if not EXIT_RE.search(_failure_branch(lines, index)):
                degrades.add(binary)
            elif line[: match.start()].strip():
                nested.add(binary)  # e.g. `if ! command -v jq ...` indented, or after `&&`
            elif len(line) - len(line.lstrip()) > 0:
                nested.add(binary)
            else:
                top_level.add(binary)
    return degrades, nested - top_level


def _script_uses(source: str, lines: list[str]) -> list[_ScriptUse]:
    """Every command-position use of a guarded binary, classified fail-soft or not."""
    uses: list[_ScriptUse] = []
    for match in SHELL_BINARY_RE.finditer(source):
        index = source.count("\n", 0, match.start("bin"))
        line = lines[index] if index < len(lines) else ""
        if PREFLIGHT_RE.search(line):
            continue  # `command -v jq` is a probe, not a use
        command, indent = _logical_command(lines, index)
        failsoft = bool(
            match.group("bang")
            or match.group("anchor") in CONDITION_ANCHORS
            or "||" in command
            or STDERR_SILENCED_RE.search(command)
        )
        uses.append(_ScriptUse(match.group("bin"), indent, failsoft))
    return uses


def binaries_in_script(path: Path) -> frozenset[str]:
    """The guarded binaries a shell script HARD-REQUIRES.

    A binary the script merely mentions is not a finding. See the module
    docstring: a use is discounted when the script declares it degrades without
    the binary, when the requirement is confined to one branch, or when the use
    itself is fail-soft.
    """
    try:
        stat = path.stat()
    except OSError:  # pragma: no cover - defensive
        return frozenset()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    cached = _SCRIPT_SCAN_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:  # pragma: no cover - defensive
        return frozenset()
    source = SHELL_COMMENT_RE.sub("", text)
    lines = source.splitlines()
    degrades, scoped = _preflight_declarations(lines)
    required = {
        use.binary
        for use in _script_uses(source, lines)
        if not use.failsoft
        and use.binary not in degrades
        and not (use.binary in scoped and use.indent > 0)
    }
    found = frozenset(required)
    _SCRIPT_SCAN_CACHE[key] = found
    return found


class _ScriptResolver:
    """Resolve a test module's ``Path`` constants, so ``bash SCRIPT`` can be followed.

    Only the idioms the suite actually uses are resolved - the module-level
    ``ROOT = Path(__file__).resolve().parents[1]`` anchor, ``/``-joined string
    segments off it, ``.parent``, and ``str(...)`` around any of them. Anything
    else returns ``None`` and the hop declines to guess.
    """

    def __init__(self, module_path: Path, tree: ast.Module) -> None:
        self.module_path = module_path.resolve()
        self.constants = self._constants(tree)

    # -- constant map ------------------------------------------------------ #
    def _constants(self, tree: ast.Module) -> dict[str, Path]:
        constants: dict[str, Path] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                targets = [t for t in node.targets if isinstance(t, ast.Name)]
                value: ast.expr | None = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target]
                value = node.value
            else:
                continue
            if value is None or not targets:
                continue
            resolved = self._expr(value, constants)
            if resolved is None:
                continue
            for target in targets:
                constants[target.id] = resolved
        return constants

    # -- expression resolution --------------------------------------------- #
    def _expr(self, node: ast.expr, constants: dict[str, Path] | None = None) -> Path | None:
        known = self.constants if constants is None else constants

        if isinstance(node, ast.Name):
            return known.get(node.id)

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            candidate = Path(node.value)
            return candidate if candidate.is_absolute() else self.module_path.parent / candidate

        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left = self._expr(node.left, known)
            right = _const_str(node.right)
            return None if left is None or right is None else left / right

        if isinstance(node, ast.Attribute):
            if node.attr == "parent":
                base = self._expr(node.value, known)
                return None if base is None else base.parent
            return None

        if isinstance(node, ast.Subscript):
            container = node.value
            if not (isinstance(container, ast.Attribute) and container.attr == "parents"):
                return None
            base = self._expr(container.value, known)
            index = node.slice
            if base is None or not isinstance(index, ast.Constant) or not isinstance(index.value, int):
                return None
            try:
                return base.parents[index.value]
            except IndexError:
                return None

        if isinstance(node, ast.Call):
            return self._call(node, known)

        return None

    def _call(self, node: ast.Call, known: dict[str, Path]) -> Path | None:
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr in {"resolve", "absolute", "expanduser"}:
                return self._expr(func.value, known)
            if func.attr == "Path" and len(node.args) == 1:
                return self._path_arg(node.args[0], known)
            return None
        if isinstance(func, ast.Name) and func.id in {"Path", "str", "fspath"} and len(node.args) == 1:
            return self._path_arg(node.args[0], known)
        return None

    def _path_arg(self, arg: ast.expr, known: dict[str, Path]) -> Path | None:
        if isinstance(arg, ast.Name) and arg.id == "__file__":
            return self.module_path
        return self._expr(arg, known)

    # -- the hop ------------------------------------------------------------ #
    def script_for_argv(self, rest: list[ast.expr]) -> Path | None:
        """The script a ``bash``/``sh`` argv runs, if it resolves to a real file."""
        for node in rest:
            literal = _const_str(node)
            if literal is not None and literal.startswith("-"):
                if literal in SHELL_STDIN_FLAGS:
                    return None  # a command string follows, not a script path
                if literal == "--":
                    continue
                continue
            path = self._expr(node)
            if path is None:
                return None
            try:
                return path if path.is_file() else None
            except OSError:  # pragma: no cover - defensive
                return None
        return None


def _merge_scripts(into: dict[Path, set[str]], other: dict[Path, set[str]]) -> bool:
    """Union ``other`` into ``into``; True when anything new was added."""
    added = False
    for path, binaries in other.items():
        current = into.setdefault(path, set())
        if not binaries <= current:
            current |= binaries
            added = True
    return added


class _ShellOutFinder(ast.NodeVisitor):
    """Collect the guarded binaries a subtree statically invokes."""

    def __init__(
        self,
        subprocess_aliases: set[str],
        os_aliases: set[str],
        resolver: _ScriptResolver | None = None,
    ) -> None:
        self.subprocess_aliases = subprocess_aliases
        self.os_aliases = os_aliases
        self.resolver = resolver
        self.binaries: set[str] = set()
        self.linenos: set[int] = set()
        self.scripts: dict[Path, set[str]] = {}

    def visit_Call(self, node: ast.Call) -> None:
        binaries, script = self._binaries_for(node)
        if binaries:
            self.binaries |= binaries
            self.linenos.add(node.lineno)
            if script is not None:
                self.scripts.setdefault(script, set()).update(binaries)
        self.generic_visit(node)

    def _binaries_for(self, node: ast.Call) -> tuple[set[str], Path | None]:
        if not node.args:
            return set(), None
        kind = self._callee_kind(node.func)
        if kind is None:
            return set(), None
        first = node.args[0]

        if kind == "os":
            literal = _literal_str(first)
            name = _first_token_binary(literal) if literal is not None else None
            return ({name} if name else set()), None

        # subprocess: an argv sequence, or a command string.
        if isinstance(first, (ast.List, ast.Tuple)):
            if not first.elts:
                return set(), None
            head = _literal_str(first.elts[0])
            if head is None:
                return set(), None
            name = head.rsplit("/", 1)[-1]
            if name in GUARDED_BINARIES:
                return {name}, None
            if name in SHELL_RUNNERS and self.resolver is not None:
                script = self.resolver.script_for_argv(list(first.elts[1:]))
                if script is None:
                    return set(), None
                binaries = set(binaries_in_script(script))
                return (binaries, script) if binaries else (set(), None)
            return set(), None

        literal = _literal_str(first)
        name = _first_token_binary(literal) if literal is not None else None
        return ({name} if name else set()), None

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

    def __init__(self, tree: ast.Module, source: str, path: Path) -> None:
        self.tree = tree
        self.path = path
        self.allow_lines = {
            i for i, line in enumerate(source.splitlines(), start=1) if ALLOW_RE.search(line)
        }
        self.resolver = _ScriptResolver(path, tree)
        self.subprocess_aliases, self.os_aliases = self._imports()
        self.skip_aliases = self._skip_aliases()
        self.module_guard = self._module_guard()
        self.helper_binaries, self.helper_scripts = self._helper_reach()

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
        finder = _ShellOutFinder(self.subprocess_aliases, self.os_aliases, self.resolver)
        finder.visit(node)
        return finder

    def _helper_reach(self) -> tuple[dict[str, set[str]], dict[str, dict[Path, set[str]]]]:
        """Module-level helpers that reach a guarded binary, transitively.

        The indirect shape the issue calls out: a ``test_`` that never names
        ``git`` itself but calls ``_git()``, which does. Script attribution
        (issue #789) rides the same fixpoint, so a ``_run()`` wrapper around
        ``["bash", str(SCRIPT)]`` still names SCRIPT in the finding.
        """
        helpers: dict[str, FunctionDef] = {
            node.name: node
            for node in self.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("test_")
        }
        direct: dict[str, set[str]] = {}
        scripts: dict[str, dict[Path, set[str]]] = {}
        for name, node in helpers.items():
            finder = self._shell_out(node)
            direct[name] = set(finder.binaries)
            scripts[name] = {p: set(b) for p, b in finder.scripts.items()}
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
                    if _merge_scripts(scripts[name], scripts[callee]):
                        changed = True
        return (
            {name: bins for name, bins in direct.items() if bins},
            {name: seen for name, seen in scripts.items() if seen},
        )


def _check_module(path: Path, source: str) -> list[Finding]:
    tree = ast.parse(source, filename=str(path))
    analysis = _ModuleAnalysis(tree, source, path)
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
    seen_scripts: dict[Path, set[str]] = {}
    _merge_scripts(seen_scripts, direct.scripts)
    indirect_via: str | None = None
    for name in sorted(_called_names(func)):
        helper = analysis.helper_binaries.get(name)
        if helper:
            if indirect_via is None:
                indirect_via = name
            needed |= helper
            _merge_scripts(seen_scripts, analysis.helper_scripts.get(name, {}))
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
        via_scripts=tuple(sorted(p for p, bins in seen_scripts.items() if bins & missing)),
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
        "A `via script` finding means the test runs a repo script that calls the binary\n"
        "(issue #789) - guard the test for that binary, or, if the script never reaches\n"
        "its codepath here, append `# binary-guard: allow <reason>` to the def line.\n"
        "Intentional exception: append `# binary-guard: allow <reason>` to the def line."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
