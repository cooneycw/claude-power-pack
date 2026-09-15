# ADR 0007: Counter-model review is part of the default lifecycle

- Status: Accepted
- Date: 2026-09-15
- Issue: #934
- Supersedes: the separate `/flow:auto_codex` review stage
- Related: [ADR 0008](0008-instrument-negative-control-bound.md) (this stage's
  second product is red cases, which is what 0008's bound asks for, sourced from
  a model that did not author the design), [ADR 0009](0009-oscillation-control.md)
  (advisory-vs-blocking is a two-sided choice, so the triggers below are
  committed here before shipping), #932 (the `instrument` definition), #775 (the
  ELI5 gate's no-bypass property, untouched).

## TL;DR

A second model reads the branch before the PR exists, **by default**, as part of
`/flow:auto`. The rule is a property - *the reviewing model must not be the
implementing model* - not a tool name. It is **advisory**: findings never fail a
run. Every run writes a **receipt**, including a skip.

## The measurement, corrected

Issue #934 was opened on the finding that the stage had run on **0 of 200**
merged PRs. That number was true when written and is no longer. Re-derived on
2026-09-15 over merged PRs #585..#1000, with its positive control:

| | |
|---|---|
| merged PRs examined | 200 |
| bodies containing `Codex pre-PR review` | **21** |
| positive control (a marker known to be present) | 197 |
| empty bodies (which would fake a zero) | 0 |

Broken down by merge date, the shape is the point:

| window | ran / merged |
|---|---|
| 2026-07-18 .. 09-13 | **0 / 170** |
| 2026-09-14 | 4 / 7 |
| 2026-09-15 | 17 / 23 |

**What changed was not appetite.** A wave orchestrator declared
`driver: flow:auto_codex` in wave policy, and every worker in that wave drove on
it. So the thesis is not "nobody wants this stage". It is:

> An opt-in stage sitting next to a faster command exists exactly as long as
> someone with authority keeps re-imposing it per wave - and that mandate dies
> with the wave.

**Observer effect, stated rather than buried.** The number moved because of an
intervention by the party doing the measuring. That does not invalidate it - the
two-month zero is untouched, and the intervention is precisely the mechanism the
corrected thesis describes - but a later reader should not discover it for
themselves inside a footnote.

## The decision

1. **The stage runs in `/flow:auto` Step 6, by default.** Not a separate command,
   not a tenth step.
2. **The rule is a property, not a tool name.** `/codex:code_review` satisfies it
   today; a `qwen:auto` or `gemma:auto` lane inherits the requirement with no
   edit, and the rule survives the lane topology changing.
3. **A skip is a recorded state**, with one of a closed set of reasons. Not an
   omission.
4. **It is advisory.** No finding fails a run. See the triggers below.
5. **One invocation, two outputs**: findings, and - for every instrument the
   change adds or modifies - the input that should make that instrument report
   the other verdict. That is verbatim what the Negative Control directive
   demands, sourced from a model that did not author the design.

### Why not a numbered step

Making it `Step 5/10` renumbers `/flow:auto`, and seven files cite `Step 3/9` -
including both #775 no-bypass guards, which hardcode the total. That cascade
buys prominence, and **prominence was never the defect**: the stage went unused
for 170 PRs because it lived in a separate command, not because it was
insufficiently visible inside one.

### Why not tier-bound

Issue #934 asks for the stage to be bound to tier: Tier 1 skips, Tier 2/3 gets
it. **There is no tier signal to bind to.** No `tier-1`/`tier-2`/`tier-3` labels
exist (the label list carries a stray `tier-4` and nothing else); 4 of 23 open
issues carry any label at all; and "tier" appears only in `/evaluate:issue` and
`spec/help.md` as prose about the concept. A search for a declared tier in issue
bodies finds only sentences *about* tiers.

So tier binding is deferred to a ticket that first makes tier a signal. What
ships instead is the property that matters more: **absent information reads as
RUN, never as skip.** Skip-by-omission is precisely the mechanism that produced
0 of 170.

## The receipt

`scripts/counter-model-receipt.py` writes one JSON file per run under
`docs/measurements/counter-model/`.

**Why not the PR body.** The stage used to record itself by appending a heading
to the PR body, which made adoption countable. That is a **marker**: written by
the thing being measured, and defeated by whoever writes it. PR #1000 ran two
review passes and fixed eleven findings, and greps as having had no cross-model
review - because its author rewrote the body by hand under a different heading.
The PR block is now a *rendering* of the receipt.

**Why in the repository.** Evidence about an instrument that does not live in
the tree cannot be re-derived by anyone else; a count held outside the repo is a
green nobody can audit. One file per run, so concurrent workers never conflict.

**Why on a skip too.** A skip with a receipt is a state. A skip without one is
indistinguishable from a stage that was never wired in - the exact condition
this issue was opened about, in which nothing anywhere recorded that the stage
had not run.

Query across runs:

