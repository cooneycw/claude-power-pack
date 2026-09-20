#!/usr/bin/env python3
"""CONSTRUCTED ANCHOR for controls/verify-coverage (issue #1028).

The gate is new, so there is no previous blind version to vendor. This is the
check the OTHER framing of the problem produces, and that framing is on the
record rather than invented for the control: issue #1028 opens by asking, of
four checkers, "what gate consumes this" - and the cheapest thing that looks
like an answer is to confirm the aggregate gate exists and has members.

So this anchor asks exactly that. Does the Makefile have a `verify` target, and
does it name at least one prerequisite? A tree where `verify` runs twenty checks
and an unaccounted twenty-first sits beside them passes here, confidently,
because nothing in this framing ever compares the LIST against the TREE.

It therefore misses all four known-bad inputs - an unclassified target, a class
that disagrees with the real prerequisite graph, a checker parked under
`utility`, and a script no build surface invokes - and agrees with the real gate
on the known-good one, which is what makes the control load-bearing rather than
decorative.

Usage, matching the real gate's so the harness can swap them:
    constructed-verify-exists-only-verify-coverage-check.py [--root DIR] [--report]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TARGET_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?!=)\s*(.*)$")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)

    makefile = Path(args.root).resolve() / "Makefile"
    if not makefile.is_file():
        print("UNACCOUNTED: no Makefile")
        return 1

    lines = makefile.read_text().splitlines()
    for i, line in enumerate(lines):
        match = TARGET_RE.match(line)
        if not match or match.group(1) != "verify":
            continue
        rest = match.group(2)
        j = i
        while rest.endswith("\\") and j + 1 < len(lines):
            j += 1
            rest = rest[:-1] + " " + lines[j].strip()
        if rest.split():
            print(f"verify-coverage-check: ok - `verify` has {len(rest.split())} prerequisite(s).")
            return 0
        print("UNACCOUNTED: `verify` names no prerequisites")
        return 1

    print("UNACCOUNTED: no `verify` target")
    return 1


if __name__ == "__main__":
    sys.exit(main())
