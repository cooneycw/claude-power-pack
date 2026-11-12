# Flow run record - issue #1718

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=1bc8b0b82a714fb7906ea5d1426e542d -->
## Run 1

- Run-id:            1bc8b0b82a714fb7906ea5d1426e542d
- Run-start:         3e52bf6d67ac80607ccb82bd5f29ecaf149e032f
- Issue:             #1718
- Base SHA:          0bf7ba72
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "GATE: GO-WITH-CONDITIONS #1718", outbox rev 60, 2026-11-12T00:34:11-05:00
- Recorded at:       2026-11-12T05:50:00Z

### Section B evidence
- The 274 "No module named yaml" failures: tests/test_cpp_runner_runtime.py points the real finish gate at the checkout the suite runs from, offline with an empty uv cache; on a 3.12 .venv uv removes it, recreates it on 3.11 and leaves it empty. Reproduced on a scratch copy. tests/test_step9_verify_executes.py rebuilds the same .venv and passes
- CI validate runs as root; about 26 test functions skip there, counted nowhere
- 406 call sites set a private subprocess timeout below the suite's 120 seconds
- One worktree-remove.sh call costs 2.1 to 2.2 seconds against the real /proc and 0.12 against a one-entry seam
- The stalled-control BLIND readings and the coordination-signal test share one cause: curl stubs that never read stdin under a piped header and pipefail. Attribution to the CI failures is unconfirmed

### Rulings and gate conditions (orchestrator)
- Rows 3 and 4 (both rebuild the surrounding venv) are their own first PR, ahead of everything not already queued. The remaining rows are the second PR, a third if it passes 800 lines.
- U1: row 5 (a gate rebuilds a .venv in place) is its own issue, medium; a committed .python-version is proposed there, not here.
- U2: tests move to the fixture process table through the documented seams; the scripts are not touched; tests whose subject is the real scan stay on real /proc and are named; the cheaper scan is a Nit Store comment.
- U3: the header-writer hardening in two frozen scripts is a Nit Store comment.
- U4: no second interpreter in CI; stated beside the skip and counted in the log.
- U5: only the named bounds change.
- Condition 1: the surrounding .venv is asserted UNCHANGED (interpreter version and site-packages listing) after the test, from a main checkout and from a linked worktree; the owned copy's cost is measured.
- Condition 2: the PR says row 1 is the test that reddened main on 2026-11-11 (pipeline 3689).
- Condition 3: the attribution of rows 18 and 19 to the CI failures stays "unconfirmed" in the PR.
- Condition 4: skip counts reported from this PR's own pipeline log; stop if validate is not root there.
- Condition 5: the CI file line, the Makefile comment and the new doc are the only non-test edits; verify-coverage-check output diffed.
- Condition 6: edits to shared test files stay inside helpers; re-sync before the gate.
- Condition 7: make lint, make typecheck; two review passes each.

## Section C - the approved plan
  1. `tests/test_cpp_runner_runtime.py` - the gate runs against an owned copy of the checkout; the surrounding .venv is asserted unchanged; the CI skip is stated
  2. `tests/test_step9_verify_executes.py` - the same owned copy; the Python 3.11 probe as its guard
  3. `tests/conftest.py` - the owned-copy fixture; later the shared non-root marker and the 3.11 probe
  4. `tests/test_silent_test_success.py` - the 3.11 probe as its guard
  5. `tests/test_code_review_diff_file_cleanup.py` - its own file, not a glob of /tmp
  6. `tests/test_code_review_diff_range.py` - removes the file it creates
  7. `tests/test_flow_finish_gate.py` - one base-environment helper
  8. `tests/test_negative_controls.py` - the untracked probe in a throwaway root
  9. `tests/test_gh_pr_merge.py` - the curl stub drains stdin
  10. `controls/flow-ci-status-stalled/run-case.sh` - the stub drains stdin; running needs the stall check to have run
  11. `tests/test_cpp_host_install_receipt.py` - the private 30 second bound removed
  12. `tests/test_worktree_remove_squash.py` - the fixture process table
  13. `tests/test_worktree_remove_partial.py` - the fixture process table where the scan is not the subject
  14. `tests/test_worktree_remove_occupied.py` - the fixture process table; an occupant the fixture holds
  15. `tests/test_worktree_sweep.py` - the fixture process table; an occupant the fixture holds
  16. `tests/test_ci_declared_facts.py` - new: the tripwire that validate runs as root
  17. `.woodpecker.yml` - the pytest line reports skips by reason
  18. `tests/test_delegated_lane_failure_detection.py` - the capture predicate, with red fixtures
  19. `tests/test_hook_permission_census.py` - the paren-depth walk, with a red fixture
  20. `Makefile` - a comment at verify naming the two tests that pin its prerequisite count
  21. `docs/agents/test-environment.md` - new: what the suite assumes, and how to read a load red
