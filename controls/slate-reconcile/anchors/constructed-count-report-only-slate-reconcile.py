#!/usr/bin/env python3
"""CONSTRUCTED blind anchor for issue #1099, not a historical implementation.

This plausible inventory reporter substitutes aggregate counts for membership
verification. It reports counts without enforcing their agreement and defaults
unreadable inputs to empty. Balanced duplicate/missing claims are invisible;
so are missing evidence and individual unaccounted or phantom memberships.
It misses every registered BAD case and agrees on GOOD. The registered hash
establishes integrity, not historicity.
"""

import argparse
import json
from pathlib import Path


def read_or_empty(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--claimed-file", type=Path, required=True)
    parser.add_argument("--open-set-capture", type=Path, required=True)
    args = parser.parse_args()
    opened = read_or_empty(args.open_set_capture)
    claimed = read_or_empty(args.claimed_file)
    total = 0
    if isinstance(claimed, dict):
        for section in ("lanes", "buckets"):
            groups = claimed.get(section, {})
            if isinstance(groups, dict):
                total += sum(len(numbers) for numbers in groups.values() if isinstance(numbers, list))
    print(f"SLATE-OK: open={len(opened)} claimed={total} - inventory reported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
