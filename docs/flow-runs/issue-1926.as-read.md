<!-- flow-run n=1 id=5cd88489f9844c7e9c3239fe585c3062 -->
## Run 1 - issue #1926 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1926
- Read at:      2026-11-28T02:28:34Z
- updatedAt:    2026-11-27T10:50:29Z   (context only - moves on comments and labels)
- Body digest:  09f1cd1e10f21714a866141a3871de751bc34334bb70e8d903d9dcc27bcdabe4   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1129 of 1129 (cap 16384)

### Body as read
## Problem

The review-yield report undercounts its population in two ways.
1. The fix-title filter is `^fix\([^)]+\)(?:!)?:` (`scripts/review-yield-report.py` about lines 102 and 273). It misses scope-less `fix:` / `fix!:` titles, and possibly `Fix ...`.
2. `provenance()` reads only the linked issue's body and comments (about lines 179-201). A PR body's `Origin:` / `Missed because:` lines are never counted.

## Proposal and acceptance

- Add `fix:` and `fix!:` to the filter. **Sample** existing `Fix ...` titles before adopting that form, and record the sample.
- This changes the denominator, so commit a case that shows the old and new populations side by side.
- PR-body parsing: first **count** what it would recover on current history, then define the PR-to-issue attribution rule, and only then adopt it. If #1877's capture point already puts these lines where the report reads, prefer that.
- Keep existing outputs reproducible: a committed fixture shows that the unchanged populations still produce identical rows.

Owner ruling 2026-11-27 (CPP advice R3c/R3d), relayed by the fleet master. Related: #1865, #1877.


<!-- end of body -->
