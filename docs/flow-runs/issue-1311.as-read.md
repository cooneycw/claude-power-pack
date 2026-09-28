# Issue #1311 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1311
- Read at:      2026-09-28T12:16:31Z
- updatedAt:    2026-09-28T11:58:01Z   (context only - moves on comments and labels)
- Body digest:  96503fcf5e7e8b88d0074ba5f2d8e4df4c66a8499a3e65c07b8b2ab7929dee12   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2730 of 2730 (cap 16384)

## Body as read
## Problem

Under load on the shared Woodpecker, three different tests turned one PR's required lane red on three consecutive runs. None of them is touched by that PR (#1307 changes only `lib/cicd/steps.py` and its tests). Each spurious red costs a full 4-9 min pipeline on a CI server the operator reports as "running hot", and it teaches "retry the red", which is how a real regression in these paths would get retried past.

| pipeline | test | failure | class |
|---|---|---|---|
| 2805 | `tests/test_test_binary_guards.py::test_real_tests_tree_is_clean`, `::test_rev_widening_reaches_zero_findings`, `tests/test_negative_controls.py::test_discover_is_not_recursive_so_nested_case_trees_are_not_double_discovered`, + 4 setup ERRORs in negative-controls battery fixtures | `Failed: Timeout (>120.0s) from pytest-timeout` | timeout budget |
| 2811 | `tests/test_flow_finish_gate.py::test_an_interrupted_gate_leaves_no_runner_json_behind` | `assert ['flow-finish-gate.9OcbCl'] == []`. The push pipeline 2810 on the SAME commit passed it. | async race: asserts cleanup before the gate has exited |
| 2815 | `tests/test_flow_wave_mailbox.py::TestSupervise::test_after_the_daemon_dies_a_new_supervise_may_start` | `assert not True` at `assert not _pid_alive(pid)` straight after `_kill_daemon(pid)` (~:2056-2057) | async race: asserts death with no wait |

Nit Store records: #864 comments 5869151666, 5869264490, 5869356963.

Same class as #1297, where the race was reproduced with the exact CI signature by delaying the fake daemon's trap: an assertion that runs before the asynchronous effect it checks.

## Scope

1. **The two async-race tests:** wait for the effect with a bounded poll (or an explicit event), never elapsed time, and never assert immediately after the action. Each needs a red case: the OLD assertion fails under an injected delay (as #1297 did), and the new one passes under the same delay.
2. **The 120s timeout budget:** first establish whether these tests are SLOW or HUNG under load. Read the per-test timings from pipeline 2805's validate step, and compare with a quiet run. Do not just raise the limit, because a bigger timeout on a hung test only hides it. If they are merely slow, make them cheaper or give them an honest budget with the measured basis stated; if hung, find what hangs.
3. **Evidence of stability:** a one-off loop run of the fixed tests (e.g. 20x), stating which copy (repo `scripts/` vs installed) and which uid it ran under.

## Not in scope

Changing pytest-timeout globally. The production code the tests exercise, unless a separate defect is reproduced (then a separate issue).

Found while orchestrating the CPP run (run45). Prioritised first in phase C at master's direction.
