#!/usr/bin/env python3
# NEGATIVE-CONTROL: controls/toy
"""A toy gate whose ONLY third-party import sits under `if TYPE_CHECKING:`.

THE ONE CONDITION THAT IS FALSE BY DEFINITION. `typing.TYPE_CHECKING` is False
whenever the interpreter is running - that is the entire point of the idiom -
so this block cannot execute and this gate loads perfectly well in an image
with no pydantic. Measured: it does.

This case exists because the walk got that wrong (issue #1162). It tracked
EXECUTION SCOPE as "anything outside a function or lambda body", which is right
for `if True:`, `try/except ImportError` and class bodies - the three shapes a
counter-model review demonstrated against its first cut - and wrong for this
one. #1163 had made `lib/cicd/__init__.py` lazy with exactly this idiom, so the
check reported that a gate importing anything from `lib.cicd` "imports pydantic
at MODULE level, the import runs on load", about code that does not run, and
blocked a ratified change.

An over-approximating check states a claim its input does not support. That is
the same contract violation as an under-approximating one; it just fails in the
direction that looks responsible.
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # never executed at runtime
    import pydantic  # noqa: F401 - the whole point of this fixture


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.parse_args()
    print("TOY_GATE: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
