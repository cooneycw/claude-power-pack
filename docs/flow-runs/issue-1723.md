# Flow run record - issue #1723

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=aabd4038244b4f3fb56b773ce0543f9f -->
## Run 1

- Run-id:            aabd4038244b4f3fb56b773ce0543f9f
- Run-start:         4c8aa79a3f58baca937692c6c19e2d896b29af40
- Issue:             #1723
- Base SHA:          4c8aa79a3f58baca937692c6c19e2d896b29af40
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 10: "GATE: GO-WITH-CONDITIONS #1723"
- Recorded at:       2026-11-12T00:05:12Z

### Section B evidence
- commits since 2026-11-11T23:37:13Z: 4c8aa79a (#1724) carries the gap; nothing since touches .claude/commands/lane or tests/test_lane_file.py
- merged PRs: #1724 (the cause), #1721 (unrelated)
- duplicate/superseding issues: none
- this host: no sibling worktree holds unpushed commits on these paths

### Conditions attached to the approval
- One rule, two triggers: the no-stamp rule is stated once and both the truncated-listing and the unreadable-listing cases point at it. Raise the budget only to the measured count.
- Step 5's heading and body must not read as overriding the rule; a reader who jumps to Step 5 meets the exception there.
- The test must fail on the document at 4c8aa79a; run it there and say so in the PR.
- make lint and make typecheck before the finish gate; the two-pipeline cap applies.
- One review pass unless it returns a medium or higher.

### Section C - the approved plan
1. `.claude/commands/lane/update.md` - Step 3: when the fix listing cannot be read, do not run Step 5 for this review, tell the owner the period that went unread, and say the row re-check was done but is not recorded as a review. Step 5: stamp only when Step 3's listing was read in full
2. `tests/test_lane_file.py` - one test pinning that wording, beside the truncation test
3. `.claude/command-word-budgets.tsv` - lane/update.md's own number rises to the measured count for the new sentences
Scope: 3 files, about 20 lines.
Risks: wording only, so the test is a pin on the document's text, not on behaviour.

### Lanes for this change
| Lane | Answer |
|---|---|
| Harness | will test: the generated lane-update skill carries the new rule (the existing generated-tree fixture) |
| Checkout | not applicable: no script behaviour changes |
| Driver | not applicable |
| Coordination | not applicable |
| CI provider | not applicable |
| Project state | not applicable: no script behaviour changes |
