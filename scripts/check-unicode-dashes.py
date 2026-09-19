#!/usr/bin/env python3
"""Enforce CLAUDE.md's "single dashes, never Unicode em or en dashes" rule
against the population it can actually be checked on (issue #1037).

CLAUDE.md:22 said the rule covers "markdown, comments, and documentation."
Nothing enforced any of it: 9 of 406 tracked `.md` files carried a literal
U+2014 (em dash) or U+2013 (en dash), and so did two non-markdown files in
comment/docstring text (`scripts/bash-prep.sh`, `tests/test_runner.py`).

This check covers tracked `.md` files only - a SCOPING DECISION, not a silent
narrowing (issue #1037 review, accepted as proposed). Comments in `.sh`/`.py`
source need per-language comment parsing to avoid flagging a dash quoted
inside a string literal, which is materially bigger than this issue's own
measured surface (9 files). CLAUDE.md:22 is reworded alongside this script to
say what is actually enforced; the non-markdown gap is filed to the Nit Store
(issue #864) naming the two files above, not silently dropped.

A SECOND, mechanically-forced exclusion: `vendor/project_next/**` is pinned by
sha256 in `.claude/project-next-vendor.json` and verified by
`make project-next-check` (see `lib/vendor.py`). It is a neighbour's content,
not ours to rewrite - the same distinction `docs/agents/detector-contracts.md`
already names for every check in this repo - and editing it to satisfy this
gate would desynchronize the vendor pin instead of fixing anything. Three of
the nine files this issue originally measured live under `vendor/`; excluded
here, they are also excluded from the count this check enforces.

A dash inside a fenced code block (``` or ~~~) is not prose - it may be an
example command, a quoted shell/log line, or a UTF-8 sample - so fenced
regions are excluded, matched by fence character and length per CommonMark
(the same shape `check-negative-controls.py` already uses for the ADR 0008
table's own fenced examples).

Usage:
    python3 scripts/check-unicode-dashes.py
    python3 scripts/check-unicode-dashes.py --root DIR
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

#: Below this many tracked .md files, the check cannot tell "scanned the repo
#: and found nothing" from "ran against the wrong root and found nothing to
#: scan" - fail closed to unknown, not clean (same floor shape as
#: check-version-consistency.py and check-claude-md-links.py).
MIN_TRACKED_MD_FILES = 50

DASH_CHARS = "—–"  # em dash, en dash
DASH_RE = re.compile(f"[{DASH_CHARS}]")

#: A fence marker, optionally inside a Markdown blockquote (`> \`\`\``, `>> ---`).
#: Without the blockquote prefix, a legitimate quoted code example inside a
#: `>` block was scanned as prose and could fail on a dash the fence exists to
#: exclude - a false positive on valid input (issue #1037 review, Codex).
FENCE_RE = re.compile(r"^\s*(?:>\s*)*(`{3,}|~{3,})\s*(.*)$")


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    text: str


def _tracked_md_files(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=root, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return []
    return [
        line for line in proc.stdout.splitlines()
        if line and not line.startswith("vendor/")
    ]


def find_dashes(text: str) -> list[tuple[int, str]]:
    """(1-indexed line, line text) for every dash-bearing line outside a fence."""
    hits: list[tuple[int, str]] = []
    fence: str | None = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        marker = FENCE_RE.match(line)
        if fence is None:
            if marker:
                fence = marker.group(1)
                continue
            if DASH_RE.search(line):
                hits.append((lineno, line))
            continue
        if (
            marker
            and marker.group(1)[0] == fence[0]
            and len(marker.group(1)) >= len(fence)
            and not marker.group(2).strip()
        ):
            fence = None
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1],
        help="repo root (default: the checkout this script lives in)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()

    md_files = _tracked_md_files(root)
    if len(md_files) < MIN_TRACKED_MD_FILES:
        print(
            f"unicode-dashes: only {len(md_files)} tracked .md file(s) found "
            f"(need >= {MIN_TRACKED_MD_FILES}) - UNKNOWN, not clean. Either this "
            "checkout is not the full repository, or `git ls-files` found "
            "nothing to scan, which means a dash could sit unwatched.",
            file=sys.stderr,
        )
        return 2

    violations: list[Violation] = []
    unreadable: list[str] = []
    for rel in md_files:
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            unreadable.append(f"{rel}: {exc}")
            continue
        for lineno, line in find_dashes(text):
            violations.append(Violation(rel, lineno, line.strip()))

    if violations:
        print(f"unicode-dashes: {len(violations)} occurrence(s) of U+2014/U+2013:", file=sys.stderr)
        for v in violations:
            print(f"  {v.path}:{v.line}: {v.text}", file=sys.stderr)
        return 1

    if unreadable:
        # A file this check could not read is a file it did not scan, so "ok"
        # must not claim it as part of the clean population (issue #1037
        # review, Codex): silently `continue`-ing past it left the success
        # message counting every enumerated path, read or not, as clean.
        print(
            f"unicode-dashes: {len(unreadable)} of {len(md_files)} tracked .md file(s) "
            "could not be read - UNKNOWN, not clean:",
            file=sys.stderr,
        )
        for entry in unreadable:
            print(f"  {entry}", file=sys.stderr)
        return 2

    print(f"unicode-dashes: ok - {len(md_files)} tracked .md file(s) clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
