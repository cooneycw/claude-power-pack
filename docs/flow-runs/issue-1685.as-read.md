<!-- flow-run n=1 id=39bf3661a9214e9593740e59f505080a -->
## Run 1 - issue #1685 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1685
- Read at:      2026-11-11T20:44:13Z
- updatedAt:    2026-11-11T20:43:17Z   (context only - moves on comments and labels)
- Body digest:  30759584f752d7733bc6fd531729ad734a5b9029f6976a5a200f696d7c1b993d   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2241 of 2241 (cap 16384)

### Body as read
## What happened

Push pipeline [3663](https://woodpecker.essent-ai.com/repos/1/pipeline/3663) on `main` at d79d0042 (the squash of PR #1683, issue #1671) failed its `validate` step: **1 failed, 10364 passed, 112 skipped**. The PR pipeline 3662 passed on the same tested tree minutes earlier, and PR #1683 does not touch the failing test or anything it exercises (`tests/test_flow_wave_mailbox.py`, `scripts/flow-wave-mailbox.sh`).

```
tests/test_flow_wave_mailbox.py:3080: ValueError
FAILED tests/test_flow_wave_mailbox.py::TestWatcherIdentityAcrossDirectories::test_a_same_wave_orphan_would_not_be_excluded_by_directory_alone
  child_pid = int(marker.read_text().strip())
  ValueError: invalid literal for int() with base 10: ''
```

## Cause (read from the code, not reproduced locally)

```python
parent = subprocess.Popen(
    ["bash", "-c", f'exec bash -c "sleep 100" & echo $! > {marker}; sleep 100'], env=env)
assert _wait_for(marker.exists, timeout=10), "child never forked"
child_pid = int(marker.read_text().strip())
```

`echo $! > marker` creates the file (the redirect opens and truncates it) before `echo` writes the pid. `marker.exists` is therefore true for a short window in which the file is empty, and a poll that lands in that window reads `''`. The readiness condition is "the file exists", and it needs to be "the file holds a pid".

## Why it matters

It reds `main`'s push pipeline for a commit whose change is unrelated, which stops the post-merge verify step of `/flow:auto` and reads as a regression in whatever merged last. The test's own docstring says it was written to be deterministic; this readiness check is the non-deterministic part left in it. #1506 / #1573 synchronised other fixtures in this file and did not cover this one.

## Suggested fix

Wait for content, not existence: poll until `marker.read_text().strip().isdigit()`, or write to a temp name and `mv` it into place in the bash snippet so the file appears already complete. Check the file for other `marker.exists` waits followed by an immediate read of the same file.

## Not established

Frequency. This is one observed failure; I did not loop the test to measure a rate.

Found while running Step 8 (verify CI) of `/flow:auto` for #1671.

<!-- end of body -->
