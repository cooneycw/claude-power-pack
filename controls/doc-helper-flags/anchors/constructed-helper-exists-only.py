#!/usr/bin/env python3
"""BLIND ANCHOR for scripts/check-doc-helper-flags.py (issue #1835).

NOT a past version of the gate - the gate is new, so the honest "before" is
"no check at all", which cannot be run against a case. This is the plausible
WEAKER check somebody would write instead: confirm every
`~/.claude/scripts/<helper>` a command document names exists under scripts/,
and call the references sound.

That check catches a renamed or deleted helper, which is real. It cannot see
the defect #1835 was: the helper exists and the FLAG does not. Run against
both committed BAD cases it prints the same clean line it prints on the GOOD
one.

Accepts the same invocation as the real gate so the harness can substitute it.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HELPER_PATH = re.compile(r"~/\.claude/scripts/([A-Za-z0-9_.-]+)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    root = parser.parse_args().root
    missing = 0
    seen = 0
    for surface in (".claude/commands", ".claude/skills", "templates"):
        base = root / surface
        if not base.is_dir():
            continue
        for doc in sorted(base.rglob("*.md")):
            for name in HELPER_PATH.findall(doc.read_text(encoding="utf-8")):
                seen += 1
                if not (root / "scripts" / name).is_file():
                    missing += 1
                    print(f"MISSING_HELPER: {doc.relative_to(root)}: {name}")
    if missing:
        return 1
    print(f"ok - {seen} helper reference(s) resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
