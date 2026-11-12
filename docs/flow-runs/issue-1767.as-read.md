<!-- flow-run n=1 id=41282d50363a42a5a215d7e85b62c8a2 -->
## Run 1 - issue #1767 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1767
- Read at:      2026-11-12T06:54:21Z
- updatedAt:    2026-11-12T06:53:56Z   (context only - moves on comments and labels)
- Body digest:  8105c889b4d012cc9e5f7b15246909b0f236876e68c2fed12dcb0e28458c484b   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2909 of 2909 (cap 16384)

### Body as read
Tier: 2

Source: owner ruling, 2026-11-12, during wave `cpp-improvement`. Asked whether #1731's close-time lane check should stay a report, join the verdict line, or refuse, the owner answered: "Verdict line". Filed by the wave orchestrator.

## Problem
Since #1731 (`68d5fedf`), `flow-plan-record.py compliance` reports on **stderr** when a plan answered "will test" for a lane and `docs/flow-runs/issue-<N>.lanes-demonstrated.md` has no row for it. It does not change the `PLAN_COMPLIANCE` verdict line. In the first three hours, two of three wave workers read only the verdict line, and **five** PRs merged without the file (#1746, #1749, #1750, #1751, #1753). The content existed in each PR body; the record did not. A note beside a verdict is not read as part of the verdict.

## Outcome
A reader of the verdict line alone learns that a lane the plan said it would test has nothing recorded as demonstrated.

## Acceptance
- When the project has a lane file, the run's plan answered "will test" for one or more lanes, and one or more of them has no row in the demonstrated file (or the file is missing or unreadable), the `PLAN_COMPLIANCE` verdict line itself says so and names the lanes. Planning decides the exact form (a suffix on the existing line, or a verdict word); it must be one a reader of that single line cannot miss.
- It does **not** refuse and does not change the exit code: the owner chose the verdict line, not a refusal.
- A project with no lane file, a waived plan, and a plan with no will-test lane produce a verdict line **byte-identical** to today's, asserted by test. That is what keeps kyle, skillc and kyle-candidate unaffected: none has a lane file.
- An unreadable demonstrated file reads as could-not-check on the line, never as "all demonstrated".
- The stderr note may stay or go; if it stays it must not contradict the line.
- **Negative control, committed:** a plan with a will-test lane and no demonstrated row shows the lanes on the verdict line; the same plan with the row does not. Registered on the existing `controls/flow-plan-record-lanes` if its anchor rules allow, otherwise its own small control with the pre-change helper as anchor.

## Constraint
- New behaviour under `scripts/flow-*`, inside the #1673 freeze. The owner's ruling is the exception for this one change.
- The verdict line is read by `/flow:auto` Step 6 and by closing reports. Name every reader in the plan and test the document's own handling against the real new line (the reader rule, #1697). If a flow command document needs a sentence, no word budget is raised.
- If the line's shape changes for a project WITH a lane file in a way another repository could read, say so at the plan gate; today no consumer repository has a lane file.

## Not checked
Whether the answers are true. This shows a will-test lane has a recorded result, not that the result is right.

Refs #1731, #1695, #1673.


<!-- end of body -->
