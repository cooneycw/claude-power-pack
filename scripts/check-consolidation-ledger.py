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
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LEDGER = ".specify/specs/codex-consolidation/ledger.md"
DEFAULT_SNAPSHOT = ".specify/specs/codex-consolidation/baseline-open.txt"
CXPP_REPO = "cooneycw/codex-power-pack"

#: `gh ... --limit N` truncates SILENTLY, so N is a ceiling and not a count.
GH_LIMIT = 200

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
ROW_RE = re.compile(r"^\s*\|(?P<first>[^|]*)\|(?P<rest>.*)$")

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
#:
#: BOTH fence characters, because CommonMark has two and recognising only one
#: leaves the other as a hole in the rule (counter-model finding F5). A
#: `~~~markdown` block holding an illustrative ledger row satisfied a real
#: obligation under the first cut. A fence closes only on the same character at
#: the same length or longer, so the opener is remembered rather than toggled -
#: a ``` line inside a ~~~ block is content, not a close.
FENCE_RE = re.compile(r"^\s*(?P<char>`{3,}|~{3,})")


def strip_fences(text: str) -> str:
    """Drop fenced code blocks; an illustrative token is not an accounting."""
    out: list[str] = []
    opener: str | None = None
    for line in text.splitlines():
        m = FENCE_RE.match(line)
        if m:
            run = m.group("char")
            if opener is None:
                opener = run
                continue
            if run[0] == opener[0] and len(run) >= len(opener):
                opener = None
                continue
            # A different fence character, or a shorter run: content, not a close.
        if opener is None:
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
        # THE SUBJECT IS THE FIRST TOKEN, NOT EVERY TOKEN (counter-model finding
        # F1). A first cell reading `cxpp#189 - related to cxpp#227` is a row
        # ABOUT 189 that mentions 227; counting both let a cross-reference in
        # someone else's title discharge 227's own missing row. A row has one
        # subject, and it is the one it leads with - the same rule
        # `scripts-inventory-check.py` and `instrument-census-check.py` use.
        subjects = CLAIM_RE.findall(row.group("first"))
        if not subjects:
            continue
        num = int(subjects[0])
        # THE DISPOSITION IS SEARCHED OUTSIDE CELL 1 (same finding). Searching
        # the whole row let a backticked vocabulary word in the TITLE stand in
        # for an empty disposition column - "the `unresolved` nit store" would
        # satisfy a row that records nothing.
        if any(f"`{d}`" in row.group("rest") for d in DISPOSITIONS):
            accounted.add(num)
        else:
            undisposed.add(num)
    return accounted, undisposed


def refresh(snapshot: Path) -> int:
    """Re-capture the snapshot from GitHub. Never reads the ledger."""
    captured: dict[str, list[int]] = {}
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
        captured[kind] = [int(n) for n in proc.stdout.split()]
    issues, prs = captured["issue"], captured["pr"]

    # REGENERATE THE PROVENANCE, NEVER COPY IT (counter-model finding F6). The
    # first cut carried every old comment line through unchanged - including
    # `Captured: <date>` and the two baseline SHAs - so a refresh produced a NEW
    # observation wearing the ORIGINAL capture's date. That defeats the one
    # thing this file exists to provide: the ability to tell a changed fact from
    # an omitted one. It also flattened the issue/PR split under both labels.
    #
    # The CODE baseline and the OBSERVATION time are different facts and are
    # printed as such: the SHAs say which tree the ledger was written against,
    # the capture date says when GitHub was last asked.
    prior = snapshot.read_text(encoding="utf-8").splitlines()
    baseline = [ln for ln in prior if ln.lstrip().startswith("#")
                and ("baseline:" in ln or "CxPP baseline" in ln or "CPP  baseline" in ln)]
    today = datetime.now(timezone.utc).date().isoformat()
    header = [
        "# Open codex-power-pack issues and PRs.",
        "#",
        "# PROVENANCE - captured from GitHub, NEVER derived from the ledger.",
        "# A snapshot built by reading the ledger would make the completeness check a",
        "# closed loop: the ledger would be compared against itself and could never be",
        "# found incomplete. Captured with:",
        "#",
        "#   gh issue list --repo cooneycw/codex-power-pack --state open --limit 200 \\",
        "#       --json number --jq '.[].number'",
        "#   gh pr list   --repo cooneycw/codex-power-pack --state open --limit 200 \\",
        "#       --json number --jq '.[].number'",
        "#",
        f"# Captured: {today}   (this is the OBSERVATION date, regenerated on every",
        "#                      --refresh; it is NOT the code baseline below)",
        *baseline,
        "#",
        "# Refresh with: python3 scripts/check-consolidation-ledger.py --refresh",
        "# A refresh that ADDS a number makes the check red until the ledger accounts",
        "# for it. That is the intended behaviour, not a failure of the snapshot.",
        "#",
        f"# issue numbers ({len(set(issues))})",
        *[str(n) for n in sorted(set(issues))],
        f"# pull request numbers ({len(set(prs))})",
        *[str(n) for n in sorted(set(prs))],
    ]
    snapshot.write_text("\n".join(header) + "\n", encoding="utf-8")
    print(f"check-consolidation-ledger: refreshed {snapshot} - "
          f"{len(set(issues))} issue(s), {len(set(prs))} PR(s), captured {today}")
    return 0


