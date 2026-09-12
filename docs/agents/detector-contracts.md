# Detector Contracts

A check, gate, guard, tripwire or allowlist makes a claim. This document is the
canonical statement of what that claim has to be able to say, and of the two
questions a reviewer asks of any diff that adds or changes one.

It exists because the pattern below was diagnosed twenty-one times across two
repositories and written down in exactly one place: issue #834. A shape that
lives in one issue cannot be applied in review, so the next instance has nothing
to reference. Other surfaces point here; they do not restate it.

## The shape

**A detector answers the question it was built for. Its reader supplies a larger
one.** Both statements are true of the code; only the narrow one is true of the
check.

The failure is never a wrong answer. It is a *correct narrow answer read as a
broad one*, which is why ordinary review does not catch it: the code does exactly
what it says, and what it says is not what the caller needs.

## The two questions

Ask both of any check in a diff. They are the whole contract; everything below is
evidence that they are worth asking.

### 1. Membership floor

> **Does this check's success message claim more than its input population
> supports?**

Not "did it examine anything" - a check that examines nothing can still be
honest. The distinction is between reporting a count and asserting a universal.
Two gates in this repository, measured against an empty input:

| gate | on an empty input | honest? |
|---|---|---|
| `check-claude-md-budget.py` | `ok - 0/2000 words`, exit 0 | **yes** - a numeric aggregate; the number *is* the population count |
| `check-claude-md-links.py`, before #841 | `ok - every repository-local pointer resolves`, exit 0 | **no** - vacuously true over zero pointers |
| `check-claude-md-links.py`, after #841 | `contains no repository-local pointers - nothing was checked`, exit 1 | **yes** - the empty population is now a state it can report |

