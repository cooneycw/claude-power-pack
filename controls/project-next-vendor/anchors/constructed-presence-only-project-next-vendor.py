#!/usr/bin/env python3
"""BLIND ANCHOR for controls/project-next-vendor - do not fix, do not lint, do not import.

CONSTRUCTED, not historical, for the same reason as the eli5 anchor beside it:
until issue #1012 `scripts/project-next-vendor.py` hardcoded VENDOR_ROOT and
MANIFEST_PATH at module level, so the pre-refactor program could only ever read
the REAL repository. Pointed at a case tree it answers a different question
rather than answering this one blindly, which disqualifies it as an anchor.

This is the plausible WEAKER CHECK instead: confirm every path the manifest
pins is present under the vendored subtree, and call that vendored. It is the
check a reader writes when "the vendored copy is complete" sounds like the same
sentence as "the vendored copy is correct".

WHAT IT CATCHES: a missing or deleted vendored file, an unreadable manifest.
WHAT IT MISSES: a file EDITED IN PLACE, which is the known-bad case and the only
failure mode a per-file hash pin exists for. It reports GOOD on
`cases/bad-drifted-file` (blind, as required) and GOOD on
`cases/good-pinned-files` (anchor sanity).

It is also blind to the second invariant the current gate carries - a contract
version taken from the manifest rather than derived from the vendored document -
but that blindness is NOT what this control scores. The registered known-bad
case is the edited file; the version path is covered by
`tests/test_project_next_vendor.py`, and saying so here keeps this anchor's
claim to the one thing it demonstrates.

Stdlib-only and network-free, like the gate.
"""

import argparse
import json
import sys
from pathlib import Path

SUBTREE = "vendor/project_next"


def main(argv=None):
    parser = argparse.ArgumentParser(description="presence-only project-next vendor check (blind anchor)")
    parser.add_argument("command", nargs="?", choices=("check",), default="check")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--upstream", action="store_true")
    mode.add_argument("--revendor", action="store_true")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = root / ".claude" / "project-next-vendor.json"
    if not manifest_path.is_file():
        print(f"project-next-vendor: manifest not found: {manifest_path}", file=sys.stderr)
        return 1
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"project-next-vendor: manifest is unreadable ({manifest_path}): {exc}", file=sys.stderr)
        return 1

    pinned = manifest.get("files")
    if not isinstance(pinned, dict) or not pinned:
        print("project-next-vendor: manifest field 'files' must be a non-empty object", file=sys.stderr)
        return 1

    absent = sorted(rel for rel in pinned if not (root / SUBTREE / rel).is_file())
    if absent:
        print("project-next-vendor: vendored files are missing:", file=sys.stderr)
        for rel in absent:
            print(f"  {rel}", file=sys.stderr)
        return 1

    # And here the check stops. No file has been read, so no byte has been
    # compared with its pin - which is the blindness this anchor demonstrates.
    print(f"project-next-vendor: {len(pinned)} vendored files are present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
