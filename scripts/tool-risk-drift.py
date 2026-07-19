#!/usr/bin/env python3
"""Drift guard for CPP's shared permission-risk taxonomy.

CPP classifies command risk in two places that MUST agree on what is dangerous:

  - scripts/classify-tool-risk.py      canonical taxonomy; used by
                                       /security:permissions (retroactive audit)
  - scripts/hook-permission-census.sh  a vendored inline copy (#482 census hook,
                                       kept self-contained so it stays fail-open)

This checks that the two SAFETY-CRITICAL sets are identical between them:

  - DESTRUCTIVE_TOKENS  commands that are never allowlisted (rm, dd, ...)
  - CODE_EXEC           interpreters / runners = arbitrary execution

so a new dangerous command added to one classifier can never be silently missed
by the other. Non-safety sets (task-runner, dual-use-net) may differ benignly and
are deliberately NOT guarded - they land in never-allowlist tiers either way.

Advisory + fail-open: warns and exits 0 by default; `--strict` exits 1 on drift
(for CI). A missing or unparseable source is skipped, never fatal.

Same discipline as scripts/eli5-core-drift.sh (the eli5-gate vendor guard).
"""
import argparse
import re
import sys
from pathlib import Path

CANONICAL = "scripts/classify-tool-risk.py"
VENDORED = "scripts/hook-permission-census.sh"
GUARDED_SETS = ("DESTRUCTIVE_TOKENS", "CODE_EXEC")


def extract_set(text, name):
    """Return the set of double-quoted tokens in a `NAME = { ... }` literal."""
    m = re.search(name + r"\s*=\s*\{(.*?)\}", text, re.S)
    if not m:
        return None
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any guarded set has drifted (CI mode)")
    ap.add_argument("--root", default=".", help="repository root (default: cwd)")
    args = ap.parse_args()
    root = Path(args.root)

    try:
        canon = (root / CANONICAL).read_text()
        vendor = (root / VENDORED).read_text()
    except OSError as exc:
        print(f"tool-risk-drift: cannot read a source ({exc}); skipping (fail-open)")
        return 0

    drift = False
    for name in GUARDED_SETS:
        a = extract_set(canon, name)
        b = extract_set(vendor, name)
        if a is None or b is None:
            where = CANONICAL if a is None else VENDORED
            print(f"tool-risk-drift: {name} not found in {where}; skipping")
            continue
        if a == b:
            print(f"tool-risk-drift: {name} in sync ({len(a)} tokens)")
        else:
            drift = True
            print(f"tool-risk-drift: DRIFT in {name}")
            print(f"  only in {CANONICAL}: {sorted(a - b)}")
            print(f"  only in {VENDORED}:  {sorted(b - a)}")

    if drift:
        print("tool-risk-drift: reconcile the two classifiers (canonical is "
              f"{CANONICAL}).")
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
