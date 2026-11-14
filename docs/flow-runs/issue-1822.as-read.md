<!-- flow-run n=1 id=65a8a34dbc4446b7a3badbd42e7396b6 -->
## Run 1 - issue #1822 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1822
- Read at:      2026-11-14T16:31:25Z
- updatedAt:    2026-11-14T16:29:41Z   (context only - moves on comments and labels)
- Body digest:  4f8037d2bf077edf487e6e376a50cb12675d553432e0c7737552847ab54622cb   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1773 of 1773 (cap 16384)

### Body as read
## Problem

The lane answers offered to the planner and the answers the helper accepts are different lists.

- `templates/delegated-driver-core.md:213`, rendered into all three delegated drivers (codex/gemma/qwen `auto`), offers: `will test`, `not applicable`, `not covered`, `needs a decision`.
- `LANE_ANSWERS` (`scripts/flow-plan-record.py:253`) accepts: `will test`, `will refuse`, `not applicable`, `not covered`.

The reviewer confirmed that `needs a decision` is rejected. The two differences are not synonyms:
- `will refuse` is a real answer, and the template leaves it out.
- `needs a decision` is an open question. It should be settled before approval and should never appear in an approved record.

Separately, answer matching is too loose. Line 426 does `...casefold().startswith(LANE_ANSWERS)` with no check for where the phrase ends, so `not applicablewhatever` is accepted. The `will test` match at line 1088 has the same problem.

## Fix

- Make the template offer exactly the answers in `LANE_ANSWERS`, with `will refuse` included. Turn `needs a decision` into a "ask the owner before approval" step instead of a table answer.
- Require the phrase to end at a word boundary (end of cell, whitespace, or punctuation) in both places.
- Add a contract check across the rendered driver commands (and `/flow:auto` if it lists answers) that compares the answers they offer to `LANE_ANSWERS`.

## Acceptance

- Red cases committed: a rendered command offering an answer the helper rejects fails the contract check, and `not applicablewhatever` is refused.
- `will test - via X` and `not applicable: reason` are still accepted.

## Source

From an external review of d90712ee (11.1.1), relayed by the owner on 2026-11-14. Checked against d90712ee before filing.


<!-- end of body -->
