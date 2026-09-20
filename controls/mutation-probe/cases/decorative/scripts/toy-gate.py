#!/usr/bin/env python3
"""A two-protection toy gate, for the mutation-probe control (issue #970).

It reports the token FORBIDDEN appearing in any file under --root, and carries
exactly two protections, each of which a real gate in this repository has an
analogue of:

  COMMENT REJECTION - a commented-out occurrence is not an occurrence. This is
  #955's `comment` protection, the one whose removal left all nine of that
  battery's controls green.
  QUOTE REJECTION   - an occurrence inside a quoted string is advice or test
  data, not the real thing. This is #955's `quote` protection.

Two protections is the minimum that makes the point: a battery covering one of
them is indistinguishable, by reading, from a battery covering both.
"""
import argparse
import pathlib
import sys

TOKEN = "FORBIDDEN"


def findings(root: pathlib.Path) -> list[str]:
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            if TOKEN not in line:
                continue
            # PROTECTION: comment rejection.
            if line.strip().startswith("#"):
                continue
            # PROTECTION: quote rejection.
            if '"' + TOKEN + '"' in line:
                continue
            hits.append(f"{path.name}:{number}")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=pathlib.Path, required=True)
    args = ap.parse_args()
    if not args.root.is_dir():
        print(f"toy-gate: UNKNOWN - root '{args.root}' is not a directory.", file=sys.stderr)
        return 2
    hits = findings(args.root)
    if hits:
        for hit in hits:
            print(f"TOY-FINDING: {hit}", file=sys.stderr)
        return 1
    print(f"toy-gate: ok - examined '{args.root}', 0 finding(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
