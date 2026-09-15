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
walking diffs: any line whose NUMERIC value or whole-line exit code changed,
keyed by the setting's own name. A knob introduced next month is watched from
its first edit without anyone adding it here.

WHAT THAT DOES NOT COVER, SAID HERE RATHER THAN IMPLIED. This header used to
claim "allowlist membership" as well. It never extracted it: `_knobs` reads
numbers, so adding a string entry to `.gitleaks.toml` and later removing it
produces no moves at all - and with any unrelated numeric move in range the run
still prints `none`, which is a clean-looking verdict about a population that
never contained the thing. That is the defect class this whole control exists
inside, sitting in its own documentation. The scope is NUMERIC SETTINGS AND
WHOLE-LINE EXIT CODES. Membership reversals, enum flips, and duration strings
are for the DIRECTIVE and the orchestrator escalation in ADR 0009 to catch; the
detector is a floor under that rule, never a substitute for it.

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

#: NEGATIVE-CONTROL: controls/check-oscillation

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
#
# The trailing context is a NEGATIVE LOOKAHEAD, not a delimiter class, and that
# is load-bearing. The first cut required the value to be followed by one of
# `,;)]` or end-of-line, which meant `timeout = 30  # seconds, see ADR 0009`
# extracted NOTHING - a knob carrying an inline rationale was invisible. That is
# the worst possible blind spot for this particular detector: ADR 0009's
# strongest tell is "the diff touches a line whose adjacent comment exists to
# explain why it is set that way", so the extractor was blindest exactly where
# the rule is strongest. `(?![\w.])` keeps the reason the delimiter class
# existed - refusing a partial number, so `version = 1.2.3` and `sha = 3f2a`
# match nothing - while letting any trailing text follow.
# The value must END here - a lookahead for a real TERMINATOR, not merely for
# "not a word character". `(?![\w.])` alone let an operator or a unit follow, so
# `timeout = 60 * 60` read as 60 and `delay = "1 minute"` as 1: `60 * 60` then
# `120 * 30` then `60 * 120` reported a reversal of a timeout that never changed,
# and a quoted duration walked straight through the exclusion this detector
# claims for duration strings. An unevaluated expression is not a knob value.
# The `\\` terminator keeps a shell line continuation (`--window 25 \`) readable.
_END = r"""(?=\s*(?:[#\\]|//|$)|[,;)\]}])"""
_VALUE = r"""["']?(?P<val>-?\d+(?:\.\d+)?)["']?""" + _END

# `name: type = 30`. Run BEFORE ASSIGN and allowed to claim the value, because
# ASSIGN reads this shape as key `int`: every annotated knob in a file then
# collapses onto one key, unrelated settings merge into a single series, and
# that series can appear to reverse when nothing did. A misattributed key is
# worse than a missed one - it is a finding pointing at the wrong line.
# The key may be QUOTED: `"timeout": 30` in JSON is the same setting as
# `timeout = 30` in Python, and `.gitleaks.toml`, `control.json` and every CI
# manifest in this repository write it the first way. Unquoted-only, a JSON
# threshold reversal produced no moves whatsoever.
_KEY = r"""["']?(?P<key>[A-Za-z_][A-Za-z0-9_.-]*)["']?"""

# The TYPE may carry commas only INSIDE brackets. Allowing them at the top
# level let the annotation reach across a parameter separator:
# `def f(timeout: int, retries=3)` extracted `{"timeout": 3}`, and because ANNOT
# claims the value span it also SUPPRESSED the correct `retries` reading. So
# moving `retries` 3 -> 5 -> 3 reported an oscillation against `timeout`, which
# never changed - a finding naming the wrong setting, which is the failure mode
# this detector can least afford.
_TYPE = r"""[A-Za-z_][A-Za-z0-9_.]*(?:\[[^\]]*\])?"""
ANNOT = re.compile(
    _KEY + r"""\s*:\s*""" + _TYPE + r"""(?:\s*\|\s*""" + _TYPE + r""")*\s*=\s*""" + _VALUE
)
ASSIGN = re.compile(_KEY + r"""\s*[:=]\s*""" + _VALUE)
# The same `(?![\w.])` boundary as _VALUE, and for the same reason one layer
# out: without it `--timeout 1m`, `--timeout 60s` and `--timeout 2m` read as 1,
# 60 and 2, so a duration that stayed equal and then grew is reported as a
# REVERSAL. A unit-bearing value is now not a knob at all, which is the right
# answer until units are normalised - a wrong number is worse than no number.
FLAG = re.compile(
    r"""--(?P<key>[A-Za-z][A-Za-z0-9-]*)[ =]["']?(?P<val>-?\d+(?:\.\d+)?)["']?(?![\w.])"""
)

