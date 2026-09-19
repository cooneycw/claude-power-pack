#!/usr/bin/env python3
"""ANCHOR - a deliberately BLIND version of scripts/instrument-census-check.py.

DO NOT FIX THIS FILE. It is evidence, not code that runs in anger. The register
swaps it in for the real gate and requires it to MISS the known-bad inputs; an
anchor that catches them proves the control is not load-bearing, and the harness
reports INERT.

WHAT IT IS. Not a historical commit - the gate is new and never shipped blind,
so there is nothing to vendor. This is the FIRST FRAMING of the problem, and it
is on the record: issue #1060 as filed said the check should report a `scripts/`
file "present in neither the census nor the exclusions table", which describes
the forward direction and says nothing about the extraction rule. Written
straight from that sentence, you get this file. Two differences from the gate,
both of which the measurement in the real file's docstring rejected:

  1. EVERY BACKTICKED TOKEN ANYWHERE IN THE DOCUMENT counts as accounting for a
     script, rather than the first token of a numbered row's column 2. Measured
     against the real ADR this rule reported 13 unaccounted files of which 7
     were false, and 110 non-file subjects drawn from the verdict-contract and
     consumer columns. Its failure direction is the dangerous one: a script
     mentioned anywhere in the prose reads as enumerated.

  2. FORWARD DIRECTION ONLY. No STALE check, so a census row naming a deleted
     script is invisible and the denominator silently inflates - which moves the
     coverage fraction in the flattering direction.

Both bad cases are missed for one of those two reasons, and the good case is
scored identically to the real gate, which is what makes the demonstration
isolated rather than "this file differs somehow".
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: NEGATIVE-CONTROL: controls/instrument-census
#:
#: Carried so that swapping this file in for the registered gate is literally
#: "the fix reverted" and the register still discovers the control. Generated
#: from the UNregistered gate, that swap removes the registration too and the
#: run reports REGISTERED: 0 instead of BLIND - red either way, but the wrong
#: diagnosis.

REPO_ROOT = Path(__file__).resolve().parents[1]
ADR_REL = "docs/decisions/0008-instrument-negative-control-bound.md"
SCRIPTS_REL = "scripts"

BACKTICKED_RE = re.compile(r"`([^`]+)`")


def run_check(root: Path) -> int:
    adr = root / ADR_REL
    scripts_dir = root / SCRIPTS_REL

    if not scripts_dir.is_dir():
        print(f"instrument-census-check: no {SCRIPTS_REL}/ under {root}; nothing compared.")
        return 1
    if not adr.is_file():
        print(f"UNACCOUNTED: {ADR_REL} does not exist under {root}")
        print("instrument-census-check: the census itself is absent; nothing compared.")
        return 1

    text = adr.read_text(encoding="utf-8")
    files = {path.name for path in sorted(scripts_dir.iterdir()) if path.is_file()}
    if not files:
        print(f"instrument-census-check: {SCRIPTS_REL}/ holds no files; nothing compared.")
        return 1

    # THE BLINDNESS: every backticked token in the whole document, not the first
    # token of a numbered row's instrument column.
    subjects = {token.strip().split()[0] for token in BACKTICKED_RE.findall(text) if token.strip()}

    findings = 0
    for name in sorted(files):
        if name in subjects or Path(name).stem in subjects:
            continue
        print(
            f"UNACCOUNTED: {SCRIPTS_REL}/{name} is named by no census row and no "
            f"exclusion in {ADR_REL}"
        )
        findings += 1

    # THE SECOND BLINDNESS: no reverse direction at all.

    print(f"INSTRUMENT_CENSUS_EXAMINED: {len(files)}")

    if findings:
        print(f"instrument-census-check: {findings} finding(s).")
        return 1

    print(
        f"instrument-census-check: ok - all {len(files)} file(s) in {SCRIPTS_REL}/ "
        f"are accounted for by {ADR_REL}, and every subject resolves."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("mode", nargs="?", default="check", choices=["check"])
    ap.add_argument("--root", default=str(REPO_ROOT))
    args = ap.parse_args(argv)
    return run_check(Path(args.root).resolve())


if __name__ == "__main__":
    sys.exit(main())
