# Readers of a changed output

When a change alters what one part of the system writes, something else reads
it. This document is the canonical statement of what a plan and a closing
report say about those readers, and of the judgement a reviewer applies to the
tests that claim to cover them. Other surfaces point here; they do not restate
it.

## Why this exists

The clear case is kyle#2309. A server response gained a field. The client that
reads it accepted only the older shape, and the client's test fed it a
hand-written copy of that older shape. Both sides stayed green while the real
pair was broken, and a real job hit it.

Every route was tested. Each was tested against a copy of the other side.

This is a different gap from [lanes](lanes.md). A lane miss is a route nobody
exercised. Here the route was exercised, with a stand-in where the real thing
should have been.

## What counts as a changed output

Anything another part parses or branches on: a response shape, a file format, a
status or verdict line, an exit code, the fields of a record, a generated file
an installer copies. In this repository: a script's `NAME: verdict` line read
by a gate or a command document; a receipt read by a later step; a helper's
JSON read by another helper.

A change that alters no such output says so in one line, and carries no rows.

## At plan approval

The plan names each reader it knows of and answers it with one of:

| Answer | Meaning |
|---|---|
| tested against real output | A test in this change feeds the reader what the writer actually produces; name the test |
| reader unchanged | The reader does not see the altered part; say why that is safe |
| not covered | A known gap, stated before the work starts |

The rows go in the SAME table as the lanes, as `Reader: <who reads it>`, so a
plan gains one block and not two. The table exists for a reader row even in a
project with no lane file: the reader rule does not depend on lanes being
adopted.

**Say how readers were looked for.** "No readers" is a result, not an
assumption, so the plan states the search it ran. A search that can find
nothing is not evidence: show it finding a known reader of some existing output
first, or say that was not checked. A reader in ANOTHER repository will not be
found by a search here and is named from knowledge; a change to an output Kyle
or skillc is known to read says so.

## A stand-in is not evidence

A hand-written copy of the other side's output shows that the reader handles
the copy. It says nothing about the pair. Where a stand-in is unavoidable - the
writer needs a network, a paid service, a second machine - the plan says what
keeps the stand-in in step with the real output, and the row reads `not covered`
if the answer is nothing.

## The same judgement, applied to lane tests

A lane marked `will test` needs more than a test that exists. The reviewer
reports a test that:

- reaches the lane or the reader only through a stand-in where the real thing
  could be used; or
- could not fail if the lane or the reader were broken.

The second is the negative-control question asked of a single test: name the
input that would make it report the other verdict.

## At close

The closing report's Evidence carries the reader rows with what happened,
beside the lane rows, and a row that differs from the plan is explained. When a
defect later turns out to be this shape, its fix says so with
`Missed because: reader not tested against real output`
([the closing-report contract](closing-report-contract.md#a-report-that-closes-a-defect-says-where-it-came-from)).

## Where it applies

Tier 2 and Tier 3 work that changes behaviour, as for lanes.

## What enforces this, and what does not

**The routing is enforced.** `tests/test_changed_output_readers.py` asserts
that this document states the three answers, that the issue contract, the
closing-report contract, the lanes reference, `/flow:eli5` and
`/codex:code_review` each link here, that the review prompt carries both
questions, and that the reader question is asked whether or not the project has
a lane file.

**The table and the tests it names are not machine-checked.** There is no gate.
Two readers check them: the approver at plan approval, and the counter-model
review, which asks whether the diff changes an output with a reader the plan
does not name, and whether each claimed test uses the real thing and could
fail.

**The second reader is a model, so its red case is a model's judgement on a
committed example pair, not a repeatable check.** `tests/fixtures/readers/`
holds two pairs:

- a writer gains a field and the reader's test uses a hand-written copy
  (`plan-stale-stub.md`), against the same change with the reader fed the
  writer's real output (`plan-real-output.md`);
- a lane marked `will test` and covered only by a stand-in
  (`plan-lane-stub-only.md`), against the same lane exercised for real
  (`plan-lane-real.md`).

Both questions were put to Codex (`gpt-6.1-sol`) over all four plans on
2026-11-11, twice: once with a first wording and once with the wording that
shipped. Each time it reported the hand-written copy in the first pair and the
stand-in in the second, naming the real thing that was available, and reported
nothing for either sound plan. That is eight runs agreeing. It does not
establish that a ninth will, and the plans are small and plain; a stand-in
buried in a large diff is a harder case nobody has measured. To repeat it, hand
the reviewer each plan with the two questions from `/codex:code_review`, and
the fixture lane list (`tests/fixtures/lanes/lanes.md`) for the lane pair.

**Not covered.** The delegated-driver review surfaces (`/codex:auto`,
`/qwen:auto`, `/gemma:auto`) ask neither question. A reader nobody knows about
produces a table that looks complete.
