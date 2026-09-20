#!/usr/bin/env python3
"""BLIND ANCHOR for controls/counter-model-reviewer-attribution (issue #1048).

CONSTRUCTED, not historical. This instrument is new, so no blind ancestor
exists on main to vendor. Integrity is established by the registered sha256;
historicity is not.

WHAT IT IS: a presence-only attributor. It counts receipts and reports OK when
any exist. It never reads a rollout, never compares a stored reviewer against a
derived one, never asks whether its extractor can discriminate, and has no
notion of an ambiguous link. Presence is mistaken for attribution.

It therefore MISSES all four known-bad inputs - the copied literal that
disagrees with its rollout, the blind extractor that cannot tell a constant from
a reading, the corpus nothing links to, and the receipt whose linked rollouts
contradict each other - and AGREES with the real instrument on the known-good
case. Every distinction the real instrument draws is absent here, which is what
makes it the demonstration that those distinctions are load-bearing.
"""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipts-dir", type=Path, required=True)
    parser.add_argument("--rollouts-dir", type=Path)
    # ACCEPTED AND IGNORED, which is the blindness itself: the real instrument
    # needs a repository boundary because a branch suffix cannot tell this
    # repository's worktree from a neighbour's. This one never links anything,
    # so it has no use for the boundary - and must still parse the flag, or it
    # would CRASH rather than MISS, and a crash cannot demonstrate blindness.
    parser.add_argument("--repo-name")
    args = parser.parse_args()
    examined = 0
    for path in args.receipts_dir.rglob("*.json"):
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(receipt, dict):
            examined += 1
    if not examined:
        print("ATTRIBUTION-UNKNOWN: examined=0 - nothing was examined")
        return 2
    print(f"ATTRIBUTION-OK: examined={examined} - receipts are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
