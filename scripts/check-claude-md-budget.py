#!/usr/bin/env python3
"""Enforce a persistent-context word budget for an always-loaded agent document.

CLAUDE.md and AGENTS.md are both loaded into every session on their surface, so
both need a cap, and the cap is the same measurement. Parameterised at #1071
rather than copied: a second 54-line script would be a second place for the
measurement to drift, and its budget would be enforced by nothing that also
enforces this one.

The defaults are the pre-#1071 behaviour exactly - no argument means CLAUDE.md at
2000 words - so the existing `make claude-md-budget-check` is unchanged.

Usage:
    python3 scripts/check-claude-md-budget.py
    python3 scripts/check-claude-md-budget.py --root DIR
    python3 scripts/check-claude-md-budget.py AGENTS.md --budget 450
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: NEGATIVE-CONTROL: controls/claude-md-budget
#:     Registered per issue #1071, in the commit that parameterised this script.
#:     Changing an instrument is the Negative Control rule's second clause: a
#:     widened check can silently stop drawing the distinction it existed for.
#:     This gate lets work THROUGH - a prerequisite of `make verify` (ADR 0008
#:     row 28) - and a blind version prints the same "ok - N/2000 words" line
#:     over a document that has doubled.

WORD_BUDGET = 2_000
#: AGENTS.md's cap is SET BY WHAT IT FORBIDS, not chosen for roundness (#1071).
#: The file is a pointer to CLAUDE.md plus what is Codex-specific; the failure it
#: exists to prevent is someone restating CLAUDE.md's Core Directives block in it,
#: which would recreate the two-documents-that-disagree defect the thin design
#: removes. That block is 389 words and the legitimate content is 308, so a copy
#: lands at 697 - this budget refuses it with 247 words to spare, and refuses even
#: half a copy (503). A cap a duplicate fits under is decoration.
AGENTS_WORD_BUDGET = 450


def word_count(path: Path) -> int:
    """Return the whitespace-delimited count used by ``wc -w``."""
    return len(path.read_text(encoding="utf-8").split())


def check(path: Path, *, budget: int = WORD_BUDGET) -> tuple[bool, int]:
    count = word_count(path)
    return count <= budget, count


def _label(path: Path) -> str:
    """The report prefix, derived from the document so it names what it read."""
    # From the FULL filename, not the stem: `CLAUDE.md` -> `claude-md-budget`.
    # Dropping the extension would rename the existing report to `claude-budget`
    # and break the verdict ADR 0008 row 28 records for this gate.
    return f"{path.name.lower().replace('.', '-')}-budget"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "document",
        nargs="?",
        default="CLAUDE.md",
        help="repo-relative document to measure (default: CLAUDE.md)",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=WORD_BUDGET,
        help=f"word budget (default: {WORD_BUDGET})",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repo root (default: the checkout this script lives in)",
    )
    args = parser.parse_args(argv)
    path = args.root.resolve() / args.document
    label = _label(path)
    if not path.is_file():
        print(f"{label}: missing {path}", file=sys.stderr)
        return 1
    within_budget, count = check(path, budget=args.budget)
    if within_budget:
        print(f"{label}: ok - {count}/{args.budget} words")
        return 0
    print(
        f"{label}: {path.name} has {count} words; budget is {args.budget} "
        f"({count - args.budget} over)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
