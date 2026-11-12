# Flow run record - issue #1727

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=efb1ed5b744a4ec48a2745c264bcce10 -->
## Run 1

- Run-id:            efb1ed5b744a4ec48a2745c264bcce10
- Run-start:         4f585adf5619414b800489e08b133e56d0c2b4d8
- Issue:             #1727
- Base SHA:          4f585adf5619414b800489e08b133e56d0c2b4d8
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          the owner chose option 2 on 2026-11-12 ("Remove it."), relayed by the wave orchestrator (wave cpp-improvement) in mailbox rev 70 to role cpp-1508 at 2026-11-12T01:51:52-05:00: "GATE: GO-WITH-CONDITIONS #1727" and "RATIFY: option 2 for #1727, by the owner"
- Recorded at:       2026-11-12T07:20:00Z

### Section B evidence
- `DeterministicRunner.resume`, behind `python -m lib.cicd resume <run_id>`, carries a failed run's earlier results without comparing the tree signature, and reports an already-succeeded run as success without running anything or looking at the tree. `run` makes the comparison before its own automatic resume.
- No caller of `lib.cicd resume`, `resume_run(`, `cmd_resume` or `runner.resume(` on origin/main of kyle, skillc or kyle-candidate (a clone at ff51017) outside pinned fixtures; in this repository only `lib/cicd/cli.py` and three tests.
- Coordination issues filed before any edit: kyle #2371, skillc #712, kyle-candidate #14.

### Section C - the approved plan
Conditions attached to the approval: `run` and its tree-checked automatic resume are untouched and its existing tests pass unchanged; before deleting the test that covers the "state loaded, nothing generated" evidence shape, establish whether `run` can produce that shape, and if it cannot, report it and leave any code that handles it; a test each that the subcommand is an argparse invalid choice (exit 2) and that importing `resume_run` raises ImportError; `status <run_id>` still works on a run recorded before the change, tested; every mention of the subcommand in command documents and docs is removed or corrected and listed; the PR closes #1727; one review pass unless it returns a medium or higher.

1. `lib/cicd/cli.py` - remove the `resume` subparser, `cmd_resume` and its dispatch entry.
2. `lib/cicd/runner.py` - remove `resume_run` and `DeterministicRunner.resume`.
3. `tests/test_runner.py` - remove the three tests that call them; add the tests that pin the removal and that `status` still works.
4. `.specify/specs/cicd-reliability/spec.md` - remove the unticked acceptance line for the subcommand.

Scope: about 90 lines out, about 40 lines of tests in. Nothing is added to the runner.

Risks: a caller that builds the command at run time, which no search can see (the coordination issues ask each repository to confirm); the evidence shape that only the removed path produced.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test: pytest on lib/cicd in this linked worktree; the removed entry points shown gone and `run`'s automatic-resume tests unchanged |
| Harness | will test: lib/cicd is bundled into Codex skills; mirrors rebuilt and tests/test_codex_skill_sync.py; a live Codex run is not covered |
| Driver | not applicable: no driver-specific code |
| Coordination | not applicable: no wave, mailbox or registry code |
| CI provider | not applicable: no pipeline or CI-status code |
| Project state | will test: the finish gate's runner lane end to end, which calls `run` and never `resume`, before and after |
