#!/usr/bin/env python3
"""BLIND PREDECESSOR of scripts/check-consolidation-ledger.py (issue #1068).

CONSTRUCTED, not historical - this gate is new, so there is no previous released
version to vendor. But it is not invented either: this is the matching rule the
gate actually shipped with in its first cut, and it was replaced because this
control's known-bad fixture PASSED it. The blindness below was measured, not
imagined.

The difference is one rule. This variant counts a `cxpp#<n>` token ANYWHERE in
the ledger; the real gate counts one only in the FIRST CELL of a table row. The
known-bad fixture's prose explains that `cxpp#227` has no row - and that
sentence contains the token, so this variant reads the explanation of an absence
as the account of it and reports ok.

It must therefore MISS the known-bad input and AGREE with the current gate on the
known-good one. If it ever catches the bad input, the control has stopped
discriminating and the framework will say so.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CLAIM_RE = re.compile(r"\bcxpp#(\d+)\b")
FENCE_RE = re.compile(r"^\s*```", re.MULTILINE)


def strip_fences(text: str) -> str:
    out, inside = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            inside = not inside
            continue
        if not inside:
            out.append(line)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)

    required = set()
    for raw in args.snapshot.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip() if not raw.lstrip().startswith("#") else ""
        if line:
            required.add(int(line))

    # THE BLIND RULE: any occurrence anywhere counts as an accounting.
    claimed = {int(m) for m in CLAIM_RE.findall(strip_fences(args.ledger.read_text(encoding="utf-8")))}

    missing = sorted(required - claimed)
    for num in missing:
        print(f"LEDGER_MISSING: cxpp#{num} is open at the baseline and has no row in {args.ledger}")
    if missing:
        print(f"check-consolidation-ledger: FAIL - {len(missing)} of {len(required)} "
              f"open entry(ies) are unaccounted for")
        return 1
    print(f"check-consolidation-ledger: ok - all {len(required)} open entry(ies) in the "
          f"{args.snapshot.name} snapshot have a row in {args.ledger.name} "
          f"(row PRESENCE only; this gate does not judge a disposition)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
