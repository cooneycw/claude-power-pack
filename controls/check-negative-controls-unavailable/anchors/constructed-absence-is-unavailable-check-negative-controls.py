#!/usr/bin/env python3
# CONSTRUCTED BLIND ARTIFACT for controls/check-negative-controls-unavailable.
# DO NOT EDIT, DO NOT LINT, DO NOT "FIX". Its sha256 is pinned by that control's
# control.json and this file is meant to stay wrong.
#
# WHAT IT RECONSTRUCTS: issue #1117 implemented naively - the version that adds
# an UNAVAILABLE verdict and stops there. Two decisions differ from the shipped
# harness, both marked inline as MUTATION 1 and MUTATION 2, and NEITHER alone is
# enough to produce the blindness:
#
#   1. a non-zero exit with no recognised message is attributed to a missing
#      tool whenever the manifest declares an unavailability signal at all;
#   2. the cross-case contradiction check does not exist.
#
# That pairing is the point. Mutation 1 is the fail-open someone writes on
# purpose, reasoning that the gate obviously has an optional tool so the exact
# wording should not matter. Mutation 2 is what a first cut simply would not
# have thought of. With the contradiction check present, Mutation 1 is caught
# anyway - MEASURED while building this anchor, which is why the first version
# of this file failed to be blind and was replaced.
#
# So this artifact MISSES a gate that goes silent, which is the blindness #946
# removed and #1117 could have reintroduced, and it agrees with the shipped
# harness on every input where a tool really is absent. A copy that always
# exited 0 would satisfy the framework's two checks and demonstrate nothing;
# this one demonstrates the specific regression the change is one edit away
# from.
"""Run every gate's registered NEGATIVE CONTROL, and prove the control can fail (issue #924).

Seven of CPP's open issues are one defect in different gates: an instrument that
returns a confident verdict it is not entitled to. A green from a blind gate and
a green from a working gate are the same bytes, so the blindness is found by the
next person to rely on the gate rather than by the gate's author.

The practice that catches this already exists - a hand-run mutation at review
time - and it worked on every merge of 2026-09-13. What it leaves behind is
nothing: no registered control, no CI step, nothing that fails the build when a
control stops discriminating. In the reviewer's own words, "if I stop doing it,
nothing notices".

THE ONE IDEA HERE: the proof that a control CAN FAIL is a by-product of RUNNING
the control, never a separate ritual someone remembers. A control with no anchor
is UNPROVEN, `--strict` refuses it, and forgetting therefore produces a red
rather than a silence.

---------------------------------------------------------------------------
What a control asserts - three checks, and why each exists
---------------------------------------------------------------------------
DISCRIMINATION   gate(known-bad) == BAD *and* gate(known-good) == GOOD.
                 Both directions. A gate wedged at "fail" passes the known-bad
                 half on its own, so the good case is what separates a working
                 gate from a stuck one.

                 A verdict is read from the gate's OUTPUT as well as its exit
                 code - see the next section, which is the whole of issue #946.

ANCHOR           the same control, run against a VENDORED BLIND ARTIFACT, must
                 FAIL - the artifact must MISS the known-bad input. This is
                 acceptance step 4 ("show the control still failing if the fix
                 is reverted"), executed on every run instead of once by hand.
                 An anchor that catches the bad input proves the control is not
                 load-bearing: INERT.

ANCHOR SANITY    the anchor must agree with the current gate on the known-GOOD
                 input. If it disagrees there too, it differs for reasons beyond
                 the blindness under test and the demonstration is not isolated.

---------------------------------------------------------------------------
A CRASH IS NOT A DETECTION - why `detect_signal` is required (issue #946)
---------------------------------------------------------------------------
The first cut decided a case from the exit code alone: `good_exit` meant GOOD
and anything else meant BAD. A gate that FELL OVER on the known-bad input
therefore scored exactly like one that REPORTED it, because an uncaught Python
exception also exits 1. `check-test-binary-guards.py` - this framework's first
consumer - exits 1 when it finds something and 1 when it raises, so for the one
control that existed the two were not separable at all, and no reordering of
this file made them so.

What that produced is this issue's own defect class occurring inside the tool
built for it: `PASS`, exit 0, and the summary "1 control(s) discriminate" for a
gate that discriminated nothing and died. The CI step was green while it
happened.

So the manifest DECLARES the signal: `detect_signal`, a regex the gate's own
output (stdout and stderr together) must carry when it genuinely reports a
finding. A BAD verdict now needs the gate to have SAID something, not merely to
have exited non-zero. Three observations replace two:

    GOOD         exit == good_exit                    - reported nothing
    BAD          exit != good_exit AND signal present - reported a finding
    UNAVAILABLE  exit != good_exit AND the DECLARED   - could not look: its own
                 unavailability signal present          tool is not installed
    UNSIGNALLED  exit != good_exit AND neither        - exited like a finding
                 present                                and said nothing that
                                                        identifies one

A declared signal is not automatically a usable one, and two ways of getting it
wrong put the old blindness straight back. A pattern that matches EMPTY output
(`.*`, a trailing `|`, a bare `^`) makes every non-zero exit a detection again;
one that matches the gate's CLEAN-run message (`^binary-guards` against a gate
that prints `binary-guards: ok - ...`) identifies a clean run as readily as a
finding. Both are refused - the first structurally, the second against the
known-GOOD run's actual output, which this harness already has in hand. Anchor
the pattern on something only a finding prints; the count in
`^binary-guards: [0-9]+ unguarded test` is there for exactly that reason.

The field is REQUIRED, and that is the load-bearing half. An OPTIONAL signal
would leave every control that omits it scored exactly as it was before this
fix, which is the fail-open being closed here - the same reason a control with
no anchor is UNPROVEN rather than quietly PASS. What would move this back is a
consumer whose detection has no stable textual marker at all; the answer there
is to give that gate a marker, not to make the field optional again.

Note the narrowing this accepts deliberately: an anchor that legitimately
CAUGHT the known-bad input while printing a message the CURRENT signal does not
match is reported UNRESOLVED ("cannot be confirmed to have missed it") rather
than INERT. That is still a red and it is a narrower claim than the old one,
which is the right direction - but it IS a change of diagnosis, and a reader
chasing an UNRESOLVED anchor should check the historical artifact's wording
before assuming it crashed.

---------------------------------------------------------------------------
Why the anchor is VENDORED and not fetched with `git show`
---------------------------------------------------------------------------
`git` IS NOT IN THE CI IMAGE. `scripts/check-test-binary-guards.py` carries the
machine-checked list (`CI_IMAGE_BINARIES`, pinned to `.woodpecker.yml`) and git
is not on it; that file's own docstring notes the rule "has now been forgotten
three times (#451, #489, #577)" and that it is structurally invisible locally,
because the dev box HAS git and `make verify` can never reproduce the failure.

A `git show <sha>^:<gate>` anchor would therefore have worked on the machine it
was written on and been INERT in the place it is meant to gate - which is this
issue's own defect class, inside the tool built for that defect class. So the
blind artifact is checked in, and git is used only to VERIFY its provenance,
where git happens to exist.

---------------------------------------------------------------------------
Seven verdicts, because collapsing any of them loses a distinction that has
already cost someone work
---------------------------------------------------------------------------
PASS        discrimination holds and the anchor demonstrates the blindness.
BLIND       the gate did not discriminate. A real alarm about the GATE.
INERT       the anchor did not miss the known-bad input, so the control is not
            load-bearing - it would not notice the gate regressing.
UNRESOLVED  a path named by the registration is missing or unreadable, the
            manifest is incomplete, or an anchor cannot be confirmed to have
            missed the known-bad input. NOT a failure of the gate: it is the
            control pointed at something that is not here or not usable, which
            presents identically to BLIND and needs the opposite response.
UNPROVEN    registered, discriminating, but carrying NO anchor - so nothing has
            demonstrated it can fail. Not PASS. `--strict` exits non-zero.
UNSIGNALLED the gate exited like a finding and said nothing that identifies
            one (issue #924's Codex review, tracked and closed as #946). Also
            an alarm about the GATE, but a DIFFERENT one from BLIND: "it missed
            the input" sends a reader into the detection logic, and this gate is
            throwing. Keeping them apart is the same rule as UNRESOLVED-vs-BLIND.
UNAVAILABLE the gate reported that ITS OWN TOOL is not installed, so it could
            not look here (issue #1117). An ENVIRONMENT fact, and the only
            verdict in this list that is not a statement about the control or
            the gate at all - which is exactly why it may not share a word with
            any of them. See the next section.

PROVENANCE is a SEPARATE AXIS, never folded into the verdict and never a verdict
of its own: `ok` when the vendored anchor was byte-compared against its recorded sha,
`unverified` when git was unavailable to check. `unverified` must never print as
`ok` - the same rule as "unknown is not 0".

---------------------------------------------------------------------------
"ITS TOOL IS MISSING" IS NOT "IT STOPPED DISCRIMINATING" (issue #1117)
---------------------------------------------------------------------------
Three registered gates drive an external binary: `secret-scan-check.sh` needs
gitleaks, `shellcheck-gate.sh` needs shellcheck, `flow-driver-retirement-check.sh`
needs jq. Each correctly REFUSES to report a clean verdict when its tool is
absent - the refusal is the honest behaviour and none of it is changing here.
What was wrong is how this harness then filed that refusal.

MEASURED on 2026-09-20 by removing one binary at a time from a PATH otherwise
identical to the real one (every other executable symlinked through, so the
absence is one tool rather than a bare `PATH=`):

    gitleaks absent    -> controls/secret-scan                  UNSIGNALLED
    shellcheck absent  -> controls/shellcheck-gate              UNSIGNALLED
    jq absent          -> controls/flow-driver-retirement-check BLIND
    git absent         -> no control changes verdict

Two different wrong answers, and the second is the louder one. UNSIGNALLED says
"the gate exited like a finding and said nothing that identifies one", which
sends a reader into that gate's detection logic. BLIND says "the gate did not
discriminate", the strongest alarm in this vocabulary. Both are accusations
about OUR CODE for a fact about THIS MACHINE, and the correct response - install
a tool - appears in neither.

The jq case is worth stating separately because it is the one the ticket for
this work predicted as UNSIGNALLED and it is not. That gate reports
`RETIREMENT: unknown - jq is not installed`, and its control declares
`^RETIREMENT: (blocked|unknown)\b` as `detect_signal` - deliberately, since for
that gate an `unknown` verdict IS the finding a caller must not delete on. So
the unavailability message MATCHES the detection pattern, the known-GOOD case
scores BAD, and the control lands on BLIND.

WHY UNAVAILABILITY IS CHECKED BEFORE DETECTION, which is the whole design.
An ordering rule that put `detect_signal` first reads naturally - a reported
finding is a finding - and leaves the jq case exactly as broken as it is today,
because that gate's two messages are not separable in that direction. The
specific pattern has to win over the general one, so `unavailable_signal` is
consulted first and `detect_signal` second.

That ordering is a FAIL-OPEN unless the pattern is constrained, because a loose
`unavailable_signal` would now excuse real findings. Three constraints, and each
is checked against output this harness already has in hand rather than against
the manifest author's intention:

  1. IT MAY NOT MATCH EMPTY OUTPUT. `.*`, a bare `^`, a trailing `|` - each
     turns every silent non-zero exit into "the tool must have been missing",
     which is the pre-#946 fail-open restored wearing a new field's name. This
     is the blindness `controls/check-negative-controls-unavailable` pins as a
     committed artifact.
  2. IT MAY NOT MATCH A CLEAN RUN. A pattern anchored on the gate's ok line
     would report a working gate as unexaminable. Checked against the known-GOOD
     case's REAL output.
  3. IT MAY NOT SURVIVE A RUN THAT PROVES THE TOOL WAS THERE. If a known-bad
     case reports unavailability while a known-good case through the SAME gate
     ran cleanly, the tool was present enough to run one and not the other -
     which is not what a missing binary does. That contradiction is UNRESOLVED,
     and it is what catches a pattern loose enough to swallow a genuine finding
     on a host where the tool IS installed.

THE FIELD IS OPTIONAL, and the asymmetry with `detect_signal` is deliberate
rather than an oversight. `detect_signal` had to be required because defaulting
it left every control exactly as blind as before the fix. Omitting
`unavailable_signal` has the opposite effect: nothing can be excused, every
verdict stays what it is today, and a gate with no external tool has nothing
truthful to declare. Absence fails CLOSED here, so it costs nothing to allow.

WHAT MOVES THIS BACK (the reversal trigger, ADR 0009). If a control ever needs
an `unavailable_signal` for a message its gate emits for a reason OTHER than its
own tool being absent, the declared-signal design is the wrong guard for that
case and this comes out rather than widening to accommodate it. The check to run
is reading the three manifests' patterns against their gates' message sets, not
waiting for a report.

---------------------------------------------------------------------------
Never read the installed copy
---------------------------------------------------------------------------
This runs against the CHECKOUT, never `~/.claude/scripts`. Measured 2026-09-13:
of 54 installed helpers 51 were byte-identical to main, 3 were not, and 0 were
dead mounts - so `st_nlink == 0` corpse-checking reports a clean bill while
stale helpers serve. `check-test-binary-guards.py` was among the three, and it
was byte-identical to `c6df826` - the very pre-fix artifact this file uses as an
anchor. A control pointed at the installed copy would have produced a REAL RED
that looked like a successful demonstration: right about the file it read, and
silent about main.

Usage:
    check-negative-controls.py [--root DIR] [--strict] [--allow-unavailable]
                               [--verify-provenance] [--quiet]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

#: NEGATIVE-CONTROL: controls/check-negative-controls
#:     Registered per issue #964. ADR 0008 hands the living list of instruments
#:     to this register, so the tool that MAINTAINS the register being absent
#:     from it made the register unreadable as a coverage map: "which
#:     instruments have controls?" returned an answer that silently excluded the
#:     thing computing it, and the exclusion looked exactly like completeness.
#:
#:     WHAT THIS ROW DOES AND DOES NOT ESTABLISH. It is a weaker member of this
#:     register than the others and the row says so in `limits` too. The
#:     discrimination is carried by the ANCHOR - a frozen, sha256-pinned copy of
#:     the pre-#946 harness, which is a different program - so a regression in
#:     THIS harness's detection logic would make it agree with the anchor and
#:     fail the control. That part is not circular.
#:
#:     It is structurally blind to a breakage in this harness's own VERDICT
#:     ASSIGNMENT: a harness mutated to emit PASS unconditionally reports PASS
#:     about itself, and the coverage claim becomes self-certifying - a stronger
#:     false statement than the accounting gap it replaced. What detects that is
#:     `tests/test_negative_controls.py`, invoked by PYTEST in the `validate` CI
#:     step: a different process, a different entry point, asserting on exit
#:     codes and stdout rather than on this harness's judgement of itself. A
#:     second opinion from the same program is not one.
#:
#:     If that pytest control ever stops failing under the verdict-assignment
#:     mutation, the external control has become decoration and this
#:     self-registration is all that remains, which is the state this design
#:     exists to prevent.
#: The registration directive, read out of the GATE file itself so the control
#: cannot outlive the instrument it covers. Deleting the gate deletes the
#: registration with it; a directive naming a directory that is not there is an
#: UNRESOLVED verdict rather than a skip, because a registration that silently
#: resolves to nothing is the rot this issue exists to stop.
REGISTRATION_RE = re.compile(r"^#:?\s*NEGATIVE-CONTROL:\s*(?P<path>\S+)\s*$", re.MULTILINE)

GOOD = "GOOD"
BAD = "BAD"

#: A third OBSERVATION, not a fourth expectation: `cases[].expect` still takes
#: only GOOD or BAD. A manifest cannot ask for UNSIGNALLED, because "I expect
#: this gate to fall over" is not a property anyone should be able to register.
UNSIGNALLED = "UNSIGNALLED"

#: A FOURTH observation and, unlike UNSIGNALLED, also a verdict (issue #1117).
#: `cases[].expect` still takes only GOOD or BAD for the same reason: "I expect
#: this machine not to have gitleaks" is not a property of the control, and a
#: manifest that could register it would be asserting the environment rather
#: than the gate.
UNAVAILABLE = "UNAVAILABLE"

PASS = "PASS"
BLIND = "BLIND"
INERT = "INERT"
UNRESOLVED = "UNRESOLVED"
UNPROVEN = "UNPROVEN"


@dataclass
class Result:
    gate: str
    control_dir: str
    verdict: str
    provenance: str = "unverified"
    #: Whether this control's files are IN THE REPOSITORY (issue #978).
    #: `tracked` / `UNTRACKED` / `unverified` when git is absent - the same
    #: three-state shape as `provenance`, and a separate axis from `verdict` for
    #: the same reason: a control exercised from the working tree behaves
    #: correctly and reports PASS, while the same commit in a CLEAN CLONE has no
    #: cases at all. Observed twice on 2026-09-15 (#964, #953), both times from
    #: a `.gitignore` blanket that a one-level negation did not reach.
    #: `unverified` is NOT a pass and NOT a failure: git is absent from the CI
    #: image by design, so this axis is checked on a dev box and in the pre-push
    #: hook. `UNTRACKED` IS a failure - it is a green that does not survive a
    #: clone, which is the defect itself.
    tracking: str = "unverified"
    details: list[str] = field(default_factory=list)


def _source_stamp(root: Path) -> str:
    """Name the copy under test: `worktree-at-<sha>`, never a bare "the helper".

    Any measurement of helper behaviour has to state WHICH COPY it ran, because
    an installed helper and a checkout can be different programs. git is absent
    in CI, so the sha comes from git when git exists, else from the CI
    environment, else it is honestly `unknown` - never guessed.
    """
    if shutil.which("git"):
        try:
            out = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if out.returncode == 0 and out.stdout.strip():
                return f"worktree-at-{out.stdout.strip()}"
        except (OSError, subprocess.SubprocessError):  # pragma: no cover - defensive
            pass
    for var in ("CI_COMMIT_SHA", "GITHUB_SHA"):
        sha = os.environ.get(var, "").strip()
        if sha:
            return f"worktree-at-{sha[:7]}"
    return "worktree-at-unknown"


#: The universe a control count is a fraction OF (issue #979).
#: ADR 0008 enumerates the instruments whose verdicts are consumed without
#: re-derivation - the ones its bound says need a committed control. That table
#: is the honest denominator, and it is DERIVED here rather than hardcoded: a
#: literal would be wrong within a day (it moved 61 -> 62 -> 63 in one morning)
#: and would be "fixed" by whoever adds the next gate, who is the person least
#: motivated to check it. Unreadable or unparseable reports UNKNOWN, never a
#: bare numerator: "2 of 61" and "61 of 61" printing the identical string is the
#: defect, and so is a denominator invented to fill the slot.
ADR_0008 = Path("docs/decisions/0008-instrument-negative-control-bound.md")
ADR_ROW_RE = re.compile(r"^\|\s*\d+\s*\|", re.MULTILINE)

#: A fenced example and a commented-out row are not the census speaking, and
#: counting them INFLATES this denominator (issue #1060). The raw regex counted
#: both: add one illustrative `| 1 | ... |` to the ADR's prose and the coverage
#: line silently reads `14 of 74` over a 73-row census. That is the same class as
#: #979 - a denominator that does not describe what it claims to - arriving by a
#: different route, and it also split this parser from the one
#: `instrument-census-check.py` uses to check the table's membership, so the two
#: readers of one table would have been counting different documents.
#:
#: Found by the counter-model review (codex, gpt-6-astra) on the #1060 branch,
#: second pass. Matched by character and length per CommonMark; comments are
#: removed AFTER fences, so a fenced `<!--` cannot pair with a real one further
#: down and delete the rows between them.
ADR_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*(.*)$")
ADR_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _census_text(text: str) -> str:
    """The ADR's own table rows: fenced examples, then HTML comments, removed."""
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        marker = ADR_FENCE_RE.match(line)
        if fence is None:
            if marker:
                fence = marker.group(1)
            else:
                out.append(line)
            continue
        if (
            marker
            and marker.group(1)[0] == fence[0]
            and len(marker.group(1)) >= len(fence)
            and not marker.group(2).strip()
        ):
            fence = None
    return ADR_COMMENT_RE.sub("", "\n".join(out))