# ANCHORED to the whole line, deliberately. `\bexit\s+\d+\b` also matches
# PROSE - "the gate must exit 3 when it cannot look" - and this repository's
# documentation discusses exit codes constantly, so every doc became a knob
# named `exit` whose value swung between paragraphs. Noise is not a neutral
# failure here: a reporting detector that cries wolf gets ignored, and being
# ignored is how this control fails. The cost is real and accepted - a guarded
# `[[ -n $x ]] && exit 3` is not seen - and it is the recoverable direction,
# because a missed knob is one line of history and a doc-wide false series
# discredits the whole report.
EXITC = re.compile(r"""^\s*exit\s+(?P<val>\d+)\s*$""")


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
    claimed: set[tuple[int, int]] = set()
    for m in ANNOT.finditer(line):
        out[m.group("key")] = float(m.group("val"))
        claimed.add(m.span("val"))
    for m in ASSIGN.finditer(line):
        # The annotated form already named this value; ASSIGN would rename it
        # after the TYPE. Keyed on the span so the suppression is about this
        # occurrence rather than about the key, which may legitimately recur.
        if m.span("val") in claimed:
            continue
        out[m.group("key")] = float(m.group("val"))
    for m in FLAG.finditer(line):
        out[f"--{m.group('key')}"] = float(m.group("val"))
    for m in EXITC.finditer(line):
        out["exit"] = float(m.group("val"))
    return out


