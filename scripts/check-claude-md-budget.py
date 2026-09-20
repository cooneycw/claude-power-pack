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
#: AGENTS.md's cap, and what it actually does - corrected at the #1071
#: post-merge review, which found the original claim false.
#:
#: IT IS A SIZE LIMIT. It rejects APPENDING CLAUDE.md's Core Directives block
#: (389 words) to AGENTS.md's current content (308): that lands at 697 and is
#: refused by 247. It does NOT forbid restating the rules in general, and the
#: original comment here said it did. A document that DELETES the Codex-specific
#: content and pastes the block in its place measures 399 words and passes -
#: verified, not reasoned about. The second copy the thin design exists to
#: prevent fits under this cap whenever someone makes room for it.
#:
#: The broader prohibition - no sentence in AGENTS.md explains a Core Directive -
#: is a SEMANTIC property and stays with review. Building a parity instrument to
#: enforce it is precisely what the thin-pointer design exists not to need, and
#: widening this one to rescue an overclaim would buy the instrument the design
#: was meant to avoid.
AGENTS_WORD_BUDGET = 450

#: THE SINGLE SOURCE for each always-loaded document's budget (#1071). The
#: Makefile and .woodpecker.yml passed `--budget 450` as a literal, so the
#: constant above was read by nothing in production and the regression test that
#: guarded it could not observe the number anyone could actually raise. Both call
#: sites now pass the document alone and the budget is resolved here.
DOCUMENT_BUDGETS = {
    "CLAUDE.md": WORD_BUDGET,
    "AGENTS.md": AGENTS_WORD_BUDGET,
}


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
        default=None,
        help="word budget (default: the document's registered budget)",
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
    budget = args.budget
    if budget is None:
        budget = DOCUMENT_BUDGETS.get(Path(args.document).name, WORD_BUDGET)
    within_budget, count = check(path, budget=budget)
    if within_budget:
        print(f"{label}: ok - {count}/{budget} words")
        return 0
    print(
        f"{label}: {path.name} has {count} words; budget is {budget} "
        f"({count - budget} over)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