def instrument_universe(root: Path) -> tuple[int | None, str]:
    """(count, provenance-phrase) for ADR 0008's enumerated instruments."""
    adr = root / ADR_0008
    try:
        text = adr.read_text(encoding="utf-8")
    except OSError:
        return None, f"{ADR_0008} is unreadable"
    rows = len(ADR_ROW_RE.findall(_census_text(text)))
    if rows == 0:
        return None, f"{ADR_0008} parsed to 0 enumerated rows"
    return rows, f"{ADR_0008}"


def discover(root: Path) -> list[tuple[Path, str]]:
    """Every REGISTRATION in `scripts/`, not every gate (issue #986).

    This used to call `REGISTRATION_RE.search`, which returns the FIRST match
    and stops. The pattern carries `re.MULTILINE` and so anticipates several
    registrations in one file, but the call could only ever yield one, and the
    docstring said "every gate carrying a registration directive" - accurate
    about gates and silent about the thing a reader wants, which is controls.

    A gate declaring three controls contributed one pair; the other two were
    never executed, never scored, and never reported as unregistered. The
    register's whole purpose is answering "is this instrument controlled", so a
    gate with one weak control and two strong ones scored as its weak one, and
    an author adding a second control to close a known blind spot got no credit
    and no warning.

    LATENT when this was fixed - three gates registered, each declaring exactly
    one, so `.search` and `.finditer` agreed. That is the reason to fix it now
    rather than after: it must land WITH or BEFORE the denominator (#979),
    because a count over an incomplete population is an undercount wearing an
    authoritative number.
    """
    found: list[tuple[Path, str]] = []
    scripts_dir = root / "scripts"
    if not scripts_dir.is_dir():
        return found
    for path in sorted(scripts_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in REGISTRATION_RE.finditer(text):
            found.append((path, match.group("path")))
    return found


#: Stands in for an exit code when the invocation could not be executed AT ALL -
#: a missing interpreter, a permissions error, a timeout. It is not a verdict.
#: Collapsing it into an exit code (it was -1, and every code but `good_exit`
#: means BAD) made an unrunnable control score as DETECTION on the known-bad case
#: and raise a GATE ALARM on the known-good one - an environment failure reported
#: as "the gate stopped discriminating", which is exactly the UNRESOLVED-versus-
#: BLIND collapse this file's verdict vocabulary exists to prevent.
UNRUNNABLE = None


def _run(argv: list[str], cwd: Path) -> tuple[int | None, str, str]:
    """`(exit code, output, diagnostic)`, or `(UNRUNNABLE, "", why)` when it never ran.

    `output` is stdout and stderr TOGETHER, newline-joined, because that is what
    `detect_signal` is matched against: a gate is free to report its findings on
    either stream, and which one it picked is not a property a control should
    have to know. The joining newline matters - a `^`-anchored pattern would
    otherwise miss the first stderr line whenever stdout ended without one.

    The diagnostic (the LAST stderr line) is kept as well, and printed on every
    case line: it is what puts `FileNotFoundError: ...` in front of a reader
    rather than leaving them with a bare exit code.
    """
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)
    except subprocess.TimeoutExpired:
        return UNRUNNABLE, "", f"timed out after 120s: {' '.join(argv)}"
    except (OSError, subprocess.SubprocessError) as exc:
        return UNRUNNABLE, "", f"{type(exc).__name__}: {exc}"
    output = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    stderr = (proc.stderr or "").strip()
    return proc.returncode, output, stderr.splitlines()[-1] if stderr else ""


