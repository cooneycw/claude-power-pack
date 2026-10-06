<!-- flow-run n=1 id=78cb9a2b9eb54d1ab4513a1e4d1a67c7 -->
## Run 1 - issue #1383 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1383
- Read at:      2026-10-06T11:02:01Z
- updatedAt:    2026-10-06T11:01:27Z   (context only - moves on comments and labels)
- Body digest:  f9957151f96ece69128b71440720b9f2ba9da76b3792e7d806056f4a1dea34c1   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2814 of 2814 (cap 16384)

### Body as read
## Problem

On the `/codex:auto` lane (and `/qwen:auto`, `/gemma:auto`), `flow-finish-gate.sh` **always fails** with:

```
flow-finish-gate: no counter-model review is recorded for this branch at this commit, so this gate cannot tell a review that found nothing from one that never ran (issue #1171).
FLOW_FINISH_GATE: fail (counter-model line missing)
```

No receipt can be written honestly for these lanes. `scripts/counter-model-receipt.py write` models only one direction: **Codex reviews code Claude implemented**.
- The reviewer is derived from a Codex `--json` exec stream (`--reviewer-exec-log`).
- The implementer is derived from the Claude session transcript (`--implementer-session-id`, defaulting to `$CLAUDE_CODE_SESSION_ID`).

On a delegated lane the roles are inverted: Codex implements, and Claude reviews in Step 5. Each available option writes a false record:
- `--status ran` from a `/codex:code_review` run records Codex reviewing its own code, while the implementer is derived as Claude. That inverts the ADR 0007 property the receipt exists to check.
- `--status skipped` accepts only `--reason codex-absent|reviewer-unavailable`, and neither is true. The reviewer (Claude) was present and did review.

## Evidence

- kyle #1582 (`/codex:auto`, 2026-10-06): the full gate passed apart from a single test that passed on rerun. Lint, typecheck, unit and browser suites were green. The only fail was `counter-model line missing`. The owner ruled to proceed to the PR with the review recorded in prose.
- None of kyle's 99 committed receipts under `docs/measurements/counter-model/` has a non-Claude implementer, so this lane has never produced a receipt.
- `flow-finish-gate.sh` ~line 339 (`verdict()`): enrolment state must be `receipt|skipped|not-enrolled|undecidable` for any pass verdict.

## Why it matters

Every delegated run hits a red gate that has no honest remedy. The pressure then goes to the dishonest ones: a fabricated skip reason, or a same-model "ran" receipt. Either one corrupts the measurement corpus #1048/#1047 just made trustworthy. A gate whose only exits are lying or bypassing gets routed around.

## Proposed direction (for grilling, not prescriptive)

- Let the receipt record the **direction**: an implementer derived from the delegated run's exec stream (the Codex/Qwen/Gemma JSONL the driver already captures) and a reviewer derived from the Claude session. Keep "derived, never asserted" (#1048) on both sides.
- Or: a recorded skip reason specific to delegated lanes, carrying the reviewing Claude session id, so the gate can tell "reviewed by the supervising model" from "never reviewed".
- Either way, add a committed negative control: a delegated-lane receipt naming the **same** model on both sides must still be refused.

Found while working kyle #1582.

