#!/usr/bin/env python3
"""ANCHOR - the OVER-BROAD framing of the unread-verdict check (issue #1198).

Constructed. It reports every seam invocation and never asks whether the status
was consulted, so it reds on the FIX as loudly as on the defect.

This is the cheapest wrong implementation to reach: "find the seam calls" is the
first half of the real check, and it passes every `bad-` case in this register.
Only the `good-` cases separate it from the gate - which is what they are for.

A gate that cannot be satisfied gets switched off, so a false positive on
correct code is not a milder failure than a false negative. It is the one that
removes the check.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCUMENTS = (".claude/commands/cpp/init.md", ".claude/commands/cpp/update.md")
SEAM = "cpp-host-write.sh"
SEAM_INVOKE_RE = re.compile(rf"{re.escape(SEAM)}\s+[a-z][a-z-]*\b")
FENCE_RE = re.compile(r"^\s*```")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    args = ap.parse_args(argv)
    present = [rel for rel in DOCUMENTS if (args.root / rel).is_file()]
    if not present:
        print("check-cpp-host-writes: UNKNOWN - no scanned document exists", file=sys.stderr)
        return 2
    total = 0
    for rel in present:
        in_fence = False
        for lineno, line in enumerate((args.root / rel).read_text(encoding="utf-8").split("\n"), 1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if not in_fence or line.lstrip().startswith("#"):
                continue
            if SEAM_INVOKE_RE.search(line):
                total += 1
                print(f"UNREAD-SEAM-VERDICT: {rel}:{lineno} {line.strip()[:90]}")
    if total:
        print(f"check-cpp-host-writes: FAIL - {total} unread seam verdict(s)")
        return 1
    print("check-cpp-host-writes: ok - no unread seam verdicts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
