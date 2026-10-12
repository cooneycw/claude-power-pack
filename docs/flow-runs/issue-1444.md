# Flow run record - issue #1444

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=ea8cd2ebbd0c4c57984fe884e3856cb9 -->
## Run 1

- Run-id:            ea8cd2ebbd0c4c57984fe884e3856cb9
- Run-start:         1c92f224827631cf16bbdb2295ebce9e9c262327
- Issue:             #1444
- Base SHA:          1c92f224
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cooneycw (operator, in-session "approved")
- Recorded at:       2026-10-12T16:55:00Z

### Section B evidence
Issue filed 2026-10-12T15:10:04Z. Commits on origin/main since: cdd37f2f (#1445),
1c92f224 (#1446); neither touches tests/test_negative_controls.py,
scripts/check-negative-controls.py or controls/check-test-binary-guards. Merged PRs
since: #1443, #1445, #1446 (none touch it). Related closed issues: #1241 (prior
battery-cost fix; ruled out caching the holder, did not consider --control scoping),
#1420, #978, #1404; none fix this. Sibling worktrees: primary only.
Measured on main (load ~4/24 cores): full-register run 53s, scoped to
--control controls/check-test-binary-guards 1.0s. The holder runs the full register
three times (~160s idle), so battery growth (26.2s at #1241 -> 53s) explains the issue
without host load.

### Section C - the approved plan
1. `tests/test_negative_controls.py` - scope the holder's three harness runs to --control controls/check-test-binary-guards; drop its gitleaks skip (keep requires_git); add a _HOLD_BUDGET (30s) self-bound that fails the holder by name; replace stale ~19s/~20s figures in comments, docstrings and the waiter's timeout message

Scope: 1 file, ~40 lines.
Risks: the holder's claim narrows from a whole-register run to the dirtied control's run;
the test now runs where gitleaks is absent; the 30s bound is a timing assertion.