Scope: 21 files; PR 1 is items 1 to 3 only.
Risks: an owned copy must be cheap; moving tests onto a fixture process table can hide a real /proc regression; shared test files are also touched by other queued branches.

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | The gate runs against an owned copy, shown from a plain clone and from a linked worktree, with the surrounding .venv unchanged afterwards |
| Harness | not applicable | Tests and fixtures; nothing installed or bundled changes |
| Driver | not applicable | No driver-facing output |
| Coordination | not applicable | Only a curl stub changes in the coordination-signal test |
| CI provider | will test (Woodpecker); not covered (GitHub Actions) | The skip-reason line and the root tripwire are read from the PR's own pipeline log |
| Project state | not applicable | No adopted file or record is read |

<!-- flow-run n=2 id=510dae0f52144152ab0e1e7ec3f29ac1 -->
## Run 2

- Run-id:            510dae0f52144152ab0e1e7ec3f29ac1
- Run-start:         fa87091af894dec8a554bb6987fee9fc951cc1a0
- Issue:             #1718
- Base SHA:          fa87091af894dec8a554bb6987fee9fc951cc1a0
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "YES to cutting rows 18 and 19 out as their own small test-only change: build it now, branch from main, its own plan record and lanes line, one Codex pass", outbox rev 94
- Recorded at:       2026-11-12T07:50:00Z

### Section B evidence
- Row 19 failed again on PR pipeline 3773 (PR #1757, `[true]`), after pipelines 3612 and 3635; row 18 read BLIND on pipelines 3553 and 3620. One cause, established in the survey: the script pipes an Authorization header into curl under `pipefail`, and the fixture's curl stub exits without reading stdin.
- commits touching these files since run 1: PR #1764 (run 1's first change) touched none of them
- This is the second change under run 1's survey, cut out of the remaining rows so it can land first; the other rows stay for a later change.

### Rulings and gate conditions (orchestrator)
- Test-only; branch from main; one Codex pass; goes directly after #1732.
- Show it red first: run the unfixed test in a loop until it fails once, or state the count run if it will not; then the fixed one the same count.

### Section C - the approved plan
1. `tests/test_gh_pr_merge.py` - the curl stub reads the header it is piped, so the writer cannot lose a race to the stub's exit (row 19)
2. `controls/flow-ci-status-stalled/run-case.sh` - the stub reads its stdin; `running` counts as the good answer only with `FLOW_CI_STALL_CHECK: checked` (row 18)
3. `controls/flow-ci-status/run-case.sh` - the stub reads its stdin (row 18, sibling)
4. `controls/flow-ci-status-wait/run-case.sh` - the stub reads its stdin (row 18, sibling)
5. `controls/flow-ci-status-cancellation/run-case.sh` - the stub reads its stdin (row 18, sibling)
6. `tests/test_curl_stubs_read_stdin.py` - every curl stub fed a header on stdin reads it; the stalled control's runner refuses `running` without a checked stall

Scope: 6 files, about 15 changed lines in fixtures and one new test file.

Risks: the control runners are instruments, and a change to one can remove the distinction it draws - each control is re-verified by name with its anchor after the change; a stub that reads stdin where nothing is piped would wait on an open stdin, so the read happens only where the header is piped.

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | not applicable | Fixtures build their own temporary directories; no checkout shape is read |
| Harness | not applicable | Tests and control runners; nothing installed or bundled changes |
| Driver | not applicable | No driver-facing output |
| Coordination | will test | The coordination-signal test is the one that failed; it is run in a loop before and after |
| CI provider | will test (recorded output) | The stubs stand in for the Woodpecker API; the four controls are verified by name. No live provider is called |
| Project state | not applicable | No adopted file or record is read |
