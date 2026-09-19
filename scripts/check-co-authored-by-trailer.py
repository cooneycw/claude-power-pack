#!/usr/bin/env python3
"""Tripwire: no tracked file names a pinned Claude model+version in a
`Co-Authored-By:` trailer (issue #1037).

Eight instructions across seven files told an agent to write a
`Co-Authored-By:` trailer naming one pinned model+version literal ("Claude"
plus a release name and number) verbatim - stale every time the assistant
model changes, and already wrong in all eight places by the time this was
noticed. A ninth, more stale copy of the same literal was found separately in
`ISSUE_DRIVEN_DEVELOPMENT.md`, and a tenth - the only one that was actually
EXECUTED rather than merely instructional - was a hardcoded constant in
`scripts/project-init.py` that stamped it onto every real commit
`/project:init` made. All ten are fixed alongside this script; this tripwire
exists so an eleventh cannot land unnoticed. (This paragraph avoids writing
the literal itself, on purpose: this file is what the pattern below scans
for, and typing a worked example here would make the checker flag its own
source.)

Uses `git grep`, not a Python walk over one file extension: the Python
constant above is exactly the case a `.md`-only or `.claude/commands/`-only
scan would have missed. `git grep`'s own exit code carries the ADR 0008
distinction directly - 0 means matches (fail), 1 means none (clean), and
anything else means the search itself did not run, which must not read as
clean.

`vendor/project_next/**` and `codex/skills/**` are excluded: the former is a
neighbour's pinned content (see check-unicode-dashes.py), and the latter is
a generated mirror of `.claude/commands/**` whose own drift is
`codex-skill-sync.py --check`'s job, not this tripwire's - scanning both
would report the same defect twice from two different files.

`git grep` returns exit 1 both when eligible files exist and contain no
match, AND when there are no eligible files at all - the two are otherwise
indistinguishable (Codex review, issue #1037: `--root .pytest_cache`
reproduced a false "ok" this way). MIN_TRACKED_FILES applies the same floor
shape as the sibling checks to the population `git ls-files` itself finds
under the same exclusions, so an empty or wrongly-rooted search reports
UNKNOWN rather than a vacuous clean.

Usage:
    python3 scripts/check-co-authored-by-trailer.py
    python3 scripts/check-co-authored-by-trailer.py --root DIR
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

#: A `Claude <name> <version>` shaped literal in a Co-Authored-By trailer -
#: matches "Claude Opus 4.6", "Claude Sonnet 5", etc. Generic guidance like
#: "Co-Authored-By: <name> <noreply@anthropic.com>" does not match: `<name>`
#: is not `Claude \S+ [\d.]+`.
TRAILER_PATTERN = r"Co-Authored-By:\s*Claude\s+\S+\s+[0-9][0-9.]*"

EXCLUDE_PATHSPECS = (":(exclude)vendor/**", ":(exclude)codex/skills/**")

#: Below this many eligible tracked files, `git grep`'s "no match" (exit 1)
#: cannot be told apart from "nothing eligible to search" - fail closed to
#: unknown, not clean (same shape as the sibling checks' floors).
MIN_TRACKED_FILES = 50


def _tracked_file_count(root: Path) -> int | None:
    """Eligible tracked files under the same exclusions as the grep itself.

    ``None`` means `git ls-files` failed.
    """
    proc = subprocess.run(
        ["git", "ls-files", "--", ".", *EXCLUDE_PATHSPECS],
        cwd=root, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    return sum(1 for line in proc.stdout.splitlines() if line)


def find_pinned_trailers(root: Path) -> tuple[list[str] | None, int]:
    """(matching lines, returncode). Lines is None when git grep itself failed."""
    proc = subprocess.run(
        ["git", "grep", "-n", "-I", "-P", TRAILER_PATTERN, "--", ".", *EXCLUDE_PATHSPECS],
        cwd=root, capture_output=True, text=True,
    )
    if proc.returncode not in (0, 1):
        return None, proc.returncode
    if proc.returncode == 1:
        return [], 0
    return [line for line in proc.stdout.splitlines() if line], 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1],
        help="repo root (default: the checkout this script lives in)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()

    matches, grep_returncode = find_pinned_trailers(root)
    if matches is None:
        print(
            f"co-authored-by-trailer: git grep exited {grep_returncode} - UNKNOWN, "
            "not clean. The search itself did not complete, which means a pinned "
            "trailer could sit unwatched.",
            file=sys.stderr,
        )
        return 2

    if matches:
        print(f"co-authored-by-trailer: {len(matches)} pinned model+version trailer(s):", file=sys.stderr)
        for line in matches:
            print(f"  {line}", file=sys.stderr)
        return 1

    tracked_count = _tracked_file_count(root)
    if tracked_count is None:
        print(
            "co-authored-by-trailer: `git ls-files` failed - UNKNOWN, not clean. "
            "The eligible population could not be established, so a clean grep "
            "cannot be trusted.",
            file=sys.stderr,
        )
        return 2
    if tracked_count < MIN_TRACKED_FILES:
        print(
            f"co-authored-by-trailer: only {tracked_count} eligible tracked file(s) found "
            f"(need >= {MIN_TRACKED_FILES}) - UNKNOWN, not clean. `git grep` finding no "
            "match is indistinguishable from having nothing to search.",
            file=sys.stderr,
        )
        return 2

    print("co-authored-by-trailer: ok - no pinned Claude model+version trailer found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
