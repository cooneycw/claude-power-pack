#!/usr/bin/env python3
"""ANCHOR - a deliberately BLIND version of scripts/host-surface-check.py.

DO NOT FIX THIS FILE. It is evidence, not code that runs in anger. The register
swaps it in for the real gate and requires it to MISS the known-bad input; an
anchor that catches it proves the control is not load-bearing, and the harness
reports INERT.

WHAT IT IS. Not a historical commit - the gate is new and never shipped blind,
so there is nothing to vendor. This is the FIRST FRAMING, and it is the one
#1139 was filed against: a HAND-MAINTAINED list of the helpers believed to write
host surfaces. #1132's table named five; a grep of the two command documents
suggested fourteen; a wider grep suggested thirty-eight. Each of those is a
hardcoded membership, and the issue's whole argument is that a wrapper built on
one of them silently fails to cover the sixth, fifteenth or thirty-ninth.

THE ONE DIFFERENCE from the real gate: membership is a constant here, and is
DERIVED from reachability there. Everything else - the declaration syntax, the
verdict lines, the exit codes - is identical, so the demonstration isolates the
derivation rather than confounding it with a second change.

WHY IT MISSES `bad-undeclared-helper`: the fixture's `fixture-writer.sh` writes
`$HOME/.claude/fixture` and declares nothing, but it is not in the list below,
so this version never looks at it and prints the same clean line it prints over
a compliant tree. That is exactly the failure mode a hand-maintained list has in
production, reproduced at fixture scale: a new helper arrives unenumerated and
the gate says ok.

It agrees with the real gate on `good-all-declared`, which is what makes the
demonstration isolated rather than a blanket disagreement.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: THE BUG, STATED: membership is written down instead of derived. A helper not
#: on this list is invisible to this version however many host surfaces it
#: writes.
KNOWN_HELPERS = (
    "cpp-commands-link.sh",
    "codex-skill-sync.py",
    "install-memory-harness.sh",
    "install-drift.sh",
    "drift-detect.sh",
)

DECLARE = "HOST-SURFACE:"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--manifest", action="store_true")
    args = ap.parse_args(argv)

    undeclared = []
    checked = 0
    for name in KNOWN_HELPERS:
        p = args.root / "scripts" / name
        if not p.is_file():
            continue
        checked += 1
        try:
            if DECLARE not in p.read_text(encoding="utf-8"):
                undeclared.append(name)
        except OSError:
            continue

    for name in undeclared:
        print(
            f"UNDECLARED: scripts/{name} is reachable from the "
            "/cpp:init or /cpp:update path and carries no "
            "`#: HOST-SURFACE:` declaration"
        )
    if undeclared:
        print(
            f"host-surface: FAIL - {len(undeclared)} of {checked} reachable "
            "script(s) declare no host surface"
        )
        return 1
    print(
        f"host-surface: ok - all {checked} reachable script(s) carry a "
        "HOST-SURFACE declaration (0 invoked but absent). This says nothing "
        "about whether a declaration is COMPLETE - understatement is not "
        "detectable here by design; see the observation harness."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
