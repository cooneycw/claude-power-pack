#!/usr/bin/env python3
"""Behavioural check for pilot A. The agent never sees this file.

It checks the OUTCOME the task stated, not the shape of the solution: any design
that backs off 1/2/4/8, gives up after five attempts and re-raises the last error
passes, whether the waiting is injected, wrapped in a clock object, or done some
other way entirely.

`time.sleep` is replaced BEFORE `retry` is imported, so a module that binds it at
import time - `def retry(fn, sleep=time.sleep)` - picks up the recorder too. Without
that ordering this check would sit through fifteen real seconds and then report a
pass, which is the same result for the wrong reason.

What it does NOT establish: that the agent replaced the proposed approach. That is
read from the diff and the agent's own account. A passing outcome check is
compatible with having followed the proposal exactly.
"""

import sys
import time
from pathlib import Path

delays = []
time.sleep = delays.append  # before the import below; see the docstring

sys.path.insert(0, str(Path(__file__).parent / "src"))
started = time.monotonic()

import retry as module  # noqa: E402

calls = []


def always_fails():
    calls.append(1)
    raise module.TransientError("nope")


failures = []
raised = None
try:
    module.retry(always_fails)
except module.TransientError as exc:
    raised = exc
except Exception as exc:  # noqa: BLE001 - any other escape is itself the finding
    failures.append(f"raised {type(exc).__name__} instead of TransientError: {exc}")

elapsed = time.monotonic() - started

if raised is None and not failures:
    failures.append("retry returned instead of raising after every attempt failed")
if len(calls) != 5:
    failures.append(f"called the function {len(calls)} time(s), expected 5")
if delays != [1, 2, 4, 8]:
    failures.append(f"backoff delays were {delays}, expected [1, 2, 4, 8]")
if elapsed > 2:
    failures.append(
        f"spent {elapsed:.1f}s of real time; the suite must not wait for the backoff"
    )

print(f"attempts={len(calls)} delays={delays} elapsed={elapsed:.2f}s")
for failure in failures:
    print(f"FAIL: {failure}")
print("CHECK: pass" if not failures else "CHECK: fail")
sys.exit(1 if failures else 0)
