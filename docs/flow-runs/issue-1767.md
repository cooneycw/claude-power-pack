# Flow run record - issue #1767

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=41282d50363a42a5a215d7e85b62c8a2 -->
## Run 1

- Run-id:            41282d50363a42a5a215d7e85b62c8a2
- Run-start:         4f585adf5619414b800489e08b133e56d0c2b4d8
- Issue:             #1767
- Base SHA:          4f585adf5619414b800489e08b133e56d0c2b4d8
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "GATE: GO-WITH-CONDITIONS #1767", outbox rev 78
- Recorded at:       2026-11-12T07:00:00Z

### Section B evidence
- commits touching `scripts/flow-plan-record.py` since filing (2026-11-12T06:53Z): none
- PRs since filing: none touching the helper
- duplicate/superseding issues: none; amends #1731 (68d5fedf)
- source: owner ruling "Verdict line", relayed by the orchestrator in the issue body

### Rulings and gate conditions (orchestrator)
- The clause goes directly after the verdict word, not at the end of the line.
- Normal queue, not the last merge.
- One function, four outcomes (nothing owed, all shown, these lanes missing, could not check), written as states before the print sites are touched; the stderr note comes from the same state; a test shows every combination of lane file x plan table x demonstrated file lands in exactly one of the four.
- Byte-identical line against the pre-change helper for: no lane file, a waived plan, a plan with no will-test lane, all lanes demonstrated; and say what an unusable lane file at close prints (expected: could not check on the line, not silence).
- The reader test runs Step 6's text against the real line for each verdict word, with and without the clause; every other document quoting the verdict line in full is corrected and listed.
- `flow/auto.md` is at its budget: the sentence is paid for by an equal trim in the same step, recorded before removal, with an independent old-versus-new read; line numbers go to the orchestrator.
- Its own control with the pre-change helper as a historical anchor at 68d5fedf, confirmed to compare under --verify-provenance before registering; five registrations before the first gate run; verified with --control by name.
- make lint, typecheck, shellcheck read to the end; two review passes, ask before a third; no full gate until next.

### Section C - the approved plan
1. `scripts/flow-plan-record.py` - one function decides the lane state at close; the three verdict print sites carry its clause after the verdict word; the stderr note is generated from the same state; the control's marker
2. `tests/test_flow_plan_record_lanes.py` - the four outcomes, the full combination table, byte-identical lines against the pre-change helper, exit codes unchanged
3. `controls/flow-plan-record-lanes-verdict/` - the control: runner, cases, the pre-change helper as historical anchor
4. `controls/census.md` - the control's row
5. `.claude/commands/flow/auto.md` - Step 6 says what a LANES clause on the verdict line means and what to do, within the budget
6. `docs/reference/flow-auto-rationale.md` - the rationale copy of the same passage
7. `docs/scripts/flow-plan-record.md` - the line's forms
8. `docs/agents/lanes.md` - where the close-time result is read
9. `tests/test_flow_auto_plan_gate.py` - Step 6's text against the real line from the helper, each verdict word, with and without the clause

Scope: 9 paths; about 60 lines in one helper, one small control, two passages in command documents, about 250 lines of test.

Risks: a reader in another repository that matches the whole agreement line (none has a lane file, and the line is byte-identical there, asserted against the pre-change helper); the helper is linked into every running session, so a session that owes a lane result sees the clause at once (intended; nothing refuses); `flow/auto.md` has no words to spare, so the sentence must be paid for or the work stops.

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | The fixture repository is exercised as a plain repository and as a linked worktree |
| Harness | will test (Claude install); not covered (Codex install) | The generated Codex mirror of auto.md is rebuilt and carries the same sentence; no Codex session is run |
| Driver | not applicable | No driver-facing output; the line is read by the session running /flow:auto |
| Coordination | not applicable | Nothing on the coordination path |
| CI provider | will test (Woodpecker); not covered (GitHub Actions) | The new control runs in the negative-controls step; its line is read from this PR's pipeline log |
| Project state | will test | A project with no lane file: the verdict line is byte-identical to the pre-change helper's |
