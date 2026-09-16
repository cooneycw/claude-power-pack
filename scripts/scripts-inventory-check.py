#!/usr/bin/env python3
"""Derive the `docs/scripts.md` entry population from `scripts/` (issue #1013).

`docs/scripts.md` is the repository's inventory of its own tooling - one section
per script, holding the accumulated per-script history that issue #711 moved out
of the always-loaded `CLAUDE.md`. Nothing generated it and nothing checked it, so
a script could be added and its entry simply never written; 17 of 68 were in that
state when this gate was built.

The harm is not "a doc is out of date". Six test files quote individual sentences
out of this file as if it were a specification, so it is trusted as complete while
being silently partial - a reader scanning it for "what tooling exists here" gets a
confident, well-written, incomplete answer with nothing marking the gap.

WHAT IS DERIVED AND WHAT IS NOT. The SET of entries is derived from the directory;
the PROSE of each entry stays hand-written, because the prose is the valuable part
and no generator can write it. This gate therefore only ever answers "is there an
entry for this script", never "is the entry any good".

THE MATCHING RULE IS THE DOCUMENT'S OWN, NOT THE EXTENSION (issue #1013 as filed
measured 44-of-67 by grepping for full basenames including `.sh`/`.py`). The file's
headings carry the STEM in backticks - ``## `flow-worktree-sweep` `` - and the
extension appears nowhere in them. Matching on basenames would have demanded every
heading in the file be rewritten to carry an extension, which is a larger and worse
change than the one asked for. Re-measured against the document's real convention
the gap is 17, and that is the number this gate is built on.

AN ENTRY CLAIM IS A BACKTICKED NAME IN ONE OF TWO POSITIONS - one rule, read by
both directions:

  * heading subject, the FIRST backticked token of a ``##``-or-deeper heading -
    ``## `flow-ci-status` ``, or ``## `check-oscillation` (#936)``. Only the
    first: ``## `alpha` (calls `beta`)`` is a section about `alpha`, and letting
    an incidental mention count would let a neighbour's prose stand in as an
    undocumented script's entry;
  * bullet head, a bullet LEADING with a backticked name - ``- `hook-mask-output`
    - prose`` - which is how the grouped sections carry the seven scripts that
    have no section of their own.

The backticks are what make it a claim rather than a coincidence, and that is
load-bearing in both directions: they let the reverse check see a stale bullet
for a deleted script, while leaving ``- shellcheck is also needed`` as the prose
it is. Measured on the real document, dropping the backtick requirement produced
three false findings, two of them possessives.

Fenced blocks and HTML comments are EXAMPLES, not the document speaking, and are
excluded before any of this - an illustrative heading would otherwise both block
every merge in the repository and satisfy a real script's missing entry.

ONE SCRIPT MAY OWN SEVERAL SECTIONS. `check-test-binary-guards` is the subject of
three, distinguished by issue-number suffixes. That is deliberate and out of scope
here (issue #1013 explicitly excludes it), so the rule asks whether at least one
entry exists and never that exactly one does.

BOTH DIRECTIONS ARE CHECKED. `MISSING` is a script with no entry - the drift the
issue is about. `UNDECLARED` is the reverse: a claim naming neither a real script
nor a declared non-script section, which is what a stale entry for a deleted
script looks like. An inventory that keeps entries for tooling
that no longer exists lies in the other direction, and only the reverse check sees
it.

The non-script sections are declared IN THE DOCUMENT, on a `scripts-inventory:`
HTML comment, rather than as a constant in here - the declaration then sits beside
the thing it governs, travels with any tree the gate is pointed at, and is visible
to whoever is editing the file. The list narrows what is checked, deliberately, but
it fails LOUDLY: a new non-script section turns this gate red until someone
declares it.

Stdlib-only, git-free and offline, so `make verify` and the slim CI image give the
same verdict.

Usage:
    scripts-inventory-check.py [--root DIR]

Output: one `MISSING:` / `UNDECLARED:` line per finding, then a verdict line.
Exit 0 when the inventory population matches the tree, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: NEGATIVE-CONTROL: controls/scripts-inventory
#:
#: This gate lets work THROUGH - `make verify` and the CI step both read its
#: green as "the inventory covers the tree" and nothing downstream re-derives
#: that - so ADR 0008's bound requires a committed case. The registration lives
#: in this file because that is what `check-negative-controls.py` enumerates: a
#: control directory alone is invisible to the battery, which then reports PASS
#: over a register the new control is not in.

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The inventory, relative to the tree being checked.
DOC_REL = "docs/scripts.md"

#: The directory whose population the inventory must cover.
SCRIPTS_REL = "scripts"

#: Sections that are legitimately about something other than one script are
#: declared on this marker inside the document itself, comma-separated:
#:
#:     <!-- scripts-inventory: non-script-sections: hooks, tools-check -->
#:
#: Read from the doc rather than hardcoded here so the declaration lives beside
#: what it describes and travels with the tree.
DECLARE_RE = re.compile(
    r"<!--\s*scripts-inventory:\s*non-script-sections:\s*(.*?)\s*-->",
    re.IGNORECASE,
)

#: A section heading (`##` or deeper - `#` is the document title, not an entry).
#: Its SUBJECT is the first backticked token on the line, and only the first:
#: ``## `alpha` (calls `beta`)`` is a section about `alpha` that mentions `beta`,
#: not two entries. The forward and reverse checks read the SAME subject, because
#: they disagreed once - the forward side matched any backticked token anywhere on
#: a heading line while the reverse side took the first - and the gap let a
#: neighbour's incidental mention stand in as an undocumented script's entry.
HEADING_RE = re.compile(r"^#{2,}\s+.*?`([^`]+)`")

#: A bullet that LEADS with a backticked name claims an entry for it. The backticks
#: are the claim: they are what separates ``- `hook-mask-output` - prose`` (an entry
#: for a script with no section of its own) from ``- shellcheck is also needed`` (a
#: sentence that happens to start with a tool's name). Without that, either the
#: reverse check cannot see a stale bullet, or ordinary prose starts reporting
#: UNDECLARED - measured on the real document, the un-backticked rule produced three
#: false findings, two of them possessives (`eli5-vendor's`).
BULLET_RE = re.compile(r"^-\s+`([^`]+)`")

#: A fenced block is an EXAMPLE, not the document speaking. A gate that reads one
#: is doubly wrong: an illustrative ``## `beta``` reports UNDECLARED and blocks every
#: merge in the repository, and an illustrative entry satisfies a real script's
#: missing one.
#:
#: FENCES ARE MATCHED BY CHARACTER AND LENGTH, per CommonMark: an opener of N or
#: more of the same character, closed only by N or more of that SAME character with
#: nothing else on the line. A fixed three-character pattern reads the inner ``` of
#: a ````-fenced example as the close and spills the rest of the example into the
#: document.
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*(.*)$")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def unfenced(text: str) -> str:
    """The document with every fenced example removed.

    EVERYTHING ELSE IS DERIVED FROM THIS, declarations included. Reading the
    declaration marker out of the raw text instead let a marker inside a fenced
    example widen the non-script allowlist and silently suppress a real stale
    entry - a false GREEN, and the worst direction for a list that narrows.
    """
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        marker = FENCE_RE.match(line)
        if fence is None:
            if marker:
                fence = marker.group(1)
            else:
                out.append(line)
            continue
        # A CLOSING fence: same character, at least as long, nothing else on the line.
        if (
            marker
            and marker.group(1)[0] == fence[0]
            and len(marker.group(1)) >= len(fence)
            and not marker.group(2).strip()
        ):
            fence = None
    return "\n".join(out)


def prose_lines(text: str) -> list[str]:
    """The document's own lines - fenced examples, then HTML comments, removed.

    The ORDER is load-bearing. Stripping comments first ran the `<!--...-->` regex
    across fenced content too, so a fenced `<!--` paired with a real comment further
    down and deleted every entry between them - a complete inventory reported as
    missing a script whose entry is plainly visible.
    """
    return COMMENT_RE.sub("", unfenced(text)).splitlines()


def entry_claims(text: str) -> list[str]:
    """Every name this document claims to carry an entry for, in order.

    ONE rule for both directions: a backticked name in heading-subject position or
    at the head of a bullet. `has_entry` and the reverse check are both derived
    from this list rather than each re-deriving it, so they cannot drift apart
    again.
    """
    claims: list[str] = []
    for line in prose_lines(text):
        match = HEADING_RE.match(line) or BULLET_RE.match(line)
        if match:
            claims.append(match.group(1))
    return claims


def script_stems(root: Path) -> dict[str, str]:
    """Every regular file in `scripts/`, mapped stem -> basename.

    DERIVED FROM THE TREE, never from a list in here: a gate that hardcodes the
    population it is checking has the very bug it exists to catch. Directories are
    skipped (they are not scripts); a file with no extension keeps its whole name
    as its stem, which is how `cpp-memory` is addressed.
    """
    scripts_dir = root / SCRIPTS_REL
    stems: dict[str, str] = {}
    for path in sorted(scripts_dir.iterdir()):
        if not path.is_file():
            continue
        stems[path.stem] = path.name
    return stems


def declared_non_script_sections(text: str) -> set[str]:
    """Section subjects the document declares are not about one script."""
    declared: set[str] = set()
    for match in DECLARE_RE.finditer(unfenced(text)):
        for name in match.group(1).split(","):
            name = name.strip().strip("`")
            if name:
                declared.add(name)
    return declared


def has_entry(text: str, stem: str) -> bool:
    """Does the document claim an entry for this stem?

    Derived from `entry_claims`, so it cannot disagree with the reverse check.
    The backticks are the boundary: `project-next` and `project-next-vendor` are
    both live in this tree, and an exact match against a delimited claim cannot
    let the longer one stand in for the shorter.
    """
    return stem in set(entry_claims(text))


def run_check(root: Path) -> int:
    doc = root / DOC_REL
    scripts_dir = root / SCRIPTS_REL

    if not scripts_dir.is_dir():
        print(f"scripts-inventory-check: no {SCRIPTS_REL}/ under {root}; nothing compared.")
        return 1
    if not doc.is_file():
        print(f"MISSING: {DOC_REL} does not exist under {root}")
        print("scripts-inventory-check: the inventory itself is absent; nothing compared.")
        return 1

    text = doc.read_text(encoding="utf-8")
    stems = script_stems(root)

    if not stems:
        # A population of zero would make every assertion below vacuously true and
        # print a clean verdict over an unexamined tree - the blind-instrument
        # shape this repository refuses to ship. See docs/agents/detector-contracts.md.
        print(f"scripts-inventory-check: {SCRIPTS_REL}/ holds no files; nothing compared.")
        return 1

    findings = 0

    for stem in sorted(stems):
        if not has_entry(text, stem):
            print(f"MISSING: {stems[stem]} has no entry in {DOC_REL}")
            findings += 1

    # EVERY claim, not only the heading ones. A script carried by a bullet alone -
    # seven are, under the grouped sections - would otherwise leave its bullet
    # behind when deleted, and the forward check has nothing left to ask about it.
    declared = declared_non_script_sections(text)
    claims = entry_claims(text)
    for subject in dict.fromkeys(claims):
        if subject in stems or subject in declared:
            continue
        print(
            f"UNDECLARED: {DOC_REL} entry `{subject}` names no file in "
            f"{SCRIPTS_REL}/ and is not declared a non-script section"
        )
        findings += 1

    # PROVENANCE ON EVERY VERDICT: an `ok` from a 68-script tree and an `ok` from a
    # 2-script fixture are otherwise the same line, and a verdict cannot be read
    # against what produced it.
    print(f"SCRIPTS_INVENTORY_EXAMINED: {len(stems)}")
    print(f"SCRIPTS_INVENTORY_CLAIMS: {len(set(claims))}")

    if findings:
        print(
            f"scripts-inventory-check: {findings} finding(s). Add the entry to "
            f"{DOC_REL}, or declare a non-script section on its "
            f"`scripts-inventory: non-script-sections:` marker."
        )
        return 1

    print(
        f"scripts-inventory-check: ok - all {len(stems)} file(s) in {SCRIPTS_REL}/ "
        f"have an entry in {DOC_REL}, and every section resolves."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", nargs="?", default="check", choices=["check"])
    ap.add_argument("--root", default=str(REPO_ROOT), help="tree to operate on")
    args = ap.parse_args(argv)
    return run_check(Path(args.root).resolve())


if __name__ == "__main__":
    sys.exit(main())
