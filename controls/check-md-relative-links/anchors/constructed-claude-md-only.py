#!/usr/bin/env python3
"""BLIND ANCHOR for controls/check-md-relative-links - do not fix, do not lint, do not import.

CONSTRUCTED: the coverage this repository had before #1413. Relative links were
checked only in CLAUDE.md (`check-claude-md-links.py`), so a link rotting in any
other document was invisible by construction. This anchor checks CLAUDE.md's
relative links and nothing else.

WHAT IT CATCHES: a dead link in CLAUDE.md.
WHAT IT MISSES: a dead link in any other document - both BAD cases. It reports
GOOD on them (blind, as required) and GOOD on `cases/good-live-links` (agrees).

Stdlib-only and network-free, like the gate.
"""

import argparse
import re
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="CLAUDE.md-only link check (blind anchor)")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--min-files", type=int, default=1)
    args = parser.parse_args(argv)
    # It still counts what it COULD examine, so a tree with no relative link
    # reads UNKNOWN exactly as the gate does: the blindness under test is the
    # scope of the existence check, nothing else.
    links = 0
    for md in args.root.rglob("*.md"):
        text = re.sub(r"`[^`\n]*`", "", md.read_text(encoding="utf-8"))
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        links += sum(1 for t in re.findall(r"\]\(([^)#\s]+)", text) if ":" not in t)
    if not links:
        print("md-relative-links: UNKNOWN - no relative link; nothing was checked.", file=sys.stderr)
        return 2
    doc = args.root / "CLAUDE.md"
    dead = []
    if doc.is_file():
        for target in re.findall(r"\]\(([^)#\s]+)", doc.read_text(encoding="utf-8")):
            if ":" not in target and not (args.root / target).exists():
                dead.append(target)
    if dead:
        print(f"md-relative-links: {len(dead)} dead relative link(s) in CLAUDE.md", file=sys.stderr)
        return 1
    print("md-relative-links: ok - CLAUDE.md links resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
