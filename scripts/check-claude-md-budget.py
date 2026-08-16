#!/usr/bin/env python3
"""Enforce the persistent-context word budget for CLAUDE.md.

Usage:
    python3 scripts/check-claude-md-budget.py
    python3 scripts/check-claude-md-budget.py --root DIR
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

WORD_BUDGET = 2_000


def word_count(path: Path) -> int:
    """Return the whitespace-delimited count used by ``wc -w``."""
    return len(path.read_text(encoding="utf-8").split())


def check(path: Path, *, budget: int = WORD_BUDGET) -> tuple[bool, int]:
    count = word_count(path)
    return count <= budget, count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repo root (default: the checkout this script lives in)",
    )
    args = parser.parse_args(argv)
    path = args.root.resolve() / "CLAUDE.md"
    if not path.is_file():
        print(f"claude-md-budget: missing {path}", file=sys.stderr)
        return 1
    within_budget, count = check(path)
    if within_budget:
        print(f"claude-md-budget: ok - {count}/{WORD_BUDGET} words")
        return 0
    print(
        f"claude-md-budget: CLAUDE.md has {count} words; budget is {WORD_BUDGET} "
        f"({count - WORD_BUDGET} over)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
