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
