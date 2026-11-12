# Flow run record - issue #1706

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=14597a63bf3b4895a645744e2214657d -->
## Run 1

- Run-id:            14597a63bf3b4895a645744e2214657d
- Run-start:         545267b95a6ff344829f9cd625c82b95e5f341ef
- Issue:             #1706
- Base SHA:          545267b95a6ff344829f9cd625c82b95e5f341ef
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 17: "GATE: GO-WITH-CONDITIONS #1706"
- Recorded at:       2026-11-12T00:40:24Z

### Section B evidence
- commits since 2026-11-11T23:07:32Z: none touching scripts/check-ignored-additions.sh, flow/auto.md, flow/finish.md, tests/test_check_ignored_additions.py or docs/reference/flow-auto-rationale.md
- merged PRs on those paths: none; open: #1701 (draft, edits flow/auto.md)
- duplicate/superseding issues: none
- this host: no sibling worktree holds unpushed commits on these paths
- checked against the tree: the guard documents .claude/gate-scratch.txt in its header and never names it in its message; both flow documents run the gate before git push; Kyle's ci_shape_check.py clones the ref from GitHub and exits 4 on an unpushed ref, by design

### Scope of this run
PR ONE of two: the guard's message (a non-closing reference). PR two, the sentence in the two flow documents, is a second run. Seq 650 is declined on the issue.

### Conditions attached to the approval
- The new test fails on 4c8aa79a; say so. Assert the marker lines and exit codes are unchanged in both modes, not only that the new line is present.
- The new stderr line goes AFTER the existing message lines; the marker lines stay last.
- make lint, make typecheck; two review passes, ask before a third; no push for CI without the merge slot.

### Section C - the approved plan
1. `scripts/check-ignored-additions.sh` - the blocking and advisory messages gain one stderr line naming .claude/gate-scratch.txt as the remedy when the gate itself wrote the files
2. `tests/test_check_ignored_additions.py` - a test that the message names the file in both modes, with markers and exit codes unchanged; it must fail on 4c8aa79a
3. `docs/scripts/check-ignored-additions.md` - one history line
4. `CHANGELOG.md` - entry
Scope: 4 files, about 40 lines.
Risks: an added stderr line could move something a consumer parses by position; the orchestrator searched kyle and skillc and found no parser of the prose, and the line is placed after the existing ones with the marker last.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | will test: blocking in a linked worktree and advisory in the main checkout; the line appears in both |
| Harness | will test: the generated Codex skills bundle the same script (existing bundle fidelity tests) |
| Driver | not applicable |
| Coordination | not covered: no Kyle repository is exercised |
| CI provider | not applicable |
| Project state | will test: with a gate-scratch file the declared paths stay silent; without one the message names the file |
