<!-- flow-run n=1 id=73f90c0400c949388d537ef67e554c86 -->
## Run 1 - issue #1362 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1362
- Read at:      2026-09-30T19:30:33Z
- updatedAt:    2026-09-30T19:00:12Z   (context only - moves on comments and labels)
- Body digest:  cfa64a309d87dd5af41948c32a3db45d6eff0d37c37cb586436022a6540c583f   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2721 of 2721 (cap 16384)

### Body as read
## Symptom

The flow finish gate's test-step line reports an expected failure (xfail) as a failure, inside a SUCCESS verdict. Observed 2026-09-30 in cooneycw/kyle, on the flow:auto run for kyle#1401:

```
[2/5] test: SUCCESS (8114 passed, 1 failed, 10 skipped)
```

Nothing failed. The two pytest invocations ended:

```
7948 passed, 7 skipped
165 passed, 3 skipped, 1 xfailed, 1 xpassed
```

The totals reconcile only if the strict `xfail` is counted as "failed" and the `xpass` as "passed": 7948 + 165 + 1 = 8114. The same thing happened on a second gate run after a merge from main: `8130 passed, 1 failed`. In both runs the gate verdict (`FLOW_FINISH_GATE: ok`) was correct; only the displayed counts are wrong.

## Cause

`lib/cicd/outcomes.py:367-370` (`_parse_pytest_line`, at `8045fb39`):

```python
passed=counts.get("passed", 0) + counts.get("xpassed", 0),
failed=counts.get("failed", 0) + counts.get("xfailed", 0),
```

This folding was **deliberate**, from #621 / PR #624 (`211a5094`). Both xfailed and xpassed tests *executed*, and #621's question was "did anything run", not "did anything fail". The summary line then reuses `failed` as if it meant failures.

## Why it matters

A line reading "N failed" beside SUCCESS teaches readers either to ignore "failed" or to stop and investigate a pass. The second happened here: the run had to reconcile the counts by hand before it could trust the gate. The first is worse, because it trains readers to miss a real failure. The summary is read as evidence by sessions that never see the raw pytest output.

## Fix, constrained by #621

Carry `xfailed` and `xpassed` as their own counts in `SuiteOutcome`, and keep the "executed" computation #621 relies on: executed = passed + failed + xfailed + xpassed + errors. Render the summary with its own categories, for example `8113 passed, 1 xfailed, 1 xpassed, 10 skipped`. Do **not** fix this by dropping xfail from the executed count. That would reopen #621's case, where a suite whose only tests are xfails reads as having executed nothing.

## Acceptance

- [ ] A pytest tail of `165 passed, 3 skipped, 1 xfailed, 1 xpassed` renders with 0 failed, 1 xfailed and 1 xpassed. The test must fail on current main; run it there and record the output.
- [ ] A tail of `1 failed, 1 xfailed` still renders 1 failed, so a real failure is not absorbed.
- [ ] #621's control still holds: an all-skipped suite is not a bare SUCCESS, and an xfail-only suite still counts as executed.

Source: Nit Store record #864 (comment 5917286405), found while working cooneycw/kyle#1401. No open issue covers gate summary counts; #621 is the closed origin of the folding, and #1298 (closed) was the nearest lib/cicd classification work.

