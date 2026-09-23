#!/usr/bin/env python3
"""Maintain-loop leading indicator: do recorded findings reach the backlog?

Issue #1085. CPP already records findings in two places - the Nit Store (#864)
and `.claude/friction.jsonl` - and nothing measured whether they MOVE. This
computes the one number that says so, from data the repository already writes,
with no new instrumentation in the flow lifecycle.

WHAT THIS REPORTS IS A PARTITION, NOT A NUMBER
----------------------------------------------
The median delay is computed over the findings whose filing can be established.
On the real population that is a minority, and a median presented as the
headline with its denominator underneath would claim more than the input
supports. So the partition IS the metric:

    attributable   a finding with an identifiable filing event -> has a delay
    excluded       explicitly dismissed; not a finding that took forever
    UNDETERMINED   filing cannot be established -> reported as undetermined

UNDETERMINED IS NEVER FOLDED INTO THE DENOMINATOR AND NEVER READS AS ZERO. The
issue is explicit: "A broken extractor's zeros look exactly like real ones, and
this is a measurement whose whole purpose is to be believed later by someone who
did not watch it run."

THE FILING EVENT IS A DEFINITION, NOT A FACT
--------------------------------------------
A finding is attributable when some issue cites its comment id
(`issuecomment-<id>`); the EARLIEST such issue is the filing event. Three
linkage sources exist in the data and they are not equal:

  - an explicit `issuecomment-<id>` citation      PRECISE, and the only one used
  - a GitHub cross-reference event on the store   identifies the ISSUE, not the
                                                  COMMENT, so it yields NO
                                                  per-finding delay
  - prose such as "filed as #N"                   redundant with the first

Only the first can start a clock, so only the first is used. The others are
named here so a reader knows they were considered and why they are absent.

THE FRICTION LEDGER IS UNDETERMINED BY CONSTRUCTION. Measured across every
record: its keys are ts, run, step, class, signal, fix, scope, outcome, risk,
harness. None links to a filed issue - `run` names the issue the RUN was about,
not what the finding became. Matching on signal text would be inference dressed
as measurement, so these records are counted in the population and reported as
undetermined rather than guessed at.

NO BANDS. `docs/decisions/0009-oscillation-control.md` governs the first
threshold anyone proposes, and #1085 defers them deliberately: a threshold set
before a baseline exists is a threshold set from an impression. Nothing here
ranks, grades or thresholds. If the number invites a band, that is a separate
decision with its own authority.

THREE STATES, NOT TWO (the #1075 lesson, applied ahead of time rather than
after review). An input that is ABSENT or UNREADABLE is UNKNOWN. An input that
is present and explicitly declares an empty population is a REAL ZERO and is
reported as one. A zero-byte file is the first, not the second: a capture that
failed leaves exactly that behind, and it must not buy a clean bill.

Usage:
    python3 scripts/maintain-loop-indicator.py --input <capture.json>
    python3 scripts/maintain-loop-indicator.py --capture <out.json>   # needs gh
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

#: NEGATIVE-CONTROL: controls/maintain-loop-indicator

NIT_STORE = 864
REPO = "cooneycw/claude-power-pack"

#: A finding is attributable only through an explicit comment citation.
CITATION_RE = re.compile(r"issuecomment-(\d+)")

#: Explicit dismissal. Kept deliberately NARROW and stated in the output: a
#: wide pattern would silently move findings out of the denominator, which is
#: the same overclaim as folding UNDETERMINED in.
#: LINE-ANCHORED, because a prose match is not a disposition (counter-model
#: finding). Searching anywhere in the body excluded a comment reading "This
#: finding was NOT dismissed; it still needs a fix" - the exclusion set is
#: supposed to separate a finding that was decided against from one that took
#: forever, and a negated sentence is neither. The Nit Store has no disposition
#: FIELD, so any textual rule is a floor rather than a census; requiring the
#: marker to OPEN a line at least means someone wrote it as a statement instead
#: of mentioning it. The output says so, so the number is read as a floor.
#: `[ \t]*`, NEVER `\s*`. The first line-anchored cut used `\s*`, which
#: MATCHES NEWLINES, so `^` anchored at a blank line and the whitespace class
#: then crossed into a later line - a "line-anchored" pattern that was not
#: anchored to anything. It left exactly one match on the real population and
#: that match was on an EMPTY line, which is how it was caught: by reading the
#: match that SURVIVED rather than only the seventeen that were removed.
DISMISSAL_RE = re.compile(
    r"^[ \t]*(?:[-*>][ \t]*)?(?:\*\*)?[ \t]*(dismissed|won'?t.?fix|not a defect|"
    r"no action needed|declined)\b",
    re.I | re.M,
)

USAGE_EXIT = 64
UNKNOWN_EXIT = 2

#: NO TOLERANCE. An earlier cut allowed one second of slack before calling a
#: pair inverted, on the reasoning that same-second creation is ordinary. But a
#: tolerance is a threshold: a filing event 0.5s BEFORE its finding entered the
#: median as `-0.00d` and counted as attributable, which is a demonstrably
#: earlier issue being read as a fast filing (counter-model finding). Any
#: negative delay means the citing issue predates the finding, which makes the
#: pair a reference rather than a filing event regardless of magnitude.


def _parse_ts(value: str) -> datetime | None:
    """An AWARE instant, or None. Never a naive datetime.

    A timezone-free timestamp used to parse happily and then raise an uncaught
    `TypeError` when subtracted from an aware one - a crash escaping the three
    verdicts this instrument declares (counter-model finding). Offsets are
    normalised to UTC so that two instants can be COMPARED as instants; the
    filing-event selection used to compare the raw STRINGS, under which
    `2026-09-10T02:00:00+03:00` sorts after `2026-09-10T00:30:00Z` while being
    the earlier moment.
    """
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def load_capture(path: Path) -> tuple[dict | None, str]:
    """(capture, reason). None means UNKNOWN, and the reason says which kind.

    Absent, unreadable, unparseable and structurally wrong all return None.
    A capture that parses and declares its lists - even as `[]` - is a real
    observation and is returned.
    """
    if not path.exists():
        return None, f"{path} does not exist"
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"{path} could not be read ({exc.__class__.__name__})"
    if not raw.strip():
        # A FAILED CAPTURE LEAVES EXACTLY THIS. `gh ... > capture.json` that
        # fails writes zero bytes, and zero bytes is not an observation that
        # nothing is open - it is the absence of an observation.
        return None, f"{path} is empty - a failed capture is not an empty population"
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"{path} is not valid JSON ({exc.msg} at line {exc.lineno})"
    if not isinstance(doc, dict):
        return None, f"{path} is valid JSON but not an object"
    for key in ("comments", "friction"):
        if not isinstance(doc.get(key), list):
            return None, f"{path} has no '{key}' list - the population is undeclared"
    if not isinstance(doc.get("issues"), list):
        return None, f"{path} has no 'issues' list - filing events cannot be established"
    # A MALFORMED MEMBER IS NOT AN ABSENT ONE (counter-model finding). The
    # population used to be filtered with `isinstance(..., dict)`, so
    # `{"comments":[null],"friction":["broken"]}` passed validation, lost both
    # records silently, and reported an OBSERVED EMPTY POPULATION - the
    # strongest clean answer this instrument has, over a capture whose lists
    # were not empty at all. A mixed list understated the denominator the same
    # way, which moves every percentage without moving anything a reader sees.
    for key in ("comments", "friction", "issues"):
        for i, member in enumerate(doc[key]):
            if not isinstance(member, dict):
                return None, (f"{path} has a malformed member at {key}[{i}] ({member!r}); "
                              f"dropping it would report a smaller population as though it "
                              f"were the whole one")
    return doc, ""


def filing_events(issues: list) -> dict[str, tuple]:
    """comment id -> (issue number, created_at) for the EARLIEST citing issue."""
    first: dict[str, tuple] = {}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        created = str(issue.get("created_at") or "")
        when = _parse_ts(created)
        if when is None:
            # An issue whose timestamp cannot be read as an instant cannot be
            # anyone's EARLIEST anything, so it is not a filing event. Skipping
            # it leaves the comment UNDETERMINED, which is the honest answer.
            continue
        body = str(issue.get("body") or "")
        for cid in set(CITATION_RE.findall(body)):
            prior = first.get(cid)
            if prior is None or when < prior[2]:
                first[cid] = (issue.get("number"), created, when)
    return first


def window_shape(days: dict[str, int], population: int) -> str:
    """The window's SHAPE, printed beside the number and not beneath it.

    Three days carrying two thirds of the population means the number describes
    a repository under orchestrated waves, not a repository at rest. That is a
    property of the measurement, not context for it, so it shares the line.

    Days with NO record are absent from `days` entirely and are NOT counted as
    quiet: the ledger cannot tell "no findings" from "nobody was working", so an
    empty day is unknown and the window is stated in ACTIVE days.
    """
    if not days:
        return "window: no dated records"
    ordered = sorted(days)
    active = len(ordered)
    top = sorted(days.values(), reverse=True)[:3]
    share = sum(top) / population * 100 if population else 0.0
    # NO CONDITIONAL LABEL, BECAUSE A CONDITIONAL LABEL IS A BAND (counter-model
    # finding, 2026-09-23). This read `wave-shaped: ...` when the top three days
    # held >= 50% and a plainer sentence otherwise, so six equally-populated
    # days earned the label and seven did not. That is a threshold-based
    # classification, which is exactly what #1085 forbids and what ADR 0009
    # governs - written into the instrument built to honour the constraint.
    # The concentration is reported as a number on every run and the reader
    # decides what it means.
    return (f"window {ordered[0]}..{ordered[-1]}, {active} active day(s), "
            f"top {len(top)} day(s) carry {sum(top)} of {population} ({share:.0f}%)")


def report(capture: dict) -> tuple[int, list[str]]:
    # A MALFORMED MEMBER IS NOT AN ABSENT ONE (counter-model finding). These
    # filtered with `isinstance(..., dict)`, so `{"comments":[null],
    # "friction":["broken"]}` passed validation, lost both records silently,
    # and reported an OBSERVED EMPTY POPULATION - the strongest clean answer
    # this instrument has, over a capture whose lists were not empty at all. A
    # mixed list understated the denominator the same way, which moves every
    # percentage without moving anything a reader can see.
    comments = list(capture["comments"])
    friction = list(capture["friction"])
    population = len(comments) + len(friction)

    if population == 0:
        # A REAL ZERO, and distinguishable from UNKNOWN because the capture
        # PARSED and DECLARED both lists. This is the issue's "reports zero
        # rather than failing" case.
        return 0, ["maintain-loop: population is EMPTY - 0 finding(s) recorded in this "
                   "capture. This is an observed zero, not an unread input."]

    events = filing_events(capture["issues"])
    delays: list[float] = []
    inverted: list[tuple] = []
    excluded = 0
    undetermined = 0
    days: dict[str, int] = {}

    for c in comments:
        created = str(c.get("created_at") or "")
        ts = _parse_ts(created)
        if ts is not None:
            days[created[:10]] = days.get(created[:10], 0) + 1
        cid = str(c.get("id") or "")
        if DISMISSAL_RE.search(str(c.get("body") or "")):
            excluded += 1
            continue
        hit = events.get(cid)
        filed = _parse_ts(hit[1]) if hit else None
        if hit is None or ts is None or filed is None:
            undetermined += 1
            continue
        delta = (filed - ts).total_seconds() / 86400
        if delta < 0:
            # INVERTED LINKAGE IS A DEFECT IN THE ATTRIBUTION, NOT A FAST FILING.
            # A citing issue created BEFORE the finding was recorded means the
            # comment is REFERENCING an existing issue rather than being filed
            # into one, so the attribution rule has matched backwards. Folding
            # it in would pull the median down with a number that is not a
            # filing delay at all - a measurement biased by its own parser.
            inverted.append((cid, hit[0], delta))
            continue
        delays.append(delta)

    # FRICTION RECORDS ARE DATED AND BELONG IN THE WINDOW (counter-model
    # finding). They were counted in the POPULATION - which is the denominator
    # the concentration share divides by - while contributing no dates, so a
    # capture whose friction records spanned three weeks reported the comment
    # dates only, and a friction-only capture reported "no dated records" with
    # every record carrying a timestamp.
    for f in friction:
        fts = str(f.get("ts") or "")
        if _parse_ts(fts) is not None:
            days[fts[:10]] = days.get(fts[:10], 0) + 1

    # THE FRICTION LEDGER CARRIES NO LINKAGE FIELD, so every record is
    # undetermined. It stays in the POPULATION because leaving it out would
    # quietly shrink the denominator and make the attributable share look
    # better than the repository's actual record-keeping supports.
    undetermined += len(friction)

    lines: list[str] = []
    attributable = len(delays)
    pct = attributable / population * 100

    if attributable:
        lines.append(
            f"maintain-loop: median {statistics.median(delays):.2f}d to file, over "
            f"{attributable} of {population} finding(s) ({pct:.1f}% attributable, "
            f"{excluded} excluded as dismissed, {undetermined} UNDETERMINED)"
        )
        lo, hi = min(delays), max(delays)
        lines.append(f"  delay spread: min {lo:+.2f}d, max {hi:+.2f}d "
                     f"(the median is over the attributable subset ONLY)")
    else:
        # NOT a clean bill. Zero attributable over a non-empty population means
        # nothing could be linked, which is a statement about the LINKAGE and
        # not about whether findings are moving.
        lines.append(
            f"maintain-loop: NO attributable finding(s) in a population of {population} "
            f"({excluded} excluded as dismissed, {undetermined} UNDETERMINED). No delay "
            f"is reported, because none can be established - this is not 'nothing is stuck'."
        )

    lines.append(f"  {window_shape(days, population)}")
    lines.append(
        f"  population: {len(comments)} nit-store comment(s) + {len(friction)} friction "
        f"record(s); friction records carry no filing linkage and are undetermined by "
        f"construction."
    )
    lines.append(
        f"  inverted (counted separately, NOT in the median and NOT undetermined): "
        f"{len(inverted)} attribution(s) name an issue created BEFORE the finding. That is "
        f"the ordinary 'file the issue, then record the nit' order - a REFERENCE to existing "
        f"work rather than a filing event - so including it would bias the median with a "
        f"number that is not a filing delay."
    )
    lines.append(
        f"  attributable means: some issue cites `issuecomment-<id>`; the EARLIEST such "
        f"issue is the filing event. excluded means the comment matches an explicit "
        f"dismissal ({DISMISSAL_RE.pattern})."
    )
    lines.append("  no band is proposed or implied (#1085 defers thresholds; ADR 0009).")
    return 0, lines


def _gh(args: list[str]) -> str | None:
    """stdout, or None. None is NOT an empty string - see the #1075 lesson."""
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True,
                             timeout=120, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def _friction_path(root: Path) -> Path | None:
    """`.claude/friction.jsonl` beside the GIT COMMON DIR, not beside `root`.

    A linked worktree does not carry the ledger; it lives in the primary
    checkout and is reached through `git-common-dir` (#471). Resolving it from
    the worktree root finds nothing and, unguarded, reports that nothing as a
    measured zero.
    """
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"],
                             capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    common = Path(out.stdout.strip())
    if not common.is_absolute():
        common = (root / common).resolve()
    return common.parent / ".claude" / "friction.jsonl"


