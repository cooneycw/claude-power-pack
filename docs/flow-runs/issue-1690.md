# Flow run record - issue #1690

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=d0e20bb75ff44308be7a617ea4170d66 -->
## Run 1

- Run-id:            d0e20bb75ff44308be7a617ea4170d66
- Run-start:         f63dc946fe65b9d2ea9df3a5446dd8380c551da7
- Issue:             #1690
- Base SHA:          f63dc946fe65b9d2ea9df3a5446dd8380c551da7
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, authority model orchestrator-only), by mailbox: "GATE: GO-WITH-CONDITIONS #1690", outbox rev 2, 2026-11-11T17:55:45-05:00
- Recorded at:       2026-11-11T22:56:06Z

### Section B evidence
- commits since filing (2026-11-11T22:01:06Z): ca8652a8 (#1694), f63dc946 (#1702); neither records a disposition
- merged PRs: #1694, #1702
- duplicate/superseding issues: none (#1673 parent; #1691, #1692, #1693 siblings that read this issue's flow/cicd bucket)
- measured at 2026-11-11T22:53:29Z: 736 comments on #864; 383 cited by 97 closed issues and 52 PRs; 353 uncited

### Gate conditions (orchestrator)
- The list opens with an owner summary: totals per disposition summing to the count, every declined and obsolete row in full with its reason, every newly filed issue with the comment ids it absorbs.
- An uncited fixed-by names the merged PR and what in it fixes the finding; hand-check 20 percent of uncited fixed-by rows.
- No new script for the count check; state the one-line command and its output in the list header.
- Issue ceiling 20; stop before a 21st.
- Flow/cicd bucket sent early, split by child (#1691, #1692, #1693, none-of-these).
- Report the CPP commit kyle, kyle-candidate and skillc pin, read-only.
- PR says Refs #1690; the close of #864 and the successor wait for the owner's read.

### Section C - the approved plan
1. `docs/measurements/nit-store-864-dispositions-2026-11.md` - the disposition list: owner summary first, then one row per comment
2. `docs/measurements/nit-store-864-dispositions-2026-11.jsonl` - the same rows as data, so the count and one-disposition rule are checkable by command

Scope: 2 files, about 740 rows each; plus filed issues and comments on GitHub (10 to 16 new issues expected, ceiling 20).

Risks: subagent dispositions can be confidently wrong and a wrong fixed-by hides a live defect (mitigated by mechanical citation checks, every medium-or-higher row, and hand samples); declined is a judgment, used only for low severity; comments keep arriving, so the list is pinned to its read timestamp and the count is re-read before the close; time against the 02:52Z deadline.
