#!/usr/bin/env python3
"""CONSTRUCTED ANCHOR - a plausible, blind framing of the same gate.

Not a strawman. This is "check the behavioural eval produced valid output",
written directly: parse each artifact, complain if one is malformed, otherwise
report clean. It is the framing skillc's own contract warns against in so many
words - "A valid JSON record, hash or echoed config alone does not authenticate
success" (PLAN.md) - and it is what someone writes when the artifact is thought of
as OUTPUT to be validated rather than as a VERDICT to be read.

It is blind in every direction the real gate can see, which is why it is the
right anchor (no count here on purpose - a number in prose goes stale against the
list beneath it, which is exactly the defect found in issue #1084's own body):

  - it never reads `status`, so an artifact recording FAIL reads as clean
  - it has nothing to validate when no artifact exists, so ABSENT reads as clean
  - it never reads `version`, so an envelope it cannot understand reads as clean
  - it never DERIVES `status` from `criteria`, so a record declaring PASS over a
    mandatory VIOLATED criterion - or over no mandatory criteria at all - reads as
    clean. This is the sharpest of the four: both forgeries are WELL FORMED and
    parse perfectly, so "validate the output" cannot distinguish them by
    construction, however carefully it is written.

and it agrees with the real gate on a genuine PASS, which is what makes the three
misses load-bearing rather than evidence that the anchor is simply broken.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="docs/measurements/behavioral-eval")
    args = parser.parse_args(argv)

    malformed = []
    for path in sorted(Path(args.dir).glob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            malformed.append(f"{path.name}: {exc}")

    if malformed:
        print("behavioral-eval: failure - " + "; ".join(malformed))
        return 1
    print("behavioral-eval: pass - artifacts are well formed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