```bash
jq -s '{runs: length,
        ran: [.[] | select(.status=="ran")] | length,
        accepted: [.[] | select(.status=="ran") | .counts.accepted] | add,
        rejected: [.[] | select(.status=="ran") | .counts.rejected] | add,
        proposed: [.[] | select(.status=="ran") | .red_cases.proposed] | add,
        covered:  [.[] | select(.status=="ran") | .red_cases.already_covered] | add}' \
  docs/measurements/counter-model/*.json
```

That is a documented query rather than a summarising script, deliberately: a
number that decides whether this stage becomes blocking should be derived in the
open by whoever is deciding.

## The ratio is a MONITOR. The diversity number is the DISCRIMINATOR.

Item 4 of the issue asks for the accept/reject ratio to be visible, on the worry
that a counter-model whose every finding the author rejects is decorative.

The first reading says the opposite. Across the 14 runs whose PR bodies carry a
parseable counts line: **80 accepted, 2 deferred, 0 rejected.**

**A 0% rejection rate is equally consistent with an excellent reviewer and an
uncritical author**, and today's findings were independently checked and were
real - so it may simply be quality. That ambiguity is the point: **the
acceptance ratio cannot discriminate between those two worlds.** Only the
diversity number can -

> how many of the counter-model's proposed red cases were already covered by the
> implementer's tests.

Both models have read our conventions and share training corpora; correlation is
the expected failure mode, not an exotic one. And the issue's own framing, which
is pre-committed here because a disappointing result named in advance cannot be
quietly re-framed afterwards:

> **Near-total overlap is a real result, not a failure - it would mean the two
> models are not failing independently on this workload, which is the assumption
> the whole design rests on and which nobody has tested.**

Neither tail of the acceptance ratio is actionable without the diversity number.

### The first diversity reading, and the conditions it was taken under

The first recorded run is this ADR's own change: **16 red cases proposed, 3
already covered** by the implementer's tests. 81% novel.

**Taken on an adversarial workload, and that has to be stated or it gets
discounted later by someone assuming the conditions were easy.** This was the
least favourable possible run for the hypothesis that the two models fail
independently:

- the change was authored by a session that had spent the entire day on this
  exact defect class - blind instruments, denominators, negative controls;
- two ADRs on that subject ([0008](0008-instrument-negative-control-bound.md)
  and [0009](0009-oscillation-control.md)) had merged that same afternoon, by
  the same author;
- the implementer was therefore primed, specifically and recently, on the kinds
  of gap a reviewer would look for.

If the counter-model were agreeing by shared corpus and shared conventions
rather than reviewing, **this is the run where that would have shown.** It did
not. A later reader comparing their own number against this one should know the
baseline was set under those conditions, not on a routine change.

## Advisory on day one, with both triggers committed

Advisory-vs-blocking is an exit-code policy, which is one of ADR 0009's own
tells, so the observation that would move it is committed here beside the
decision rather than left to judgement later. **Two-sided, because it is:**

**PROMOTE to blocking** when, across **N >= 10** recorded runs, the diversity
number shows the counter-model proposing red cases our own tests did *not*
already cover, at a rate that justifies the cost. That is independent failure,
measured.

**DEMOTE, or rethink the stage,** on either of:

- `rejected` trending toward the total - the issue's original worry: the stage
  is decorative and the author is no-opping it; or
- `rejected` staying at **zero** *while* the diversity number shows near-total
  overlap. That is the case the first reading points at, and it says the two
  models are not failing independently - in which case this stage is measuring
  agreement, not review.

## Acceptance item 4 is a measurement programme, not a deliverable

"Ten runs recorded with the diversity measurement" cannot be satisfied by a pull
request: ten runs happen over days, and gating a release blocker on wall-clock
time helps nobody. **This ADR ships the recorder, not the readings.** The
mechanism plus the first recorded run closes the ticket; the ten-run diversity
result is a follow-up reading against the triggers above. Item 4 is not skipped -
it is accumulating.

## What is not covered

- **The reviewing model's judgement is not exercised in CI.** Neither `codex`
  nor `git` is in the CI image, a live call spends the user's quota, and the
  reviewer is not deterministic across runs. The red case for the stage is built
  on **recorded transcripts**: the same nine-line file reviewed twice, once with
  a seeded defect and once without. What CI checks is the stage's handling of a
  reviewer's output.
- **A transcript that is absent, truncated, or off-format reads as
  `unparseable`, never as clean.** All three contain zero finding headings,
  which is byte-identical - to anything counting headings - to a review that
  found nothing wrong.
- Tier binding, as above.

## Consequences

- Every `/flow:auto` run spends a counter-model call, or records why it did not.
- The accumulated receipts are the first data this project has ever had about
  whether cross-model review finds anything the implementer would not have.
- `/flow:auto_codex` survives as a delegating alias with its own retirement
  trigger: **no live role in any wave declares `driver=flow:auto_codex`.**
  Retiring it while roles are driving on it removes the lifecycle command those
  sessions are executing.
