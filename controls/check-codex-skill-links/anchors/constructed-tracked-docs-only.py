#!/usr/bin/env python3
"""BLIND ANCHOR for controls/check-codex-skill-links - do not fix, do not lint, do not import.

CONSTRUCTED: the coverage this repository had before #1494. The gate's default
mode (`scripts/check-md-relative-links.py`, no `--codex-skills`) EXCLUDES
`codex/skills/` by design - its own comment says the mirror's "sources are
checked where they live" - which is right for a link that resolves to
something that is ALSO mirrored, and blind for a link whose target is never
mirrored at all. This anchor reproduces exactly that exclusion: it walks every
`.md` file under `--root` and checks its relative links, except any file whose
path contains a `codex/skills/` component.

Each case tree also carries a harmless top-level `README.md` with one live,
self-referential link - OUTSIDE `codex/skills/` - so this anchor's own
(empty-everywhere-else) population is not always zero, and it can genuinely
AGREE with the gate on the GOOD case rather than reporting UNKNOWN there too.

WHAT IT CATCHES: nothing inside `codex/skills/` - by construction, the exact
exclusion the real default mode applies.
WHAT IT MISSES: the dead mirror link in `cases/bad-dead-mirror-link`. It sees
only that case's harmless `README.md`, finds its one link live, and reports
GOOD (blind, as required) where the gate reports BAD.
AGREES on `cases/good-live-mirror-links` (both GOOD, via the same README.md)
and on `cases/unknown-no-links` (both UNKNOWN - no non-mirror .md file at all
there). That is the gap #1494 closes, not a flaw in this anchor.

Stdlib-only and network-free, like the gate.
"""

import argparse
import re
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="codex/skills-excluded link check (blind anchor)")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--min-files", type=int, default=1)
    parser.add_argument("--codex-skills", action="store_true")  # accepted, changes nothing: the blindness IS ignoring this axis
    args = parser.parse_args(argv)

    examined_files = [
        p for p in args.root.rglob("*.md")
        if "codex/skills/" not in p.relative_to(args.root).as_posix() + "/"
        and "codex/skills" not in p.relative_to(args.root).parts
    ]
    if len(examined_files) < args.min_files:
        print(
            f"md-relative-links: UNKNOWN - only {len(examined_files)} non-mirror "
            f".md file(s) (need >= {args.min_files}); this is not the population "
            "the gate is for, so a clean result would mean nothing.",
            file=sys.stderr,
        )
        return 2

    dead = 0
    examined = 0
    for doc in examined_files:
        text = re.sub(r"`[^`\n]*`", "", doc.read_text(encoding="utf-8"))
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        for target in re.findall(r"\]\(([^)#\s]+)", text):
            if ":" in target or target.startswith("/"):
                continue
            examined += 1
            if not (doc.parent / target).exists():
                dead += 1

    if not examined:
        print(
            f"md-relative-links: UNKNOWN - {len(examined_files)} non-mirror .md "
            "file(s) carry no relative link at all; nothing was checked.",
            file=sys.stderr,
        )
        return 2
    if dead:
        print(f"md-relative-links: {dead} dead relative link(s) of {examined}", file=sys.stderr)
        return 1
    print(f"md-relative-links: ok - {examined} relative link(s) resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
