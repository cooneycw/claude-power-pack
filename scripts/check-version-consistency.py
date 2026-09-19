#!/usr/bin/env python3
"""Verify every place that states the project's CURRENT version agrees with
`pyproject.toml` (issue #1037).

`CLAUDE.md:167` said "Current version: 7.5.0" while `pyproject.toml` said
"8.0.0" - stale for the four days since the 8.0.0 release, in the document
loaded into every session's context. Issue #938 had already named the
version-drift failure class and enumerated four locations to check "together,
since the drift between them is the usual failure" - and left CLAUDE.md off
that list. The criterion named the failure correctly and enumerated the wrong
population; a fifth location drifted through a release whose own acceptance
criterion was about drift.

So locations are DERIVED here, not hardcoded, from three independent claim
SHAPES rather than three specific files:

  1. The literal phrase "Current version:" followed by a semver, in any
     tracked file. This is the exact phrase that just failed, and searching
     for the PHRASE rather than a file+line means a future document using the
     same wording is covered automatically.
  2. README.md's own bold release banner, `**vX.Y.Z**` - by convention the
     FIRST such token in the file, not a hardcoded line number.
  3. The topmost dated release heading in CHANGELOG.md (`## [X.Y.Z] - ...`)
     and in README.md's own release-notes section (`### vX.Y.Z (...)`) -
     ASSUMES this repository's existing newest-first changelog convention
     holds. That is a checked convention nowhere else in this repo either;
     if it is ever violated on purpose, this heuristic needs an escape hatch
     that does not exist yet. Noted rather than engineered for a case that
     has not happened (issue #1037 review).

A MEMBERSHIP FLOOR applies to the derived location set itself, not only to
the docs/agents/ glob in the sibling check below (issue #1037 review,
required fix 2): if grepping for "Current version:" and the two banner/
heading shapes together yields fewer than MIN_LOCATIONS matches, that is
UNKNOWN (exit 2), not "clean" - a zero here must distinguish "every location
agrees" from "the phrasing this check looks for no longer exists anywhere,"
exactly the asymmetry ADR 0008 exists to keep visible. Without this floor, a
reformatted CLAUDE.md:167 or a renamed release-notes heading would make the
derived set empty, every derived location trivially "agree" (vacuously, over
zero items), and the check would report clean while genuine drift sat
unwatched.

A FAILED ENUMERATION MUST NOT HIDE BEHIND A SATISFIED FLOOR (Codex review,
issue #1037): the "Current version:" phrase scan depends on `git ls-files`,
but README.md's banner and CHANGELOG.md's heading are read directly from the
filesystem and do not. A broken or absent `git` would silently drop every
tracked-file location - including CLAUDE.md's own "Current version:" line,
the exact fact this check exists for - while README/CHANGELOG alone can still
supply the two locations MIN_LOCATIONS asks for, reporting clean over a scan
that never looked at CLAUDE.md at all. `git ls-files` failing is therefore
tracked as its own distinguishable state, not folded into "zero locations
found," and reported as UNKNOWN regardless of how many other locations were
found by other means.

`vendor/project_next/**` is excluded from the tracked-file phrase scan for
the same reason `check-unicode-dashes.py` excludes it: a vendored project's
own "Current version:" line states ITS version, not CPP's, and comparing it
to CPP's `pyproject.toml` would fail a clean tree over a neighbour's content
(Codex review, issue #1037).

Usage:
    python3 scripts/check-version-consistency.py
    python3 scripts/check-version-consistency.py --root DIR
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib  # stdlib since 3.11, matching pyproject.toml's own requires-python floor
from dataclasses import dataclass
from pathlib import Path

#: Below this many derived locations, the check cannot tell "all agree"
#: from "found nothing to check" - fail closed to unknown, not clean.
MIN_LOCATIONS = 2

CURRENT_VERSION_RE = re.compile(r"Current version:\s*(\d+\.\d+\.\d+)")
README_BANNER_RE = re.compile(r"\*\*v(\d+\.\d+\.\d+)\*\*")
CHANGELOG_HEADING_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)
README_RELEASE_HEADING_RE = re.compile(r"^### v(\d+\.\d+\.\d+)", re.MULTILINE)


@dataclass(frozen=True)
class Location:
    where: str
    version: str


def _tracked_md_files(root: Path) -> list[str] | None:
    """Tracked `.md` files, excluding a neighbour's vendored content.

    Returns ``None`` when `git ls-files` itself fails - distinguishable from
    a successful run finding zero files, so a broken enumeration cannot be
    silently absorbed into "no tracked-file locations" and outvoted by
    README/CHANGELOG alone (Codex review, issue #1037).
    """
    proc = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=root, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    return [
        line for line in proc.stdout.splitlines()
        if line and not line.startswith("vendor/")
    ]


def ground_truth_version(root: Path) -> str | None:
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return None
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version")
    return version if isinstance(version, str) else None


def find_locations(root: Path) -> list[Location] | None:
    """``None`` means `git ls-files` failed - a distinguishable UNKNOWN, not
    an empty tracked-file population that README/CHANGELOG locations alone
    could outvote."""
    md_files = _tracked_md_files(root)
    if md_files is None:
        return None

    locations: list[Location] = []

    for rel in md_files:
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in CURRENT_VERSION_RE.finditer(text):
            locations.append(Location(f"{rel}: \"Current version:\"", match.group(1)))

    readme = root / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        banner = README_BANNER_RE.search(text)
        if banner:
            locations.append(Location("README.md: bold release banner", banner.group(1)))
        release_heading = README_RELEASE_HEADING_RE.search(text)
        if release_heading:
            locations.append(
                Location("README.md: topmost \"### vX.Y.Z\" heading", release_heading.group(1))
            )

    changelog = root / "CHANGELOG.md"
    if changelog.is_file():
        text = changelog.read_text(encoding="utf-8")
        heading = CHANGELOG_HEADING_RE.search(text)
        if heading:
            locations.append(
                Location("CHANGELOG.md: topmost \"## [X.Y.Z]\" heading", heading.group(1))
            )

    return locations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1],
        help="repo root (default: the checkout this script lives in)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()

    truth = ground_truth_version(root)
    if truth is None:
        print("version-consistency: could not read [project].version from pyproject.toml",
              file=sys.stderr)
        return 1

    locations = find_locations(root)
    if locations is None:
        print(
            "version-consistency: `git ls-files` failed - UNKNOWN, not clean. "
            "README/CHANGELOG alone could satisfy the location floor while "
            "never examining a single tracked file, which means drift in one "
            "could sit unwatched.",
            file=sys.stderr,
        )
        return 2
    if len(locations) < MIN_LOCATIONS:
        print(
            f"version-consistency: only {len(locations)} version location(s) found "
            f"(need >= {MIN_LOCATIONS}) - UNKNOWN, not clean. Either this checkout is "
            "missing README.md/CHANGELOG.md, or the phrases/headings this check looks "
            "for no longer exist anywhere, which means drift could sit unwatched.",
            file=sys.stderr,
        )
        return 2

    mismatches = [loc for loc in locations if loc.version != truth]
    if mismatches:
        print(
            f"version-consistency: {len(mismatches)} location(s) disagree with "
            f"pyproject.toml's version ({truth}):",
            file=sys.stderr,
        )
        for loc in mismatches:
            print(f"  {loc.where}: {loc.version}", file=sys.stderr)
        return 1

    print(f"version-consistency: ok - {len(locations)} location(s) agree with {truth}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