def _github_unreadable(dest: Path) -> int:
    """The shared "GitHub could not be read" refusal, so the message is one text."""
    print("maintain-loop: UNKNOWN - GitHub could not be read, so no capture was "
          "written. A PARTIAL capture is worse than none: it would parse, look like "
          "an observation, and under-report the population.", file=sys.stderr)
    return UNKNOWN_EXIT


def capture(dest: Path, root: Path) -> int:
    """Write a capture document from live data. Never writes a partial one."""
    comments = _gh(["api", "--paginate",
                    f"repos/{REPO}/issues/{NIT_STORE}/comments",
                    "--jq", '.[] | {id:(.id|tostring), created_at:.created_at, body:.body}'])
    # `incomplete_results` IS PART OF THE ANSWER AND THE PROJECTION THREW IT
    # AWAY (counter-model finding). GitHub's search API returns partial results
    # when a query times out and SAYS SO in that flag; `--jq '.items[] | ...'`
    # discarded it, so a truncated result set was indistinguishable from a
    # complete one. A missing citing issue does not make a finding undetermined
    # - it silently promotes a LATER issue to "earliest", which is a confident
    # wrong delay rather than an absent one. This is the same population-ceiling
    # shape as a silent `--limit` truncation, one field over.
    incomplete = _gh(["api", "--paginate",
                      f"search/issues?q=repo:{REPO}+issuecomment+in:body&per_page=100",
                      "--jq", ".incomplete_results"])
    if incomplete is None:
        return _github_unreadable(dest)
    if any(tok.strip().lower() == "true" for tok in incomplete.split()):
        print("maintain-loop: UNKNOWN - GitHub reported `incomplete_results: true` for "
              "the citing-issue search, so the filing events it returned are a subset "
              "of an unknown size. A missing citing issue does not read as undetermined; "
              "it promotes a later one to 'earliest' and reports a confident wrong delay. "
              "No capture was written.", file=sys.stderr)
        return UNKNOWN_EXIT
    issues = _gh(["api", "--paginate",
                  f"search/issues?q=repo:{REPO}+issuecomment+in:body&per_page=100",
                  "--jq", '.items[] | {number:.number, created_at:.created_at, body:.body}'])
    if comments is None or issues is None:
        print("maintain-loop: UNKNOWN - GitHub could not be read, so no capture was "
              "written. A PARTIAL capture is worse than none: it would parse, look "
              "like an observation, and under-report the population.", file=sys.stderr)
        return UNKNOWN_EXIT

    def _lines(blob: str) -> tuple[list, str]:
        """(records, reason). A non-empty reason means UNKNOWN, never a subset.

        This used to `continue` past a line that would not parse, so a ledger
        containing `{"ts":` - a truncated trailing record, which is what an
        interrupted append leaves - contributed nothing and the capture was
        written anyway. That capture then PARSED and reported an observed zero
        (counter-model finding). A partial capture is worse than none, as the
        comment below its GitHub sibling already said.
        """
        out = []
        for n, line in enumerate(blob.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                return [], f"line {n} is not valid JSON ({exc.msg})"
            if not isinstance(record, dict):
                return [], f"line {n} is {type(record).__name__}, not an object"
            out.append(record)
        return out, ""

    # THE DURABLE BUFFER IS IN THE MAIN CHECKOUT, NOT THIS WORKTREE. A linked
    # worktree has no `.claude/friction.jsonl` of its own - the ledger is
    # resolved through `git-common-dir`, exactly as `friction-log.sh` does, so
    # that signals captured inside a worktree survive its removal (#471).
    #
    # The first cut of this function read `root/.claude/friction.jsonl` and
    # fell open to `[]` when it was absent. Run from a worktree it reported
    # "0 friction record(s)" as an OBSERVATION while 73 records sat in the main
    # checkout: a population silently shrunk to nothing, announced as a count.
    # That is the defect this whole instrument exists to make impossible, in
    # the instrument, written by the author who had just documented it four
    # lines above as "a PARTIAL capture is worse than none".
    fpath = _friction_path(root)
    if fpath is None or not fpath.is_file():
        print("maintain-loop: UNKNOWN - the friction ledger could not be located "
              "(looked for .claude/friction.jsonl beside the git common dir). No "
              "capture was written: an absent ledger is not an empty one, and a "
              "capture missing half its population would parse and look complete.",
              file=sys.stderr)
        return UNKNOWN_EXIT
    try:
        friction, why = _lines(fpath.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        print(f"maintain-loop: UNKNOWN - {fpath} exists but could not be read "
              f"({exc.__class__.__name__}).", file=sys.stderr)
        return UNKNOWN_EXIT
    if why:
        print(f"maintain-loop: UNKNOWN - {fpath}: {why}. No capture was written: a "
              f"record that cannot be read is not a record that is absent, and a "
              f"capture missing it would parse and look complete.", file=sys.stderr)
        return UNKNOWN_EXIT

    parsed = {}
    for name, blob in (("comments", comments), ("issues", issues)):
        records, why = _lines(blob)
        if why:
            print(f"maintain-loop: UNKNOWN - the {name} response could not be read "
                  f"({why}). No capture was written.", file=sys.stderr)
            return UNKNOWN_EXIT
        parsed[name] = records

    doc = {
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": f"github:{REPO}#{NIT_STORE} + .claude/friction.jsonl",
        "comments": parsed["comments"],
        "issues": parsed["issues"],
        "friction": friction,
    }
    dest.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"maintain-loop: captured {len(doc['comments'])} comment(s), "
          f"{len(doc['issues'])} citing-issue candidate(s), "
          f"{len(doc['friction'])} friction record(s) -> {dest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", type=Path, default=None,
                    help="capture document to measure")
    ap.add_argument("--capture", type=Path, default=None,
                    help="fetch live data and write a capture document here (needs gh)")
    ap.add_argument("--root", type=Path, default=Path("."))
    args = ap.parse_args(argv)

    if args.capture is not None:
        return capture(args.capture, args.root)
    if args.input is None:
        print("maintain-loop: usage - one of --input or --capture is required. "
              "Absent both, this reports NOTHING rather than defaulting to a "
              "population it was not given.", file=sys.stderr)
        return USAGE_EXIT

    doc, reason = load_capture(args.input)
    if doc is None:
        # UNKNOWN, NEVER CLEAN, and never this instrument's zero. The whole
        # purpose of the measurement is to be believed by someone who did not
        # watch it run, so an input it could not read must say so.
        print(f"maintain-loop: UNKNOWN - {reason}. No number is reported; this run "
              f"says NOTHING about whether findings are reaching the backlog.",
              file=sys.stderr)
        return UNKNOWN_EXIT

    code, lines = report(doc)
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
