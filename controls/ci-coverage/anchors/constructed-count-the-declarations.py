#!/usr/bin/env python3
"""CONSTRUCTED ANCHOR for controls/ci-coverage (issue #1146).

THIS IS NOT AN INVENTED STRAW MAN. It is the framing #1146 itself used before
the gate existed: commit `a9408bc` appended a `ci: runs <step>` or
`ci: excluded <reason>` clause to all 27 gates and reported the result as
"22 ci: runs, 5 ci: excluded" - a count obtained by grepping the Makefile. That
count is what this file is. It was the honest summary of the work at the time,
and it is the cheapest thing that looks like an answer to "is every gate
dispositioned?".

WHAT IT CANNOT SEE, which is the whole reason the real gate reads three
populations instead of one:

  * it never opens `.woodpecker.yml`, so `ci: runs ghost-step` counts as
    coverage;
  * it never reads the `verify:` rule, so a prerequisite with no clause is
    simply not counted - absence lowers the number and raises no finding, and
    an empty `verify:` list lowers it to zero without a word;
  * it accepts any word after `ci:`, so `ci: run validate` and a bare
    `ci: excluded` are declarations as far as it is concerned;
  * it binds nothing to a target, so an annotation naming a target that does
    not exist counts exactly like one that does.

A DECLARATION COUNTED IS NOT A FACT CHECKED. That sentence is the entire
distinction between this file and `scripts/check-ci-coverage.py`, and this
anchor exists so the distinction is demonstrated rather than asserted: it must
MISS every committed bad case and AGREE with the real gate on the good one.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CLAUSE_RE = re.compile(r"^##\s*verify-coverage:.*?\bci:\s*(?P<word>\S+)", re.MULTILINE)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)

    makefile = Path(args.root).resolve() / "Makefile"
    text = makefile.read_text(encoding="utf-8") if makefile.is_file() else ""

    runs = 0
    excluded = 0
    for match in CLAUSE_RE.finditer(text):
        if match.group("word").startswith("run"):
            runs += 1
        else:
            excluded += 1

    print(f"CI_COVERAGE_DECLARATIONS: {runs + excluded}")
    print(
        f"check-ci-coverage: ok - {runs + excluded} declaration(s) found: "
        f"{runs} run in CI, {excluded} excluded"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
