#!/usr/bin/env python3
"""CONSTRUCTED BLIND ANCHOR for scripts/pytest-parallel-differential.py (issue #1086).

NOT A HISTORICAL REVISION. The gate is new and never shipped blind, so there is
no commit to vendor and `--verify-provenance` reports `unverified` here - which is
correct and must never be read as `ok`. What this file IS: the first framing of
the problem, written down before the distinction the gate exists to draw was
noticed.

That framing is "did the two runs agree", answered by comparing HOW MANY tests
passed and HOW MANY failed. It is the reading issue #1086 names and rejects in one
sentence - "the same pass/fail SET, not merely the same colour" - and it is the
obvious thing to write if you have not yet been bitten by it. It is also exactly
what a human does when they glance at two runs: 4262 passed, 1 failed, both times,
same numbers, done.

WHAT IT MISSES, and why each miss is the point:

  bad-substituted-node   3 passes serially, 3 passes in parallel. Identical
                         tallies, and a different test ran. Every count this
                         anchor examines agrees; the POPULATION does not, and no
                         count can say so.

  bad-dangerous-flip     1 pass and 1 failure on both sides - with the pass and
                         the failure swapped between two different tests. One of
                         them failed serially and passed in parallel, which is the
                         direction that must block, and the tally is byte-identical
                         either way.

  good-matched           agrees with the real gate: identical tallies, and the
                         populations genuinely match. This is the anchor-sanity
                         half. If it disagreed here too, it would differ from the
                         current gate for reasons beyond the blindness under test
                         and the demonstration would not be isolated.

The exit contract is the real gate's, because a control's verdict is read from the
exit code AND the output: an anchor that crashed would exit non-zero and score as
having CAUGHT the bad input, which accuses a healthy anchor of not being blind.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def tally(path: Path) -> dict[str, int]:
    """How many passed, how many failed. Nothing about WHICH."""
    if not path.is_file():
        print(f"DIFFERENTIAL-UNKNOWN: {path} does not exist", file=sys.stderr)
        raise SystemExit(2)
    tree = ET.parse(path)
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for case in tree.getroot().iter("testcase"):
        verdict = "PASS"
        for child in case:
            name = child.tag.rsplit("}", 1)[-1]
            if name in ("failure", "error"):
                verdict = "FAIL"
                break
            if name == "skipped":
                verdict = "SKIP"
                break
        counts[verdict] += 1
    if not sum(counts.values()):
        print(f"DIFFERENTIAL-UNKNOWN: {path} carries zero test cases", file=sys.stderr)
        raise SystemExit(2)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", type=Path)
    parser.add_argument("--parallel", type=Path)
    parser.add_argument("--pair", type=Path)
    args = parser.parse_args(argv)

    if args.pair is not None:
        serial_path = args.pair / "serial.xml"
        parallel_path = args.pair / "parallel.xml"
    elif args.serial is not None and args.parallel is not None:
        serial_path, parallel_path = args.serial, args.parallel
    else:
        parser.error("pass --pair <dir>, or both --serial and --parallel")

    serial = tally(serial_path)
    parallel = tally(parallel_path)

    print(f"  tally serial:   {serial}")
    print(f"  tally parallel: {parallel}")

    if serial != parallel:
        print(
            f"BLOCKS - the runs disagree: {serial} serially vs {parallel} in parallel."
        )
        return 1

    print("VERDICT: no dangerous-direction changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
