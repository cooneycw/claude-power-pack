#!/usr/bin/env python3
"""Compare a SERIAL and a PARALLEL run of the same commit, node by node (issue #1086).

WHY A GREEN PARALLEL RUN IS WEAKER EVIDENCE THAN A GREEN SERIAL ONE. Add `-n`,
watch the suite finish in a fraction of the time, and the natural reading is
"same tests, less time". A test whose isolation broke does not usually FAIL,
though - it passes for the wrong reason, because a sibling worker created the
resource it asserts on. The speedup is visible; the weakening is not. So the
acceptance question for a parallelism change is not "is it green" but "did the
same tests run, and did they reach the same verdicts".

#: NEGATIVE-CONTROL: controls/pytest-parallel-differential

THREE THINGS THIS DECIDES, and they are deliberately separate:

  MEMBERSHIP FLOOR   the two runs collected the same SET of node ids. This is the
                     cheapest way to catch a worker that silently collected
                     nothing: a green over 3,900 tests and a green over 4,263
                     print the same colour, and only the denominator separates
                     them. A count comparison is not enough - a substituted node
                     keeps the count and changes the population.

  DANGEROUS          a node that FAILS serially and PASSES in parallel. This is
                     the direction that must block: whatever made it pass, it was
                     not the code under test, and shipping it converts a real red
                     into a silent green for as long as the parallelism holds.

  QUARANTINE         a node that PASSES serially and FAILS in parallel. A flake
                     to quarantine rather than a reason to abandon the change -
                     but still a DIFFERENCE, so it is reported and exits non-zero.
                     Calling it agreement because it is the "safe" direction would
                     be the same overclaim in the other direction.

CONTRACT
  exit 0  identical node-id sets AND no node changed verdict
  exit 1  a difference, named: VIOLATED / BLOCKS / QUARANTINE
  exit 2  UNKNOWN - a file is missing, unparseable, or carries zero test cases.
          NOT a pass. Two empty reports have identical node-id sets and agree
          perfectly, which is the most flattering wrong answer available here.

The membership floor is checked FIRST and reported alongside the differential
rather than short-circuiting it, because "which tests vanished" and "which tests
changed verdict" are different diagnoses and a reader chasing one should not have
to re-run to see the other.

NODE IDENTITY is `classname::name` from the JUnit XML, which is what pytest writes
for both serial and xdist runs of the same commit. Not the `file` attribute: it is
absent in some pytest versions and present in others, and an identity that depends
on the writer's version is not an identity.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


class Unknown(Exception):
    """The comparison could not be made. Never a pass."""


def _verdict(case: ET.Element) -> str:
    """One test case's outcome.

    ERROR counts as FAIL: a test that errored did not pass, and separating the
    two here would let an error-to-pass flip escape the dangerous-direction check
    while a failure-to-pass flip was caught.
    """
    for child in case:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag in ("failure", "error"):
            return FAIL
        if tag == "skipped":
            return SKIP
    return PASS


def load(path: Path) -> dict[str, str]:
    """`{node_id: verdict}` for one JUnit XML report."""
    if not path.is_file():
        raise Unknown(f"{path} does not exist")
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise Unknown(f"{path} is not parseable XML: {exc}") from exc

    outcomes: dict[str, str] = {}
    for case in tree.getroot().iter("testcase"):
        classname = case.get("classname", "")
        name = case.get("name", "")
        if not name:
            raise Unknown(f"{path} carries a <testcase> with no name attribute")
        node_id = f"{classname}::{name}" if classname else name
        if node_id in outcomes:
            raise Unknown(
                f"{path} carries {node_id} twice, so node ids are not identities in "
                f"this report and no comparison over them means anything"
            )
        outcomes[node_id] = _verdict(case)

    if not outcomes:
        # A zero-case report is a denominator, not a clean result. Two of them
        # agree perfectly, which is exactly the shape ADR 0008 calls blind.
        raise Unknown(f"{path} carries zero test cases; 0 examined is not 0 differences")
    return outcomes


def compare(serial: dict[str, str], parallel: dict[str, str]) -> int:
    """Report the membership floor and the differential. Returns an exit code."""
    only_serial = sorted(set(serial) - set(parallel))
    only_parallel = sorted(set(parallel) - set(serial))

    if only_serial or only_parallel:
        print(
            f"MEMBERSHIP FLOOR: VIOLATED - {len(serial)} serial node(s) vs "
            f"{len(parallel)} parallel node(s); "
            f"{len(only_serial)} only serial, {len(only_parallel)} only parallel"
        )
        for node in only_serial[:20]:
            print(f"  only in serial:   {node}")
        for node in only_parallel[:20]:
            print(f"  only in parallel: {node}")
    else:
        print(f"MEMBERSHIP FLOOR: OK - identical node-id sets ({len(serial)} node(s))")

    shared = sorted(set(serial) & set(parallel))
    changed = [n for n in shared if serial[n] != parallel[n]]
    dangerous = [n for n in changed if serial[n] == FAIL and parallel[n] == PASS]
    quarantine = [n for n in changed if serial[n] == PASS and parallel[n] == FAIL]
    other = [n for n in changed if n not in dangerous and n not in quarantine]

    print(f"OUTCOME DIFFERENTIAL: {len(changed)} node(s) changed verdict")
    print(f"  tally serial:   {_tally(serial)}")
    print(f"  tally parallel: {_tally(parallel)}")

    for node in dangerous:
        print(f"  DANGEROUS {serial[node]}->{parallel[node]}: {node}")
    for node in quarantine:
        print(f"  quarantine {serial[node]}->{parallel[node]}: {node}")
    for node in other:
        print(f"  changed    {serial[node]}->{parallel[node]}: {node}")

    if dangerous:
        print(
            f"BLOCKS - {len(dangerous)} test(s) fail serially and pass in parallel. "
            f"Whatever made them pass was not the code under test."
        )
        return 1
    if only_serial or only_parallel:
        print("BLOCKS - the two runs did not examine the same population.")
        return 1
    if quarantine or other:
        print(
            f"QUARANTINE - {len(quarantine) + len(other)} test(s) changed verdict in the "
            f"non-dangerous direction. Not agreement; triage them before quoting this pair."
        )
        return 1

    print("VERDICT: no dangerous-direction changes")
    return 0


def _tally(outcomes: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for verdict in outcomes.values():
        counts[verdict] = counts.get(verdict, 0) + 1
    return dict(sorted(counts.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serial", type=Path, help="JUnit XML from the serial run")
    parser.add_argument("--parallel", type=Path, help="JUnit XML from the parallel run")
    parser.add_argument(
        "--pair",
        type=Path,
        help="a directory holding serial.xml and parallel.xml (the control-case shape)",
    )
    args = parser.parse_args(argv)

    if args.pair is not None:
        serial_path = args.pair / "serial.xml"
        parallel_path = args.pair / "parallel.xml"
    elif args.serial is not None and args.parallel is not None:
        serial_path, parallel_path = args.serial, args.parallel
    else:
        parser.error("pass --pair <dir>, or both --serial and --parallel")

    try:
        serial = load(serial_path)
        parallel = load(parallel_path)
    except Unknown as exc:
        print(f"DIFFERENTIAL-UNKNOWN: {exc}", file=sys.stderr)
        print("DIFFERENTIAL-UNKNOWN: this is not a pass.", file=sys.stderr)
        return 2

    return compare(serial, parallel)


if __name__ == "__main__":
    raise SystemExit(main())
