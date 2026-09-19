#!/usr/bin/env python3
"""Derive the consolidation ledger's required population from a captured snapshot (issue #1068).

`.specify/specs/codex-consolidation/ledger.md` is the migration's accounting of
what happens to every open codex-power-pack (CxPP) obligation. Children #1069 to
#1076 read it to decide what may be moved, adapted or retired, and #1076 reads it
to decide whether the repository may be archived at all. Nothing downstream
re-derives it: a capability absent from the ledger is not reported as undecided,
it is simply never considered again.

That is the failure this gate exists to make loud. An incomplete ledger and a
complete one read identically - both are long, both are confident, and the
missing row is missing from the very document a reader would consult to notice
it. The ADR 0008 bound applies squarely: this verdict is consumed by decisions
that will not independently re-derive the fact, and it is read by other sessions
and another repository.

WHAT IS DERIVED AND WHAT IS NOT. The POPULATION is derived from a captured
snapshot of CxPP's open issues and PRs; the DISPOSITION prose stays hand-written,
because the judgement is the valuable part and no generator can make it. This
gate only ever answers "is there a row for this number", never "is the
disposition right".

WHY THE SNAPSHOT IS A COMMITTED FILE AND NOT A LIVE QUERY. CI has no network and
no `gh` credentials, so a live query would make the gate skip - and a skipped
gate that prints nothing looks exactly like a passing one. The snapshot is
committed, and `--refresh` re-captures it on a host that does have `gh`.

WHY THE SNAPSHOT IS NOT BUILT FROM THE LEDGER. This is the whole design. A
snapshot derived by scanning the ledger for `cxpp#N` tokens would compare the
ledger against itself: every number present would be a number required, the
check could never be red, and it would ship green forever while proving nothing.
The snapshot's provenance header records the `gh` commands it came from for
exactly this reason - so a later maintainer refreshing it cannot accidentally
close the loop.

WHY EXTRA ROWS ARE NOT A FINDING. The ledger legitimately cites numbers outside
the snapshot: PRs that merged before the baseline (cxpp#287), issues closed
earlier, CPP issue numbers. Flagging those would make the gate red on correct
prose and it would be switched off - the oscillation ADR 0009 predicts. This gate
is one-directional by design, and the direction it does not check is stated in
its own success line rather than left for a reader to assume.

#: NEGATIVE-CONTROL: controls/ledger-completeness
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_LEDGER = ".specify/specs/codex-consolidation/ledger.md"
DEFAULT_SNAPSHOT = ".specify/specs/codex-consolidation/baseline-open.txt"
CXPP_REPO = "cooneycw/codex-power-pack"

#: A ledger row claims an entry by naming it `cxpp#<n>` IN THE FIRST CELL of a
#: table row. Two halves, and both were measured against the real document.
#:
#: The `cxpp` prefix is load-bearing: the ledger also cites bare CPP numbers
#: (`#1069`, `cpp#864`), and matching those would let a CPP issue number stand in
#: as an account of a CxPP obligation.
#:
#: THE FIRST-CELL RULE WAS NOT THE FIRST DESIGN, and the reason it is here is
#: worth the lines. The first cut matched `cxpp#<n>` ANYWHERE in the file, and
#: this control's own known-bad fixture PASSED it: the fixture's prose explains
#: that `cxpp#227` has no row, and that sentence contains the token, so the scan
#: counted the explanation of the absence as the account of it. Better prose
#: makes a whole-file text scan MORE likely to pass, not less - the well-written
#: ledger is the one most likely to discuss the entries it never tabulated. The
#: same shape is why the two sibling gates in this repository key on a specific
#: position (`scripts-inventory-check.py`: first backticked token of a heading;
#: `instrument-census-check.py`: first backticked token of column 2) rather than
#: on presence.
#:
#: The narrower rule also drops citations in a DISPOSITION cell - "CPP #1035
#: records the same family", "landed via PR cxpp#287" - which are cross
#: references, not accountings. A row must be a row.
CLAIM_RE = re.compile(r"\bcxpp#(\d+)\b")
ROW_RE = re.compile(r"^\s*\|(?P<first>[^|]*)\|")

#: A row must also SAY something. Independent review (#1068 review.md, finding
#: R3) pointed out that presence alone lets a row read `| cxpp#239 | | | | |`
#: and pass: the entry is accounted for in the sense that its number appears,
#: and accounted for in no other sense. The issue's acceptance asks for a
#: recorded disposition per obligation, so an empty one is not a lesser row, it
#: is the absence the ledger exists to prevent - wearing a row's clothing.
#:
#: The vocabulary is closed at six and lives in the ledger's own header table.
#: It is duplicated here deliberately rather than parsed out of the document:
#: reading the permitted values FROM the file under test would let a ledger
#: legitimise any word by adding it to its own table, which is the same closed
#: loop the snapshot's provenance header exists to prevent.
DISPOSITIONS = (
    "already-covered",
    "move",
    "adapt",
    "transfer",
    "owner-approved-retirement",
    "unresolved",
)

#: Fenced blocks are examples, not the document speaking. A `cxpp#123` inside a
#: worked example would otherwise satisfy a real obligation's missing row.
FENCE_RE = re.compile(r"^\s*```", re.MULTILINE)


def strip_fences(text: str) -> str:
    """Drop fenced code blocks; an illustrative token is not an accounting."""
    out, inside = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            inside = not inside
            continue
        if not inside:
            out.append(line)
    return "\n".join(out)


def read_snapshot(path: Path) -> set[int]:
    """Numbers required to appear in the ledger. Comments and blanks ignored."""
    nums: set[int] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip() if not raw.lstrip().startswith("#") else ""
        if line:
            nums.add(int(line))
    return nums


def read_claims(path: Path) -> tuple[set[int], set[int]]:
    """(accounted, undisposed) - first cell of a table row, `cxpp#` prefixed.

    A number lands in `accounted` only if its row also names a disposition; one
    whose row does not appears in `undisposed` INSTEAD, so an empty row cannot
    satisfy the requirement it looks like it satisfies.
    """
    accounted: set[int] = set()
    undisposed: set[int] = set()
    for line in strip_fences(path.read_text(encoding="utf-8")).splitlines():
        row = ROW_RE.match(line)
        if not row:
            continue
        nums = {int(m) for m in CLAIM_RE.findall(row.group("first"))}
        if not nums:
            continue
        if any(f"`{d}`" in line for d in DISPOSITIONS):
            accounted |= nums
        else:
            undisposed |= nums
    return accounted, undisposed


def refresh(snapshot: Path) -> int:
    """Re-capture the snapshot from GitHub. Never reads the ledger."""
    numbers: list[int] = []
    for kind in ("issue", "pr"):
        proc = subprocess.run(
            ["gh", kind, "list", "--repo", CXPP_REPO, "--state", "open",
             "--limit", "200", "--json", "number", "--jq", ".[].number"],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            print(f"check-consolidation-ledger: refresh failed on {kind} list: "
                  f"{proc.stderr.strip()}", file=sys.stderr)
            return 2
        numbers.extend(int(n) for n in proc.stdout.split())

    header = [ln for ln in snapshot.read_text(encoding="utf-8").splitlines()
              if ln.lstrip().startswith("#")]
    body = "\n".join(str(n) for n in sorted(set(numbers)))
    snapshot.write_text("\n".join(header) + "\n" + body + "\n", encoding="utf-8")
    print(f"check-consolidation-ledger: refreshed {snapshot} - "
          f"{len(set(numbers))} open entry(ies)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--ledger", type=Path, default=None)
    ap.add_argument("--snapshot", type=Path, default=None)
    ap.add_argument("--refresh", action="store_true",
                    help="re-capture the snapshot from GitHub (needs network + gh)")
    args = ap.parse_args(argv)

    ledger = args.ledger or args.root / DEFAULT_LEDGER
    snapshot = args.snapshot or args.root / DEFAULT_SNAPSHOT

    if args.refresh:
        return refresh(snapshot)

    for path, what in ((snapshot, "snapshot"), (ledger, "ledger")):
        if not path.is_file():
            # An absent input is UNKNOWN, never clean. Exiting 0 here would make a
            # deleted ledger indistinguishable from a complete one.
            print(f"check-consolidation-ledger: {what} not found at {path}", file=sys.stderr)
            return 2

    required = read_snapshot(snapshot)
    if not required:
        print(f"check-consolidation-ledger: {snapshot} parsed to 0 required entries - "
              f"the check would pass vacuously", file=sys.stderr)
        return 2

    claimed, undisposed = read_claims(ledger)
    missing = sorted(required - claimed)

    for num in missing:
        if num in undisposed:
            print(f"LEDGER_MISSING: cxpp#{num} has a row in {ledger} but no disposition, "
                  f"so nothing is recorded about what happens to it")
        else:
            print(f"LEDGER_MISSING: cxpp#{num} is open at the baseline and has no row in {ledger}")

    if missing:
        print(f"check-consolidation-ledger: FAIL - {len(missing)} of {len(required)} "
              f"open entry(ies) are unaccounted for")
        return 1

    print(f"check-consolidation-ledger: ok - all {len(required)} open entry(ies) in the "
          f"{snapshot.name} snapshot have a row in {ledger.name} carrying one of the "
          f"{len(DISPOSITIONS)} dispositions (presence and non-emptiness only; this gate "
          f"does not judge whether a disposition is RIGHT)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
