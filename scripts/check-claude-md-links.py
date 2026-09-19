#!/usr/bin/env python3
"""Check that repository-local pointers in CLAUDE.md resolve.

Markdown links are unambiguous pointers, so every relative link is checked.
Backtick spans are checked only when they start with one of the named
``PATH_PREFIXES`` below. CLAUDE.md also quotes inline commands and flags such as
``git push``, ``--dry-run``, and ``make lint``; scanning every span would create
false positives. A check people learn to ignore is worse than no check, so the
prefix list is deliberately explicit and reviewable.

A second gate lives here too (issue #1037): CLAUDE.md's Project Map claims to
be the list of canonical `docs/agents/*.md` documents, and that claim drifted
silently - `docs/agents/delivery-pilots.md` existed on disk, unreferenced, and
nothing noticed because the link-resolution check above only ever looks at
targets CLAUDE.md already names; a document it fails to mention is invisible
to it by construction. `find_undocumented_canonical_docs` inverts the
direction: it enumerates the directory and asks what CLAUDE.md is silent
about. A MEMBERSHIP FLOOR (`MIN_CANONICAL_AGENT_DOCS`) applies to the disk
glob itself, mirroring `check-version-consistency.py`'s floor on its own
derived set - an accidentally-empty or shrunk `docs/agents/` would otherwise
make "every on-disk doc is referenced" trivially true over zero files, which
must read as UNKNOWN, not clean.

Usage:
    python3 scripts/check-claude-md-links.py
    python3 scripts/check-claude-md-links.py --root DIR
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator
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

#: The directory CLAUDE.md's Project Map claims to enumerate in full.
CANONICAL_AGENTS_DIR = "docs/agents"

#: Below this many files on disk, the check cannot tell "every canonical doc
#: is referenced" from "the directory is empty or missing" - fail closed to
#: unknown, not clean (issue #1037 review, same floor shape as
#: check-version-consistency.py's MIN_LOCATIONS).
MIN_CANONICAL_AGENT_DOCS = 8

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


def _iter_examined_targets(source: str) -> Iterator[tuple[str, str]]:
    """Every repository-local pointer this gate considers, as (target, kind).

    The population find_broken_links checks for existence - shared so a
    "nothing to check" count can never drift from what the gate actually
    examines (issue #841, the #840/#842 lesson applied from the start: one
    enumeration, two callers, not two copies of one).
    """
    for match in MARKDOWN_LINK_RE.finditer(source):
        target = _normalize_target(match.group(1))
        if target is not None:
            yield target, "markdown link"
    for match in BACKTICK_RE.finditer(source):
        target = match.group(1).strip()
        if target.startswith(PATH_PREFIXES):
            yield target, "backtick path"


def find_broken_links(root: Path, source: str) -> list[Finding]:
    findings: set[Finding] = set()
    for target, kind in _iter_examined_targets(source):
        if not (root / target).exists():
            findings.add(Finding(target, kind))
    return sorted(findings, key=lambda finding: (finding.target, finding.kind))


def find_undocumented_canonical_docs(root: Path, source: str) -> tuple[list[str], int]:
    """On-disk `docs/agents/*.md` files CLAUDE.md's Project Map never names.

    Returns ``(missing, disk_count)``. ``disk_count`` is exposed so the caller
    can apply the membership floor: a shrunk or missing directory must not
    read as "every canonical doc is referenced" over zero files.
    """
    agents_dir = root / CANONICAL_AGENTS_DIR
    if not agents_dir.is_dir():
        return [], 0
    on_disk = sorted(f"{CANONICAL_AGENTS_DIR}/{path.name}" for path in agents_dir.glob("*.md"))
    referenced = {
        target for target, _kind in _iter_examined_targets(source)
        if target.startswith(f"{CANONICAL_AGENTS_DIR}/")
    }
    missing = [doc for doc in on_disk if doc not in referenced]
    return missing, len(on_disk)


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
    source = path.read_text(encoding="utf-8")
    examined = sum(1 for _ in _iter_examined_targets(source))
    if not examined:
        # Issue #841: a present CLAUDE.md with zero link-shaped tokens must not
        # read the same as a clean scan. This script has exactly one caller
        # (Makefile:74, no --root), so it only ever runs against CPP's own
        # checkout - a CPP CLAUDE.md with no repository-local pointers is not a
        # legitimate state, the file IS the project map, so this cannot fire on
        # a real input.
        print(
            f"claude-md-links: {path} contains no repository-local pointers - nothing was checked",
            file=sys.stderr,
        )
        return 1
    findings = find_broken_links(root, source)
    if findings:
        print(f"claude-md-links: {len(findings)} broken pointer(s)", file=sys.stderr)
        for finding in findings:
            print(f"  {finding.kind}: {finding.target}", file=sys.stderr)
        return 1

    missing_canonical, canonical_disk_count = find_undocumented_canonical_docs(root, source)
    if canonical_disk_count < MIN_CANONICAL_AGENT_DOCS:
        print(
            f"claude-md-links: only {canonical_disk_count} {CANONICAL_AGENTS_DIR}/*.md "
            f"file(s) found (need >= {MIN_CANONICAL_AGENT_DOCS}) - UNKNOWN, not clean. "
            "Either the directory is missing or was emptied, which means an "
            "undocumented canonical doc could sit unwatched.",
            file=sys.stderr,
        )
        return 2
    if missing_canonical:
        print(
            f"claude-md-links: {len(missing_canonical)} canonical doc(s) on disk are not "
            "referenced by CLAUDE.md's Project Map:",
            file=sys.stderr,
        )
        for doc in missing_canonical:
            print(f"  {doc}", file=sys.stderr)
        return 1

    print("claude-md-links: ok - every repository-local pointer resolves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
