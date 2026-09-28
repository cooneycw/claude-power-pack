# Issue #1320 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1320
- Read at:      2026-09-28T16:33:37Z
- updatedAt:    2026-09-28T16:28:10Z   (context only - moves on comments and labels)
- Body digest:  d2da162ca9eddbb26c49d03e1f4d756124c7675914de11003c084bbcc6075107   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1914 of 1914 (cap 16384)

## Body as read
## Problem

The ELI5/plan approval gate (Step 3 → Step 4 of /flow:auto) can be skipped by being the SECOND run on an issue. Found by run45 w3 while planning #1267 item 5 (one record per run), and read at dad589b:

- `scripts/flow-plan-record.py` `reconcile` (~:93-134) restores the COMMITTED `docs/flow-runs/issue-<N>.md` from HEAD for any run.
- `scripts/step3-record-guard.sh` (the PreToolUse hook) allows an edit when the record exists and says `Approval: granted`. It has no notion of WHICH run was approved.
- `approve` stamps `flow-plan-baseline-<issue>` in the git dir, keyed on the issue alone.
- `head-check` (~:492) asks only that the record file EXISTS at the head.

So a resumed or re-run issue whose first run's approved record is committed starts with a record that already reads `Approval: granted`. The guard lets it edit before its own plan has been presented or approved. #1267 item 5 framed this as lost history (one path per issue). It's worse than that: the gate is satisfied by the previous run.

## Scope (planned, option B, as ruled on #1267 item 5)

Run identity: `reconcile` mints a per-run id into the git dir; the record becomes append-only `## Run <n>` sections, each with `Run-id:`; `approve`, `step3-record-guard.sh`, `compliance` and `head-check` all key on the CURRENT run's section. A legacy single record parses as Run 1.

## Acceptance

- Red case, on the pre-fix base: a repo whose committed record has Run 1 approved; reconcile mints run 2; an edit is attempted. The guard must REFUSE (pre-fix: ALLOWS).
- Good case: run 2 appends its approved section and edits freely (the guard's control must include it, because a guard bug blocks every edit in every flow worktree).
- head-check passes only when the current run's section is at the head.
- Legacy records on main keep working as Run 1.

Owner: run45 w3, as the follow-up PR to #1267's first PR. Relates to #1267 item 5.
