#!/usr/bin/env python3
"""BLIND ANCHOR for controls/command-docs-budget - do not fix, do not lint, do not import.

CONSTRUCTED. The plausible WEAKER CHECK: confirm every command document has a
line in the budget table, and call that "within budget". It is the check a
reader writes when "every document has a declared budget" sounds like the same
sentence as "every document is inside its declared budget".

WHAT IT CATCHES: a command document with no declared budget, a missing table.
WHAT IT MISSES: a declared document OVER its budget - the known-bad case and
the only failure a word cap exists for. It reports GOOD on
`cases/bad-command-over-budget` (blind, as required) and GOOD on
`cases/good-command-at-budget` (anchor sanity).

Stdlib-only and network-free, like the gate.
"""

import argparse
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="declared-only budget check (blind anchor)")
    parser.add_argument("--commands", action="store_true")
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    root = args.root.resolve()
    commands = root / ".claude" / "commands"
    table = root / ".claude" / "command-word-budgets.tsv"
    if not commands.is_dir() or not table.is_file():
        print("command-docs-budget: missing commands directory or budget table", file=sys.stderr)
        return 1
    declared = {
        line.split("\t")[1]
        for line in table.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#") and "\t" in line
    }
    documents = sorted(p.relative_to(commands).as_posix() for p in commands.rglob("*.md"))
    undeclared = [name for name in documents if name not in declared]
    for name in undeclared:
        print(f"command-docs-budget: {name} has no declared budget", file=sys.stderr)
    if undeclared:
        return 1
    print(f"command-docs-budget: ok - {len(documents)} command documents declared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