def _observe(
    exit_code: int,
    good_exit: int,
    output: str,
    signal: re.Pattern[str],
    unavailable: re.Pattern[str] | None = None,
) -> str:
    """What the run SAYS happened - four answers, not two (issues #946, #1117).

    The exit code alone cannot separate "I found the planted problem" from "I
    fell over", because a crash exits non-zero too. So a non-zero exit is only
    read as detection when the gate also emitted its declared signal; without it
    the honest answer is UNSIGNALLED, which is neither verdict.

    `unavailable` is consulted BEFORE `signal`, and the docstring section
    "ITS TOOL IS MISSING IS NOT IT STOPPED DISCRIMINATING" is where that order
    is argued: the two messages are not separable in the other direction for
    `flow-driver-retirement-check.sh`, whose unavailability line is a legitimate
    member of its own detection pattern. The constraints that keep this from
    being a fail-open are enforced by the caller, against real output.
    """
    if exit_code == good_exit:
        return GOOD
    if unavailable is not None and unavailable.search(output):
        return UNAVAILABLE
    # MUTATION 1 of 2. A control that DECLARES an unavailability signal is read
    # as "this gate drives a tool that can go missing", so a non-zero exit
    # carrying no recognised message is charitably attributed to that tool
    # instead of being called UNSIGNALLED. It reads as tolerance for a gate whose
    # wording drifted; it is the pre-#946 fail-open arriving by a new route, and
    # it excuses a gate that CRASHES.
    if unavailable is not None and not signal.search(output):
        return UNAVAILABLE
    return BAD if signal.search(output) else UNSIGNALLED


