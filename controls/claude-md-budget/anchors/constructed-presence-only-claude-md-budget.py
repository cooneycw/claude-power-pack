#!/usr/bin/env python3
"""BLIND ANCHOR for controls/claude-md-budget - do not fix, do not lint, do not import.

CONSTRUCTED, not historical, and NOT the pre-#1071 script. The gate's own
registration suggested using the unparameterised version as the anchor, on the
grounds that it "cannot be pointed at a fixture at all". It can: it has carried
`--root` since before #1071, and pointed at `cases/bad-over-budget` it exits 1 -
it DETECTS the known-bad input. An anchor that detects the known-bad case is not
an anchor, so that one disqualifies itself for the opposite of the stated reason.

This is the plausible WEAKER CHECK instead: confirm the document is present and
not empty, and call that within budget. It is the check a reader writes when
"the always-loaded file is there" sounds like the same sentence as "the
always-loaded file is small enough to load".

WHAT IT CATCHES: a missing or empty CLAUDE.md.
WHAT IT MISSES: a file OVER its word budget, which is the known-bad case and the
only failure a word cap exists for. It reports GOOD on `cases/bad-over-budget`
(blind, as required) and GOOD on `cases/good-within-budget` (anchor sanity).

Stdlib-only and network-free, like the gate.
"""

import argparse
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="presence-only budget check (blind anchor)")
    parser.add_argument("document", nargs="?", default="CLAUDE.md")
    parser.add_argument("--budget", type=int, default=2000)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    path = args.root.resolve() / args.document
    if not path.is_file():
        print(f"claude-md-budget: missing {path}", file=sys.stderr)
        return 1
    if not path.read_text(encoding="utf-8").strip():
        print(f"claude-md-budget: {path.name} is empty", file=sys.stderr)
        return 1
    print(f"claude-md-budget: ok - {path.name} present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
