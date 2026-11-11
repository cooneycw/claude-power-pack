#!/usr/bin/env python3
"""BLIND ANCHOR for controls/lane-file-age - do not fix, do not lint, do not import.

CONSTRUCTED. The plausible WEAKER CHECK: confirm the project HAS a lane file,
and call that "reviewed". It is the check a reader writes when "the project
keeps a lane list" sounds like the same sentence as "somebody read the list
recently".

WHAT IT CATCHES: nothing about age. It tells a project with a lane file from
one without.
WHAT IT MISSES: a review date that is OLD, and a list with no review date at
all - both known-bad cases, and the only things an age advisory exists to say.
It reports fresh on `cases/bad-one-day-past` and on `cases/bad-no-review-date`
(blind, as required) and fresh on `cases/good-at-threshold` (anchor sanity).

Stdlib-only and network-free, like the gate.
"""

import argparse
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="presence-only lane file check (blind anchor)")
    parser.add_argument("command", choices=["age"])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--today", default=None)
    parser.add_argument("--threshold-days", type=int, default=60)
    args = parser.parse_args(argv)

    path = args.root / ".claude" / "lanes.md"
    if not path.exists():
        print("LANE_FILE_AGE: absent - this project has no .claude/lanes.md; nothing is asked")
        return 0
    print("LANE_FILE_AGE: fresh - the project has a lane file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
