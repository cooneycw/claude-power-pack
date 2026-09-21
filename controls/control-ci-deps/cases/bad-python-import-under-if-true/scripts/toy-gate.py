#!/usr/bin/env python3
# NEGATIVE-CONTROL: controls/toy
"""A toy gate importing pydantic under `if True:` - which DOES run.

THE NEGATIVE MEMBERSHIP for the TYPE_CHECKING exemption (issue #1162). That
exemption is matched as a LITERAL - the bare name `TYPE_CHECKING` or the
attribute `typing.TYPE_CHECKING` - and never by evaluating the condition, so a
block that is just as "obviously" constant to a reader must still report.

Without this case, widening the exemption to "any if whose test looks constant"
would keep the sibling case green and nothing would object. The first cut of
the fix ALSO deferred the whole `ast.If` including its `else:`, which silently
exempted an import that runs; that is why the walker now defers only the `if`
body, and why this case is a pair with its sibling rather than a spare.
"""

from __future__ import annotations

import argparse

if True:  # noqa: SIM108 - deliberately a runtime branch that executes
    import pydantic  # noqa: F401 - the whole point of this fixture


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.parse_args()
    print("TOY_GATE: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
