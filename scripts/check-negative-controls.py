#!/usr/bin/env python3
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
    UNKNOWN      exit != good_exit AND the DECLARED   - could not look HERE, or
                 refusal signal present                 not completely: this
                                                        INPUT defeated it
    UNSIGNALLED  exit != good_exit AND none of them   - exited like a finding
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

Still seven. UNKNOWN (issue #1129) is deliberately NOT an eighth: it is an
OBSERVATION and a registrable EXPECTATION, so a gate whose refusal branch
behaves as registered is part of PASS, and one whose refusal branch has stopped
working is BLIND - an alarm the vocabulary above already carries. Adding a
verdict for it would say that a working control is somehow unresolved.

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
  3. IT MAY NOT SURVIVE A RUN THAT PROVES THE TOOL WAS THERE. If any case
     reports unavailability while another case through the SAME gate produced a
     REAL VERDICT - a clean run OR a genuine detection - the tool was present
     enough to run one and not the other, which is not what a missing binary
     does. That contradiction is UNRESOLVED, and it is what catches a pattern
     loose enough to swallow a genuine finding on a host where the tool IS
     installed. Both verdicts count as proof the gate ran: counting only the
     clean one left a gate that DETECTED its known-bad input and then claimed
     unavailability on the known-good one entirely unguarded (counter-model
     review of this change).

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
"I COULD NOT LOOK HERE" IS A PROPERTY OF THE GATE, SO A CASE MAY DEMAND IT
(issue #1129)
---------------------------------------------------------------------------
Every gate in this tree answers in THREE branches, not two: clean, a finding,
and "I could not look, or could not look COMPLETELY". The third exists because
a gate that examined nothing prints the same confident zero as one that examined
everything - "0 examined is not 0 findings", the house rule from #952 - and it
is reported as its own exit with its own message for exactly that reason.

That branch could not be REGISTERED. A case exercising it exits non-zero with a
refusal message that does not match `detect_signal`, so it observed UNSIGNALLED,
and UNSIGNALLED takes the WHOLE control down rather than exercising the branch.
The only way to keep a control green was therefore to never write a case for its
gate's refusal half - which is the half whose failure is hardest to notice from
outside, and so the half most worth controlling.

MEASURED, and this is why it is one issue and not a hunch: mutation-probing
`controls/shellcheck-gate` (#970/PR #1128) enumerated 12 protections of
`scripts/shellcheck-gate.sh` and found 7 of the 8 unexercised ones sitting in
exactly this position, every one a refusal-reporting branch.

So `cases[].expect` now takes a THIRD value, `UNKNOWN`, and the manifest declares
the marker that identifies a refusal: `unknown_signal`.

WHY THIS IS REGISTRABLE WHEN `UNAVAILABLE` IS NOT, which is the whole of the
design and the thing to read twice. They look like the same widening and are
not. UNAVAILABLE says the gate's own TOOL is not installed - a fact about THIS
MACHINE. A manifest that could register it would be asserting the environment,
and "I expect this host not to have gitleaks" is not a property of the control,
so it stays an OBSERVATION the harness makes and is never compared against an
expectation. UNKNOWN says the gate refused BECAUSE OF THIS INPUT - the case tree
handed to it is what produced the refusal, the same way a known-bad tree is what
produces a finding. That IS a property of the gate, it is deterministic given
the committed case, and so a case may demand it and IS scored against it.

TWO CONSEQUENCES OF THAT ASYMMETRY, both deliberate:

  - AN UNKNOWN OBSERVATION IS COMPARED AGAINST `expect`; an UNAVAILABLE one is
    recorded and skipped. A mismatch in EITHER direction is a gate alarm and
    lands BLIND: a gate that reports CLEAN where the case must defeat it is the
    false-clean this branch exists to prevent, and a gate that refuses where it
    must give a verdict has stopped answering the question. The sentence in the
    result says which happened, because they send a reader to different code.
  - THE #1117 CROSS-CASE CONTRADICTION GUARD DOES NOT APPLY HERE, and its
    absence is a decision rather than an omission. That guard exists because a
    binary that is not installed is not installed for EVERY case, so "unavailable
    here, clean there" cannot be what a missing tool produces. Refusal is the
    opposite: it is per-input BY CONSTRUCTION, so "refused here, clean there" is
    precisely what a correct pair looks like. Importing the guard would refuse
    every well-formed UNKNOWN registration.

THERE IS NO EIGHTH VERDICT. UNKNOWN is an observation and an expectation; a
control whose UNKNOWN case behaves as registered is simply part of PASS. Nothing
about "this gate has a refusal branch and it works" is a statement about the
control or the environment, which is what the verdict vocabulary is for.

WHAT KEEPS THE NEW FIELD FROM BEING A FAIL-OPEN. A third expectation is a third
way to excuse a non-zero exit, so `unknown_signal` carries the same shape of
constraint `unavailable_signal` does, checked against output this harness already
has in hand rather than against the author's intention:

  1. IT MAY NOT MATCH EMPTY OUTPUT. `.*`, a bare `^`, a trailing `|` - each turns
     every silent non-zero exit into "it must have refused", which is the
     pre-#946 fail-open restored wearing a third field's name.
  2. IT MAY NOT MATCH A CLEAN RUN. A pattern anchored on the gate's ok line would
     report a working gate as having refused. Checked against the known-GOOD
     case's REAL output - and, like constraint 3, against the ANCHOR's output in
     both anchor loops: exiting like a clean run while announcing a refusal is
     not a verdict at all, since the run cannot have examined the input and also
     have been unable to look at it.
  3. IT MAY NOT MATCH OUTPUT THAT `detect_signal` ALSO MATCHES. This is the one
     the issue names in terms: a marker that also identified a finding would make
     a refusal and a detection the same evidence, "which is #946 undone". Checked
     on every case's real output, in both directions, so a gate whose two
     messages are genuinely inseparable is refused rather than silently ordered.
     ALSO ON THE ANCHOR'S OUTPUT, because an anchor is a different program and a
     check over the cases is no evidence about it - the first cut covered only
     the cases, so ambiguous output was refused from the gate and accepted as
     anchor agreement. NOT on a run already identified as UNAVAILABLE: there the
     question is moot (the case is skipped, never scored), and firing would turn
     an environment fact into an accusation about the manifest. Both corrections
     come from the counter-model review of this change.

WHAT A REFUSAL IS NOT EVIDENCE OF. It does not establish that the gate's own
tool was installed, and the first cut of this expectation assumed it did -
reasoning that since `unavailable_signal` is consulted first, a refusal must mean
the gate got PAST its availability check. That holds only for a gate that checks
its tool before validating its input, and `shellcheck-gate.sh` does the opposite:
it refuses a non-directory `--root` one line BEFORE it looks for shellcheck. So a
refusal stays out of the evidence that satisfies the #1117 contradiction check;
only a clean run or a genuine detection proves the gate reached the work.

PRECEDENCE: `unavailable_signal`, then `unknown_signal`, then `detect_signal` -
most specific first, for the reason the #1117 section argues at length. It is
load-bearing here rather than tidy: `shellcheck-gate.sh` reports BOTH its absent
linter and its other refusals through one `shellcheck-gate: UNKNOWN - ` marker,
so the tool-absent line is a strict SUBSET of the refusal marker. Consulted in
the other order, a box that simply lacks shellcheck would score UNKNOWN, be
compared against an expectation, and become a gate alarm again - #1117 undone by
the change that cites it. `tests/test_negative_controls.py` pins the order.

WHAT MOVES THIS BACK (the reversal trigger, ADR 0009). If a gate's refusal and
its detection cannot be told apart by their messages - constraint 3 firing on a
manifest whose patterns are both honest - then the declared-signal design is the
wrong guard for that gate, and the answer is to give that gate a distinguishable
refusal marker, not to relax the constraint. Should that prove impossible for a
real gate, this expectation comes out rather than widening to accommodate it.

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
import sys
from dataclasses import dataclass, field
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

#: This checkout, so the census EXTRACTION RULE is loaded from the program while
#: the census DOCUMENT is read from `--root`. See `_census_rule` below.
REPO_ROOT = Path(__file__).resolve().parents[1]

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
#: NEGATIVE-CONTROL: controls/check-negative-controls-unavailable
#:     A SECOND registration on this gate (issue #1117), covering a property the
#:     row above does not: that a gate reporting its own tool absent is still
#:     told apart from a gate that went silent. Separate rather than two more
#:     cases on the existing control because the property is only observable
#:     under `--allow-unavailable`, and adding that flag to the other control's
#:     invocation would make its frozen pre-#946 anchor exit 2 on an
#:     unrecognised argument - turning a working control UNRESOLVED to test an
#:     unrelated one. Several registrations per gate have been supported since
#:     #986; this is the first gate to use it, which is worth knowing if that
#:     path ever looks untested.
#:
#:     It inherits the self-registration caveat stated in full above and does
#:     not repeat it: this harness judging itself is the weaker half, and
#:     `tests/test_negative_controls.py` under pytest is the external opinion.
#: NEGATIVE-CONTROL: controls/check-negative-controls-unknown
#:     A THIRD registration on this gate (issue #1129), covering the property
#:     the other two do not: that a gate which REFUSED a verdict is still told
#:     apart from one that FELL OVER, now that `cases[].expect` can register the
#:     refusal. The three sit in a row on purpose - #946 asks whether a crashing
#:     gate is told from a detecting one, #1117 whether a silent gate is told
#:     from one whose own TOOL is absent, and this one whether a silent gate is
#:     told from one the INPUT defeated. Each new way for a non-zero exit to be
#:     excused needs its own committed demonstration, because each is a fresh
#:     route back to scoring on the exit code alone.
#:
#:     SEPARATE RATHER THAN TWO MORE CASES ON THE FIRST CONTROL, and this was
#:     MEASURED rather than assumed: run against this control's known-bad tree,
#:     that control's frozen pre-#946 anchor reports UNRESOLVED and exits 1
#:     ("control.json has case(s) with an unknown expect value: ['UNKNOWN']").
#:     An anchor exiting non-zero on the known-bad input reads as having CAUGHT
#:     it, so those cases would report a working control INERT and send someone
#:     to replace a sound artifact.
#:
#:     It inherits the self-registration caveat stated in full above and does
#:     not repeat it.
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

#: A FIFTH observation and - alone among the three that are not GOOD or BAD - a
#: REGISTRABLE EXPECTATION (issue #1129). `cases[].expect` takes it, because
#: unlike UNSIGNALLED ("I expect this gate to fall over") and UNAVAILABLE ("I
#: expect this host to lack a binary") it names something the CASE INPUT
#: produces: the gate refused to report a verdict about a population this tree
#: defeated it on. That is a property of the gate, deterministic given the
#: committed case, so a case may demand it and is scored against it. It is NOT a
#: control verdict - see the docstring section that carries the argument.
UNKNOWN = "UNKNOWN"

#: What `cases[].expect` accepts. Named rather than spelled inline at the one
#: validation site, because a reader asking "what may a case register?" should
#: find one answer and not have to trust that the validation and the docstring
#: agree.
REGISTRABLE = (GOOD, BAD, UNKNOWN)

#: WHAT KIND OF INSTRUMENT THIS CONTROL IS ABOUT (issue #1085). Every control
#: until now was a GATE - something that lets work through or stops it - and the
#: blindness requirement was written for exactly that: a BAD case, which the
#: harness scores by EXIT CODE (`if exit_code == good_exit: return GOOD`), so a
#: detection must be non-zero.
#:
#: A REPORTER has no non-zero verdict to give. Its job is to produce a number a
#: person reads; its legitimate answers are a measurement, an observed zero, and
#: "I could not look". Requiring it to fail on some input means inventing a
#: threshold - a BAND - which is precisely what the issue that needed this
#: forbids. So a reporter demonstrates blindness on the REFUSAL AXIS instead: an
#: UNKNOWN case where the ANCHOR reports CLEAN. The fixed instrument refuses the
#: input, the blind one answers it confidently. That is a discrimination.
#:
#: NOT NAMED `kind`, deliberately: `kind` already exists one level down on
#: anchors (constructed, historical, synthetic, vendored). One file, one word,
#: two unrelated taxonomies is a tax on every future reader.
GATE_SUBJECT = "gate"
REPORTER_SUBJECT = "reporter"
SUBJECT_KINDS = (GATE_SUBJECT, REPORTER_SUBJECT)

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
    #: Which blindness requirement this control was held to (issue #1085).
    #: Defaults to `gate`, which is what every control meant before the field
    #: existed, so a Result built anywhere else reads as a gate.
    subject_kind: str = "gate"
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


#: The sibling gate that owns "what subject is this census row about" - the
#: first backticked token of column 2, head word only (issue #1060). The rule is
#: IMPORTED rather than re-implemented, for the reason #1060 recorded when it
#: split this file's row parser from that one: two readers of one table drift
#: apart silently, and the drift is invisible precisely because both keep
#: printing numbers. `verify-coverage-check.py` imports it the same way (#1028).
CENSUS_GATE_REL = "scripts/instrument-census-check.py"


def _census_rule():
    """The census extraction rule, loaded from THIS CHECKOUT, or None.

    THE RULE COMES FROM THE PROGRAM, THE DOCUMENT FROM `--root`. Loading the
    rule from `root` would execute the target tree's own Python - and `--root`
    is pointed at fixture trees on every run of this file's own control. It is
    also wrong on the merits: "what counts as a census subject" is this
    repository's rule, not something each tree redefines.

    None means the rule is UNREADABLE, never "there are no subjects". Every
    caller reports `unknown` on it; an absent rule must not read as an empty
    census, which would make membership vacuously perfect.
    """
    gate = REPO_ROOT / CENSUS_GATE_REL
    if not gate.is_file():
        return None
    try:
        spec = spec_from_file_location("instrument_census_check", gate)
        if spec is None or spec.loader is None:
            return None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:  # noqa: BLE001 - any failure here is UNREAD, never EMPTY
        return None
    if not hasattr(module, "census_subjects") or not hasattr(module, "declared_externals"):
        return None
    return module


@dataclass
class Census:
    """What ADR 0008's table says, as three separate facts (issue #1036).

    `rows` alone was the whole denominator, and printing it beside a count of
    REGISTERED CONTROLS produced `21 of 89` - a sentence whose two numbers come
    from populations nothing relates. This carries the relationship instead:

    rows        how many instruments the census enumerates. The denominator.
    subjects    WHICH instruments, so a registered control's gate can be
                resolved against them. None when the rule or the document
                could not be read - never an empty set, which would report
                every registered control as a non-member.
    external    how many of those rows name a subject the document itself
                declares has no file under `scripts/` (`ruff`, `pytest`,
                `gitleaks`, `make`, the `lib.*` entry points). The denominator
                is not homogeneous and said nothing about it.

                THESE ARE NOT "UNREGISTRABLE", and the issue that asked for
                this count corrected itself on exactly that word. They cannot
                carry a marker THEMSELVES, but `controls/secret-scan` already
                covers `gitleaks` by wrapping it in
                `scripts/secret-scan-check.sh`. Wrapping is the route for the
                rest, so this number describes the CURRENT DISCOVERY RULE, not
                a ceiling on what can be controlled.
    """

    rows: int | None = None
    subjects: set[str] | None = None
    external: int | None = None
    whence: str = ""
    #: Set when the two readers of this one table disagree about how many rows
    #: it has. Membership is then reported `unknown` rather than computed from a
    #: subject set that is provably not the row set - the drift #1060 warned of,
    #: arriving as a wrong answer instead of a missing one.
    disagreement: str = ""


def instrument_census(root: Path) -> Census:
    """ADR 0008's census: how many rows, which subjects, how many external.

    WHICH DOCUMENT is the census is asked of the census rule's `resolve_adr`
    (issue #1264), so a repository that files the decision elsewhere - kyle's
    `docs/adr/0005-...` - gets a universe instead of `unknown` by construction.
    With the rule unloadable only the default path is tried, which is what this
    function did before, and the membership half reports the rule's absence.
    """
    rule = _census_rule()
    resolver = getattr(rule, "resolve_adr", None)
    if resolver is not None:
        adr, adr_name = resolver(root)
        if adr is None:
            return Census(whence=adr_name)
    else:
        adr, adr_name = root / ADR_0008, str(ADR_0008)
    try:
        text = adr.read_text(encoding="utf-8")
    except OSError:
        return Census(whence=f"{adr_name} is unreadable")
    rows = len(ADR_ROW_RE.findall(_census_text(text)))
    if rows == 0:
        return Census(whence=f"{adr_name} parsed to 0 enumerated rows")

    census = Census(rows=rows, whence=adr_name)
    if rule is None:
        census.disagreement = f"{CENSUS_GATE_REL} could not be loaded"
        return census
    try:
        subjects = rule.census_subjects(text)
        externals = rule.declared_externals(text)
    except Exception as exc:  # noqa: BLE001 - a broken rule is UNREAD, never EMPTY
        census.disagreement = f"{CENSUS_GATE_REL} raised {type(exc).__name__}: {exc}"
        return census

    # A row this file counts but the sibling extracts no subject from (no
    # backticked token in column 2) means the two readers are looking at
    # different documents. Reporting membership against the smaller set would
    # name real rows as non-members, so the honest answer is `unknown`.
    if len(subjects) != rows:
        census.disagreement = (
            f"{adr_name} parses to {rows} row(s) here and {len(subjects)} subject(s) "
            f"via {CENSUS_GATE_REL}"
        )
        return census

    census.subjects = set(subjects)
    census.external = sum(1 for subject in subjects if subject in externals)
    return census


#: WHERE A MARKER CAN BE SEEN AT ALL, stated because "no control found" and "I
#: did not look there" are otherwise the same silence (issue #1036). `discover`
#: below calls `iterdir()`, not `rglob()`, so a registration is invisible in
#: `controls/`, in `lib/`, in a config file such as `.gitleaks.toml`, and in any
#: `scripts/` SUBDIRECTORY.
#:
#: THAT FITS CPP AND IS NOT A UNIVERSAL RULE. This repository's instruments are
#: overwhelmingly top-level scripts, and `instrument-census-check.py` derives the
#: census population with the same `scripts/`-only rule - so widening one without
#: the other would split the numerator's population from the denominator's, which
#: is the defect this whole line of work is about. A repository whose instruments
#: are library modules (kyle: 64 of 77 enumerated verdict contracts are not under
#: `scripts/`) needs that decision made for BOTH readers at once, not here.
#:
#: This constant is a CLAIM, and `tests/test_negative_controls.py` holds it: a
#: marker planted in a `scripts/` subdirectory must not be discovered. Widen
#: `discover` and that case fails, which is what brings someone back to this text.
DISCOVERY_SCOPE = "scripts/* (top-level files only; subdirectories are not read)"


def census_membership(
    registrations: list[tuple[Path, str]], census: Census
) -> tuple[int | None, list[str] | None]:
    """`(members, nonmembers)` for the discovered registrations (issue #1036).

    The gate a registration covers is the FILE THE DIRECTIVE LIVES IN -
    `evaluate` refuses any manifest that declares otherwise - so the census
    subject to resolve against is that file's basename, which is the form the
    census table uses.

    `(None, None)` when the census subjects could not be read. An unreadable
    membership list must not report every control as a non-member, and must not
    report every control as a member either: both are confident answers to a
    question nothing answered.
    """
    if census.subjects is None:
        return None, None
    names = sorted({path.name for path, _ in registrations})
    nonmembers = [name for name in names if name not in census.subjects]
    return len(names) - len(nonmembers), nonmembers


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
    unknown: re.Pattern[str] | None = None,
) -> str:
    """What the run SAYS happened - five answers, not two (issues #946, #1117, #1129).

    The exit code alone cannot separate "I found the planted problem" from "I
    fell over", because a crash exits non-zero too. So a non-zero exit is only
    read as detection when the gate also emitted its declared signal; without it
    the honest answer is UNSIGNALLED, which is neither verdict.

    PRECEDENCE IS MOST-SPECIFIC-FIRST and every step of it is load-bearing:
    `unavailable`, then `unknown`, then `signal`.

    `unavailable` before `signal` is argued in the docstring section "ITS TOOL
    IS MISSING IS NOT IT STOPPED DISCRIMINATING": the two messages are not
    separable in the other direction for `flow-driver-retirement-check.sh`,
    whose unavailability line is a legitimate member of its own detection
    pattern.

    `unavailable` before `unknown` is the same rule one level down, and it is
    why the order is not merely tidy. `shellcheck-gate.sh` reports its absent
    linter AND its other refusals through one `shellcheck-gate: UNKNOWN - `
    marker, so the tool-absent line is a strict SUBSET of the refusal marker.
    Reversed, a host that simply lacks shellcheck would observe UNKNOWN, be
    scored against an expectation, and turn an environment fact back into a gate
    alarm - the #1117 defect restored by the change that cites it.

    The constraints that keep any of these from being a fail-open are enforced
    by the caller, against real output.
    """
    if exit_code == good_exit:
        return GOOD
    if unavailable is not None and unavailable.search(output):
        return UNAVAILABLE
    if unknown is not None and unknown.search(output):
        return UNKNOWN
    return BAD if signal.search(output) else UNSIGNALLED


#: What a discrimination failure ACTUALLY WAS, keyed by (expected, observed).
#: A BLIND verdict sends someone into a gate's source, and the sentence is what
#: decides WHERE they look, so the six directions are spelled out rather than
#: collapsed into "missed a known-bad input" / "flagged a known-good input"
#: (issue #1129). Those two were exhaustive when GOOD and BAD were the only
#: registrable expectations; with a third they would attribute a refusal to
#: whichever of the two it was not, which is a confident sentence about the
#: wrong branch.
_MISMATCH = {
    (BAD, GOOD): "missed a known-bad input",
    (BAD, UNKNOWN): "REFUSED a known-bad input instead of reporting the finding in it",
    (GOOD, BAD): "flagged a known-good input",
    (GOOD, UNKNOWN): "REFUSED a known-good input instead of reporting it clean",
    # The false-clean the refusal branch exists to prevent, and the reason
    # #1129 called this half the one most worth controlling.
    (UNKNOWN, GOOD): "reported CLEAN on an input it cannot examine - the false-clean "
                     "its refusal branch exists to prevent",
    (UNKNOWN, BAD): "reported a FINDING on an input it cannot examine, so a verdict it is "
                    "not entitled to is being presented as one it is",
}


def _ambiguous(output: str, signal: re.Pattern[str], unknown: re.Pattern[str] | None) -> bool:
    """Can a REFUSAL and a FINDING be told apart in this output? (issue #1129)

    Consulting `unknown_signal` before `detect_signal` is a precedence rule, not
    a licence for the two to overlap: where both match one output, the ordering
    silently decides which of two honest-looking patterns wins, and a gate that
    started REPORTING what it used to REFUSE keeps scoring UNKNOWN and passes.

    A FUNCTION RATHER THAN AN INLINE TEST because it has THREE call sites, and
    the counter-model review of this change (codex/gpt-6-astra, MEDIUM) found
    the first cut had only one. It ran over the CASE loop alone, so ambiguous
    output was refused when the current gate produced it and ACCEPTED as
    anchor agreement when the ANCHOR produced it - and an anchor is a different
    program, so a check on the gate is no evidence about it. The control then
    reported PASS on exactly the evidence this function exists to reject.

    Callers must skip it for an observation already identified as UNAVAILABLE,
    for the reason argued at the call site.
    """
    return unknown is not None and bool(unknown.search(output)) and bool(signal.search(output))


def _anchor_output_fault(
    output: str,
    observed: str,
    signal: re.Pattern[str],
    unknown: re.Pattern[str] | None,
    raw_unknown: str,
    raw_signal: str,
    where: str,
) -> str:
    """The reason this anchor's output cannot be read at all, or "" (issue #1129).

    The current gate's output is held to two rules about the refusal marker: it
    may not be ambiguous with the detection signal, and it may not accompany a
    CLEAN exit. Both were enforced over the cases only, and the counter-model
    review of this change found each gap in turn - an anchor is a DIFFERENT
    PROGRAM, so a check on the gate is no evidence about it, and both anchor
    loops were accepting output the gate-side rules reject one function earlier.

    Returned as a SENTENCE rather than a bool because both call sites need to
    say which fault and where, and a third and fourth copy of these two
    conditions is how they drifted apart the first time.
    """
    if observed != UNAVAILABLE and _ambiguous(output, signal, unknown):
        return (
            f"emitted BOTH the declared refusal marker /{raw_unknown}/ and the detection "
            f"signal /{raw_signal}/ on {where}, so what it did there cannot be established"
        )
    # Not a verdict at all: it cannot have examined the input and also have been
    # unable to look at it. Reading it as agreement certifies incoherent evidence.
    if observed == GOOD and unknown is not None and unknown.search(output):
        return (
            f"exited like a CLEAN run on {where} while printing the declared refusal marker "
            f"/{raw_unknown}/, so it cannot be read as having examined that input at all"
        )
    return ""


def _mismatch(expected: str, observed: str) -> str:
    """The sentence for this direction, or an honest fallback naming both.

    The fallback is not decoration: a pair absent from the table means this
    function has fallen behind the vocabulary, and printing a WRONG sentence
    from a default would be worse than printing a plain one - it is the same
    "confident verdict it is not entitled to" the whole file exists to refuse.
    """
    return _MISMATCH.get((expected, observed), f"expected {expected} and observed {observed}")


def _invoke(spec: list[str], gate: Path, case: Path, root: Path) -> tuple[int | None, str, str]:
    argv = [part.replace("{gate}", str(gate)).replace("{case}", str(case)) for part in spec]
    return _run(argv, root)


#: Written by the interpreter, never authored - see `_tracking()` (issue #1239).
_DERIVED_BYTECODE_SUFFIXES = frozenset({".pyc", ".pyo"})


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
    # DERIVED BYTECODE IS NOT A CONTROL FILE (issue #1239). A case that runs
    # Python writes `__pycache__/*.pyc` beside itself, so every run after the
    # first in a checkout reported UNTRACKED on files no clean clone needs. The
    # exclusion is by NAME and exactly this wide: excluding every IGNORED path
    # instead would blind this check to the #964/#953 shape it exists for - a
    # load-bearing `case.json` swallowed by the blanket `*.json`.
    on_disk = {
        p.resolve()
        for p in control_dir.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.relative_to(control_dir).parts
        and p.suffix not in _DERIVED_BYTECODE_SUFFIXES
    }
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
    #: ABSENT IS NOT EMPTY. `spec.get("cases", [])` turned a manifest that
    #: declares no `cases` key at all into one declaring an empty list, and the
    #: requirement checks below then reported it as "registers no BAD case" -
    #: a sentence about cases, for a file that has none. Both refuse, so this
    #: was never a false clean, but it named the wrong defect and sent a reader
    #: looking for a case list that does not exist.
    cases_declared = isinstance(spec.get("cases"), list)
    cases: list[dict[str, str]] = spec.get("cases") if cases_declared else []
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
    # THREE STATES, THREE SENTENCES (issue #1085). This was one message for
    # "no invocation", "no `cases` key at all" and "an empty `cases` list",
    # which are three different repairs. ABSENT is not EMPTY: `spec.get("cases",
    # [])` renders a manifest that never declares the key as one declaring an
    # empty list, and the reader is then sent looking for a case list that does
    # not exist. Neither was ever a false clean - all three refuse - but a
    # refusal that names the wrong defect costs the same time as no refusal.
    if not invocation:
        res.details.append(
            "control.json names no `invocation`, so there is no way to run the gate"
        )
        return res
    if not cases_declared:
        res.details.append(
            "control.json declares no `cases` key at all, so there is nothing to run - "
            "which is a different defect from declaring an empty list, and from declaring "
            "a one-sided one"
        )
        return res
    if not cases:
        res.details.append(
            "control.json declares an EMPTY `cases` list, so nothing is exercised"
        )
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
    # PARSED BEFORE THE SIGNAL REQUIREMENTS, because WHICH marker is required
    # depends on what kind of instrument this is (issue #1085 follow-up).
    raw_subject = spec.get("subject_kind", GATE_SUBJECT)
    if raw_subject not in SUBJECT_KINDS:
        res.details.append(
            f"control.json declares subject_kind {raw_subject!r}, which is not one of "
            f"{list(SUBJECT_KINDS)}. It is refused rather than defaulted: a value this "
            f"harness does not recognise must not silently acquire the rules of one it does"
        )
        return res
    res.subject_kind = raw_subject

    raw_signal = spec.get("detect_signal", "")
    #: OMITTED IS NOT INVALID (counter-model finding, 2026-09-22). The first cut
    #: keyed the exemption on `has_signal` - "is there a usable pattern" - which
    #: is true of an ABSENT field and equally true of `"detect_signal": ""`,
    #: `null`, `0` or `[]`. A control that DECLARED a broken signal therefore
    #: took the reporter branch, had the sentinel substituted, and passed with
    #: its validations disabled: the author said something and the harness
    #: silently heard nothing.
    #:
    #: The exemption is for a control that makes NO detection claim. Making a
    #: bad one is a different act and keeps the old answer, so an explicit value
    #: of any shape falls through to the usable-pattern check below and is
    #: refused there. This is the absent-versus-empty distinction that this very
    #: change's rationale is built on, written into the change itself.
    signal_omitted = "detect_signal" not in spec
    raw_unknown_peek = spec.get("unknown_signal", "")
    has_unknown = isinstance(raw_unknown_peek, str) and bool(raw_unknown_peek.strip())

    # THE MARKER REQUIREMENT RELOCATES FOR A REPORTER, IT IS NOT REMOVED.
    #
    # `detect_signal` is required because a non-zero exit must be tellable from
    # a CRASH (#946). For a GATE that is the detection marker, because a gate's
    # non-zero exit IS its finding. A REPORTER has no finding: its only non-zero
    # exit is a refusal, and `unknown_signal` is what separates that from a
    # crash. So a reporter may omit `detect_signal` and must then declare
    # `unknown_signal` - the same guarantee, carried by the marker that can
    # actually carry it.
    #
    # THE TEST FOR WHETHER A FIELD MAY BE OPTIONAL IS ALREADY IN THIS FILE, at
    # the `unavailable_signal` asymmetry: "`detect_signal` had to be required
    # because defaulting it left every control exactly as blind as before the
    # fix. Omitting `unavailable_signal` has the opposite effect ... Absence
    # fails CLOSED here, so it costs nothing to allow." This meets that test -
    # absence of `detect_signal` on a reporter fails closed, because the
    # requirement moves rather than lapsing, and nothing is left unmarked.
    #
    # AND THE GUARDS MOVE WITH IT. `unknown_signal` carries the same two
    # protections `detect_signal` has: it may not match EMPTY output, and it
    # may not match the gate's CLEAN output. Relocating a requirement without
    # its guards would be the same defect one boundary further out; these were
    # checked rather than assumed.
    if raw_subject == REPORTER_SUBJECT and signal_omitted:
        if not has_unknown:
            res.details.append(
                "control.json declares subject_kind 'reporter' with neither a detect_signal "
                "nor an unknown_signal, so a non-zero exit from this instrument cannot be "
                "told from a crash (issue #946). A reporter may omit detect_signal - it has "
                "no finding to mark - but it must then declare unknown_signal, because the "
                "requirement RELOCATES and does not lapse"
            )
            return res
        #: A pattern that cannot match anything, standing in for "this subject
        #: makes no detection claim". Downstream, `_observe` then returns
        #: UNSIGNALLED for any non-zero exit that carries no refusal marker -
        #: which is the correct verdict for a reporter that exited oddly, and
        #: is why omitting the field does not open a hole.
        raw_signal = r"(?!x)x"
        signal_is_declared = False
    else:
        signal_is_declared = True

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
    if signal_is_declared and signal.search(""):
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

    # THE GATE'S REFUSAL MARKER (issue #1129). Optional like `unavailable_signal`
    # and for the same reason: omitting it excuses nothing, so absence fails
    # CLOSED - a manifest that declares no refusal marker cannot register an
    # UNKNOWN case, and every control that has one today scores exactly as it
    # does now. The two refusals that need REAL OUTPUT - a pattern matching a
    # clean run, and one matching output `detect_signal` also matches - are
    # enforced below, where that output exists. These two are structural and are
    # checked before any case runs.
    raw_unknown = spec.get("unknown_signal", "")
    unknown_sig: re.Pattern[str] | None = None
    if raw_unknown:
        if not isinstance(raw_unknown, str) or not raw_unknown.strip():
            res.details.append("control.json unknown_signal is not a usable pattern")
            return res
        try:
            unknown_sig = re.compile(raw_unknown, re.MULTILINE)
        except re.error as exc:
            res.details.append(f"control.json unknown_signal is not a usable regex: {exc}")
            return res
        if unknown_sig.search(""):
            res.details.append(
                f"control.json unknown_signal /{raw_unknown}/ matches empty output, so every "
                "silent non-zero exit would be excused as a refusal (issue #1129)"
            )
            return res

    # A one-sided control tests nothing, so it may not reach PASS. This was only
    # DOCUMENTED before, and the code required a non-empty list: a GOOD-only
    # control passed against a gate that was genuinely blind, and a BAD-only one
    # passed against a gate wedged at "fail". Both printed the summary line "N
    # control(s) discriminate", which is a claim neither population supported.
    expects = {case.get("expect") for case in cases}
    unrecognised = expects - set(REGISTRABLE)
    if unrecognised:
        res.details.append(
            f"control.json has case(s) with an unknown expect value: {sorted(map(str, unrecognised))}"
        )
        return res
    # An UNKNOWN case with no marker to recognise a refusal by can NEVER observe
    # UNKNOWN: it would fall through to UNSIGNALLED or BAD and be reported as a
    # gate alarm, sending a reader into the gate's detection logic for what is a
    # missing line in this manifest. Refused here, with the sentence that names
    # the actual defect (issue #1129).
    if UNKNOWN in expects and unknown_sig is None:
        res.details.append(
            "control.json registers an UNKNOWN case but declares no unknown_signal, so a "
            "refusal by this gate cannot be told from a crash (issue #1129)"
        )
        return res
    # A CASE MUST LIVE UNDER ITS OWN CONTROL (issue #1157). What makes a control
    # a readable unit is that everything it needs is beneath it: the register can
    # be understood one directory at a time, and moving a control moves its
    # cases with it. One `input` reaching out with `../../` ends that - the
    # registration still looks valid after a directory move that silently broke
    # it, and a reader can no longer tell what a control covers by looking at it.
    #
    # REFUSED RATHER THAN DISCOURAGED. It was raised as a way to register #1146's
    # two trees without relocating them, rejected on the property above, and a
    # schema that permits a path it never intends to see is a schema that will
    # eventually see it. `resolve()` is deliberate: a case that reaches outside
    # THROUGH A SYMLINK is the same escape wearing a different spelling.
    control_root = control_dir.resolve()
    for case in cases:
        rel = str(case.get("input", ""))
        try:
            resolved = (control_dir / rel).resolve()
        except (OSError, RuntimeError):
            #: RuntimeError, not just OSError (#1157 counter-model review, LOW).
            #: `Path.resolve()` raises RuntimeError on a symlink LOOP under the
            #: supported 3.11/3.12, and an uncaught one here would abort the
            #: whole harness with a traceback - so ONE malformed control would
            #: stop every other control being reported at all. A control that
            #: cannot be resolved is UNRESOLVED, which is what it means.
            resolved = None
        if resolved is None or not resolved.is_relative_to(control_root):
            res.details.append(
                f"control.json case {case.get('name', rel)!r} has input {rel!r}, which resolves "
                f"outside its own control directory. A control is a unit: everything it needs "
                "lives under it, or a directory move breaks a registration that still looks valid"
            )
            return res

    # `anchor_expect` DECLARES WHAT THE ANCHOR MUST DO ON THIS CASE (issue
    # #1157), and it is FAIL-CLOSED: absent means "must agree with the current
    # gate", which is what every case meant before this field existed, so no
    # existing registration changes meaning.
    #
    # THREE REFUSALS, and the third is the one that would otherwise rot quietly:
    #   - an unknown value is a typo that would silently read as "must agree";
    #   - `clean` without a recorded REASON is the escape hatch this field would
    #     become if the cost were optional - a bypass wearing a schema field;
    #   - `anchor_expect` on ANYTHING THAT IS NOT AN UNKNOWN CASE. Two separate
    #     reasons, and the block below states the second where it is enforced:
    #     on a BAD case the declaration is never read at all, because only GOOD
    #     and UNKNOWN cases reach the anchor-sanity loop - a declaration nobody
    #     reads is the defect this file exists to catch, one level in, sitting
    #     in the manifest looking load-bearing and governing nothing. On a GOOD
    #     case it IS read, and that is worse: the diagnosis it triggers blames
    #     the manifest for what is an anchor's own false positive.
    for case in cases:
        declared = case.get("anchor_expect")
        if declared is None:
            continue
        if declared != "clean":
            res.details.append(
                f"control.json case {case.get('input')!r} declares anchor_expect "
                f"{declared!r}; the only value that changes anything is 'clean', and an "
                "unrecognised one would read as 'must agree' while looking deliberate"
            )
            return res
        #: UNKNOWN ONLY, and the narrowing is a CORRECTNESS fix rather than
        #: caution (#1157 counter-model review, MEDIUM). The first cut allowed
        #: it on GOOD cases too, on the reasoning that both kinds reach the
        #: sanity loop. They do - but the DIAGNOSIS below does not fit a GOOD
        #: case: an anchor that misses the known-bad input and reports a finding
        #: on the known-GOOD one is producing a FALSE POSITIVE, which is an
        #: anchor defect that INERT names correctly and that removing a
        #: declaration cannot repair. Sending that reader to "correct the
        #: registration" would attribute an anchor's defect to the manifest -
        #: the ownership question, failed by the check written to ask it.
        #:
        #: The structural impossibility this field exists for is specific to a
        #: refusal: only there can agreement be unobtainable BY CONSTRUCTION,
        #: because an anchor able to refuse an empty population must derive it
        #: and would then stop being blind. A GOOD case has no such bind.
        if case.get("expect") != UNKNOWN:
            res.details.append(
                f"control.json case {case.get('input')!r} declares anchor_expect on a "
                f"{case.get('expect')} case. It is only meaningful on an UNKNOWN case, where "
                "agreement can be impossible by construction; elsewhere a disagreement is a "
                "defect in the ANCHOR, which INERT already names and no declaration repairs"
            )
            return res
        #: A STRING WITH TEXT IN IT, not merely something that survives str()
        #: (#1157 counter-model review, MEDIUM). `str(x or "")` accepted `true`,
        #: `1`, `[""]` and `{"": ""}` - each renders non-empty and each records
        #: no reason whatever, so the cost the field charges could be paid in
        #: counterfeit. The point of the reason is that a human wrote down why;
        #: a type that cannot carry that is refused rather than coerced.
        reason = case.get("anchor_expect_reason")
        if not isinstance(reason, str) or not reason.strip():
            res.details.append(
                f"control.json case {case.get('input')!r} declares anchor_expect: clean with "
                "no anchor_expect_reason naming why this anchor cannot derive the population. "
                "Without that cost the field is a bypass for any inconvenient disagreement"
            )
            return res

    # WHICH BLINDNESS REQUIREMENT APPLIES DEPENDS ON THE SUBJECT (issue #1085).
    # Absent means `gate`, which is what every control meant before this field
    # existed, so all of them take the unchanged branch. An UNRECOGNISED value
    # is REFUSED rather than defaulted: defaulting on a typo is how a narrow
    # exception becomes a wide one, and `"Reporter"` must not silently buy the
    # relaxation that `"reporter"` buys.
    if GOOD not in expects:
        res.details.append("control.json registers no GOOD case, so a gate wedged at 'fail' would pass")
        return res

    if raw_subject == GATE_SUBJECT:
        if BAD not in expects:
            res.details.append(
                "control.json registers no BAD case, so nothing exercises the blindness"
            )
            return res
    else:
        # A REPORTER PAYS DIFFERENTLY, IT DOES NOT PAY LESS. It must still put
        # up a case where the anchor and the fixed instrument DISAGREE - an
        # UNKNOWN case carrying `anchor_expect: clean`, meaning the anchor
        # answers confidently where this instrument refuses.
        #
        # The manifest check is only half of it, and deliberately so: the other
        # half is DEMONSTRATED, not declared. #1196 already runs the anchor on
        # every UNKNOWN case and reds as UNRESOLVED when a declaration stops
        # being true, so a reporter whose anchor quietly learns to refuse loses
        # its qualification automatically. Nothing new watches it, because
        # something already does.
        qualifying = [
            c for c in cases
            if c.get("expect") == UNKNOWN and c.get("anchor_expect") == "clean"
        ]
        if not qualifying:
            res.details.append(
                "control.json declares subject_kind 'reporter' but registers no UNKNOWN "
                "case carrying `anchor_expect: clean`, so nothing exercises the blindness. "
                "A reporter demonstrates it on the refusal axis - an input this instrument "
                "refuses and the anchor answers clean - and 'reporter' is a second way to "
                "pay, never a waiver"
            )
            return res

    # -- DISCRIMINATION ---------------------------------------------------- #
    bad_cases: list[Path] = []
    #: Names of the cases whose gate reported its own tool absent, and of the
    #: cases where the gate DEMONSTRABLY RAN. Collected across the whole loop
    #: rather than acted on in it, because the contradiction that catches a loose
    #: `unavailable_signal` is a relationship BETWEEN cases and cannot be seen
    #: from inside one (issue #1117).
    #:
    #: "RAN" IS BOTH VERDICTS, NOT JUST THE CLEAN ONE (counter-model review,
    #: MEDIUM). The first cut recorded only `observed == GOOD`, so a gate that
    #: genuinely DETECTED its known-bad input and then reported its tool absent
    #: on the known-good one produced no contradiction at all and was excused as
    #: UNAVAILABLE - exit 0 under the local posture. A successful detection is
    #: proof the tool was there every bit as much as a clean run is; excluding it
    #: made the guard blind to the half where the gate had already shown it could
    #: work.
    unavailable_cases: list[str] = []
    ran_cases: list[str] = []
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
        observed = _observe(code, good_exit, output, signal, unavailable, unknown_sig)
        res.details.append(
            f"case {case['name']}: expected={expected} observed={observed} (exit {code})"
            + (f" [stderr: {diag}]" if diag else "")
        )
        # A REFUSAL AND A FINDING MAY NOT BE THE SAME EVIDENCE (issue #1129).
        # Checked on EVERY case's real output and BEFORE anything is scored,
        # because the failure is in the MANIFEST and every downstream verdict
        # built on these two patterns would otherwise blame the gate.
        #
        # EXCEPT ON A RUN ALREADY IDENTIFIED AS UNAVAILABLE, which the
        # counter-model review of this change caught (codex/gpt-6-astra,
        # MEDIUM). This check asks "can a refusal be told from a finding"; on a
        # run where the most specific declared pattern already said "my tool is
        # absent", that question is moot - the case is skipped and never scored
        # against an expectation - so firing here turns an ENVIRONMENT FACT into
        # an accusation about the manifest. The shape that exposed it is not
        # contrived: a detection pattern and a refusal pattern may each
        # legitimately carry the tool-absent message as one alternative, which
        # is the relationship `flow-driver-retirement-check.sh` already has
        # between its unavailability line and its own detection pattern. Nothing
        # is certified by the exemption: a control whose cases all report
        # UNAVAILABLE lands UNAVAILABLE, which already says nothing about the
        # gate, and a real overlap still fires on any case that actually ran.
        if observed != UNAVAILABLE and _ambiguous(output, signal, unknown_sig):
            res.verdict = UNRESOLVED
            res.details.append(
                f"control.json unknown_signal /{raw_unknown}/ and detect_signal /{raw_signal}/ "
                f"BOTH match this gate's output on case {case['name']}, so a refusal and a "
                f"finding are the same evidence and cannot be told apart (issue #1129)"
            )
            return res
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
        # The same refusal, one field along (issue #1129). A refusal marker
        # anchored on the gate's ok line would report a gate that examined
        # everything and found nothing as a gate that could not look - and it
        # would do so on the very cases that prove the gate works.
        if observed == GOOD and unknown_sig is not None and unknown_sig.search(output):
            res.verdict = UNRESOLVED
            res.details.append(
                f"control.json unknown_signal /{raw_unknown}/ also matches this gate's CLEAN "
                f"output on case {case['name']}, so it reports a working gate as having refused"
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
        # A REFUSAL IS **NOT** PROOF THE GATE'S TOOL WAS PRESENT, and the first
        # cut of #1129 had this wrong. It admitted UNKNOWN here, reasoning that
        # precedence puts `unavailable_signal` first, so a refusal must mean the
        # gate got PAST its own availability check.
        #
        # That reasoning assumes every gate checks its tool before it validates
        # its input, and the counter-model review of this change disproved it
        # (codex/gpt-6-astra, MEDIUM) against the very gate #1129 registers:
        # `scripts/shellcheck-gate.sh` refuses a non-directory `--root` on line
        # 52 and only reaches `command -v shellcheck` on line 53. So on a host
        # WITHOUT the tool, such a case refuses for an input reason while every
        # other case reports the tool absent - and counting the refusal as
        # "it ran" produced the #1117 contradiction verdict, whose sentence
        # asserts "the tool was present". That is a confident false statement
        # about the machine, made by the file whose entire subject is verdicts
        # nothing entitles you to, and it would defeat `--allow-unavailable` for
        # a plain environment failure.
        #
        # Only a CLEAN RUN or a GENUINE DETECTION proves the gate ran: each
        # requires the gate to have reached the work. A refusal may come from
        # anywhere, including before the tool was ever looked for.
        if observed in (GOOD, BAD):
            ran_cases.append(case["name"])
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
        if signal_is_declared and expected == GOOD and observed == GOOD and signal.search(output):
            res.verdict = UNRESOLVED
            res.details.append(
                f"control.json detect_signal /{raw_signal}/ also matches this gate's known-GOOD "
                f"output, so it identifies a clean run as readily as a finding"
            )
            return res
        if observed != expected:
            res.verdict = BLIND
            res.details.append("the gate did not discriminate: it " + _mismatch(expected, observed))
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
    if unavailable_cases and ran_cases:
        res.verdict = UNRESOLVED
        res.details.append(
            f"control.json unavailable_signal /{raw_unavailable}/ reports the gate's tool absent "
            f"on case(s) {', '.join(unavailable_cases)} while case(s) {', '.join(ran_cases)} "
            f"produced a real verdict through the same gate, so the tool was present. A missing "
            f"binary is missing for every case; this pattern is matching something else "
            f"(issue #1117)"
        )
        return res
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

    #: Cases the anchor must AGREE with the current gate on. GOOD cases carry
    #: the original anchor-sanity property: an anchor that disagrees there
    #: differs for reasons beyond the blindness under test, so the demonstration
    #: is not isolated.
    #:
    #: AN UNKNOWN CASE IS HELD TO THAT SAME STANDARD BY DEFAULT, not a new
    #: one (issue #1129). The anchor must refuse where the gate refuses. That is
    #: the conservative direction - it refuses MORE, never less - and the
    #: alternative was considered and rejected: accepting either agreement OR
    #: blindness would admit two outcomes, discriminate less, and invent a third
    #: anchor semantics for no gain.
    #:
    #: THAT REJECTION STILL STANDS AS WRITTEN, AND IT IS WHY `anchor_expect` IS
    #: A PER-CASE DECLARATION RATHER THAN A RELAXED RULE (issue #1157). Taking
    #: its three objections one at a time, because only one of them reaches the
    #: field below and it would be easy - and wrong - to claim none do:
    #:
    #:   "admit two outcomes"  does NOT reach it. A declared expectation admits
    #:       exactly ONE outcome per case and reds on anything else.
    #:   "discriminate less"   does NOT reach it; it follows from the first.
    #:   "invent a third anchor semantics"  DOES REACH IT. There were exactly
    #:       two - GOOD/UNKNOWN must AGREE, BAD must MISS - and `anchor_expect:
    #:       clean` is a third. The field does not avoid inventing one; it IS
    #:       the third semantics.
    #:
    #: What defeats the third objection is its own final clause - FOR NO GAIN -
    #: and the gain is measurable rather than argued. MEASURED on the register
    #: at e9a58b6: 45 controls, 190 cases, and UNKNOWN = 1. One refusal case in
    #: the whole register, because the rule below forbade the rest.
    #:
    #: THE COST IT WAS PAYING, which is a property of the PAIR rather than of
    #: either file: an anchor frozen from before a gate's refusal branch existed
    #: reports CLEAN where the gate refuses, lands INERT, and thereby forbade
    #: any UNKNOWN case on that control while it stood. Same shape as the
    #: `sh-extension` entry in controls/shellcheck-gate, and found the same way.
    #: MEASURED on controls/ci-coverage, which is why #1146 could not register
    #: the two trees it had already committed:
    #:
    #:     gate    exit 2  "UNKNOWN - derived 0 prerequisites ... the population
    #:                      is empty, so a clean verdict would rest on nothing"
    #:     anchor  exit 0  "ok - 2 declaration(s) found: 1 run in CI, 1 excluded"
    #:
    #: The anchor answers with a CONFIDENT COUNT over a population the gate
    #: refuses to judge. That is the blindness the case exists to demonstrate,
    #: so a case may now DECLARE it - and pay for the declaration with a
    #: recorded reason - instead of being refused registration for it.
    #:
    #: The default is unchanged and fail-closed: no `anchor_expect` means "must
    #: agree", and a declaration that stops being true reds as UNRESOLVED rather
    #: than decaying into silence.
    sanity_cases = [
        (control_dir / c["input"], c["expect"], c.get("anchor_expect"))
        for c in cases
        if c["expect"] in (GOOD, UNKNOWN)
    ]
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
            observed = _observe(code, good_exit, output, signal, unavailable, unknown_sig)
            # The anchor is a DIFFERENT PROGRAM, so the gate-side rules about the
            # refusal marker say nothing about its output (issue #1129,
            # counter-model review).
            fault = _anchor_output_fault(
                output, observed, signal, unknown_sig, raw_unknown, raw_signal,
                "the known-bad input",
            )
            if fault:
                res.verdict = UNRESOLVED
                res.details.append(f"anchor {anchor['sha']} {fault}")
                return res
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
            # REFUSING IS NOT CATCHING (issue #1129). Without this branch an
            # anchor that declined to examine the known-bad input falls into the
            # `observed != GOOD` arm below and is reported INERT - "it CAUGHT the
            # known-bad input" - which accuses a perfectly blind artifact of
            # being load-bearing and sends someone to replace it. The anchor did
            # not catch anything; it said it could not look, and the required
            # property is simply not established. Same narrowing #946 made for a
            # crashing anchor, for the same reason.
            if observed == UNKNOWN:
                res.verdict = UNRESOLVED
                res.details.append(
                    f"anchor {anchor['sha']} REFUSED the known-bad input rather than examining "
                    f"it, so it cannot be confirmed to have MISSED it"
                    + (f" [stderr: {diag}]" if diag else "")
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

        for case_path, case_expect, anchor_expect in sanity_cases:
            #: "known-GOOD" for a GOOD case, "known-UNEXAMINABLE" for an UNKNOWN
            #: one. The property is identical - the anchor must AGREE - but a
            #: message naming the wrong kind of input sends a reader looking for
            #: a clean-run disagreement that is not there.
            kind = "known-GOOD" if case_expect == GOOD else "known-UNEXAMINABLE"
            code, output, diag = _invoke(invocation, anchor_path, case_path, root)
            if code is UNRUNNABLE:
                res.verdict = UNRESOLVED
                res.details.append(f"anchor {anchor['sha']} could not be executed - {diag}")
                return res
            observed = _observe(code, good_exit, output, signal, unavailable, unknown_sig)
            # As in the known-bad loop above, and needed separately: an anchor can
            # miss the known-bad input correctly and still be incoherent on the
            # inputs meant to establish it differs in nothing else.
            fault = _anchor_output_fault(
                output, observed, signal, unknown_sig, raw_unknown, raw_signal,
                f"a {kind} input",
            )
            if fault:
                res.verdict = UNRESOLVED
                res.details.append(f"anchor {anchor['sha']} {fault}")
                return res
            if observed == UNAVAILABLE:
                res.verdict = UNRESOLVED
                res.details.append(
                    f"anchor {anchor['sha']} reports its tool absent on a {kind} input while "
                    f"the current gate ran, so the anchor-sanity check cannot be resolved"
                )
                return res
            if observed is UNSIGNALLED:
                res.verdict = UNRESOLVED
                res.details.append(
                    f"anchor {anchor['sha']} exited {code} on a {kind} input without the "
                    f"declared detection signal, so the anchor-sanity check cannot be resolved "
                    f"(it may have crashed)"
                    + (f" [stderr: {diag}]" if diag else "")
                )
                return res
            #: WHAT THE ANCHOR IS HELD TO. Absent `anchor_expect`, it is the
            #: gate's own verdict - the original property, unchanged for every
            #: case that does not declare otherwise. A case declaring `clean`
            #: asserts the opposite: this anchor cannot derive the population at
            #: all, so it returns a confident GOOD where the gate refuses, and
            #: THAT is the blindness the case exists to show.
            expected = GOOD if anchor_expect == "clean" else case_expect
            if observed != expected:
                if anchor_expect == "clean":
                    #: NOT INERT, AND THE DIFFERENCE IS THE WHOLE POINT OF
                    #: HAVING SEVEN VERDICTS. INERT means "the anchor is not
                    #: blind enough, replace it" - which here would send someone
                    #: to discard an anchor that has just been shown to be MORE
                    #: capable than the manifest records. Nothing is wrong with
                    #: the anchor or the gate; the REGISTRATION is stale, which
                    #: is UNRESOLVED's own definition ("the manifest is
                    #: incomplete... NOT a failure of the gate").
                    res.verdict = UNRESOLVED
                    res.details.append(
                        f"anchor {anchor['sha']} is declared blind on a {kind} input "
                        f"(anchor_expect: clean) but observed {observed}, so it CAN derive the "
                        "population the declaration says it cannot. The recorded "
                        "anchor_expect_reason is stale: correct the registration rather than "
                        "replacing the anchor"
                    )
                    return res
                res.verdict = INERT
                res.details.append(
                    f"anchor {anchor['sha']} disagrees with the current gate on a {kind} input "
                    f"(anchor observed {observed}, the gate {case_expect}), "
                    "so it differs for reasons beyond the blindness under test"
                )
                return res

    res.verdict = PASS
    return res


def _headline(
    results: list[Result],
    census: Census,
    members: int | None,
    nonmembers: list[str] | None,
    whence: str,
    registered: int | None = None,
) -> str:
    """The sentence everyone quotes - as a relationship, not a fraction (#1036).

    `21 of 89 enumerated instruments carry a control that discriminates` was
    two independently-derived counts printed as one ratio. The numerator was
    REGISTERED CONTROLS, the denominator ADR 0008 CENSUS ROWS, and nothing
    asserted a registered control's gate appeared in the census at all - so the
    line read "21 of the 89 are controlled" and meant "21 controls exist, some
    unknown number of which are among the 89". A registered control whose gate
    was absent from the census produced exactly the same output as one present.

    Three facts now, each with its own population:

      how many controls were REGISTERED AND DISCRIMINATE          (the numerator)
      how many of those are CENSUS MEMBERS, and which are not     (the relation)
      what the DENOMINATOR is made of                             (the composition)

    A non-member is NAMED. That is the whole remedy asked for, and it is derived
    - there is no list to maintain and no exception to remember.

    `results` IS THE DISCRIMINATING POPULATION AND `registered` IS EVERY
    REGISTRATION (issue #1117). They were the same number until UNAVAILABLE
    existed, because anything short of PASS failed the run and never reached
    this sentence. They can differ now, and the sentence keeps them apart on
    purpose: "23 registered" is a fact about the register, "21 of 90 carry a
    control that discriminates" is a fact about this run, and collapsing them
    would let an unexamined control read as a covered instrument.
    """
    discriminating = len(results)
    total = discriminating if registered is None else registered
    if census.rows is None:
        return (
            f"{discriminating} discriminating control(s) of {total} registered, against an "
            f"UNKNOWN universe ({whence}) - this is a sample, and how large a sample "
            "cannot be said"
        )
    if members is None or nonmembers is None:
        return (
            f"{total} registered; how many are among the {census.rows} enumerated "
            f"instruments ({whence}) is UNKNOWN - {census.disagreement or 'the census subjects could not be read'}"
        )

    outside = (
        "none registered outside the census"
        if not nonmembers
        else f"{len(nonmembers)} registered OUTSIDE the census ({', '.join(nonmembers)})"
    )
    composition = (
        ""
        if census.external is None
        else (
            f"; the denominator is {census.rows - census.external} registrable + "
            f"{census.external} external subject(s) with no file under scripts/ for a "
            "marker, reachable only by wrapping"
        )
    )
    return (
        f"{total} registered, {members} of {census.rows} enumerated instruments "
        f"({whence}) carry a control that discriminates, {outside}{composition}; "
        f"discovery reads {DISCOVERY_SCOPE}"
    )


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
    #: A SYNTHETIC ANCHOR HAS NO HISTORICAL ARTIFACT TO BE COMPARED WITH, so the
    #: git step below cannot say anything about it (issue #1157). Its `sha` is
    #: `0000000` by construction and its `origin` is a SENTENCE describing the
    #: design it embodies, not a path - so the lookup is meaningless, and the
    #: digest check above is the whole of what provenance can establish here.
    #:
    #: THIS WAS NOT THEORETICAL, AND THE MECHANISM IS EXACT. When the string
    #: after the colon contains PATHSPEC GLOB METACHARACTERS, git stops reading
    #: the argument as `<rev>:<path>` and reads it as a PATHSPEC - and a
    #: pathspec that matches nothing exits 0 with no output and no stderr.
    #: Reproduced in a fresh repository, one variable at a time:
    #:
    #:     git show '0000000:plain'         -> 128, "invalid object name"
    #:     git show '0000000:has[^-]glob'   -> 0, zero bytes, empty stderr
    #:     git show '0000000:star*'         -> 0, zero bytes, empty stderr
    #:     git cat-file -e '0000000:...'    -> 128 for BOTH
    #:
    #: So it is conditional on the ORIGIN TEXT, not on the sha: an origin
    #: sentence containing a regex or a wildcard takes the silent path and a
    #: plain one takes the loud path. That is why exactly one of this
    #: repository's five synthetic anchors was affected -
    #: controls/deletion-accounting, whose origin quotes the pattern `^-[^-]`.
    #: Its `returncode != 0` guard never fired, the empty output was hashed, and
    #: the control was accused of disagreeing with a commit that does not exist:
    #: a command reporting success while establishing nothing, its emptiness
    #: read as content, inside the file written for that defect.
    if anchor.get("kind") == "synthetic" or anchor.get("sha") in ("0000000", "n/a", ""):
        return "unverified"
    #: EXISTENCE FIRST, WITH A PROBE THAT ACTUALLY REFUSES (#1157 counter-model
    #: re-review, MEDIUM). `git show` is not an existence test: on a reference it
    #: cannot resolve it can exit 0 and print NOTHING, so a caller hashing its
    #: stdout compares sha256("") against a real file and calls that MISMATCH.
    #: `git cat-file -e` answers the question actually being asked - measured on
    #: the reference that caused this: cat-file -e exits 128 where show exits 0.
    #:
    #: THE FIRST FIX FOR THIS WAS "empty stdout means unverified", AND IT WAS
    #: WRONG IN THE OTHER DIRECTION: a zero-byte file is a legitimate committed
    #: artifact (this repository tracks several), so that rule excused a real
    #: historical anchor from verification entirely - replace the file with
    #: content, update the manifest digest, and it verified as `unverified`
    #: instead of MISMATCH. Establishing existence separately lets the byte
    #: comparison include empty content, which is the only shape that is right
    #: in both directions.
    try:
        probe = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", f"{anchor['sha']}:{anchor['origin']}"],
            capture_output=True, timeout=30, check=False,
        )
        if probe.returncode != 0:
            return "unverified"
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
    #: A NARROWING SELECTOR, added for issue #970's mutation probe, which needs to
    #: ask "did THIS control notice" rather than "did the register notice". Running
    #: the whole register to answer that dilutes the signal in both directions: an
    #: unrelated control already red makes every mutation read as caught, and 22
    #: healthy controls do not make the 23rd's silence any quieter.
    #:
    #: A selector that silently selects NOTHING is the hazard, not the feature - it
    #: turns an empty run into an exit-0 "clean". So a `--control` that matches no
    #: registration refuses, non-zero, WITHOUT `--strict`: an unmatched selector is
    #: an unchecked run, which is the same rule the no-registrations branch below
    #: already applies to the whole register.
    parser.add_argument("--control", default=None, metavar="REL",
                        help="evaluate only the control registered at this path "
                             "(e.g. controls/shellcheck-gate); refuses if it matches nothing")
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    stamp = _source_stamp(root)
    registrations = discover(root)

    if args.control is not None:
        wanted = args.control.rstrip("/")
        registrations = [pair for pair in registrations if pair[1].rstrip("/") == wanted]
        if not registrations:
            print("NEGATIVE_CONTROL_SOURCE: " + stamp)
            print("NEGATIVE_CONTROL_REGISTERED: 0")
            print(f"negative-controls: --control {args.control!r} matched no registration - "
                  "nothing was checked. This is UNCHECKED, not clean.", file=sys.stderr)
            return 1

    # The universe is a property of the TREE, not of the results, so it is stated
    # on every exit including the ones that found nothing (#979). A run that
    # reports no denominator is the defect whatever its verdict.
    census = instrument_census(root)
    universe, whence = census.rows, census.whence
    universe_line = f"NEGATIVE_CONTROL_UNIVERSE: {universe if universe is not None else 'unknown'}"

    # WHERE THE MARKERS WERE LOOKED FOR, on every exit (issue #1036). A register
    # that reports its count without its search scope invites the reader to take
    # the count as a statement about the repository; it is a statement about
    # `scripts/`.
    scope_line = f"NEGATIVE_CONTROL_DISCOVERY_SCOPE: {DISCOVERY_SCOPE}"

    if not registrations:
        print("NEGATIVE_CONTROL_SOURCE: " + stamp)
        print("NEGATIVE_CONTROL_REGISTERED: 0")
        print(universe_line)
        print(scope_line)
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
    print(scope_line)
    # A COUNT ON EVERY RUN, INCLUDING ZERO (issue #1117). A line that appears
    # only when something is unexamined cannot be told from a line nobody
    # emitted, so a consumer reading it would learn "unexamined: absent" and have
    # no way to know whether that means none or means an older harness.
    unavailable_results = [r for r in results if r.verdict == UNAVAILABLE]
    print(f"NEGATIVE_CONTROL_UNAVAILABLE: {len(unavailable_results)}")

    # THE RELATIONSHIP BETWEEN THE TWO NUMBERS, not two numbers side by side
    # (issue #1036). Every discovered registration's gate is resolved against
    # the census's own subjects, and a gate that is not among them is NAMED.
    # Without this, `21 of 89` reads as "21 of the 89 are controlled" while
    # meaning "21 controls exist, an unknown number of which are among the 89".
    #
    # A NON-MEMBER IS REPORTED, NOT FAILED, and that is a decision rather than
    # an oversight: whether it should fail is a separate question (the issue
    # says so in terms), and printing the fact does not pre-empt it. What is
    # closed here is that the two states used to produce identical output.
    members, nonmembers = census_membership(registrations, census)
    print(f"NEGATIVE_CONTROL_CENSUS_MEMBERS: {'unknown' if members is None else members}")
    print(f"NEGATIVE_CONTROL_CENSUS_NONMEMBERS: "
          f"{'unknown' if nonmembers is None else len(nonmembers)}")
    for name in nonmembers or []:
        print(f"NEGATIVE_CONTROL_CENSUS_NONMEMBER: {name}")
    if census.disagreement:
        print(f"NEGATIVE_CONTROL_CENSUS_UNREAD: {census.disagreement}")
    print(f"NEGATIVE_CONTROL_UNIVERSE_EXTERNAL: "
          f"{'unknown' if census.external is None else census.external}")
    registrable = (
        None if census.rows is None or census.external is None
        else census.rows - census.external
    )
    print(f"NEGATIVE_CONTROL_UNIVERSE_REGISTRABLE: "
          f"{'unknown' if registrable is None else registrable}")

    for res in results:
        print(f"NEGATIVE_CONTROL_GATE: {res.gate}")
        # WHICH CONTROL, not just which gate (issue #1117). A gate may carry
        # several registrations - #986 made discovery see them all - and until
        # this line existed the blocks for two controls on ONE gate were
        # byte-identical in their only identifying field. A reader chasing a
        # failure, and any consumer scoping an assertion to one control, would
        # have silently addressed whichever came first. The Result has carried
        # `control_dir` since the beginning; it was simply never printed.
        print(f"NEGATIVE_CONTROL_CONTROL: {res.control_dir}")
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
    # PROVENANCE IS A THIRD AXIS AND IT IS NOW READ (issue #1157). It was
    # computed on every run, printed on every run, and consumed by nothing: a
    # control could report `NEGATIVE_CONTROL_PROVENANCE: MISMATCH` beside
    # `NEGATIVE_CONTROL_VERDICT: PASS` and the gate stayed green. Observed on a
    # real branch, where a manifest sat on a digest two edits old through a full
    # green `make verify` - the disagreement was on screen the whole time.
    #
    # A reader seeing both lines reasonably assumes the verdict accounted for
    # the one above it. It did not, and that is worse than not printing it: the
    # parser defects this file guards against lose evidence BEFORE the verdict,
    # while this had the evidence, correct, and did not look at it.
    #
    # `unverified` MUST NOT FAIL, and keeping that distinction is the whole
    # reason this is safe to switch on: it is the ordinary state of a synthetic
    # anchor, of a run without `--verify-provenance`, and of the CI image, which
    # has no git. Only MISMATCH - the recorded digest disagreeing with the bytes
    # actually committed - is a claim that something is wrong.
    failing = [
        r for r in results
        if (r.verdict != PASS or r.tracking == "UNTRACKED" or r.provenance == "MISMATCH")
        and id(r) not in excused
    ]
    if not args.quiet:
        print()
        if failing:
            for res in failing:
                #: NAME THE AXIS THAT FAILED. Printing the VERDICT alone produced
                #: lines reading `negative-controls: scripts/x.sh -> PASS` for a
                #: control that had just failed on tracking or provenance - a
                #: failure announcing a pass, which cost a reader real time
                #: (#1061) before it cost this line.
                axes = [res.verdict] if res.verdict != PASS else []
                if res.tracking == "UNTRACKED":
                    axes.append("UNTRACKED")
                if res.provenance == "MISMATCH":
                    axes.append("PROVENANCE:MISMATCH")
                print(f"negative-controls: {res.gate} -> {'/'.join(axes) or res.verdict}")
                for line in res.details:
                    print(f"    {line}")
        else:
            # The message states what this run actually established, including the
            # #946 half: every claim here has an input population behind it -
            # and, since #1036, the RELATION between the two populations rather
            # than the two numbers pressed together.
            #
            # THE POPULATION IS THE CONTROLS THAT DISCRIMINATED, not every
            # registration (issue #1117). Those were the same set until
            # UNAVAILABLE existed, because anything short of PASS made the run
            # fail and never reached this branch. Under `--allow-unavailable` an
            # unexamined control DOES reach it, and counting it among the ones
            # that "carry a control that discriminates" would be a fresh
            # overclaim introduced by the change that exists to stop one.
            #
            # Membership is therefore re-derived over the discriminating
            # registrations alone. The CONTRACT lines above keep #1036's own
            # population - every discovered registration - because the question
            # they answer ("is this control's gate in the census at all?") is
            # about registration, not about how the run went.
            discriminating = [r for r in results if r.verdict == PASS]
            disc_registrations = [
                reg for reg, res in zip(registrations, results) if res.verdict == PASS
            ]
            disc_members, disc_nonmembers = census_membership(disc_registrations, census)
            headline = _headline(
                discriminating, census, disc_members, disc_nonmembers, whence,
                registered=len(registrations),
            )
            # THE KIND BREAKDOWN IS NAMED, NOT IMPLIED (issue #1085). The
            # residual risk this design cannot close is a GATE author declaring
            # `reporter` to escape needing a BAD case - a mis-declaration, not
            # a mechanism failure, and the only defence against it is that
            # somebody SEES it. A count in the summary is how: a reporter
            # arriving in this repository changes a number on a line everyone
            # already reads. Same doctrine as printing members rather than
            # totals, pointed at the taxonomy itself.
            gate_rs = [r for r in discriminating if r.subject_kind == GATE_SUBJECT]
            reps = [r for r in discriminating if r.subject_kind == REPORTER_SUBJECT]

            # THE CLAIM IS BUILT FROM THE POPULATION, NOT ASSERTED OVER IT
            # (counter-model finding, 2026-09-22). This line used to end "each
            # reporting its declared detection signal on the known-bad input"
            # UNIVERSALLY, and then append the kind breakdown after it. Over a
            # battery of reporters that certified a detection that cannot
            # happen: a reporter has no known-bad input and emits no detection
            # signal, by the same structural fact that made this whole change
            # necessary. The appended explanation EXPLAINED the contradiction
            # instead of removing it, which is a success message claiming more
            # than its input population supports - the exact question this file
            # makes every other gate answer.
            claims: list[str] = []
            if gate_rs:
                claims.append(
                    f"{len(gate_rs)} gate control(s), each reporting its declared detection "
                    f"signal on the known-bad input and demonstrated against an anchor that "
                    f"misses it"
                )
            if reps:
                claims.append(
                    f"{len(reps)} reporter control(s) ("
                    + ", ".join(sorted(r.control_dir for r in reps))
                    + "), each REFUSING an input its anchor answers clean - a reporter has no "
                      "known-bad input to detect, so it demonstrates blindness on the refusal "
                      "axis instead"
                )
            if not claims:
                claims.append("0 gate control(s) and 0 reporter control(s)")
            print(f"negative-controls: ok - {headline}; " + "; ".join(claims))
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
