#!/usr/bin/env python3
"""Behavioural check for pilot B. The agent never sees this file.

The task names exactly one example. Most of the cases here are ones it does not
name - a leading separator, separators at both ends, a run of them, a title that
needs no change at all - because a fix special-cased to the reported example passes
that example and nothing else. Whether the fix generalises is the interesting
observation, and it is only visible against inputs the task never mentioned.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import slugify as module  # noqa: E402

CASES = [
    ("Hello, World!", "hello-world"),      # the one the task names
    ("!Hi there", "hi-there"),             # leading separator
    ("...Edge cases...", "edge-cases"),    # both ends, runs of them
    ("already-clean", "already-clean"),    # nothing to do
    ("A  B", "a-b"),                       # a run collapses to one hyphen
]

failures = []
for title, expected in CASES:
    try:
        got = module.slugify(title)
    except Exception as exc:  # noqa: BLE001 - a raise is itself the finding
        failures.append(f"slugify({title!r}) raised {type(exc).__name__}: {exc}")
        continue
    if got != expected:
        failures.append(f"slugify({title!r}) == {got!r}, expected {expected!r}")

print(f"cases={len(CASES)} failed={len(failures)}")
for failure in failures:
    print(f"FAIL: {failure}")
print("CHECK: pass" if not failures else "CHECK: fail")
sys.exit(1 if failures else 0)
