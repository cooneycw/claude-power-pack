<!-- flow-run n=1 id=a8f6bd6c4c954a50bcda7b1d75fc764e -->
## Run 1 - issue #1731 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1731
- Read at:      2026-11-12T02:17:01Z
- updatedAt:    2026-11-12T01:07:08Z   (context only - moves on comments and labels)
- Body digest:  b79376409516b0dfe87664308ba47ad0d215232a75e2b4092c55d021689b297d   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2811 of 2811 (cap 16384)

### Body as read
Tier: 2

Source: owner request, 2026-11-11, during wave `cpp-improvement`: "Can we insist on negative tests for the lane tables presence?" Filed by the wave orchestrator.

## Problem
Since #1695 (`658cdd55`), `/flow:eli5` requires a plan's Section C to answer every lane listed in `.claude/lanes.md`. Nothing checks it. In the first two and a half hours after the rule landed, one of three wave workers left the lane table out of three plans (#1708, #1693, #1713) and the orchestrator approved all three without noticing. #1708 merged with no lane table in `docs/flow-runs/issue-1708.md`. A rule that holds only when someone remembers to look is not being enforced.

## Outcome
A plan record with no lane table, or with a listed lane left unanswered, cannot be approved in a project that has a lane file. The check is shown able to fail by committed cases.

## Acceptance
- When the project has a readable `.claude/lanes.md`, plan approval refuses a record whose Section C has no lanes table, and refuses one that leaves any listed lane without one of the four answers (will test, will refuse, not applicable, not covered). The refusal names the missing lanes.
- A project with no lane file is silent and unaffected: approval behaves exactly as today. An unreadable lane file is reported as unknown and does not pass as "no lanes".
- At close, a lane answered "will test" at approval has a matching row saying what was demonstrated, or the compliance step reports it by name. (Planning decides whether this half refuses or reports.)
- **Negative control, committed** (`controls/`, registered with its gate marker): a record with no table is refused; a record missing one lane is refused and names it; a record answering every lane passes; a project with no lane file passes with no lane output. Each red case is shown red.
- Records approved before this lands are not re-judged.

## Constraint
- This is new behaviour under `scripts/flow-*`, inside the #1673 freeze. The owner's request is the exception for this one change; no word budget is raised on a flow command document.
- If the refusal adds or changes any line `flow-plan-record.py` prints on stdout, urgent coordination issues go to kyle, skillc and kyle-candidate before merge (owner ruling of 2026-11-11). Prefer the existing refusal shape so no reader changes. Neither kyle nor skillc has a lane file today, so the check is silent there either way.
- `scripts/flow-plan-record.py` is being edited for #1713; branch after that lands.

## Not checked
- Whether the answers are true. This check proves the table is present and complete, not that a lane marked "will test" was tested well. The independent review's lane question (#1695) and the `Missed because: lane not exercised` record (#1697) remain the checks on that.

Refs #1695, #1696, #1673.


<!-- end of body -->
