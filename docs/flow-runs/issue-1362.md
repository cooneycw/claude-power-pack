# Flow run record - issue #1362

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=73f90c0400c949388d537ef67e554c86 -->
## Run 1

- Run-id:            73f90c0400c949388d537ef67e554c86
- Run-start:         8045fb39ab03bd7f9a405fec322d01c5eeb8c367
- Issue:             #1362
- Base SHA:          8045fb39
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          session user (interactive "approved", 2026-09-30)
- Recorded at:       2026-09-30T19:40:00Z

### Section B evidence
commits: none touching lib/cicd/ or tests/test_cicd_outcomes.py since 2026-09-30T19:00:12Z.
PRs merged since: #1361, #1359, #1358, #1356 (none touch lib/cicd).
dup/superseding issues: none (search "xfail" -> #1362, Nit Store #864).
sibling worktrees: none with unpushed commits on these paths.

### Section C - the approved plan
1. `lib/cicd/outcomes.py` - add xfailed/xpassed fields; executed includes them (#621 kept); pytest parser stops folding; unittest expected failures -> xfailed; summary/aggregate/merge/to_dict carry them.
2. `tests/test_cicd_outcomes.py` - new-contract xfail test, issue tail red-on-main case, real failure not absorbed, xfail-only executed, all-skipped nothing_ran, unittest expected failures, aggregation sums.

Scope: 2 files, ~60 lines. Risk: #769 rerun trigger (failed+errors>0) no longer counts xfails.
