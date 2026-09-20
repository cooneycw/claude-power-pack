#!/usr/bin/env python3
"""BLIND ANCHOR for controls/project-next-ownership - do not fix, do not lint, do not import.

CONSTRUCTED, not historical. There is no earlier version of the ownership gate
to take an anchor from: `scripts/project-next-ownership.py` is new at #1069, so
a historical anchor does not exist and inventing one would be a fiction. This is
the plausible WEAKER CHECK a reader writes instead: confirm every path the
manifest pins is PRESENT under the tree, and call that owned. It is the check
someone writes when "the engine is all here" sounds like the same sentence as
"the engine is what we pinned".

WHAT IT CATCHES: a missing or deleted engine file, an unreadable manifest.
WHAT IT MISSES: a file EDITED IN PLACE with its pin untouched - the known-bad
case, and the exact failure the ownership pin exists for now that no upstream
remains to notice it. It reports GOOD on `cases/bad-drifted-file` (blind, as
required) and GOOD on `cases/good-pinned-files` (anchor sanity).

It is also blind to the derived-contract-version invariant and to an unpinned
module added to the package, but that is NOT what this control scores - the
registered known-bad case is the edited file. Those two paths are covered by
`tests/test_project_next_ownership.py`, and saying so keeps this anchor's claim
to the one thing it demonstrates.

Stdlib-only and network-free, like the gate.
"""

import argparse
import json
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="presence-only project-next ownership check (blind anchor)")
    parser.add_argument("command", nargs="?", choices=("check",), default="check")
    parser.add_argument("--repin", action="store_true")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = root / ".claude" / "project-next-ownership.json"
    if not manifest_path.is_file():
        print(f"DRIFT: {manifest_path} is missing - the engine is unpinned.")
        return 1
    try:
        files = json.loads(manifest_path.read_text(encoding="utf-8")).get("files", {})
    except json.JSONDecodeError:
        print("DRIFT: the ownership manifest does not parse as JSON.")
        return 1

    missing = [rel for rel in files if not (root / rel).is_file()]
    for rel in sorted(missing):
        print(f"DRIFT: {rel} is pinned but absent from the tree.")
    if missing:
        return 1
    print(f"project-next ownership: {len(files)} files present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
