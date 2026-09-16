#!/usr/bin/env python3
"""BLIND ANCHOR for scripts/scripts-inventory-check.py (issue #1013).

CONSTRUCTED, not historical: the real gate is new, so there is no previous blind
version to vendor and the honest "before" is "no check at all", which cannot be
run against a case.

This is the weaker check someone would plausibly have written INSTEAD, and the
reason it is plausible is on the record: an exploration pass on this very file
reported that `check-test-binary-guards` appeared as a heading three times, and
issue #1013 had to carry a "Correction to an earlier report" saying it does not.
That framing - the inventory's problem is that it is MESSY - produces exactly this
instrument: confirm the document exists, is not empty, and has no duplicate
headings, then call the inventory checked.

It is blind to the thing that actually goes wrong. A script added with no entry
leaves every heading unique and the document non-empty, so this reports clean on
the known-bad input. A stale section for deleted tooling is invisible to it for
the same reason: it never compares the document against `scripts/` at all.

It must MISS both known-bad inputs and AGREE with the real gate on the known-good
one. If it ever CATCHES a bad case, the real gate's control is not load-bearing
and the registration is wrong.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

HEADING_RE = re.compile(r"^#{2,}\s+(.*)$")


def run_check(root: Path) -> int:
    doc = root / "docs/scripts.md"
    if not doc.is_file():
        print("MISSING: docs/scripts.md does not exist")
        return 1

    text = doc.read_text(encoding="utf-8").strip()
    if not text:
        print("MISSING: docs/scripts.md is empty")
        return 1

    headings = [m.group(1).strip() for line in text.splitlines() if (m := HEADING_RE.match(line))]
    duplicates = sorted(h for h, n in Counter(headings).items() if n > 1)
    if duplicates:
        print(f"DRIFT: docs/scripts.md repeats heading(s): {duplicates}")
        return 1

    print(f"scripts-inventory-check: ok - {len(headings)} section(s), no repeats.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", nargs="?", default="check", choices=["check"])
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    return run_check(Path(args.root).resolve())


if __name__ == "__main__":
    sys.exit(main())