Both original forms exited 0 having examined nothing. Only one was a defect,
because only one asserted something about every member of a set it never
established was non-empty. A count reports what it found; a universal claim over
an empty set reports a guarantee it never tested. The third row is the remedy
landed (#847) and is what "fixed" looks like: not a wider scan, but a detector
that can now say the one thing it previously could not.

The remedy is that the detector must be able to **represent the state it
currently cannot see**. A fixed set of four names cannot represent a fifth; an
iteration over the installed side cannot represent a missing item; a `0` returned
because the directory does not exist cannot be told from a `0` that means clean.

### 2. Ownership boundary

> **Can a non-zero from this check distinguish "our thing changed" from
> "something that is not ours changed"?**

If not, an unrelated neighbour produces a finding, or worse is silently counted
as ours. Watcher-shaped argv belonging to a different mailbox satisfies a
watcher-shaped search (#821). A variable that is shaped like a per-session
variable while being a property of the parent process is forwarded by a check
keyed on the shape (kyle#994).

The inverted form is worth naming separately: a *correct broad* answer can be
overridden by a narrow one. In #869 `kill -0` correctly says the pid is dead and
the presence of a socket file says otherwise, and the file wins. Here the narrow
check does not merely get over-read - it defeats the broad one.

## Writing the answer into the code

For any check in a diff, ask the two questions and **write the answer into the
code as a test.** A comment saying what the check does not cover decays; a test
named for the state the detector cannot currently represent does not.

Two test shapes carry this, and a reviewer should expect to see the relevant one:

- **A positive control**, proving the detector is capable of firing at all.
  Prior art: `tests/test_pythonpath_lib_depth.py::test_depth_detector_can_fire`
  (#816).
- **A named residual**, pinning a known blind spot as a property rather than a
  TODO. Prior art:
  `tests/test_flow_wave_mailbox.py::test_a_same_wave_orphan_would_not_be_excluded_by_directory_alone`
  (#821).

A test that passes over an empty population proves nothing, and is itself an
instance of question 1. This applies to the tripwire guarding this document:
`tests/test_detector_contracts.py` asserts its own surface list is non-empty and
complete before asserting anything about the surfaces in it.

## A worked example, from this repository's own tooling

`scripts/flow-driver-capability.sh` decides which driver an issue may run on. Asked
about #834 - the issue that produced this document - it answered:

```
FLOW_DRIVER_NEEDS=implementation
FLOW_DRIVER_CHECK: fit
```

That answer is correct. The deliverable *is* a source diff, not research and not a
live-source question, which is what the three declared axes (`scope`, `web`,
`container`) are about. Its reader took it for **"can this driver do this issue?"**
- and the #735 execution fence forbids the delegated driver from reading
`.claude/commands/**`, which is where five of #834's nine files live. The driver
was structurally inapplicable and the preflight said `fit` (#877).

This is question 1 in a non-obvious dress. The check's input population was the
deliverable's **kind**; the population it needed was the deliverable's **paths**.
There is no axis for "the planned file list intersects the fence", so the check
cannot represent the state that decides the answer - and `fit` therefore claims
more than its population supports.

It is the specimen worth remembering because both halves are inside this
repository's own tooling, and because the detector that mis-routed the issue about
detectors saying too little was the detector choosing that issue's driver. The
routing rule it implies - *an issue whose deliverable includes any file under
`.claude/commands/**` or `.claude/skills/**` runs on `/flow:auto`* - is #877's to
land, not this document's.

## When widening is not the remedy

**"Widen the detector" does not generalise, and assuming it does is how this
document would make things worse.**

`scripts/delegated-run-check.sh` (#836) is the strongest case. `is_fatal` is
scoped to the top level of an event *deliberately*: the recursive version existed,
made every fenced `git commit` attempt a failed run, and was reverted for a stated
reason that still holds. The header says it outright - *a guard against false
success that manufactures false failure is not an improvement.* The author knew
the scope exactly, documented it, and chose it correctly. The reader supplies the
larger question anyway.

So where the narrow answer is right, **the larger question needs somewhere else to
live** - a new channel, a caller-supplied postcondition, a separate signal - not a
widened existing one. That is a different and harder fix than widening, and
recognising which of the two you are looking at is the judgement this document
asks for.

## What the two open dependents answer

Stated here so each is implementable against this contract rather than against a
conversation:

| issue | question it answers | shape of the fix |
|---|---|---|
| #836 | **Ownership boundary**, in its hardest form: `DELEGATED_RUN_STATUS` cannot distinguish "the delegated *process* ran cleanly" from "the delegated *work* happened". A denied tool call satisfies every signal the checker has. | **Not** widening `is_fatal` - see above. The larger question needs its own home: a distinct non-fatal signal, or a caller-supplied postcondition. |
| #831 | **Membership floor**: `check-test-binary-guards.py` answers "is a *guarded* binary unguarded" and is read as "is *any* binary unguarded". A fixed set of four names cannot represent a fifth. | Make the set able to represent a binary nobody put on it. Measurement on the pinned CI image found no live gap behind it, so this is a correctness fix, not an outage fix. |

## Seven properties that let it survive review

These are why the two questions are worth asking explicitly rather than trusting
a careful reader to notice.

**It survives awareness.** The kyle#994 workaround named four variables and had no
floor for the namespace beside it - the same defect as the allowlist it was
working around. It was written by the person who had just diagnosed that
allowlist. Every other instance was written by someone who had not yet seen the
pattern; that one was not, which is the strongest available evidence that this is
a cognitive pull rather than a run of unrelated oversights.

**It survives correct scoping.** See "When widening is not the remedy" above.

**A narrow input set conceals it.** #833 was latent *because* `GUARDED_BINARIES`
held four long, distinctive tokens. Widening the set - the fix #831 asks for - is
what exposed it, producing 101 false findings from one `case` label. So "this has
never caused a problem" is not evidence a detector is sound; it can mean only that
nothing has yet been passed to it that its blind spot covers. Fixing one blind
spot exposes the next: #831 -> #833 -> #838 -> #840 -> #841 is a five-step cascade
in one file family, each step invisible until its predecessor closed.

**It appears in the instrument built to detect it.** A `/proc` scan written to
verify that every session held a live mailbox watch reported three watches for its
own session; two were the probe matching itself, because it matched on a substring
that is by construction inside the command line doing the matching. The useful
part is the direction: **self-matching inflates a count and cannot manufacture an
absence**, so the diagnosis it was built for ("this session has no watch") was
still sound - but sound by luck. Had the failure been "two watches racing", the
same instrument would have reported it backwards. An instrument whose error has a
known direction can still be trusted for the half of the question that direction
cannot reach, and that is a much narrower warrant than "the tool works".

**The gap can be self-inflicted by the instrument.** In kyle#997 the narrow answer
was manufactured rather than inherent: watch invocations ended `2>&1 | tail -40`,
and later `; echo "EXIT=$?"`. Both make the reported status that of a command that
cannot fail.

```
false | tail -1                    -> 0     pipeline exit = LAST command
false; echo x                      -> 0     compound exit = LAST command
set -o pipefail; false | tail -1    -> 1
bash -c 'exit 5' 2>&1 | tail -40    -> 0     <- the masking form
```

The conclusion drawn was "the harness masks the exit code", and the evidence for
it was the 0 the instrument had just forced. **The measurement apparatus produced
the artifact it then detected**, and because the same artifact was present in
every run, the false pattern looked consistent across hours - consistency read as
corroboration when it was a constant. A bare control run settled it in one attempt:
exit 5, reported accurately. The lesson is not "know the pipefail rule"; it is that
a reading taken *through* an instrument is not evidence about the state *without*
it, and the cheapest defence is a control with the instrument removed.

**It survives a relay, and the relay widens it.** A worker measured which Kyle
`steward` archetype exists and answered about `memory-steward`. The answer was
forwarded upward, over the forwarder's own signature, without re-measuring, as an
answer about `steward` - and used to argue that an operator's request named
something else. One `ls` on the same host would have shown four steward manifests.
The gap was introduced **by the act of passing the result along**: a forwarder
verifies claims they receive and stops verifying claims they transmit, as though
transmission were not also assertion, and the recipient cannot tell the two apart
because both arrive with the same signature on them. Remedy, same cost as the
others: **verify what you forward at the standard you verify what you receive.**

**Knowing the pattern confers no immunity.** While verifying #833's fix, a
reviewer checking for overcorrection asked `binaries_in_script()` whether three
scripts declared any mandatory guarded binary. All three returned `[]`, and that
was very nearly read as "the real invocations are still detected". It is not:
`[]` is also what you get when the name is not in the guarded set, which it was
not. Two questions with the same empty answer - question 1 again, in the
verification rather than in the code. It was caught because the uniformity looked
wrong, not because the check said so. This instance occurred inside a review
conducted *for* this pattern.

## The instance index

The twenty-one instances this contract was derived from. Kept here, in the guidance,
rather than in the issue that indexed them - a finding that lives only in a closed
issue is the condition #834 was filed to end. Link new instances here.

| instance | the check answers | the reader takes it for | state |
|---|---|---|---|
| #804 | did this step pass, in some run | did this tree pass | fixed |
| #808 | did the gates I know about run | did the gates run | fixed |
| #810 | did the base move in this window | did the base move | open |
| #816 / #819 | is this literal pattern present | is the invocation correct | fixed |
| #821 | is there watcher-shaped argv | is there a watcher on *my* mailbox | fixed |
| #823 | is the repo clean | is what sessions execute clean | fixed |
| #828 | does each installed helper match | is every helper installed | fixed |
| #831 | is a *guarded* binary unguarded | is *any* binary unguarded | open |
| #833 | is this name at command position | is this binary invoked | fixed |
| #835 | can this driver do implementation-scope / web work | can this driver do *this* task | fixed |
| #836 | did the delegated process exit clean | did the delegated work happen | open |
| #838 | is this name at command position | is this binary invoked (assignment, quoted text) | fixed |
| #840 | are the tests I found all guarded | are all tests guarded (0 when there are none) | fixed |
| #841 | do the pointers I found resolve | do all pointers resolve (vacuous over zero) | fixed |
| #845 | is there a watcher with this wave NAME | is there a watcher on this mailbox (ps lane) | fixed |
| #848 / #852 | did the merge happen | did the merge complete, cleanup included | #848 fixed, #852 open |
| #867 | has *anything* acknowledged this message | did the agent behind this role receive it | open |
| #869 | is there a socket file at this path | is that session alive | open |
| #877 | is this deliverable a code change | can this driver do *this issue* (fence-forbidden paths) | open |
| kyle#994 | is this variable one of the nine safe ones | is this variable safe to forward | fixed |
| kyle#997 | what did the task *wrapper* exit with | what did the *watch* exit with | fixed |

Three further instances have no issue number because they were found in
instruments and in relays rather than in shipped checks; they are described under
"Seven properties" above.

Three of these (#867, #869, #877) were filed after the index was written, and #877
was found while routing the work that produced this document. That is the standing
argument for keeping this file current rather than treating the class as closed.

## What this document does not do

It is guidance plus a routing tripwire, not a scanner. "Does this success message
claim more than its input population supports" is a question about the relationship
between a message and a population, and it is not mechanically decidable - a
checker for it would be an instance of the very pattern. What is enforced
mechanically is narrower and stated honestly: `tests/test_detector_contracts.py`
fails when a review surface stops pointing here, and the required test shapes above
are carried by review.
