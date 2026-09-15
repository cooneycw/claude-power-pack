#!/usr/bin/env python3
"""check-oscillation.py - report knobs that have been moved BACK (issue #936).

THE PATTERN. Some choices run down the middle of opposing trade-offs, and the
project swings between them. Each swing is locally correct - it fixes the pain
actually present - and the pain on the other side is invisible at that moment
because it was fixed last time. The result is motion without progress, and the
record of why the knob was where it was gets overwritten by the move.

THE SIGNATURE IS MECHANICAL AND LIVES IN GIT HISTORY: the same knob moved in
the opposite direction. Not "changed twice" - CHANGED BACK.

---------------------------------------------------------------------------
IT REPORTS. IT DOES NOT FAIL THE BUILD. (owner ruling, 2026-09-15)
---------------------------------------------------------------------------
A blocking detector that flags every threshold edit gets switched off, and
switching it off is itself an oscillation - performed by the control built to
prevent oscillation. So a FINDING never fails anything.

That is deliberately NOT the same as an exit code that cannot fail, which this
repository has spent the day removing. The split:

    found / none  -> exit 0   a verdict about the knobs
    unknown       -> exit 3   a verdict about THIS RUN's ability to look

A population of zero is UNKNOWN, never "none" (#952): "I examined 400 knob
changes and none reversed" and "I examined nothing" are different facts and
must not share an exit code or a word. The build is never failed by what this
finds; it is failed by this being unable to look.

---------------------------------------------------------------------------
THE POPULATION IS DERIVED FROM HISTORY. THERE IS NO KNOB LIST.
---------------------------------------------------------------------------
A hardcoded list of "the knobs we care about" is a coverage enumeration, and
this repository has spent the day finding those stale. Knobs are discovered by
walking diffs: any line whose numeric value, exit code, or allowlist membership
changed, keyed by the setting's own name. A knob introduced next month is
watched from its first edit without anyone adding it here.

---------------------------------------------------------------------------
THIS SCRIPT IS SUBJECT TO ITS OWN RULE
---------------------------------------------------------------------------
`--window` is a threshold, which is one of the issue's own tells. Its reversal
trigger is committed beside it below, because a control exempting itself from
its own directive is the most conspicuous possible way to fail.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

EXIT_REPORTED = 0
EXIT_USAGE = 2
EXIT_UNKNOWN = 3

# How many commits apart two opposing moves may be and still count as one
# oscillation.
#
# REVERSAL TRIGGER (issue #936, and this setting is a threshold, which is one of
# that issue's own tells): if findings are dominated by pairs whose two moves are
# separated by unrelated work - a knob tightened in January and loosened in
# November for a reason nobody connects - the window is too wide and the report
# becomes noise, which is how a reporting detector gets ignored rather than
# switched off. Narrow it, and record long-range reversals as a separate,
# lower-confidence class rather than deleting them.
#
# It is deliberately generous: a MISSED oscillation is silent, while a
# noisy one is visible and complained about. Failing toward visible is the
# recoverable direction.
DEFAULT_WINDOW = 50

# A knob assignment: `name = 30`, `name: 30`, `name=30`, `--flag 30`, `exit 3`.
# Quoted values count - a timeout written "30" is still a timeout.
ASSIGN = re.compile(
    r"""(?P<key>[A-Za-z_][A-Za-z0-9_.-]*)\s*[:=]\s*["']?(?P<val>-?\d+(?:\.\d+)?)["']?\s*(?:[,;)\]]|$)"""
)
FLAG = re.compile(r"""--(?P<key>[A-Za-z][A-Za-z0-9-]*)[ =]["']?(?P<val>-?\d+(?:\.\d+)?)["']?""")
EXITC = re.compile(r"""\bexit\s+(?P<val>\d+)\b""")


@dataclass
class Move:
    sha: str
    ordinal: int
    subject: str
    path: str
    key: str
    before: float
    after: float

    @property
    def direction(self) -> int:
        return (self.after > self.before) - (self.after < self.before)