def _invoke(spec: list[str], gate: Path, case: Path, root: Path) -> tuple[int | None, str, str]:
    argv = [part.replace("{gate}", str(gate)).replace("{case}", str(case)) for part in spec]
    return _run(argv, root)


def _tracking(control_dir: Path, root: Path) -> tuple[str, list[str]]:
    """Are this control's files IN THE REPOSITORY? (issue #978)

    A control is exercised from the WORKING TREE. So a control whose case files
    are untracked behaves correctly, discriminates, and reports PASS - while the
    same commit in a clean clone has no cases at all. A green from a control that
    does not exist downstream is indistinguishable from a green from one that
    does, and that is the whole defect.

    Observed twice on 2026-09-15 from one root cause: `.gitignore` carries a
    blanket `*.json` negated only by `!controls/*/control.json`, one level deep,
    so nested manifests under `controls/*/cases/**` were silently skipped by
    `git add -A`. #964 shipped that way; #953's selftest reported 14/14 against
    files that were not in the repository.

    Returns `unverified` when git is absent - which is the CI image, by design
    (see the vendored-anchor note above). `unverified` is neither a pass nor a
    failure; `UNTRACKED` is a failure, because it names a green that will not
    survive a clone.
    """
    if not shutil.which("git"):
        return "unverified", []
    if not control_dir.is_dir():
        return "unverified", []
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", str(control_dir)],
            capture_output=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - defensive
        return "unverified", []
    if out.returncode != 0:
        return "unverified", []
    tracked = {
        (root / p).resolve()
        for p in out.stdout.decode("utf-8", "replace").split("\0")
        if p
    }
    on_disk = {p.resolve() for p in control_dir.rglob("*") if p.is_file()}
    missing = sorted(str(p.relative_to(root)) for p in (on_disk - tracked))
    if missing:
        shown = missing[:5]
        detail = [
            f"{len(missing)} file(s) under {control_dir.relative_to(root)} are NOT tracked, "
            "so this control does not exist in a clean clone: " + ", ".join(shown)
            + ("..." if len(missing) > len(shown) else "")
        ]
        return "UNTRACKED", detail
    return "tracked", []


