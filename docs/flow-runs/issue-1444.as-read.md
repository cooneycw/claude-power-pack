<!-- flow-run n=1 id=ea8cd2ebbd0c4c57984fe884e3856cb9 -->
## Run 1 - issue #1444 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1444
- Read at:      2026-10-12T16:42:24Z
- updatedAt:    2026-10-12T15:10:04Z   (context only - moves on comments and labels)
- Body digest:  e05bf6f7bd9f3b2567eb9accef69867234edc725d25673701d796cdea30238c9   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1734 of 1734 (cap 16384)

### Body as read
## Problem

`tests/test_negative_controls.py::test_self_registration_is_blind_to_a_verdict_assignment_breakage` fails intermittently with:

```
AssertionError: could not take the live controls tree lock within 150.0s (...cpp-live-controls-<hash>.lock); another test is holding it far longer than its ~20s window
```

Its lock partner, `test_an_untracked_control_file_refuses_the_green`, is documented as holding `live_controls_tree_exclusive()` for ~19-20s. On this host on 2026-10-12 it measured:

| tree | duration (`--durations`) |
|---|---|
| #1442 branch (main + `.claude/security.yml`) | 170.95s |
| #1441 branch (main + one new control, no `security.yml`) | 163.37s |

Both are past the 150s budget (`_LOCK_BUDGET`), so whenever xdist schedules the two tests to overlap, the waiter fails. That happened in 2 of 2 full `flow-finish-gate.sh` runs on the #1442 branch (7571 passed, 1 failed). The #1441 branch's `make verify` passed only because the two did not overlap that run. Host load average was ~12 on 24 cores, with other CPP and skillc suites running concurrently.

## Not yet known

Whether the slowdown comes from the controls battery growing since the ~20s figure was measured, or from host load. Neither branch's change can account for 140s+. Measuring the holder on a clean `origin/main` export, idle and under load, separates the two.

## Why it matters

It is an intermittent red in `make verify` and `flow-finish-gate.sh` for every CPP run, and nothing in the diff under review causes it. The test's own docstring calls this outcome "a defect in that test, not here".

Found while running `/flow:auto #1442`. Merged past it with owner approval.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

