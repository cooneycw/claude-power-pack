# Flow run record - issue #1726

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=9a339207415a4b488d0161bffa83ef10 -->
## Run 1

- Run-id:            9a339207415a4b488d0161bffa83ef10
- Run-start:         ee4ca592f6a6c5da9c51750f9afe46abe091761b
- Issue:             #1726
- Base SHA:          ee4ca592f6a6c5da9c51750f9afe46abe091761b
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "GATE: GO-WITH-CONDITIONS #1726", outbox rev 42, 2026-11-11T22:18:46-05:00
- Recorded at:       2026-11-12T04:35:00Z

### Section B evidence
- 0dea8c26 (#1693) moved lines; the issue's line numbers are stale. No refusal was removed or added by it
- ee4ca592 (#1709) added tests for many claim paths and sweep --apply tests with real removal, and added stand-down branches with their own tests; it added no registered control for the claim helper and no --apply case to the sweep's control
- The guard's --help still prints a hard-coded line range
- Each of the thirty listed refusals is confirmed individually as the first step

### Rulings and gate conditions (orchestrator)
- Condition 1: the table on #1726 puts every refusal in exactly one of three columns: now has a case (named); already had one (named); unreachable, with what would have to be true to reach it.
- Condition 2: a refusal that is unreachable AND guards against data loss goes to the orchestrator by mail the moment it is found, and to the top of the PR.
- Condition 3: each new test asserts the exit code and the specific message and is shown red by neutering its refusal in a scratch copy; for failure-injection cases, a stub failing for the wrong caller does not make the test pass.
- Condition 4: the three controls are verified with --control by name; registrations before the first gate run; every removal-running runner works only inside a mktemp directory, takes no path from the environment, and refuses a target outside the directory it created.
- Condition 5: the claim control uses a historical anchor only if its commit is on main's history and still discriminates; otherwise a constructed anchor, and say which and why.
- Condition 6: the guard's --help is bounded by the header's own extent, with a test red against the line-range version.
- Condition 7: over 800 lines, split by script into two PRs and tell the orchestrator first.
- Condition 8: make lint, make typecheck, make shellcheck read to the end; two review passes.
- No test hook is added to a script to reach a refusal.

## Section C - the approved plan
  1. `tests/test_merge_tail_refusals.py` - new: one test per reachable refusal, asserting exit code and message, grouped by script
  2. `controls/flow-worktree-claim/control.json` - new control for the claim helper, with its runner, cases and anchor
  3. `controls/flow-worktree-guard/control.json` - gains an exit-3 leak case
  4. `controls/flow-worktree-sweep/control.json` - gains an --apply case and a partial exit-3 case
  5. `controls/census.md` - the three rows updated
  6. `scripts/flow-worktree-guard.sh` - --help prints the header by its own extent
  7. `tests/test_flow_helper_help.py` - the guard joins the test that fails on a line-range --help
  8. `docs/scripts/flow-worktree-guard.md` - the help fix, one line
Scope: 8 named files plus control case fixtures and runners. One script line changed. About 500 lines of test and fixture.
Risks: some refusals may be unreachable; failure-injection stubs can fail for the wrong caller; controls for deleting scripts run real removals in a temporary repository.

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | Every case builds a main checkout plus a linked worktree |
| Harness | will test (Claude install); not covered (Codex install) | The guard's --help reads its own file and is tested through a symlink. No test runs the helpers from a Codex bundle |
| Driver | not applicable | No driver-facing output changes |
| Coordination | not applicable | No coordination path |
| CI provider | will test (recorded output) | gh-pr-merge's cases feed it recorded gh output through the stub the existing tests use; no live provider |
| Project state | not applicable | No adopted file or record is read |
