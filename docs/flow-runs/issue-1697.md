# Flow run record - issue #1697

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=22808977ef614e6fb293278fbb2a9382 -->
## Run 1

- Run-id:            22808977ef614e6fb293278fbb2a9382
- Run-start:         4c8aa79a3f58baca937692c6c19e2d896b29af40
- Issue:             #1697
- Base SHA:          4c8aa79a3f58baca937692c6c19e2d896b29af40
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 13: "GATE: GO-WITH-CONDITIONS #1697"
- Recorded at:       2026-11-12T00:18:55Z

### Section B evidence
- commits since 2026-11-11T22:17:20Z: 658cdd55 (#1704) and 4c8aa79a (#1724) touched the two contracts, flow/eli5.md, codex/code_review.md and project/init.md for lanes; ce8d1821 (#1720) touched project/init.md. None adds a defect-origin line or a reader rule
- merged PRs: #1704, #1720, #1724; no open PR on these paths
- duplicate/superseding issues: #1698 folded into this issue and closed; none of #1705-#1719 covers either part
- this host: no sibling worktree holds unpushed commits on these paths
- two premises of the issue were wrong and its acceptance was amended on 2026-11-11 with the orchestrator's agreement: /project:init installed no issue templates; sessions file defects with gh, not the web form

### Scope of this run
This run delivers PART 1 only (PR A, a non-closing reference). Part 2 is a second run and a second PR, with its own Step-3 note.

### Conditions attached to the approval (PR A)
- One spelling: Origin: and Missed because: are fixed phrases with a closed answer list stated in ONE document (closing-report-contract.md); the issue contract, the form and /github:issue-create point at it or are tested equal to it. The test compares them and is shown red by altering one copy.
- "Readable later without a new tool" is proved: the one gh search command is in the contract; the PR says what it returns today and that an empty result does not show the search works; it is shown finding one seeded example.
- Blank and unknown on the form are distinguishable; say how.
- For each trimmed at-cap document: independent old-versus-new read before review; moved text verbatim in docs/commands-reference.md in a commit that lands before the removal; before and after word counts in the PR; no budget raised.
- The project-neutral form carries nothing specific to this repository.
- make lint and make typecheck before the gate; two review passes, ask before a third; no push for CI without the merge slot.

### Section C - the approved plan
1. `docs/agents/issue-contract.md` - a defect report says where the behaviour came from, pointing at the one list in the closing-report contract; one underlying defect is counted once
2. `docs/agents/closing-report-contract.md` - the Origin: and Missed because: lines with their closed answer lists, and the one gh search that reads them back
3. `.github/ISSUE_TEMPLATE/bug-report.yml` - optional Origin field
4. `.claude/commands/github/issue-create.md` - the bug path asks for the origin; equal trim, budget stays 591
5. `templates/github/ISSUE_TEMPLATE/bug-report.yml` - a project-neutral bug form carrying the field, for new projects
6. `.claude/commands/project/init.md` - Step 3 copies that form into the new repository; equal trim, budget stays 3848
7. `docs/commands-reference.md` - receives what items 4 and 6 move out, verbatim, in a commit before the removal
8. `tests/test_defect_origin.py` - pins the two lines and their answers across the contract, the issue contract, both forms, the issue-create question and the init step, and compares the copies
9. `CHANGELOG.md` - entry
Scope: 9 files, about 250 lines. No script, no gate.
Risks: two documents at their word caps are trimmed (independent old-versus-new read before review); the origin line is honest only if sessions fill it, and nothing checks that except the counter-model review of a fix.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | not applicable: no path-dependent behaviour |
| Harness | will test: the generated github-issue-create and project-init skills carry the new sentences |
| Driver | not applicable to Part 1: no review text changes |
| Coordination | not applicable |
| CI provider | not applicable |
| Project state | will test: the project-neutral form is a file the init step names, and the test checks it exists and carries the field |

<!-- flow-run n=2 id=827a3f784963499198a57af44e7561b4 -->
## Run 2

- Run-id:            827a3f784963499198a57af44e7561b4
- Run-start:         e33525d0f78c98cc613493a852e1bb0a777462a0
- Issue:             #1697
- Base SHA:          e33525d0f78c98cc613493a852e1bb0a777462a0
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only): "GATE: GO-WITH-CONDITIONS #1697" (mailbox rev 13, conditions 6-8 for Part 2), the Part 2 Step-3 note approved with additions (a) and (b) (rev 15), and the owner request added to Part 2 (rev 21, recorded on the issue as comment 6811369213)
- Recorded at:       2026-11-12T02:43:57Z