def collect_moves(root: Path, rev_range: str) -> tuple[list[Move], int]:
    """Walk history and derive every knob move. Returns (moves, commits_seen)."""
    # --first-parent IS THE LINEAGE, and it is not a performance flag.
    # `git log --no-merges` alone lists commits from BOTH sides of every merge
    # and interleaves them, while find_oscillations() reads adjacent entries as
    # successive states of one setting. Two branches independently moving a
    # shared base of 30 to 60 and to 10 then render as a swing that neither
    # branch performed. First-parent asks the question this detector is
    # actually for - what did the INTEGRATED branch's settings do over time -
    # and it is exact for this repository, whose merges are squashes.
    #
    # --diff-merges=first-parent IS WHY --no-merges IS ABSENT. Pairing
    # --first-parent with --no-merges looked right and dropped every change
    # DELIVERED BY a merge commit, not merely those introduced by conflict
    # resolution: on a repository that merges pull requests rather than
    # squashing them, two PRs taking a setting 30 -> 60 -> 30 produced no moves
    # at all - a silent, total blindness reading as `none`. Keeping merges and
    # diffing each against its first parent asks the one coherent question,
    # "what did the integrated branch's settings do over time", and answers it
    # for squash and merge histories alike.
    #
    # THE EXPLICIT --diff-merges IS FOR OLD GIT, and its mutation deliberately
    # survives on this host. git implies --diff-merges=first-parent from
    # --first-parent only since 2.36; on 2.31-2.35 the flag is the difference
    # between reading merge diffs and reading nothing. Measured here on 2.43:
    # dropping it changes no output and kills no test, so it cannot be pinned
    # behaviourally from this box. tests/test_oscillation_control.py asserts its
    # PRESENCE instead and says outright that an argv assertion is a guard on
    # intent, not on behaviour.
    proc = subprocess.run(
        ["git", "log", "--reverse", "--unified=0", "--first-parent",
         "--diff-merges=first-parent", "--format=%x00%H%x00%s", "-p", rev_range],
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
        if raw.startswith("+++ "):
            # EVERY `+++` line ends the previous file, including one whose path
            # git has QUOTED (`+++ "b/odd\tname"`, which is also the default for
            # non-ASCII). Matching only `+++ b/` left `path` pointing at the
            # PREVIOUS file, so the quoted file's hunks were attributed to its
            # neighbour - a reversal reported against a file that did not
            # reverse. Unrecognised now means "no path", which downgrades a
            # false attribution to a miss; flush() already declines to emit
            # moves without one.
            flush()
            path = raw[6:] if raw.startswith("+++ b/") else ""
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
        for chain in _chains(seq):
            findings.extend(_reversals_in(chain, window))
    return findings


def _chains(seq: list[Move]) -> list[list[Move]]:
    """Split one (path, key) series into continuous sub-series, one per site.

    Continuity was first checked between ADJACENT moves only, which silenced a
    real reversal the moment anything landed between its two halves: first
    60 -> 30, second 10 -> 20, first 30 -> 60 is a genuine swing at the first
    site, and neither adjacent pair is continuous, so nothing was reported. The
    moves have to be threaded into per-site chains BEFORE the direction test,
    not filtered pairwise after it.

    `reversed()` so a value lands on the most recently extended chain; two
    sites that genuinely pass through the same value can still be threaded
    together, and that ambiguity is a known limit rather than a claim.
    """
    chains: list[list[Move]] = []
    for m in seq:
        for chain in reversed(chains):
            if chain[-1].after == m.before:
                chain.append(m)
                break
        else:
            chains.append([m])
    return chains


def _reversals_in(chain: list[Move], window: int) -> list[Finding]:
    findings: list[Finding] = []
    for a, b in zip(chain, chain[1:]):
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
            # CONTINUITY (see _chains) is what makes `(path, key)` behave like
            # an identity: one file can hold two call sites spelling the same
            # setting, and threading each into its own chain stops a move at
            # `first(timeout=60 -> 30)` pairing with an unrelated later move at
            # `second(timeout=10 -> 20)`.
            #
            # KNOWN MISS, deliberately left: two sites changed inside ONE hunk
            # collapse in flush()'s dict, so the second hides the first. Silent
            # rather than wrong - see ADR 0009's stated blind spots.
            #
            if b.ordinal - a.ordinal <= window:
                findings.append(Finding(a.path, a.key, [a, b]))
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
    def unknown(reason: str, explain: str, commits: int = 0) -> int:
        """Every way this run can fail to LOOK, reported identically.

        FOUR CAUSES, ONE VERDICT, ONE EXIT CODE, and a REASON field to tell them
        apart - the #953 convention: a different CONCLUSION earns a new verdict,
        the same conclusion reached for a different cause earns a reason. They
        were folded together at first, so a range git REFUSED ("HEAD~200" on a
        90-commit repo) printed the same line as a range that resolved and held
        no knob edits. Both are "could not look", and a reader chasing the
        first goes looking for knobs that were never the problem.
        """
        print(f"check-oscillation: {explain} This is UNKNOWN, not clean.", file=sys.stderr)
        print(f"OSCILLATION_SOURCE: {args.rev_range}")
        print(f"OSCILLATION_COMMITS: {commits}")
        print("OSCILLATION_EXAMINED: 0")
        print(f"OSCILLATION_REASON: {reason}")
        print("OSCILLATION: unknown")
        return EXIT_UNKNOWN

    if not root.is_dir() or probe.returncode != 0:
        return unknown(
            "not-a-git-repository",
            f"{root} is not a git repository, so no history could be read.",
        )

    # Does the RANGE resolve at all? `HEAD~200..HEAD` on a younger repository is
    # refused by git, and that is a different fact from a range that resolves to
    # nothing - which is different again from a real history holding no knob
    # edits. Asked separately so each can say which it is.
    resolved = subprocess.run(["git", "rev-list", "--count", args.rev_range],
                              cwd=root, capture_output=True, text=True)
    if resolved.returncode != 0:
        return unknown(
            "range-unresolvable",
            f"git could not resolve the range {args.rev_range} in {root} "
            f"({resolved.stderr.strip().splitlines()[-1] if resolved.stderr.strip() else 'no detail'}); "
            f"a range naming a commit this history does not have examines nothing.",
        )

    moves, commits = collect_moves(root, args.rev_range)

    # SCANNED NOTHING IS NOT CLEAN (#952). A range that resolves to no commits,
    # or a history with no knob edits in it, has not established that nothing
    # oscillated - it has established that this run could not look.
    if commits == 0:
        return unknown(
            "range-empty",
            f"the range {args.rev_range} resolved but contains no commits.",
        )
    if not moves:
        return unknown(
            "no-knob-changes",
            f"examined {commits} commit(s) in {args.rev_range} and found NO knob "
            f"changes at all, so nothing was compared.",
            commits=commits,
        )

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
    print("OSCILLATION_REASON: -")
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
