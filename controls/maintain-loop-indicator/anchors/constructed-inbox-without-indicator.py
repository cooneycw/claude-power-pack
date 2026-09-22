#!/usr/bin/env python3
"""CONSTRUCTED ANCHOR for maintain-loop-indicator (issue #1085).

Not a historical commit: this instrument is new, so no frozen prior version
exists. This reproduces the state of the world #1085 was written against, in
the issue's own words - "CPP has the inbox and not the indicator":

    `.claude/friction.jsonl`, the `cpp-memory` ledger, the Nit Store (#864),
    and `/self-improvement:retro` all capture findings. Nothing measures
    whether they move.

So it COUNTS the population and says nothing about timing. It reads the same
capture document and reports a confident total, which is exactly the blindness
under test: a count of recorded findings cannot distinguish findings that
reached the backlog in a day from findings that have been sitting for a week,
and it never emits the detection marker because it computes no delay.

It is deliberately NOT a broken copy of the real script. An anchor that differs
by a typo proves only that the typo matters; this one differs by the CAPABILITY
the issue adds, which is what the control needs to demonstrate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=None)
    ap.add_argument("--capture", type=Path, default=None)
    ap.add_argument("--root", type=Path, default=Path("."))
    args = ap.parse_args(argv)

    if args.input is None or not args.input.is_file():
        print("maintain-loop: no capture to read", file=sys.stderr)
        return 2
    try:
        doc = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("maintain-loop: no capture to read", file=sys.stderr)
        return 2
    if not isinstance(doc, dict):
        return 2

    comments = doc.get("comments") or []
    friction = doc.get("friction") or []
    total = len(comments) + len(friction)
    # A COUNT, offered with confidence. No delay, no partition, no undetermined
    # set - the inbox reporting its own size and calling that the answer.
    print(f"maintain-loop: {total} finding(s) recorded "
          f"({len(comments)} nit-store, {len(friction)} friction)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