def evaluate(directive_file: Path, control_rel: str, root: Path, verify_provenance: bool) -> Result:
    control_dir = (root / control_rel).resolve()
    res = Result(gate=str(directive_file.relative_to(root)), control_dir=control_rel, verdict=UNRESOLVED)

    # Computed FIRST so it survives every early return below. evaluate() exits at
    # ~20 points, and a tracking axis recorded late would be absent from exactly
    # the results that failed for another reason - which are the ones most likely
    # to be under-built.
    res.tracking, tracking_details = _tracking(control_dir, root)
    res.details.extend(tracking_details)

    manifest = control_dir / "control.json"
    if not manifest.is_file():
        res.details.append(f"no control.json at {control_rel}")
        return res
    try:
        spec = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        res.details.append(f"control.json unreadable: {exc}")
        return res

    invocation: list[str] = spec.get("invocation", [])
    good_exit: int = int(spec.get("good_exit", 0))
    cases: list[dict[str, str]] = spec.get("cases", [])
    anchors: list[dict[str, str]] = spec.get("anchors", [])

    # The manifest's `gate` is authoritative for WHAT IS INVOKED; the directive's
    # location is only how the control was DISCOVERED. Reading the discovered file
    # instead was a real defect in the first cut of this script, and this file's
    # own negative control is what caught it: with the declared gate absent, the
    # harness ran the file carrying the directive, which exited 0, and reported
    # BLIND. That is the exact collapse this verdict vocabulary exists to prevent -
    # "the control points at code that is not here" reported as "the gate stopped
    # discriminating". They present identically and need opposite responses.
    declared = spec.get("gate", "")
    if not declared:
        res.details.append("control.json names no gate")
        return res
    gate = (root / declared).resolve()
    if not gate.is_file():
        res.details.append(f"declared gate is absent from this checkout: {declared}")
        return res
    res.gate = declared
    # A registration must live NEXT TO the gate it covers. A directive in one file
    # declaring a control for another is the separate-document rot this design is
    # meant to avoid, so it is refused rather than followed.
    if gate != directive_file.resolve():
        res.details.append(
            f"registration lives in {directive_file.name} but declares gate {declared}"
        )
        return res
    if not invocation or not cases:
        res.details.append("control.json names no invocation or no cases")
        return res

    # A REQUIRED field, refused on absence rather than defaulted (issue #946).
    # Defaulting it - to a pattern that matches everything, or to "no signal
    # declared means score on the exit code" - would leave every control that
    # omits it exactly as blind to a crashing gate as before the fix, and the
    # omission would be invisible. An UNUSABLE pattern is refused for the
    # mirror-image reason: an uncompilable regex silently treated as "never
    # matches" turns every genuine detection into an UNSIGNALLED red with an
    # unrelated diagnosis, and an EMPTY pattern matches every output, which
    # restores exit-code-only scoring while looking like a fix.
    raw_signal = spec.get("detect_signal", "")
    if not isinstance(raw_signal, str) or not raw_signal.strip():
        res.details.append(
            "control.json declares no detect_signal, so a non-zero exit from this gate "
            "cannot be told from a crash (issue #946)"
        )
        return res
    try:
        signal = re.compile(raw_signal, re.MULTILINE)
    except re.error as exc:
        res.details.append(f"control.json detect_signal is not a usable regex: {exc}")
        return res
    # Refusing the empty STRING is not enough: `.*`, a trailing `|`, `(?:)` and
    # `^` all compile fine and match ANY output, silence included. A signal that
    # matches nothing-at-all cannot separate a finding from a crash by
    # construction, so every non-zero exit becomes BAD again - the pre-#946
    # scoring restored wholesale, wearing this field's own name. Measured: `.*`
    # and `toy-gate: [0-9]+ finding|` each produced PASS for a gate that crashed
    # on the known-bad input (found by the Codex review of this change).
    if signal.search(""):
        res.details.append(
            f"control.json detect_signal /{raw_signal}/ matches empty output, so it cannot "
            "separate a finding from a crash (issue #946)"
        )
        return res

    # OPTIONAL, unlike detect_signal, and the asymmetry is argued in the
    # docstring: omitting this excuses nothing, so absence fails CLOSED. What is
    # NOT optional is usability once declared. An uncompilable pattern would
    # silently never match and leave the conflation in place under a field that
    # claims to have fixed it; a pattern matching EMPTY output would excuse every
    # silent non-zero exit, which is the pre-#946 fail-open restored by a new
    # route. Both are refused here, structurally, before any case runs. The two
    # refusals that need real output - a pattern matching a clean run, and one
    # surviving a run that proves the tool was there - are enforced below, where
    # that output exists.
    raw_unavailable = spec.get("unavailable_signal", "")
    unavailable: re.Pattern[str] | None = None
    if raw_unavailable:
        if not isinstance(raw_unavailable, str) or not raw_unavailable.strip():
            res.details.append("control.json unavailable_signal is not a usable pattern")
            return res
        try:
            unavailable = re.compile(raw_unavailable, re.MULTILINE)
        except re.error as exc:
            res.details.append(f"control.json unavailable_signal is not a usable regex: {exc}")
            return res
        if unavailable.search(""):
            res.details.append(
                f"control.json unavailable_signal /{raw_unavailable}/ matches empty output, so "
                "every silent non-zero exit would be excused as a missing tool (issue #1117)"
            )
            return res

    # A one-sided control tests nothing, so it may not reach PASS. This was only
    # DOCUMENTED before, and the code required a non-empty list: a GOOD-only
    # control passed against a gate that was genuinely blind, and a BAD-only one
    # passed against a gate wedged at "fail". Both printed the summary line "N
    # control(s) discriminate", which is a claim neither population supported.
    expects = {case.get("expect") for case in cases}
    unknown = expects - {GOOD, BAD}
    if unknown:
        res.details.append(f"control.json has case(s) with an unknown expect value: {sorted(map(str, unknown))}")
        return res
    if BAD not in expects:
        res.details.append("control.json registers no BAD case, so nothing exercises the blindness")
        return res
    if GOOD not in expects:
        res.details.append("control.json registers no GOOD case, so a gate wedged at 'fail' would pass")
        return res

    # -- DISCRIMINATION ---------------------------------------------------- #
    bad_cases: list[Path] = []
    #: Names of the cases whose gate reported its own tool absent, and of the
    #: cases that ran CLEANLY. Collected across the whole loop rather than acted
    #: on in it, because the contradiction that catches a loose
    #: `unavailable_signal` is a relationship BETWEEN cases and cannot be seen
    #: from inside one (issue #1117).
    unavailable_cases: list[str] = []
    clean_cases: list[str] = []
    unavailable_reason = ""
    for case in cases:
        case_path = control_dir / case["input"]
        if not case_path.is_dir():
            res.details.append(f"case input missing: {case['input']}")
            return res
        expected = case["expect"]
        code, output, diag = _invoke(invocation, gate, case_path, root)
        if code is UNRUNNABLE:
            res.details.append(f"case {case['name']}: the gate could not be executed - {diag}")
            return res
        observed = _observe(code, good_exit, output, signal, unavailable)
        res.details.append(
            f"case {case['name']}: expected={expected} observed={observed} (exit {code})"
            + (f" [stderr: {diag}]" if diag else "")
        )
        # Checked BEFORE the expected/observed comparison, on EVERY case rather
        # than only the known-bad one. A gate that falls over on the known-GOOD
        # input would otherwise be reported as having "flagged a known-good
        # input" - a false-alarm diagnosis that sends a reader into detection
        # logic for a gate that is simply throwing.
        # BEFORE the UNSIGNALLED check below, because a clean run that also
        # matches the unavailability pattern is a defect in the PATTERN and must
        # not be reported as anything about the gate. Mirror of the
        # detect_signal refusal further down, and it fires on every case rather
        # than only the known-good one: a gate wedged clean would otherwise hide
        # it on the known-bad side.
        if observed == GOOD and unavailable is not None and unavailable.search(output):
            res.verdict = UNRESOLVED
            res.details.append(
                f"control.json unavailable_signal /{raw_unavailable}/ also matches this gate's "
                f"CLEAN output on case {case['name']}, so it reports a working gate as "
                f"unexaminable"
            )
            return res
        # Recorded and skipped, NOT compared against `expect`. A missing tool
        # makes the gate say nothing about this input, so scoring it against an
        # expectation is how "your machine lacks gitleaks" became BLIND.
        if observed == UNAVAILABLE:
            unavailable_cases.append(case["name"])
            if not unavailable_reason:
                # THE LINE THAT MATCHED, not the last line of stderr. `_run`
                # hands back the trailing stderr line, which for these gates is
                # the reassurance ("this is not a pass.") rather than the fact
                # ("shellcheck is not installed"). The matching line is the one
                # that identified the unavailability, so it is the one a reader
                # needs; falling back to `diag` keeps a reason present either way.
                unavailable_reason = diag
                if unavailable is not None:
                    for line in output.splitlines():
                        if unavailable.search(line):
                            unavailable_reason = line.strip()
                            break
            continue
        if observed == GOOD:
            clean_cases.append(case["name"])
        if observed is UNSIGNALLED:
            res.verdict = UNSIGNALLED
            res.details.append(
                f"the gate exited {code} without emitting its declared detection signal "
                f"/{raw_signal}/, so this run cannot be told from a crash"
            )
            return res
        # The structural check above is a floor, not the discriminator. A pattern
        # can miss the empty string and still identify nothing - `^binary-guards`
        # against a gate that prints `binary-guards: ok - ...` on a clean tree.
        # The known-GOOD run is already executed here, so the signal is checked
        # against REAL output rather than against the manifest author's
        # intention. This is the same two-sided property the control's own test
        # asserts for its regex, enforced for every control instead of one.
        # `observed == GOOD` is load-bearing, not redundant: a gate WEDGED at
        # "fail" prints its finding line on the known-good input too, so without
        # it this refusal fires on a perfectly good regex and blames the manifest
        # for a broken gate - a non-zero that cannot tell our thing from a
        # neighbour's. The distinguishing condition is a CLEAN EXIT whose output
        # still matches: the gate said "nothing here" and the pattern matched
        # anyway. A wedged gate exits non-zero and stays BLIND, where it belongs.
        if expected == GOOD and observed == GOOD and signal.search(output):
            res.verdict = UNRESOLVED
            res.details.append(
                f"control.json detect_signal /{raw_signal}/ also matches this gate's known-GOOD "
                f"output, so it identifies a clean run as readily as a finding"
            )
            return res
        if observed != expected:
            res.verdict = BLIND
            res.details.append(
                "the gate did not discriminate: it "
                + ("missed a known-bad input" if expected == BAD else "flagged a known-good input")
            )
            return res
        if expected == BAD:
            bad_cases.append(case_path)

    # -- UNAVAILABILITY, ADJUDICATED ACROSS THE CASES ---------------------- #
    # THE CONTRADICTION THAT CATCHES A LOOSE PATTERN (issue #1117). A binary that
    # is not installed is not installed for every case, so "unavailable here,
    # clean there" is not something a missing tool produces - it is what a
    # pattern loose enough to match a genuine finding produces on a host where
    # the tool IS present, which is the fail-open this field could otherwise
    # introduce. Refused as UNRESOLVED, naming both sides, rather than excused.
    #
    # This is the constraint that makes consulting `unavailable_signal` before
    # `detect_signal` safe. Without it the ordering would be a silent precedence
    # rule; with it, an author who writes a pattern broad enough to swallow
    # detections gets a red on any machine that can actually run the gate - which
    # is every CI run, where the tools are pinned into the image on purpose.
    # MUTATION 2 of 2. The cross-case contradiction check is ABSENT here -
    # 'unavailable on one case, clean on another' is accepted rather than
    # refused. Its absence is what lets Mutation 1 stand: with the check in
    # place, a silent gate whose sibling case ran cleanly is caught anyway.
    if unavailable_cases:
        res.verdict = UNAVAILABLE
        res.details.append(
            f"the gate reports its own tool is not installed, so case(s) "
            f"{', '.join(unavailable_cases)} examined nothing here. This control is UNEXAMINED, "
            f"not clean, and says nothing about the gate"
            + (f": {unavailable_reason}" if unavailable_reason else "")
        )
        return res

    # -- ANCHOR + ANCHOR SANITY -------------------------------------------- #
    if not anchors:
        res.verdict = UNPROVEN
        res.details.append("no anchor: nothing has demonstrated this control can fail")
        return res

    good_cases = [control_dir / c["input"] for c in cases if c["expect"] == GOOD]
    provenances: list[str] = []
    for anchor in anchors:
        anchor_path = control_dir / anchor["path"]
        if not anchor_path.is_file():
            res.verdict = UNRESOLVED
            res.details.append(f"anchor missing: {anchor['path']}")
            return res

        # Record provenance BEFORE the behavioural checks below, and re-aggregate
        # on every anchor. All of those checks can return early, and aggregating
        # only on the success path discarded a MISMATCH already measured on an
        # EARLIER anchor - printing the default `unverified` instead. Verdict and
        # provenance are separate axes: a failing verdict must not quietly soften
        # what provenance had already established.
        provenances.append(_provenance(anchor, anchor_path, root, verify_provenance))
        res.provenance = _aggregate_provenance(provenances)

        # The SAME misscore lives on this side of the loop (issue #946). An
        # anchor is required to MISS the known-bad input; one that CRASHES on it
        # also exits non-zero, and was therefore reported as having CAUGHT it -
        # INERT, which accuses a healthy anchor of not being blind and sends
        # someone to replace a perfectly good artifact. It is UNRESOLVED
        # instead: the required property could not be CONFIRMED, which is a
        # narrower and honest claim.
        for case_path in bad_cases:
            code, output, diag = _invoke(invocation, anchor_path, case_path, root)
            if code is UNRUNNABLE:
                res.verdict = UNRESOLVED
                res.details.append(f"anchor {anchor['sha']} could not be executed - {diag}")
                return res
            observed = _observe(code, good_exit, output, signal, unavailable)
            # Reached only when every CASE ran, so the tool was present a moment
            # ago; an anchor reporting it absent is therefore about the anchor,
            # not the environment. UNRESOLVED either way - the required property
            # was not established - but the sentence a reader gets differs.
            if observed == UNAVAILABLE:
                res.verdict = UNRESOLVED
                res.details.append(
                    f"anchor {anchor['sha']} reports its tool absent on the known-bad input while "
                    f"the current gate ran, so it cannot be confirmed to have MISSED it"
                )
                return res
            if observed is UNSIGNALLED:
                res.verdict = UNRESOLVED
                res.details.append(
                    f"anchor {anchor['sha']} exited {code} on the known-bad input without the "
                    f"declared detection signal, so it cannot be confirmed to have MISSED it "
                    f"(it may have crashed)"
                    + (f" [stderr: {diag}]" if diag else "")
                )
                return res
            if observed != GOOD:
                res.verdict = INERT
                res.details.append(
                    f"anchor {anchor['sha']} CAUGHT the known-bad input, so this control would "
                    "not notice the gate regressing to it"
                )
                return res
            res.details.append(f"anchor {anchor['sha']}: missed the known-bad input (blind, as required)")

        for case_path in good_cases:
            code, output, diag = _invoke(invocation, anchor_path, case_path, root)
            if code is UNRUNNABLE:
                res.verdict = UNRESOLVED
                res.details.append(f"anchor {anchor['sha']} could not be executed - {diag}")
                return res
            observed = _observe(code, good_exit, output, signal, unavailable)
            if observed == UNAVAILABLE:
                res.verdict = UNRESOLVED
                res.details.append(
                    f"anchor {anchor['sha']} reports its tool absent on a known-GOOD input while "
                    f"the current gate ran, so the anchor-sanity check cannot be resolved"
                )
                return res
            if observed is UNSIGNALLED:
                res.verdict = UNRESOLVED
                res.details.append(
                    f"anchor {anchor['sha']} exited {code} on a known-GOOD input without the "
                    f"declared detection signal, so the anchor-sanity check cannot be resolved "
                    f"(it may have crashed)"
                    + (f" [stderr: {diag}]" if diag else "")
                )
                return res
            if observed != GOOD:
                res.verdict = INERT
                res.details.append(
                    f"anchor {anchor['sha']} disagrees with the current gate on a known-GOOD input, "
                    "so it differs for reasons beyond the blindness under test"
                )
                return res

    res.verdict = PASS
    return res


