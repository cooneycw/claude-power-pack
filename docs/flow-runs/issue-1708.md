# Flow run record - issue #1708

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=6bf7d629731d4467ba8992f90b54a21e -->
## Run 1

- Run-id:            6bf7d629731d4467ba8992f90b54a21e
- Run-start:         f731c1158fcc61109db6b1faf9abb0390e4f430d
- Issue:             #1708
- Base SHA:          f731c1158fcc61109db6b1faf9abb0390e4f430d
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "GATE: GO-WITH-CONDITIONS #1708", outbox rev 6, 2026-11-11T18:49:22-05:00
- Recorded at:       2026-11-11T23:49:43Z

### Section B evidence
- commits touching .claude/commands/flow/cleanup.md since filing: none
- PRs in the wave since filing: #1720, #1721, #1722; none touches the file
- duplicate/superseding issues: none (#1693 covers the scripts, #1709 covers claims)
- verified at f731c115: Step 4 deletes on a gone upstream alone; line 299 is a POST through gh api

### Gate conditions (orchestrator)
- Finding 672 ruling: drop Bash(gh api:*) from allowed-tools; record it on #1708 and amend the acceptance line.
- Word budget stays 2258: pay for new text by trimming inside the same file, with an old-versus-new instruction read of what is trimmed; state before and after counts.
- No sentence in the file may give "remote deleted" as a sufficient reason (also line 167 prose, the line 332 note, the report line).
- The merged-PR query names MAIN_REPO's repository explicitly and requires headRefOid equal to the local tip; a different head is "kept: tip differs from merged head".
- gh failure, empty output and unparseable output all keep the branch, reason "could not ask GitHub"; add the empty-output case.
- make lint and make typecheck before the finish gate.

### Section C - the approved plan
1. `.claude/commands/flow/cleanup.md` - Step 4 deletes a gone-upstream branch only on proof its current tip landed (merge-helper record, else merged PR head equal to tip); everything else is kept and named; allowed-tools drops gh api and gains gh pr list
2. `tests/test_flow_cleanup_branch_proof.py` - runs the document's Step 4 block in a scratch repository with a stub gh over the proven, unproven, tip-past-merge, gh-failed and empty-output cases

Scope: 2 files, about 40 lines changed in the document, about 150 lines of test.

Risks: the test pins the block's text, not an agent's behaviour; a branch squash-merged outside the helper whose local tip was later amended is kept (intended); the merged-PR proof needs network, and offline such a branch is kept.
