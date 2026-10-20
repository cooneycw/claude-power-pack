#!/usr/bin/env python3
"""Regenerate one constructed anchor from its origin and stored unified patch.

Usage: python3 scripts/regenerate-blind-anchor.py CONTROL [--write]
The existing anchor's module docstring is preserved verbatim.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import re
import tempfile
from pathlib import Path


def split_docstring(source: str) -> tuple[str, str]:
    """Keep the literal module docstring, including its surrounding prefix."""
    node = ast.parse(source).body[0]
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Constant):
        raise ValueError("expected a module docstring")
    if not isinstance(node.value.value, str):
        raise ValueError("expected a string module docstring")
    lines = source.splitlines(keepends=True)
    return "".join(lines[:node.end_lineno]), "".join(lines[node.end_lineno:])


def apply_patch(code: str, patch: str) -> str:
    """Apply exact unified-diff hunks; refuse changed or ambiguous context."""
    lines = patch.splitlines(keepends=True)
    source = code.splitlines(keepends=True)
    cursor = 0
    output: list[str] = []
    index = 2  # diff -u file headers
    while index < len(lines):
        if not re.match(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", lines[index]):
            raise ValueError("invalid unified patch hunk")
        index += 1
        old: list[str] = []
        new: list[str] = []
        while index < len(lines) and not lines[index].startswith("@@"):
            line = lines[index]
            if line.startswith((" ", "-")):
                old.append(line[1:])
            if line.startswith((" ", "+")):
                new.append(line[1:])
            index += 1
        matches = [pos for pos in range(cursor, len(source) - len(old) + 1)
                   if source[pos:pos + len(old)] == old]
        if len(matches) != 1:
            raise ValueError("patch context changed or is ambiguous")
        pos = matches[0]
        output.extend(source[cursor:pos])
        output.extend(new)
        cursor = pos + len(old)
    return "".join(output + source[cursor:])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("control")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    control = root / "controls" / args.control
    spec_path = control / "control.json"
    spec_text = spec_path.read_text(encoding="utf-8")
    spec = json.loads(spec_text)
    anchors = [anchor for anchor in spec["anchors"] if anchor.get("kind") == "constructed"]
    if len(anchors) != 1:
        parser.error("expected exactly one constructed anchor")
    anchor = control / anchors[0]["path"]
    current = anchor.read_text(encoding="utf-8")
    docstring, _ = split_docstring(current)
    _, code = split_docstring((root / anchors[0]["origin"]).read_text(encoding="utf-8"))
    try:
        regenerated = docstring + apply_patch(
            code, anchor.with_suffix(".patch").read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"drift: {anchor.relative_to(root)} ({exc})")
        print("".join(difflib.unified_diff(
            current.splitlines(keepends=True), (docstring + code).splitlines(keepends=True),
            fromfile=str(anchor), tofile="origin code (patch refused)")), end="")
        return 1
    if args.write:
        anchor.write_text(regenerated, encoding="utf-8")
        anchors[0]["sha256"] = hashlib.sha256(anchor.read_bytes()).hexdigest()
        spec_path.write_text(
            json.dumps(spec, indent=2) + ("\n" if spec_text.endswith("\n") else ""),
            encoding="utf-8",
        )
        print(f"wrote: {anchor.relative_to(root)}")
        return 0
    with tempfile.TemporaryDirectory(prefix="cpp-anchor-regen-") as scratch:
        candidate = Path(scratch) / anchor.name
        candidate.write_text(regenerated, encoding="utf-8")
        delta = "".join(difflib.unified_diff(
            current.splitlines(keepends=True), candidate.read_text(encoding="utf-8").splitlines(keepends=True),
            fromfile=str(anchor), tofile="regenerated"))
    print(f"{'drift' if delta else 'matches'}: {anchor.relative_to(root)}")
    print(delta, end="")
    return int(bool(delta))


if __name__ == "__main__":
    raise SystemExit(main())