def _aggregate_provenance(values: list[str]) -> str:
    """Conservative: a `MISMATCH` anywhere survives, and `ok` needs EVERY anchor.

    Assigning per anchor into the single result field let the LAST anchor win, so
    a `MISMATCH` on an earlier one disappeared and the reported provenance
    depended on list order rather than on evidence. Provenance may be strengthened
    only by verification, never by position - the same rule that keeps
    `unverified` from printing as `ok`.
    """
    if not values:
        return "unverified"
    if "MISMATCH" in values:
        return "MISMATCH"
    return "ok" if all(value == "ok" for value in values) else "unverified"


def _provenance(anchor: dict[str, str], anchor_path: Path, root: Path, verify: bool) -> str:
    """`ok` only after a byte comparison against the recorded sha; else `unverified`.

    Never `ok` on a digest the manifest supplies about itself alone - that would
    only prove the file has not changed since someone wrote the digest down, not
    that it is the historical artifact it claims to be.
    """
    digest = hashlib.sha256(anchor_path.read_bytes()).hexdigest()
    if digest != anchor.get("sha256", ""):
        return "MISMATCH"
    if not verify:
        return "unverified"
    if not shutil.which("git"):
        return "unverified"
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "show", f"{anchor['sha']}:{anchor['origin']}"],
            capture_output=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - defensive
        return "unverified"
    if out.returncode != 0:
        return "unverified"
    return "ok" if hashlib.sha256(out.stdout).hexdigest() == digest else "MISMATCH"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--strict", action="store_true", help="exit non-zero on anything that is not PASS")
    # THE LOCAL POSTURE, AND DELIBERATELY NOT THE CI ONE (issue #1117). `--strict`
    # keeps its meaning exactly: UNAVAILABLE fails it like everything that is not
    # PASS. CI pins gitleaks, shellcheck and jq into the image on purpose, and
    # `.woodpecker.yml` rests on this harness reddening rather than reporting a
    # shorter battery if a staging step stops delivering one - so tolerating
    # unavailability THERE would retire that guarantee silently.
    #
    # `make verify` is the caller that needs the other posture: it is a local
    # gate on a developer box that may legitimately lack any of the three, and
    # before this flag the battery could not be consumed locally at all. What it
    # tolerates it must also SAY, so the summary names every unexamined control.
    parser.add_argument(
        "--allow-unavailable",
        action="store_true",
        help="with --strict: do not fail on UNAVAILABLE (a gate whose own tool is absent); "
             "report it as unexamined instead",
    )
    parser.add_argument("--verify-provenance", action="store_true", help="byte-compare anchors against git history")
    parser.add_argument("--quiet", action="store_true", help="contract lines only")
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    stamp = _source_stamp(root)
    registrations = discover(root)

    # The universe is a property of the TREE, not of the results, so it is stated
    # on every exit including the ones that found nothing (#979). A run that
    # reports no denominator is the defect whatever its verdict.
    universe, whence = instrument_universe(root)
    universe_line = f"NEGATIVE_CONTROL_UNIVERSE: {universe if universe is not None else 'unknown'}"

    if not registrations:
        print("NEGATIVE_CONTROL_SOURCE: " + stamp)
        print("NEGATIVE_CONTROL_REGISTERED: 0")
        print(universe_line)
        print("NEGATIVE_CONTROL_UNAVAILABLE: 0")
        print("negative-controls: no gate carries a registration - nothing was checked. "
              "This is UNCHECKED, not clean.")
        return 1 if args.strict else 0

    results = [evaluate(gate, rel, root, args.verify_provenance) for gate, rel in registrations]
    # Emitted HERE rather than in the success branch, so a FAILING run states its
    # denominator too. `REGISTERED` keeps the meaning it already had - how many
    # registrations were discovered - and is not re-purposed.
    print(f"NEGATIVE_CONTROL_REGISTERED: {len(registrations)}")
    print(universe_line)
    # A COUNT ON EVERY RUN, INCLUDING ZERO (issue #1117). A line that appears
    # only when something is unexamined cannot be told from a line nobody
    # emitted, so a consumer reading it would learn "unexamined: absent" and have
    # no way to know whether that means none or means an older harness.
    unavailable_results = [r for r in results if r.verdict == UNAVAILABLE]
    print(f"NEGATIVE_CONTROL_UNAVAILABLE: {len(unavailable_results)}")

    for res in results:
        print(f"NEGATIVE_CONTROL_GATE: {res.gate}")
        print(f"NEGATIVE_CONTROL_SOURCE: {stamp}")
        for line in res.details:
            print(f"NEGATIVE_CONTROL_DETAIL: {line}")
        print(f"NEGATIVE_CONTROL_PROVENANCE: {res.provenance}")
        print(f"NEGATIVE_CONTROL_TRACKING: {res.tracking}")
        print(f"NEGATIVE_CONTROL_VERDICT: {res.verdict}")

    # UNTRACKED fails alongside a bad verdict (#978). A control can discriminate
    # perfectly and still not exist downstream, so PASS alone is not sufficient.
    #
    # UNAVAILABLE is EXCUSED ONLY WHEN ASKED FOR, and never when the control is
    # also UNTRACKED (issue #1117): "this machine lacks gitleaks" and "this
    # control does not exist in a clean clone" are independent facts, and
    # tolerating the first must not swallow the second. The axes stay separate
    # here exactly as they do in the Result.
    excused = (
        {id(r) for r in unavailable_results if r.tracking != "UNTRACKED"}
        if (args.strict and args.allow_unavailable)
        else set()
    )
    failing = [
        r for r in results
        if (r.verdict != PASS or r.tracking == "UNTRACKED") and id(r) not in excused
    ]
    if not args.quiet:
        print()
        if failing:
            for res in failing:
                print(f"negative-controls: {res.gate} -> {res.verdict}")
                for line in res.details:
                    print(f"    {line}")
        else:
            # The message states what this run actually established, including the
            # #946 half: every claim here has an input population behind it.
            #
            # THE NUMERATOR IS THE CONTROLS THAT DISCRIMINATED, not the controls
            # that were registered (issue #1117). Those were the same number
            # until UNAVAILABLE existed; counting an unexamined control as one
            # that "carries a control that discriminates" would be a fresh
            # overclaim introduced by the very change that exists to stop one.
            discriminating = [r for r in results if r.verdict == PASS]
            if universe is None:
                scope = (
                    f"{len(discriminating)} control(s) of an UNKNOWN universe "
                    f"({whence}) - this is a sample, and how large a sample cannot be said"
                )
            else:
                scope = (
                    f"{len(discriminating)} of {universe} enumerated instruments "
                    f"({whence}) carry a control that discriminates"
                )
            print(f"negative-controls: ok - {scope}, "
                  "each reporting its declared detection signal on the known-bad input "
                  "and demonstrated against an anchor that misses it")
    # NAMED, NOT COUNTED, AND PRINTED ON EVERY RUN THAT HAS ANY - including a
    # failing one, where an unexamined control is part of why the picture is
    # incomplete. A tolerated verdict that is not said out loud is the silence
    # this whole file exists to refuse: a developer whose box lacks gitleaks
    # would otherwise read a green `make verify` as the same evidence CI has.
    if unavailable_results and not args.quiet:
        print()
        print(
            f"negative-controls: {len(unavailable_results)} control(s) NOT EXAMINED here - the "
            f"gate's own tool is not installed. This is unexamined, not clean:"
        )
        for res in unavailable_results:
            print(f"    {res.gate} -> UNAVAILABLE")
            for line in res.details:
                if "not installed" in line:
                    print(f"        {line}")
    return 1 if (failing and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
