# Issue #1084 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1084
- Read at:      2026-09-26T14:23:31Z
- updatedAt:    2026-09-21T23:32:56Z   (context only - moves on comments and labels)
- Body digest:  a80ca6d5c1001d596b76ad9dacad92555cb382e6f795034473ed4414a2fef12a   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3850 of 3850 (cap 16384)

## Body as read
Parent: #1079.

Status: proposed work, not authorization to implement.

Depends on: None within the wave. Related: #861 (delivery pilots), #970 (the mutation requirement).

## Outcome

A change to `CLAUDE.md` or to a skill can be told whether it made the work better or worse, by a case that would have reported differently had the change been wrong.

## Current state

Verified at `5ceb966`, `make verify` runs fourteen targets:

```
verify: tools-check lint test typecheck shellcheck oscillation \
        binary-guards-check negative-fixture-check \
        claude-md-budget-check claude-md-links-check claude-md-behavior-check \
        project-next-check delegated-core-check \
        scripts-inventory-check instrument-census-check
```

None is an eval. The delivery-pilot work from #861 exists as `scripts/run-delivery-pilots.py`, fixtures under `tests/fixtures/delivery_pilots/`, and a maintained report at `docs/agents/delivery-pilots.md`. The playbook's counterpart - a suite that runs on every change to the instructions and whose pass rate is enforced as a merge check - has no CPP equivalent.

## Scope, deliberately narrow

**One discriminating case and the gate that consumes it.** Not a suite, not a threshold, not a platform.

The reason for the narrow scope is in the existing research: a prior live evaluation lane was found to ask the model which skill it *would* activate, supplying the checkpoint identifiers being tested in the prompt. That produces evidence about declared routing and workflow knowledge, not about activation, completed artifacts, or avoided actions. A pass rate computed over cases of that shape is a number that cannot go down for the right reason.

Ship one case that is known to discriminate before building anything that averages over many.

## Acceptance

- One behavioral case that runs non-interactively, does real work against a real fixture, and is graded on an artifact rather than on the model's own account of what it would do.
- The case is registered where a change to `CLAUDE.md` or to a skill causes it to run. A check with no path from a change to a verdict is the failure #1028 consolidates, and this must not add a fifth instance of it.
- The report distinguishes **what was machine-checked from what was judged**, per `docs/agents/issue-contract.md`. "The suite passed" is evidence about checks; whether the intended behaviour arrived is a judgement.
- An unavailable model or a failed harness reports `UNKNOWN`, never `ok`. A harness that exits zero on total API failure is a known trap and the grader must not inherit it.
- No pass-rate threshold is introduced by this issue. A threshold over one case is not a rate, and `docs/decisions/0009-oscillation-control.md` applies to the first person who proposes one.

## Negative control (ADR 0008), and its relation to #970

The committed case must be paired with a **mutation the passing case is required to catch**: a deliberately degraded instruction set, or a fixture the correct behaviour would reject, on which the case reports failure.

#970 already argues that a control battery cleared by inspection cannot distinguish a load-bearing control from a decorative one. An eval suite is a control battery, and it inherits that argument the moment it exists. The playbook reaches the same place from the other direction and is worth recording because it is the same claim in different words: *as models improve, cases that once discriminated stop doing so, and new ones must be added.* A case that no longer discriminates is a decorative control that still reports green.

## Constraint

**Do not gate on a suite that has not been shown to discriminate.** A pass-rate merge check over cases that cannot fail is a gate that clears everything, and it would be indistinguishable from a working one on every run until the day it mattered.

