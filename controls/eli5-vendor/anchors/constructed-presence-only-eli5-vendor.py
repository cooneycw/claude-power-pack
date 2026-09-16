#!/usr/bin/env python3
"""BLIND ANCHOR for controls/eli5-vendor - do not fix, do not lint, do not import.

CONSTRUCTED, not historical. The honest "before" for this gate is not a weaker
program: it is a gate that could not be aimed at a case tree AT ALL, because
`scripts/eli5-vendor.py` hardcoded its repository root at module level until
issue #1012. Run against a fixture it would have read the REAL repository and
reported on that, which is not a blind verdict about the case - it is an answer
to a different question, and it cannot serve as an anchor.

So this is the plausible WEAKER CHECK someone writes instead: confirm the
vendored document is present and still carries its marker pair, and call that
vendored. It is not a straw man - "the vendored tree is intact" is exactly the
level of assurance this link had before #591, when a drift script existed and
was invoked by nothing.

WHAT IT CATCHES: a deleted vendored file, a deleted or unterminated marker pair.
WHAT IT MISSES: the failure that actually happens - the core edited in place
with its markers intact, which is the known-bad case. It therefore reports GOOD
on `cases/bad-drifted-core` (blind, as required) and GOOD on
`cases/good-pinned-core` (anchor sanity: it differs from the current gate only
in the blindness under test, not for some unrelated reason).

Stdlib-only and network-free, like the gate, so it gives the same verdict in the
slim CI image as on a dev box.
"""

import argparse
import json
import sys
from pathlib import Path

BEGIN_MARKER = "<!-- eli5-core:begin"
END_MARKER = "<!-- eli5-core:end"


def main(argv=None):
    parser = argparse.ArgumentParser(description="presence-only eli5 vendor check (blind anchor)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--upstream", action="store_true")
    mode.add_argument("--revendor", action="store_true")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = root / ".claude" / "eli5-vendor.json"
    if not manifest_path.is_file():
        print(f"eli5-vendor: manifest not found: {manifest_path}", file=sys.stderr)
        return 1
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"eli5-vendor: manifest is unreadable ({manifest_path}): {exc}", file=sys.stderr)
        return 1

    relative = manifest.get("vendored", {}).get("file", ".claude/commands/flow/eli5.md")
    vendored = root / relative
    if not vendored.is_file():
        print(f"eli5-vendor: {vendored} not found", file=sys.stderr)
        return 1

    lines = vendored.read_text(encoding="utf-8").splitlines()
    begun = False
    ended = False
    for line in lines:
        if not begun and line.startswith(BEGIN_MARKER):
            begun = True
        elif begun and line.startswith(END_MARKER):
            ended = True
            break
    if not begun or not ended:
        print(f"eli5-vendor: {vendored} has no usable marker pair", file=sys.stderr)
        return 1

    # And here the check stops. Nothing has been hashed, so nothing has been
    # compared with the manifest - which is the blindness this anchor exists to
    # demonstrate.
    print(f"eli5-vendor: vendored core is present in {relative}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
