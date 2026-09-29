# Flow run record - issue #1347

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=a342cf208c904ba4b064bf8beb5e179d -->
## Run 1

- Run-id:            a342cf208c904ba4b064bf8beb5e179d
- Run-start:         31b5a2ff4d719a92d5beda4c36e08c6f05f804aa
- Issue:             #1347
- Base SHA:          31b5a2ff4d719a92d5beda4c36e08c6f05f804aa
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run48:cpp2-orch (orchestrator), mailbox message 2500 replying to plan 2499
- Recorded at:       2026-09-28T22:25:30Z

### Section B evidence
#1347 is open and the defect was introduced by PR #1344 (846431d). No commits since 846431d touch tests/test_supervise_sweep.py. Measured: xdist workers share one process group (gw0/gw1/gw2 all pgid 307073, same sid), so pgid alone cannot separate the fixture from a neighbour. No duplicate or superseding issue.

### Section C - the approved plan
1. `tests/test_supervise_sweep.py` - _kin treats an unreadable environ as fatal only for a pid that could be the fixture's, judged from /proc/<pid>/stat: same uid, same pgid, start time >= the fixture's, comm bash or sleep. The residual is stated. The test body moves into a helper whose cleanup is in a finally, followed by a lenient reaper that never raises and never touches an unmarked pid. Committed cases: (a) a neighbour's unreadable pid does not fail, red on main; (b) the fixture's own unreadable child still fails, and also reds under the mutation "every pid is a neighbour"; (c) _kin raising mid-test still leaves the fixture reaped, red on main.

Scope: 1 test file, ~80 lines.
Risks: comm is truncated to 15 chars (fine for bash and sleep); start time is compared in the same clock-tick units.
