# Flow run record - issue #1731

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=a8f6bd6c4c954a50bcda7b1d75fc764e -->
## Run 1

- Run-id:            a8f6bd6c4c954a50bcda7b1d75fc764e
- Run-start:         e2c0d037343d39e41dfade1e6dafa4c48684b789
- Issue:             #1731
- Base SHA:          e2c0d037343d39e41dfade1e6dafa4c48684b789
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "GATE: GO-WITH-CONDITIONS #1731", outbox rev 33, 2026-11-11T21:18:39-05:00
- Recorded at:       2026-11-12T03:05:00Z

### Section B evidence
- commits since filing: 6b6cc29e (#1713) is the only one on scripts/flow-plan-record.py; it added the Section C reader and no lane check
- duplicate/superseding issues: none (#1695 added the rule and said no gate; #1696 added the lane-file commands)
- approve at 6b6cc29e stamps any record that has a run section and never opens .claude/lanes.md

### Rulings and gate conditions (orchestrator)
- D1: refusal is the existing `FLOW_PLAN_RECORD: error - <reason>` line on stdout, exit 1, nothing written. No coordination issue.
- D2: the close half reports on stderr and does not refuse.
- D3: the stability digest excludes ONLY the `### Lanes demonstrated` block, from that heading to the next heading of the same or higher level or the end of the section. Red case: a Section C line added after the block still reads as changed. Documented in docs/agents/flow-plan-record.md.
- D4: an unusable lane file refuses, with unknown in the reason and /lane:update named.
- D5: `Lanes: none - <reason>` is accepted with a non-empty reason; a bare `Lanes: none` refuses; approve prints one stderr note quoting the reason. Not machine-judged.
- D6: an answer counts when the cell starts with one of the four phrases; an empty cell or any other start is unanswered and named. A table lane not in the lane file is ignored.
- Condition 1: the control is registered with its gate marker and verified with --control by name; all registrations before the first gate run; the blind anchor is approve at 6b6cc29e.
- Condition 2: with no lane file, stdout, stderr and exit code are byte-identical to today, asserted.
- Condition 3: lane-file.py missing: approve refuses loudly in a project with a lane file and stays silent in one without. Report what the Codex bundle ships. lane-file.py may be added to flow-helpers-install.sh's list if missing.
- Condition 4: heading matches are anchored to heading lines; red case with the words in prose.
- Condition 5: mail the merge commit promptly.
- Condition 6: make lint, make typecheck; two review passes. No push without the slot.

## Section C - the approved plan
  1. `scripts/flow-plan-record.py` - approve refuses a record with no lanes table or an unanswered listed lane when the project has a lane file; the stability digest excludes the Lanes demonstrated block; compliance reports undemonstrated will-test lanes on stderr
  2. `tests/test_flow_plan_record_lanes.py` - new: every case, the unaffected paths, the digest red case
  3. `controls/flow-plan-record-lanes/control.json` - new control with its cases, runner and blind anchor
  4. `controls/census.md` - row 108 gains the approval refusal
  5. `docs/agents/lanes.md` - what is and is not machine-checked; where the demonstrated rows go
  6. `docs/agents/flow-plan-record.md` - the refusal, the close-time report, the one block outside the digest
  7. `docs/scripts/flow-plan-record.md` - the same, one paragraph
  8. `tests/test_lanes_contract.py` - the pinned sentence about machine checking changes with item 5
  9. `scripts/flow-helpers-install.sh` - lane-file.py added to the helper list only if it is missing there
Scope: 9 named files plus the control's case fixtures and any registration file the control checks require. About 150 lines of Python, about 300 of test.
Risks: this turns on for every CPP flow run when it merges; a copy-mode install without lane-file.py refuses in a project with a lane file; the heading match must not fire on prose.

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | approve and compliance in a linked worktree and in a main checkout of a temporary repository |
| Harness | will test (Claude install); not covered (Codex install) | A test runs the helper through a symlink, and one with the sibling lane-file.py absent shows a loud refusal. No test runs approve from a Codex bundle; what the bundle ships is read and reported |
| Driver | not covered | Delegated drivers call the same approve; no live delegated run |
| Coordination | not applicable | No coordination path |
| CI provider | not applicable | Nothing provider-dependent |
| Project state | will test | No lane file (silent, identical output), complete table, incomplete table, unusable lane file |
