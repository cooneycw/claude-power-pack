#!/usr/bin/env python3
"""Reject captured-stream relays inside control TemporaryDirectory blocks."""
#: NEGATIVE-CONTROL: controls/control-cleanup-relay

import argparse
import ast
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_TREES = {"anchors", "cases", "history"}


def relay_lines(source: str) -> list[int]:
    tree = ast.parse(source)
    names = {"TemporaryDirectory"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "tempfile":
            names.update(a.asname or a.name for a in node.names if a.name == "TemporaryDirectory")

    def temporary(expression):
        if not isinstance(expression, ast.Call):
            return False
        function = expression.func
        return ((isinstance(function, ast.Attribute) and function.attr == "TemporaryDirectory")
                or (isinstance(function, ast.Name) and function.id in names))

    # Conservative lexical aliases: assignments may carry captured output into
    # a later sink. No execution-order or arbitrary dynamic-call inference.
    tainted = set()

    def captured(expression):
        return any((isinstance(child, ast.Attribute) and child.attr in {"stdout", "stderr"})
                   or (isinstance(child, ast.Name) and child.id in tainted)
                   for child in ast.walk(expression))

    assignments = [node for node in ast.walk(tree) if isinstance(node, (ast.Assign, ast.AnnAssign))]
    while True:
        before = set(tainted)
        for assignment in assignments:
            if (not isinstance(assignment.value, (ast.Attribute, ast.BinOp, ast.JoinedStr, ast.Name))
                    or not captured(assignment.value)):
                continue
            targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
            tainted.update(target.id for target in targets if isinstance(target, ast.Name))
        if before == tainted:
            break

    sys_names = {"sys"}
    streams = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            sys_names.update(alias.asname or alias.name for alias in node.names if alias.name == "sys")
        elif isinstance(node, ast.ImportFrom) and node.module == "sys":
            streams.update(alias.asname or alias.name for alias in node.names
                           if alias.name in {"stdout", "stderr"})

    def sink(function):
        if isinstance(function, ast.Name):
            return function.id == "print"
        if not isinstance(function, ast.Attribute) or function.attr != "write":
            return False
        stream = function.value
        return ((isinstance(stream, ast.Name) and stream.id in streams)
                or (isinstance(stream, ast.Attribute) and stream.attr in {"stdout", "stderr"}
                    and isinstance(stream.value, ast.Name) and stream.value.id in sys_names))

    lines = set()
    for block in ast.walk(tree):
        if (not isinstance(block, (ast.With, ast.AsyncWith))
                or not any(temporary(item.context_expr) for item in block.items)):
            continue
        for node in ast.walk(block):
            if (isinstance(node, ast.Call) and sink(node.func)
                    and any(captured(argument) for argument in node.args)):
                lines.add(node.lineno)
    return sorted(lines)


def check(root: Path) -> int:
    controls = root / "controls"
    if not controls.is_dir() or controls.is_symlink():
        print("CONTROL_RELAY: unknown - controls is absent or not a physical directory")
        return 2
    files, excluded, errors, findings = [], [], [], []

    def walk_error(error):
        errors.append(f"cannot enumerate controls: {type(error).__name__}")

    for parent, directories, names in os.walk(controls, followlinks=False, onerror=walk_error):
        directory = Path(parent)
        relative = directory.relative_to(controls)
        for name in list(directories):
            child = directory / name
            if len(relative.parts) == 1 and name in FIXTURE_TREES:
                excluded.append(child.relative_to(root).as_posix())
                directories.remove(name)
            elif child.is_symlink():
                errors.append(f"{child.relative_to(root)}: implementation directory is a symlink")
                directories.remove(name)
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            path = directory / name
            label = path.relative_to(root).as_posix()
            files.append(label)
            if path.is_symlink():
                errors.append(f"{label}: implementation file is a symlink")
                continue
            try:
                lines = relay_lines(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, SyntaxError) as exc:
                errors.append(f"{label}: cannot read/parse ({type(exc).__name__})")
                continue
            findings.extend(f"{label}:{line}" for line in lines)
    print(f"CONTROL_RELAY_FILES: {len(files)}")
    print(f"CONTROL_RELAY_FIXTURE_TREES: {len(excluded)} (cases, anchors and history not examined)")
    if not files:
        errors.append("empty Python control implementation population")
    for finding in sorted(findings):
        print(f"CONTROL_RELAY_SITE: {finding}")
    if errors:
        for error in sorted(errors):
            print(f"CONTROL_RELAY_UNEXAMINED: {error}")
        print("CONTROL_RELAY: unknown - implementation population was not fully examined")
        return 2
    if findings:
        print("CONTROL_RELAY: bad - captured-stream relay inside TemporaryDirectory")
        return 1
    print(f"CONTROL_RELAY: ok - {len(files)} Python control implementations examined")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    return check(parser.parse_args().root)


if __name__ == "__main__":
    raise SystemExit(main())
