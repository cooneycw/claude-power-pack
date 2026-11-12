# Flow run record - issue #1719

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=c0042c9c274e4e90b299a0380b4fa6dc -->
## Run 1

- Run-id:            c0042c9c274e4e90b299a0380b4fa6dc
- Run-start:         48d4c479d90361d97c27d78d282629184709dcb3
- Issue:             #1719
- Base SHA:          48d4c479d90361d97c27d78d282629184709dcb3
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "GATE: GO-WITH-CONDITIONS #1719", outbox rev 25, 2026-11-11T20:09:46-05:00
- Recorded at:       2026-11-12T01:10:13Z

### Section B evidence
- commits touching the files below since filing: none
- PRs since filing: #1720, #1721, #1722, #1729 merged; none touches these rows
- duplicate/superseding issues: none; row 563 joined from #1713
- all twelve rows confirmed at 48d4c479

### Rulings and gate conditions (orchestrator)
- Fix: 687, 573, 675, 724, 729, 627, 563 (merge.md), 711. One PR, one commit per row.
- 662 and 661 are features: one Nit Store comment each. 565 declined with a Nit Store comment naming the coordination route. 660 not reproduced: one Nit Store comment with the git version needed.
- security/permissions.md line 32 is left unless that document's own convention says the installed path.
- 687 gets a committed case as well as a test; if the only non-crash verdict is one a caller accepts as fine, stop and bring the options.
- Run the battery and the provenance check after each origin-file commit; drop any comment row that breaks an anchor and report which.
- Show verify-coverage-check before and after the Makefile annotation edit.
- Show the two project-next tests failing loudly when ownership.json is unreadable.
- #1719 carries a table of all twelve rows before the PR closes it.
- make lint, make typecheck; two review passes; no push until the merge slot.

### Section C - the approved plan
1. `scripts/check-negative-controls.py` - a non-synthetic anchor missing sha or origin is a reported malformed registration, not a KeyError (687); census wording (724)
2. `scripts/check-behavioral-eval.py` - docstring says what is and is not checked (573)
3. `scripts/host-surface-check.py` - docstring no longer says every declaration is authored (675)
4. `scripts/host-surface-observe.py` - the same (675)
5. `scripts/instrument-census-check.py` - census location wording (724)
6. `scripts/verify-coverage-check.py` - census location wording (724)
7. `scripts/bandit-audit.py` - census wording (724) and the docs/scripts.md pointer (729)
8. `scripts/mutation-probe.py` - docs/scripts.md pointer (729)
9. `scripts/counter-model-reviewer-attribution.py` - docs/scripts.md pointer (729)
10. `Makefile` - census location in two comment lines (724)
11. `.woodpecker.yml` - census location in two comment lines (724)
12. `docs/agents/shared-stash-stack.md` - census location (724)
13. `.agents/CODEX_SETUP.md` - retired server removed (627)
14. `.claude/commands/flow/merge.md` - the bare helper call uses the installed path (563)
15. `tests/project_next/test_output_contract.py` - version read from ownership.json (711)
16. `tests/test_project_next_preflight.py` - version read from ownership.json (711)
17. `tests/test_negative_controls_malformed_anchor.py` - the missing-sha anchor is reported, not a crash (687)

Scope: 17 files, about 40 changed comment lines, about 10 lines of code in one function, about 60 lines of test.

Risks: seven of the script files are the origin of a registered control's anchor, and a comment edit there can break an anchor, which decides how many comment rows survive; the 687 verdict must not make a malformed anchor look fine; a grab-bag is easy to review badly, so each row is its own commit.

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | The 687 test builds its fixture control in a temporary tree; the gate runs in a linked worktree and CI in a clean clone |
| Harness | will test (Claude install); not covered (Codex install) | merge.md's helper call takes the installed path; the generated Codex mirror is rebuilt and checked by the gate and its call line is read and reported; no live Codex run |
| Driver | not applicable | No driver-facing output changes |
| Coordination | not applicable | Nothing on the coordination path |
| CI provider | not applicable | .woodpecker.yml changes are two comment lines |
| Project state | will test | 711: the two tests read ownership.json and must fail loudly when it is unreadable |
