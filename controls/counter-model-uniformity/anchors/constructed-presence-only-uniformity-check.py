#!/usr/bin/env python3
"""BLIND ANCHOR for controls/counter-model-uniformity (issue #1091).

CONSTRUCTED, not historical. This gate is new, so no blind ancestor exists on
main to vendor. Integrity is established by the registered sha256; historicity
is not. This weaker instrument checks only that some receipt records exist.
It mistakes presence for proof, never reading independent reviewer evidence.
It MISSES copied literals, unverified uniformity and a skipped-only population,
and AGREES with both GOOD cases. Presence is mistaken for examination, and
examination for verification: none of the three denominators is distinguished.
"""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipts-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path)
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
        print("UNIFORMITY-UNKNOWN: examined=0 - nothing was examined")
        return 2
    print(f"UNIFORMITY-OK: examined={examined} - receipts are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
