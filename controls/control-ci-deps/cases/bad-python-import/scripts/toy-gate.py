#!/usr/bin/env python3
# NEGATIVE-CONTROL: controls/toy
"""A toy gate that imports a third-party module AT MODULE LEVEL.

`pydantic` is the real one: the negative-controls image has no virtualenv and
installs no python packages, so this import raises ModuleNotFoundError the
moment the battery loads this gate - and the battery refuses to skip a control
it cannot run, so ONE such control takes the whole register down. That is the
failure `check-control-ci-deps` exists to catch and could not see: it examined
the invocation (`python3`, which the image has), the shebang (likewise) and a
SHELL gate's binaries, never what a PYTHON gate imports (issue #1168).

The import is at module level on purpose. That makes it UNCONDITIONAL - loading
the module executes it - which is what the walk is entitled to decide. An import
inside a function would be conditional on a call path and is counted, not
followed.
"""

import argparse

import pydantic  # noqa: F401 - the whole point of this fixture


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.parse_args()
    print("TOY_GATE: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
