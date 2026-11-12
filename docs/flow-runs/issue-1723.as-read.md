<!-- flow-run n=1 id=aabd4038244b4f3fb56b773ce0543f9f -->
## Run 1 - issue #1723 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1723
- Read at:      2026-11-12T00:04:11Z
- updatedAt:    2026-11-11T23:37:13Z   (context only - moves on comments and labels)
- Body digest:  f1ce09de8aceaa6c04e0dd7c5d30c615d9a6f653bfbf5e210989a09d57ee8585   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2242 of 2242 (cap 16384)

### Body as read
Tier: 1

Source: deferred finding from the Codex counter-model review of #1696 (`gpt-6.1-sol`, pass 3, 2026-11-11). The wave orchestrator ruled it be filed as its own issue and worked immediately; the receipt for #1696 records it as deferred.

## Outcome
`/lane:update` never advances a lane file's review date past fixes nobody read.

Step 3 of `.claude/commands/lane/update.md` lists the fix issues closed since the last review, so the owner can spot a lane nobody listed. When `gh` cannot be read at all (not signed in, no network), the document says to report that the list was not examined. It then still reaches Step 5 and stamps today's date. The next update searches from that new date, so every fix closed in the unread interval is skipped by every later review.

The same document already guards the neighbouring case: a full page of results is treated as truncated, and the review date is left where it was. The outright-failure path has no such rule.

## Acceptance
- When the closed-fix listing cannot be read, the command leaves the review date where it was: Step 5 is not run for that review, and the owner is told which period went unread. One sentence in Step 3, mirroring the truncation rule, plus the matching condition where Step 5 says to stamp.
- `tests/test_lane_file.py` pins it: an assertion on the Step 3 wording, beside `test_update_treats_a_full_page_of_fixes_as_truncated`.
- The command document stays within the word budget this change declares for it; raise only that one new number if needed, with the reason in the PR.

## Constraint
- Wording only. No change to `scripts/lane-file.py`: `stamp` cannot know whether a listing was read, and should not try.
- A review where the rows were re-checked but the fix listing was unreadable is still useful work. The command should say so and say plainly that it is not recorded as a review.

## Assumption
That refusing to stamp is right even when the owner has just read every row. The alternative, stamping and noting the unread period somewhere, has nowhere durable to put the note: the lane file carries one date and nothing else.

Related: #1696 (the command), #1695 (lanes exercised), #1700 (review loops that keep finding real things past the pass ceiling).


<!-- end of body -->