### Section B evidence
- Part 1 merged as e2c0d037 (#1738): the defect-origin lines and their closed lists, including the answer "reader not tested against real output" that Part 2's closing rows point at
- commits on Part 2's paths since the Part 1 run: e2c0d037 only; 4c8aa79a and 658cdd55 (lanes) are what Part 2 reuses: the "Lanes for this change" table, the lane section in flow/eli5.md, the LANES_LINE hand-over and lane question in codex/code_review.md, docs/agents/lanes.md
- merged or open PRs delivering a reader rule: none
- duplicate/superseding issues: none (#1698 was folded into this issue)
- this host: no sibling worktree holds unpushed commits on these paths

### Scope of this run
PART 2 of #1697 (PR B). It closes the issue.

### Conditions attached to the approval (PR B)
- flow/eli5.md: ONE sentence, inside the owner's freeze exception, budget unchanged at 2,651. If one sentence cannot carry it, stop and say so.
- Reader rows share the lanes table; the rule still applies in a repository with no lane file, and that is tested.
- The negative control is a model's judgement on a committed example pair: say so in the PR in those words and record the observation with its date and model.
- Owner request: the review also judges each lane TEST - one that reaches the lane only through a stand-in where the real thing could be used, or that could not fail if the lane were broken. Same judgement as the reader rule, so the wording is shared; the committed examples gain a lane case. codex/code_review.md stays at 6,359.
- For each trimmed at-cap document: independent old-versus-new read before review; moved text verbatim in docs/commands-reference.md in a commit before the removal; before and after word counts in the PR.
- The closing-report reader rows point at the "reader not tested against real output" answer from Part 1, so the two parts name the same thing once.
- make lint, make typecheck; two review passes, ask before a third; no push without the merge slot.

### Section C - the approved plan
1. `docs/agents/changed-output-readers.md` - the rule: a plan that changes an output names each reader and says tested against real output (naming the test), reader unchanged and why that is safe, or not covered; how readers were searched for; a stand-in is not evidence; the same judgement applied to lane tests
2. `docs/agents/issue-contract.md` - the rule in two sentences, linking item 1
3. `docs/agents/closing-report-contract.md` - reader rows in Evidence beside the lane rows, pointing at the Part 1 answer
4. `docs/agents/lanes.md` - reader rows go in the same table as `Reader: <who>`; a lane test is judged, not only counted
5. `.claude/commands/flow/eli5.md` - one sentence in the existing lane section; equal trim, budget stays 2651
6. `.claude/commands/codex/code_review.md` - the reader question and the test-quality question; equal trim, budget stays 6359
7. `docs/commands-reference.md` - receives the moved text, verbatim, in a commit before the removal
8. `tests/fixtures/readers/plan-stale-stub.md` - a writer gains a field and the reader's test uses a hand-written copy
9. `tests/fixtures/readers/plan-real-output.md` - the same change with the reader fed the writer's real output
10. `tests/fixtures/readers/plan-lane-stub-only.md` - a will-test lane covered only by a stand-in
11. `tests/fixtures/readers/plan-lane-real.md` - the same lane exercised for real
12. `tests/test_changed_output_readers.py` - pins the rule, the routing, the prompt questions, that the reader question does not depend on a lane file, and the example pairs
13. `CLAUDE.md` - one project-map line
14. `CHANGELOG.md` - entry
Scope: 14 files, about 400 lines. No script, no gate.
Risks: two documents at their word caps are trimmed (independent old-versus-new read before review); the red cases for both review questions are a model's judgement, recorded as observations, not make verify checks; the delegated-driver review surfaces get neither question.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | not applicable: no path-dependent behaviour |
| Harness | will test, with a new test in this diff: the generated flow-eli5 skill carries the new sentence. /codex:code_review is not generated as a Codex skill, so it has no mirror |
| Driver | not covered: the delegated-driver review surfaces get neither new question |
| Coordination | not applicable |
| CI provider | not applicable |
| Project state | will test, with new tests in this diff: the review hand-over with a lane file and without one - the reader question must be asked either way |
| Reader: the counter-model review prompt, read by the reviewing model | not covered by a deterministic test: its behaviour is a model's judgement, observed on the committed example pairs and recorded |
| Reader: tests/test_lanes_contract.py, which reads the prompt text between fixed markers | will test: it runs unchanged against the real edited document in this diff's gate |
