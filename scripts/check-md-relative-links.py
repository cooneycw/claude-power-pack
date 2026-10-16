#!/usr/bin/env python3
"""Check that relative markdown links in this repository's tracked .md files resolve.

Issue #1413. Citations rotted in documents nothing checked: CLAUDE.md's own
pointers are gated by `check-claude-md-links.py`, and every other document was
not. This gate covers the citation shape that is unambiguous - an inline
markdown link `[text](relative/path)` - across every tracked `.md` file.

WHY LINKS AND NOT BACKTICK PATHS. The first attempt (#1413's parked branch)
scanned backtick spans that look like repository paths. Over its narrowest
population it still reported 35 findings, and reading them showed only a
handful were rot: the rest were consumer-project files named in prose
(`.claude/deploy.yaml`), another repository's paths quoted while narrating it,
placeholders, and deliberately non-existent names quoted as counterexamples. A
backtick span does not say "this file exists here"; a relative link does. A
check people learn to route around is worse than none, so the link is the
population this gate enforces.

WHAT IT SKIPS, AND WHY:
- URLs (any `scheme:`), bare `#anchors`, and absolute `/paths` - not relative
  files in this tree. A link's own `#fragment` is stripped; only the file is
  checked, never the heading.
- Links inside fenced code blocks and inline code spans - examples, not links.
- Image links `![...](...)`, and reference-style definitions `[id]: path` -
  out of scope; the limit is stated, not hidden.
- `EXCLUDED_PREFIXES` below: generated or copied text whose links resolve from
  somewhere else, run records describing a bygone tree, and control cases that
  are dead on purpose.

The tracked population comes from `git ls-files` (cached plus untracked files
not ignored, so a new document is checked before it is committed). Fewer files
than `--min-files`, or zero links examined, is UNKNOWN (exit 2) - a scan over
nothing is not a clean scan.

Exit codes: 0 every examined link resolves, 1 a dead link, 2 UNKNOWN.

Usage:
    python3 scripts/check-md-relative-links.py
    python3 scripts/check-md-relative-links.py --root DIR --min-files N
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

#: NEGATIVE-CONTROL: controls/check-md-relative-links

#: Below this many tracked .md files the real repository cannot be what was
#: scanned (it holds several hundred) - UNKNOWN, not clean. Control cases pass a
#: smaller floor explicitly.
MIN_TRACKED_MD_FILES = 100

#: Each prefix is text whose links do not resolve from where it sits, by design:
#: - `codex/skills/`: generated mirrors (`make codex-skills`); their sources are
#:   checked where they live.
#: - `templates/`, `.specify/templates/`: rendered into another tree, where
#:   their relative links resolve.
#: - `docs/flow-runs/`, `docs/measurements/`: records of a bygone tree.
#: - `controls/`: negative-control cases, some dead on purpose.
#: - `tests/`: fixtures, likewise.
EXCLUDED_PREFIXES = (
    "codex/skills/",
    "templates/",
    ".specify/templates/",
    "docs/flow-runs/",
    "docs/measurements/",
    "controls/",
    "tests/",
)

LINK_RE = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)")
FENCE_RE = re.compile(r"^\s*(?:>\s*)*(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


@dataclass(frozen=True)
class DeadLink:
    path: str
    line: int
    target: str


class GitUnavailable(Exception):
    """git itself is not installed - a fact about this host, not the tree."""


def tracked_md_files(root: Path) -> list[str] | None:
    """Tracked .md paths relative to `root`, or None when git cannot list them.

    Raises GitUnavailable when there is no git binary at all.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.md"],
            cwd=root, capture_output=True, text=True,
        )
    except FileNotFoundError as exc:
        raise GitUnavailable from exc
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return sorted({
        line for line in proc.stdout.splitlines()
        if line and not line.startswith(EXCLUDED_PREFIXES)
    })


def _link_target(raw: str) -> str | None:
    """The relative file a link names, or None when it names no local file."""
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1:target.index(">")]
    else:
        target = target.split(maxsplit=1)[0] if target else ""
    target = unquote(target).split("#", 1)[0].split("?", 1)[0]
    if not target or target.startswith("/") or SCHEME_RE.match(target):
        return None
    return target


def links_in(text: str) -> list[tuple[int, str]]:
    """`(line number, target)` for every relative link outside code."""
    found: list[tuple[int, str]] = []
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        m = FENCE_RE.match(line)
        if m:
            marker = m.group(1)
            if fence is None:
                fence = marker[0] * len(marker)
            elif marker.startswith(fence):
                fence = None
            continue
        if fence is not None:
            continue
        for link in LINK_RE.finditer(INLINE_CODE_RE.sub("", line)):
            target = _link_target(link.group(1))
            if target is not None:
                found.append((number, target))
    return found


def find_dead_links(root: Path, files: list[str]) -> tuple[list[DeadLink], int]:
    dead: list[DeadLink] = []
    examined = 0
    for rel in files:
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for number, target in links_in(text):
            examined += 1
            if not (path.parent / target).exists():
                dead.append(DeadLink(rel, number, target))
    return dead, examined


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="repository root (default: the checkout this script lives in)")
    parser.add_argument("--min-files", type=int, default=MIN_TRACKED_MD_FILES,
                        help=f"membership floor (default {MIN_TRACKED_MD_FILES})")
    args = parser.parse_args(argv)
    root = args.root.resolve()

    try:
        files = tracked_md_files(root)
    except GitUnavailable:
        print("md-relative-links: UNAVAILABLE - git is not installed", file=sys.stderr)
        return 2
    if files is None:
        print(f"md-relative-links: UNKNOWN - `git ls-files` could not list {root}; "
              "nothing was examined, which is not a pass.", file=sys.stderr)
        return 2
    if len(files) < args.min_files:
        print(f"md-relative-links: UNKNOWN - only {len(files)} tracked .md file(s) "
              f"(need >= {args.min_files}); this is not the population the gate is "
              "for, so a clean result would mean nothing.", file=sys.stderr)
        return 2
    dead, examined = find_dead_links(root, files)
    if not examined:
        print(f"md-relative-links: UNKNOWN - {len(files)} tracked .md file(s) carry no "
              "relative link at all; nothing was checked.", file=sys.stderr)
        return 2
    if dead:
        print(f"md-relative-links: {len(dead)} dead relative link(s) of {examined} "
              f"across {len(files)} tracked .md file(s):", file=sys.stderr)
        for d in dead:
            print(f"  {d.path}:{d.line}: ({d.target}) does not exist", file=sys.stderr)
        return 1
    print(f"md-relative-links: ok - {examined} relative link(s) across {len(files)} "
          "tracked .md file(s) resolve (file existence only; URLs, anchors, images "
          "and reference-style links are not examined)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
