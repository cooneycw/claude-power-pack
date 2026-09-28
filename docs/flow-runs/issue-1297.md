# Flow run record - issue #1297

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1297
- Base SHA:          7d1ad79
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 1845 in reply to ELI5 message 1843
- Recorded at:       2026-09-28T12:20:00Z

## Section B evidence
- REPRODUCED on 7d1ad79: a fake daemon whose `trap '' TERM` is delayed 0.3s dies of
  SIGTERM (-15) right after `_fake_daemon` returns, 3/3; the target test with that
  delay fails with the CI signature `assert 1 == 2`. INFERRED: that pipeline 2769's
  failure was this race.
- Commits since filing on tests/test_supervise_sweep.py / tests/supervise_reap.py:
  none after #1295. Merged PRs since: 1296, 1302, 1304, 1305, 1306. Duplicate: none.

## Section C - the approved plan
1. `tests/test_supervise_sweep.py` - `_fake_daemon` gains `setup` + a ready file written after it; bounded wait that fails clearly with cleanup on early exit or timeout; argv wait fails instead of falling through; target test moves its trap into setup; new tests for the delayed trap, early exit and never-ready

Scope: 1 test file, ~80 lines. Risk: the other five callers inherit a stricter start.
Production reaper untouched. Negative control re-proved by mutating reap._sweep_kill.