@dataclass
class Finding:
    path: str
    key: str
    moves: list[Move] = field(default_factory=list)

    def render(self) -> str:
        arrows = " -> ".join(
            [f"{self.moves[0].before:g}"] + [f"{m.after:g}" for m in self.moves]
        )
        where = ", ".join(f"{m.sha[:8]} ({m.subject[:44]})" for m in self.moves)
        return f"OSCILLATION_FINDING: {self.path}:{self.key}  {arrows}\n    {where}"


def _knobs(line: str) -> dict[str, float]:
    """Every knob-looking setting on one line, keyed by its own name."""
    out: dict[str, float] = {}
    for m in ASSIGN.finditer(line):
        out[m.group("key")] = float(m.group("val"))
    for m in FLAG.finditer(line):
        out[f"--{m.group('key')}"] = float(m.group("val"))
    for m in EXITC.finditer(line):
        out["exit"] = float(m.group("val"))
    return out


def collect_moves(root: Path, rev_range: str) -> tuple[list[Move], int]:
    """Walk history and derive every knob move. Returns (moves, commits_seen)."""
    # ANCHOR BLINDNESS (constructed, issue #936): this variant reads only the
    # NEWEST commit. It therefore observes at most ONE move and can never see a
    # sequence reverse - which is precisely the insight the real gate encodes.
    # It is the honest "before" for a detector that did not previously exist:
    # looking at a single change tells you nothing about oscillation.
    rev_range = "HEAD~1..HEAD"
    proc = subprocess.run(
        ["git", "log", "--reverse", "--unified=0", "--no-merges",
         "--format=%x00%H%x00%s", "-p", rev_range],
        cwd=root, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return [], 0

    moves: list[Move] = []
    sha = subject = ""
    path = ""
    ordinal = -1
    removed: list[str] = []
    added: list[str] = []

    def flush() -> None:
        """Pair removed/added lines within a hunk by shared knob key."""
        if not (removed and added and path):
            removed.clear()
            added.clear()
            return
        before: dict[str, float] = {}
        after: dict[str, float] = {}
        for ln in removed:
            before.update(_knobs(ln))
        for ln in added:
            after.update(_knobs(ln))
        for key in sorted(set(before) & set(after)):
            if before[key] != after[key]:
                moves.append(Move(sha, ordinal, subject, path, key, before[key], after[key]))
        removed.clear()
        added.clear()

    for raw in proc.stdout.splitlines():
        if raw.startswith("\x00"):
            flush()
            _, sha, subject = raw.split("\x00", 2)
            ordinal += 1
            path = ""
            continue
        if raw.startswith("+++ b/"):
            flush()
            path = raw[6:]
            continue
        if raw.startswith("@@"):
            flush()
            continue
        if raw.startswith("-") and not raw.startswith("---"):
            removed.append(raw[1:])
        elif raw.startswith("+") and not raw.startswith("+++"):
            added.append(raw[1:])
    flush()
    return moves, ordinal + 1


def find_oscillations(moves: list[Move], window: int) -> list[Finding]:
    """A knob whose direction REVERSES within `window` commits.

    Changed twice is not the signature. Changed BACK is.
    """
    by_knob: dict[tuple[str, str], list[Move]] = defaultdict(list)
    for m in moves:
        by_knob[(m.path, m.key)].append(m)

    findings: list[Finding] = []
    for (path, key), seq in sorted(by_knob.items()):
        seq.sort(key=lambda m: m.ordinal)
        for a, b in zip(seq, seq[1:]):
            if not (a.direction and b.direction and a.direction != b.direction):
                continue
            # DIFFERENT COMMITS. Two opposing edits inside ONE commit are not an
            # oscillation - they are one author settling on a value while
            # writing it, or a generated file being rewritten. The signature is
            # a swing ACROSS time, not within a single change. The first cut
            # missed this and reported a lockfile's package sizes, both "moves"
            # carrying the same sha.
            if a.sha == b.sha:
                continue
            if b.ordinal - a.ordinal <= window:
                findings.append(Finding(path, key, [a, b]))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--root", default=".", help="repository to examine")
    ap.add_argument("--range", dest="rev_range", default="HEAD~200..HEAD",
                    help="git revision range (default: HEAD~200..HEAD)")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW,
                    help=f"max commits between opposing moves (default: {DEFAULT_WINDOW})")
    ap.add_argument("--json", action="store_true", help="machine-readable findings")
    # ADAPTER, not a build policy. The negative-control framework decides a
    # case from the EXIT CODE (`GOOD = exit == good_exit`), so a detector that
    # exits 0 for both verdicts has its known-BAD case scored GOOD and the
    # control is blind. This flag lets controls/check-oscillation register a
    # real two-sided case without changing what the build sees.
    #
    # REVERSAL TRIGGER (this is an exit-code policy, one of #936's own tells):
    # the build must NEVER pass this. If it ever appears in a Makefile target
    # or a CI step, the detector has become blocking - which the owner ruled
    # against precisely because a blocking detector gets switched off, and
    # switching it off is itself an oscillation. Remove it from the build and
    # keep it to the control registration. tests/test_oscillation_control.py
    # asserts the build does not use it.
    ap.add_argument("--exit-on-finding", action="store_true",
                    help="exit 1 when a finding exists (for the control framework only)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    # Ask git, rather than looking for a `.git` entry. A bare repository has no
    # `.git` at all, and the control fixtures are bare repos - a hardcoded path
    # assumption would have reported them UNKNOWN and the control would have
    # been unregistrable for a reason that had nothing to do with the gate.
    probe = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=root if root.is_dir() else ".",
                           capture_output=True, text=True)
    if not root.is_dir() or probe.returncode != 0:
        print(f"check-oscillation: {root} is not a git repository, so no history "
              f"could be read. This is UNKNOWN, not clean.", file=sys.stderr)
        print("OSCILLATION_EXAMINED: 0")
        print("OSCILLATION: unknown")
        return EXIT_UNKNOWN

    moves, commits = collect_moves(root, args.rev_range)

    # SCANNED NOTHING IS NOT CLEAN (#952). A range that resolves to no commits,
    # or a history with no knob edits in it, has not established that nothing
    # oscillated - it has established that this run could not look.
    if commits == 0 or not moves:
        print(f"check-oscillation: examined {commits} commit(s) and found NO knob "
              f"changes at all in {args.rev_range}. Nothing was compared, so this "
              f"is UNKNOWN rather than clean.", file=sys.stderr)
        print(f"OSCILLATION_SOURCE: {args.rev_range}")
        print(f"OSCILLATION_COMMITS: {commits}")
        print("OSCILLATION_EXAMINED: 0")
        print("OSCILLATION: unknown")
        return EXIT_UNKNOWN

    findings = find_oscillations(moves, args.window)
    knobs = len({(m.path, m.key) for m in moves})

    if args.json:
        print(json.dumps({
            "source": args.rev_range, "commits": commits, "examined": len(moves),
            "knobs": knobs, "window": args.window,
            "findings": [
                {"path": f.path, "key": f.key,
                 "values": [f.moves[0].before] + [m.after for m in f.moves],
                 "commits": [m.sha for m in f.moves]}
                for f in findings
            ],
        }, indent=2))
        return EXIT_REPORTED

    print(f"OSCILLATION_SOURCE: {args.rev_range}")
    print(f"OSCILLATION_COMMITS: {commits}")
    print(f"OSCILLATION_EXAMINED: {len(moves)}")
    print(f"OSCILLATION_KNOBS: {knobs}")
    print(f"OSCILLATION_WINDOW: {args.window}")
    for f in findings:
        print(f.render())
    print(f"OSCILLATION: {'found' if findings else 'none'}")
    if findings and args.exit_on_finding:
        return 1
    if findings:
        print(f"\ncheck-oscillation: {len(findings)} knob(s) moved BACK. This is a "
              f"REPORT, not a failure - see docs/decisions/0009-oscillation-control.md.\n"
              f"Each one wants a committed reversal trigger beside the setting.",
              file=sys.stderr)
    return EXIT_REPORTED


if __name__ == "__main__":
    sys.exit(main())
