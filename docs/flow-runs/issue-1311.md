# Flow run record - issue #1311

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1311
- Base SHA:          e04cd02a677fa403576786c811511ef41a150551
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox messages 1914 and 1921 in reply to 1913 and ELI5 1916
- Recorded at:       2026-09-28T13:00:00Z

## Section B evidence
- 1a (finish-gate runner JSON) is a REAL leak in scripts/flow-finish-gate.sh, not a
  test race: slow-tee injection leaks 2/2, control 3/3 clean. Filed as #1313; the
  test stays as-is. Dropped from #1311.
- 1b (mailbox supervise death check): REPRODUCED - after kill_supervise_daemon returns
  True, an unreaped zombie reads alive to the test's kill(0) `_pid_alive`
  (`assert not True`, the CI signature) and dead to supervise_reap.pid_alive.
- 2 (timeouts): pipeline 2805 stacks show active work (ast.parse; subprocess
  communicate on the battery) - slow, not hung. Recurring across 2805/2817/2825.
  Quiet baseline pending a suite slot (host under freeze).

## Section C - the approved plan
1. `tests/test_flow_wave_mailbox.py` - 1b: assert kill_supervise_daemon's True and check death with the zombie-excluding pid_alive; red case = an unreaped zombie
2. `tests/test_negative_controls.py` - test_discover_is_not_recursive calls discover() directly instead of the whole battery; per-test budgets for the battery fixture / mutant scan only after a quiet baseline
3. `tests/test_test_binary_guards.py` - per-test budget or a cheaper scan, after the quiet baseline

Scope: ~3 test files, ~100 lines. Risk: a per-test budget can hide a hang - each states its
measured basis. check-negative-controls.py untouched. No global timeout change.