def read_capture_date(path: Path) -> str | None:
    """The `# Captured: <date>` the snapshot records about ITSELF, or None.

    Hardcoding a date here printed "captured 2026-09-19" for every snapshot,
    including a custom one and one `--refresh` had just regenerated - inventing
    provenance for a file that carries its own (counter-model finding,
    2026-09-22). Absent, the line says the date is not recorded rather than
    supplying one.
    """
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"#\s*Captured:\s*(\S+)", raw.strip())
            if m:
                return m.group(1)
    except (OSError, UnicodeDecodeError):
        return None
    return None


def read_live_open(path: Path) -> set[int] | None:
    """Numbers open RIGHT NOW, from a supplied file, or None if unreadable.

    A FILE rather than a network call by default, for two reasons: the gate runs
    in a CI image with no `gh` credentials, and a test needs to drive this axis
    deterministically. `--live-from-github` is the online form.

    None, NOT AN EXCEPTION (counter-model finding, 2026-09-22). `read_snapshot`
    calls `int()` on every non-comment line, so `101\ninvalid\n` raised an
    uncaught ValueError and the process exited 1 - which is this gate's code for
    A LEDGER DEFECT. An unreadable input would have been reported as an
    incomplete ledger: a crash rendering as a verdict, and the wrong verdict.
    Permission and decoding failures had the same shape.
    """
    try:
        return read_snapshot(path)
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def fetch_live_open() -> set[int] | None:
    """Live open issues AND PRs from GitHub, or None if they cannot be obtained.

    None is NOT an empty set, and the caller must not conflate them: an empty
    set would mean "nothing is open", which is a finding; None means "I could
    not look", which is UNKNOWN. Returning `set()` on failure would report the
    strongest possible clean result at exactly the moment the gate went blind.
    """
    numbers: set[int] = set()
    for kind in ("issue", "pr"):
        try:
            out = subprocess.run(
                ["gh", kind, "list", "--repo", CXPP_REPO, "--state", "open",
                 "--limit", str(GH_LIMIT), "--json", "number", "--jq", ".[].number"],
                capture_output=True, text=True, timeout=60, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if out.returncode != 0:
            return None
        got = [int(t) for t in out.stdout.split() if t.strip().isdigit()]
        # THE CEILING IS NOT A COUNT, IT IS AN UNKNOWN (counter-model finding,
        # 2026-09-22). `--limit N` truncates silently, so a repository with more
        # than N open entries returns exactly N and the axis would report "every
        # open entry has a row" over a population it did not see - the SAME
        # population-ceiling defect this axis was added to remove, reintroduced
        # one layer out. At the ceiling we cannot establish completeness, so we
        # decline to answer rather than answer from a truncated set.
        if len(got) >= GH_LIMIT:
            return None
        numbers.update(got)
    return numbers


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--ledger", type=Path, default=None)
    ap.add_argument("--snapshot", type=Path, default=None)
    ap.add_argument("--refresh", action="store_true",
                    help="re-capture the snapshot from GitHub (needs network + gh)")
    ap.add_argument("--live-open", type=Path, default=None,
                    help="file of numbers open RIGHT NOW; enables the LIVE axis offline")
    ap.add_argument("--live-from-github", action="store_true",
                    help="enable the LIVE axis by querying GitHub (needs network + gh)")
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

    captured = read_capture_date(snapshot)
    captured_clause = (f"captured {captured}" if captured
                       else "capture date not recorded in the snapshot")

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

    # ---------------------------------------------------------------- #
    # AXIS 2 - LIVE. The frozen snapshot answers "is every obligation that
    # existed AT THE BASELINE accounted for". It is structurally incapable of
    # answering "does an obligation exist that this ledger has never seen",
    # because its population is a 2026-09-19 file: an issue opened afterwards
    # is not absent from the answer, it is absent from the QUESTION.
    #
    # Measured when this axis was added: baseline = 41, live = 41, and the
    # sets differ in BOTH directions - cxpp#290 arrived, cxpp#239 left. The
    # totals are identical, so nothing that compares counts can see it. That
    # is why every line below names MEMBERS.
    #
    # The snapshot is deliberately NOT refreshed to close this. Refreshing it
    # would destroy the historical baseline the completeness argument rests
    # on, and would make the gate unable to answer its original question in
    # order to answer this one. Two axes, two populations, each named.
    # ---------------------------------------------------------------- #
    live: set[int] | None = None
    live_source = None
    if args.live_open is not None:
        if not args.live_open.is_file():
            print(f"check-consolidation-ledger: live-open file not found at "
                  f"{args.live_open}", file=sys.stderr)
            return 2
        live = read_live_open(args.live_open)
        live_source = str(args.live_open)
        if live is None:
            print(f"check-consolidation-ledger: UNKNOWN - {args.live_open} could not be "
                  f"read or parsed as a list of issue numbers. An unreadable input is not "
                  f"a ledger defect and must not be reported as one.", file=sys.stderr)
            return 2
        if not live:
            # AN EMPTY FILE IS NOT AN OBSERVED EMPTY POPULATION (counter-model
            # finding, 2026-09-22). `gh ... > live.txt` that FAILS leaves a
            # zero-byte file behind, and that is byte-identical to a successful
            # observation that nothing is open. The frozen axis already refuses
            # its own empty parse for this reason; the live axis must too, or
            # the cheapest possible failure buys the strongest possible clean.
            print(f"check-consolidation-ledger: UNKNOWN - {args.live_open} parsed to 0 "
                  f"live entries. A failed capture leaves an empty file that is "
                  f"indistinguishable from 'nothing is open', so this is refused rather "
                  f"than read as a clean live axis.", file=sys.stderr)
            return 2
    elif args.live_from_github:
        live = fetch_live_open()
        live_source = f"GitHub ({CXPP_REPO})"
        if live is None:
            # UNKNOWN, NEVER CLEAN. The axis was REQUESTED and could not run,
            # which is not the same as not asking. Exiting 0 here would report
            # the strongest clean result at the moment the gate went blind -
            # the failure this whole file exists to make impossible.
            print(f"check-consolidation-ledger: UNKNOWN - the live axis was requested "
                  f"but {CXPP_REPO} could not be read (no gh, no credentials, or no "
                  f"network). This run says NOTHING about obligations opened since "
                  f"{snapshot.name} was captured.", file=sys.stderr)
            return 2

    unseen: list[int] = []
    resolved: list[int] = []
    if live is not None:
        # SUBTRACTING `undisposed` HERE WOULD LET AN EMPTY ROW DISCHARGE A NEW
        # OBLIGATION (counter-model finding, 2026-09-22). `| cxpp#103 | | | | |`
        # lands in `undisposed`, and the baseline axis - which is what reports
        # undisposed rows - cannot reach #103 because it is outside the frozen
        # set. So the live axis owns that case for its own population, exactly
        # as the baseline axis owns it for its own, and the two messages say
        # which of the two conditions was found.
        unseen = sorted(live - claimed)
        resolved = sorted(required - live)
        for num in unseen:
            if num in undisposed:
                print(f"LEDGER_UNSEEN: cxpp#{num} is open NOW and has a row in {ledger} "
                      f"with NO disposition, so nothing is recorded about what happens "
                      f"to it - an obligation that postdates the {snapshot.name} baseline")
            else:
                print(f"LEDGER_UNSEEN: cxpp#{num} is open NOW and has no row in {ledger} - "
                      f"an obligation that postdates the {snapshot.name} baseline")

    if missing or unseen:
        parts = []
        if missing:
            parts.append("baseline-without-a-row " + ", ".join(f"cxpp#{n}" for n in missing))
        if unseen:
            parts.append("live-without-a-row " + ", ".join(f"cxpp#{n}" for n in unseen))
        print(f"check-consolidation-ledger: FAIL - {'; '.join(parts)}")
        return 1

    # THE SUCCESS LINE NAMES MEMBERS, NOT TOTALS, and says which direction is
    # the gap. `41 == 41` was true on the day this axis was written while the
    # sets disagreed on two members in opposite directions, so a total here
    # would be a number that cannot be wrong and therefore cannot be evidence.
    if live is None:
        print(f"check-consolidation-ledger: ok on the BASELINE axis only - every entry in "
              f"the {snapshot.name} snapshot ({captured_clause}) has a row in "
              f"{ledger.name} carrying one of the {len(DISPOSITIONS)} dispositions. "
              f"THE LIVE AXIS WAS NOT EXAMINED: an obligation opened since that capture "
              f"would not appear in this answer. Pass --live-open <file> or "
              f"--live-from-github to check it.")
        return 0

    drift = (", ".join(f"cxpp#{n}" for n in resolved) if resolved else "none")
    print("check-consolidation-ledger: ok on BOTH axes")
    print(f"  BASELINE ({snapshot.name}, {captured_clause}): every entry has a row in "
          f"{ledger.name} carrying one of the {len(DISPOSITIONS)} dispositions.")
    print(f"  LIVE ({live_source}): every open entry has a row. "
          f"live-without-a-row is THE GAP, and it is empty.")
    print(f"  baseline entries no longer live - ordinary resolution, NOT a gap: {drift}")
    print("  (Presence and non-emptiness only; this gate does not judge whether a "
          "disposition is RIGHT.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
