#!/usr/bin/env python3
"""BLIND ANCHOR for scripts/delegated-core-vendor.py (issue #1011).

NOT a past version of the gate - the gate is new, so the honest "before" is "no
check at all", which cannot be run against a case and therefore cannot
demonstrate anything. This is the plausible WEAKER check somebody would write
instead: confirm each driver file still carries its `delegated-core` marker
pair, and call that vendored.

That check is not stupid. It catches a driver file whose markers were deleted,
which is a real failure. What it cannot see is the failure that actually
happens - a rendered region edited IN PLACE, markers intact, bytes no longer
the core - because it never renders the template and never compares anything.
Run against the committed known-BAD case it reports the same clean line it
reports on the known-GOOD one, which is exactly what "a green from a blind
instrument and a green from a working one look identical" means.

Accepts the same invocation as the real gate so the harness can substitute it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DRIVERS = ("codex", "qwen", "gemma")
REGIONS = ("A", "B")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="check", choices=["check"])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    problems = 0
    for driver in DRIVERS:
        rel = f".claude/commands/{driver}/auto.md"
        path = root / rel
        if not path.is_file():
            print(f"MISSING: {rel}")
            problems += 1
            continue
        text = path.read_text(encoding="utf-8")
        for region in REGIONS:
            if f"delegated-core:begin {region}" not in text or f"delegated-core:end {region}" not in text:
                print(f"MISSING: {rel} has no delegated-core:{region} marker pair")
                problems += 1

    if problems:
        return 1
    print(f"delegated-core-vendor: {len(DRIVERS)} driver(s) match the canonical core.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
