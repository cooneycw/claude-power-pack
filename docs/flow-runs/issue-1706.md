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

<!-- flow-run n=2 id=8c037a03ebd14f0980b66d75d0369d55 -->
## Run 2

- Run-id:            8c037a03ebd14f0980b66d75d0369d55
- Run-start:         d152fae166613cdb035be40b904518a363929ed4
- Issue:             #1706
- Base SHA:          d152fae166613cdb035be40b904518a363929ed4
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 39: "#1706 PR two: cut it from main now (PR one is in). It is already approved"
- Recorded at:       2026-11-12T03:55:00Z

### Section B evidence
- commits since 2026-11-11T23:07:32Z on flow/auto.md, flow/finish.md or docs/reference/flow-auto-rationale.md: none
- merged PRs on those paths: none; PR one of this issue was #1739 (e33525d0), the guard's message; open: #1701 (draft)
- duplicate/superseding issues: none
- another worker (#1700) will reword flow/auto.md lines 745-746 and 785-786; this run stays inside Step 6 item 2 (lines 810-827)
- checked against the tree at d152fae1: both documents still run the gate before git push and neither says what to do when a project's gate needs the pushed head

### Scope of this run
PR TWO of two: one sentence in each flow document, paid for by an equal trim. Closes the issue (seq 631, 652, 654, 655, 671).

### Section C - the approved plan
1. `.claude/commands/flow/auto.md` - Step 6 item 2 gains one sentence: when the project's gate needs the pushed head, push the branch first, then gate; trimmed in the same item so the budget is not raised
2. `.claude/commands/flow/finish.md` - the same sentence after the gate invocation; an equal trim of history prose in the same section
3. `docs/reference/flow-auto-rationale.md` - why the order stays gate-then-push by default
4. `docs/commands-reference.md` - the trimmed text, recorded in a commit before it is removed
5. `tests/test_flow_gate_pushed_head.py` - both documents and both generated Codex skills carry the sentence, placed after the gate invocation; fails on d152fae1
6. `CHANGELOG.md` - entry
Scope: 6 files, about 80 lines, most of it the test.
Risks: a trim removes an instruction rather than explanation; an independent old-versus-new read checks that before review.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | not applicable: prose with no path-dependent behaviour |
| Harness | will test, with a new test in this diff: the generated flow-auto and flow-finish Codex skills carry the sentence |
| Driver | not covered: the delegated drivers' own finish text is not changed |
| Coordination | not covered: no Kyle repository is exercised; whether Kyle's gate then passes on a pushed head is not measured here |
| CI provider | not applicable |
| Project state | not applicable: the sentence is conditional prose; no file or record is adopted |
| Reader: an agent following /flow:auto or /flow:finish in a consumer repository | not covered by a deterministic test: whether it pushes first is a model's behaviour |
