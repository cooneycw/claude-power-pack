#!/usr/bin/env python3
"""ANCHOR - the NAIVE framing of the unread-seam-verdict check (issue #1198).

Constructed, not a historical revision: this is the implementation the real one
was written against, and the three cases that separate them were each a real
mistake before they were fixtures.

Three shortcuts, all of which read naturally:

1. **Key the finding on a nearby success claim.** "A seam call followed by a
   checkmark" is the defect as first described, so it is the obvious rule. It
   excuses `bad-unguarded-loop-no-claim`: ninety calls, no claim, nothing
   linked, and the step reports nothing - which is the shape that actually
   bit on 2026-09-22.
2. **Look at the next raw LINE for `$?`.** It reads the jq program text after a
   `<<'JQ'` opener as though it were shell, so `bad-status-only-inside-heredoc`
   passes on a `$?` that is a string inside a heredoc body.
3. **Ignore backslash continuations.** The line after a `json-merge-sections \\`
   is that statement's own arguments, so `good-continuation-then-handler` is
   reported as unguarded - a FALSE POSITIVE on correct code, and the direction
   of error that gets a gate switched off.
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
CLAIM_RE = re.compile(r"echo\s+\"?[✓√]")
FENCE_RE = re.compile(r"^\s*```")


def scan_naive(text: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    lines = text.split("\n")
    in_fence = False
    for idx, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence or line.lstrip().startswith("#"):
            continue
        if not SEAM_INVOKE_RE.search(line):
            continue
        following = lines[idx + 1] if idx + 1 < len(lines) else ""
        if "$?" in following:
            continue
        #: SHORTCUT 1: only a nearby checkmark makes it a finding.
        if not any(CLAIM_RE.search(nxt) for nxt in lines[idx + 1: idx + 8]):
            continue
        findings.append((idx + 1, line.strip()))
    return findings


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
        for lineno, line in scan_naive((args.root / rel).read_text(encoding="utf-8")):
            total += 1
            print(f"UNREAD-SEAM-VERDICT: {rel}:{lineno} {line[:90]}")
    if total:
        print(f"check-cpp-host-writes: FAIL - {total} unread seam verdict(s)")
        return 1
    print("check-cpp-host-writes: ok - no unread seam verdicts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
