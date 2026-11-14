<!-- flow-run n=1 id=5a0c6451735d4d52bdf8a2014b16e670 -->
## Run 1 - issue #1823 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1823
- Read at:      2026-11-14T17:33:58Z
- updatedAt:    2026-11-14T16:29:49Z   (context only - moves on comments and labels)
- Body digest:  722882ed23e9b59be3f57c172455f2f7a366b2143e1a2a2a3ecc3642d3f247b2   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1787 of 1787 (cap 16384)

### Body as read
## Problem

The close-time lane check counts a lane as demonstrated if its row has **any non-empty result cell** (`row[1].strip()` in `lanes_at_close`, `scripts/flow-plan-record.py`). `TODO`, `failed`, or `n/a` all pass. Because the check lets work through, this is a blind spot, not only a gap in the feature.

A related weakness: a `Checkout: will test` row can name just one value (for example a linked worktree) and still read as covering the whole lane. Neither the plan nor the results say which values were tested and which were not.

## Proposal

- **Explicit result states.** Each demonstration row gives one of `passed`, `failed`, `not run`, `refused as expected`, plus a reference to the test or observation. Promised refusals (`will refuse`) need evidence too. Only `passed` / `refused as expected` with a reference count as demonstrated. `failed` / `not run` are reported as such.
- **Name the values tested.** `will test` rows in the plan list the values they will test and the ones they won't, plus any combinations that matter (for example Codex in a linked worktree). Do **not** require every combination of every value.

## Acceptance

- Red cases committed: a row with a non-empty but invalid state (for example `TODO`), and a row with `passed` but no reference, are both reported as not demonstrated. A `will refuse` lane with no refusal evidence is reported.
- A `will test` row that lists no values is flagged at approval.

## Later (not in scope)

Measuring whether the tables help (plans changed, omissions caught, lane defects that escaped, review effort) is worth doing once these results can be trusted.

## Source

From an external review of d90712ee (11.1.1), relayed by the owner on 2026-11-14. The issue is the close-time lane check; it builds on #1821.



<!-- end of body -->
