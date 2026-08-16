#!/usr/bin/env python3
"""Check that repository-local pointers in CLAUDE.md resolve.

Markdown links are unambiguous pointers, so every relative link is checked.
Backtick spans are checked only when they start with one of the named
``PATH_PREFIXES`` below. CLAUDE.md also quotes inline commands and flags such as
``git push``, ``--dry-run``, and ``make lint``; scanning every span would create
false positives. A check people learn to ignore is worse than no check, so the
prefix list is deliberately explicit and reviewable.

Usage:
    python3 scripts/check-claude-md-links.py
    python3 scripts/check-claude-md-links.py --root DIR
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

PATH_PREFIXES = (
    "docs/",
    "scripts/",
    "lib/",
    ".claude/",
    ".specify/",
    "codex/",
    "templates/",
    "tests/",
    "vendor/",
    "extras/",
)

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
BACKTICK_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")


@dataclass(frozen=True)
class Finding:
    target: str
    kind: str


def _normalize_target(raw: str) -> str | None:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    target = unquote(target).split("#", 1)[0]
    if not target or target.startswith(("#", "/", "http://", "https://", "mailto:")):
        return None
    return target


def find_broken_links(root: Path, source: str) -> list[Finding]:
    findings: set[Finding] = set()
    for match in MARKDOWN_LINK_RE.finditer(source):
        target = _normalize_target(match.group(1))
        if target is not None and not (root / target).exists():
            findings.add(Finding(target, "markdown link"))
    for match in BACKTICK_RE.finditer(source):
        target = match.group(1).strip()
        if target.startswith(PATH_PREFIXES) and not (root / target).exists():
            findings.add(Finding(target, "backtick path"))
    return sorted(findings, key=lambda finding: (finding.target, finding.kind))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repo root (default: the checkout this script lives in)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    path = root / "CLAUDE.md"
    if not path.is_file():
        print(f"claude-md-links: missing {path}", file=sys.stderr)
        return 1
    findings = find_broken_links(root, path.read_text(encoding="utf-8"))
    if not findings:
        print("claude-md-links: ok - every repository-local pointer resolves")
        return 0
    print(f"claude-md-links: {len(findings)} broken pointer(s)", file=sys.stderr)
    for finding in findings:
        print(f"  {finding.kind}: {finding.target}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
