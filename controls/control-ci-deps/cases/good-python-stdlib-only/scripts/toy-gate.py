#!/usr/bin/env python3
# NEGATIVE-CONTROL: controls/toy
"""A toy gate whose module-level imports are all stdlib.

    The guard rail for its `bad-python-import` sibling: "flag a python gate whose
    imports the image lacks" is satisfiable by flagging every python gate, which
    would red 26 of this repository's 41 controls and make the check useless.
    """

import argparse
import json  # noqa: F401 - stdlib only; the point is that the image HAS it


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.parse_args()
    print("TOY_GATE: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
