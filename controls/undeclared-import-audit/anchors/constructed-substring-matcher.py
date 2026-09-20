#!/usr/bin/env python3
"""THE PLAUSIBLE FIRST CUT of an undeclared-import gate, and it is blind (issue #1041).

CONSTRUCTED, not historical, and permanently so - ADR 0008 pre-rules this for a
gate introduced by its own pull request: there is no blind ancestor of
`scripts/undeclared-import-audit.py` on main, the anchor commit dies with the
squash, and `--verify-provenance` therefore reads `unverified` forever rather
than "git is absent here". Integrity is established by the sha256 recorded in
control.json; historicity is not claimed.

WHAT IT IS, AND WHY IT IS NOT A STRAWMAN. This is the implementation an author
reaches for first: walk the tree, collect imports, drop stdlib and first-party,
and ask whether the name appears in the dependency list. It shares the real
gate's population, its stdlib screen and its first-party screen, so it differs
in exactly two places - which is what makes the demonstration isolated rather
than a comparison of two unrelated programs.

BLINDNESS 1 - THE DECLARATION TEST IS A SUBSTRING MATCH. `"requests" in
pyproject_text` is True when the only thing declared is `types-requests`, the
type STUBS. That is not a contrived input: it is the exact state issue #1041 was
filed against, where the root lock carried `types-requests` and `urllib3` and no
`requests`. This anchor reports that tree CLEAN.

BLINDNESS 2 - THE LEDGER HAS NO STALE DIRECTION. It reads `.undeclared-import-allow`
and accepts what the lines name, and never asks whether a line accounts for
anything. A record therefore outlives the import it records, which is how an
allowlist decays into a permanent blindfold nobody re-reads.

It prints `UNDECLARED-IMPORT:` on the findings it DOES make, so an anchor that
unexpectedly caught a known-bad input scores INERT rather than UNRESOLVED (#946).
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

PRUNE = (
    "mcp-second-opinion", "controls", "codex/skills",
    "docs/research/forced-claim-prototype-2026-09-15/cases",
    ".git", ".venv", "venv", "node_modules", "__pycache__",
)
SYS_PATH_DIR = "src"


def discover(root: Path) -> list[Path]:
    found: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        for entry in sorted(current.iterdir()):
            if entry.is_symlink():
                continue
            rel = entry.relative_to(root).as_posix()
            if entry.is_dir():
                if rel in PRUNE or entry.name in PRUNE:
                    continue
                stack.append(entry)
            elif entry.suffix == ".py":
                found.append(entry)
    return sorted(found)


def provided(root: Path, files: list[Path]) -> set[str]:
    names: set[str] = set()
    for entry in root.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            names.add(entry.name)
        elif entry.suffix == ".py":
            names.add(entry.stem)
    for path in files:
        if SYS_PATH_DIR in path.parts[:-1]:
            names.add(path.stem)
    return names


def hard_imports(tree: ast.Module, rel: str) -> list[tuple[str, int, str]]:
    out: list[tuple[str, int, str]] = []

    def record(node: ast.AST) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((rel, node.lineno, alias.name.split(".")[0]))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.append((rel, node.lineno, node.module.split(".")[0]))

    def top(stmt: ast.stmt) -> None:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            record(stmt)
        elif isinstance(stmt, ast.Try):
            catches = any(
                h.type is None
                or any(isinstance(n, ast.Name) and n.id in {"ImportError", "ModuleNotFoundError", "Exception"}
                       for n in ast.walk(h.type))
                for h in stmt.handlers
            )
            if not catches:
                for inner in stmt.body:
                    top(inner)
        elif isinstance(stmt, ast.If):
            checking = any(
                (isinstance(n, ast.Name) and n.id == "TYPE_CHECKING")
                or (isinstance(n, ast.Attribute) and n.attr == "TYPE_CHECKING")
                for n in ast.walk(stmt.test)
            )
            if not checking:
                for inner in stmt.body + stmt.orelse:
                    top(inner)

    for stmt in tree.body:
        top(stmt)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--allow-file", default=None)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        print("undeclared-import-audit: selftest ok")
        return 0

    root = Path(args.root).resolve()
    allow_file = Path(args.allow_file) if args.allow_file else root / ".undeclared-import-allow"

    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        print(f"UNDECLARED-IMPORT-UNKNOWN: {pyproject} is not present")
        return 2
    # BLINDNESS 1: the declared set is never parsed. The raw text is searched.
    declared_text = pyproject.read_text(encoding="utf-8")

    accepted: set[tuple[str, str]] = set()
    if allow_file.is_file():
        for raw in allow_file.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) >= 3 and parts[0] == "allow":
                accepted.add((parts[1], parts[2]))
    # BLINDNESS 2: nothing ever asks whether an accepted pair was observed.

    files = discover(root)
    if not files:
        print(f"UNDECLARED-IMPORT-UNKNOWN: no Python file under {root}")
        return 2
    first_party = provided(root, files)
    stdlib = set(sys.stdlib_module_names)

    findings = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, SyntaxError, ValueError):
            continue
        for _, lineno, name in hard_imports(tree, rel):
            if name in stdlib or name in first_party:
                continue
            if (rel, name) in accepted:
                continue
            if name in declared_text:
                continue
            findings += 1
            print(f"UNDECLARED-IMPORT: {rel}:{lineno} imports `{name}`, which no pyproject.toml dependency declares")

    if findings:
        return 1
    print(f"undeclared-import-audit: ok - {len(files)} file(s) examined, 0 undeclared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
