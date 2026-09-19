#!/usr/bin/env python3
"""Reconcile independently measured open issues with hand-maintained claims.

A finding lost in a mailbox loses one observation. An instrument left in a
session scratchpad silently weakens every later measurement it would have
checked, without leaving any warning in the output. This repository instrument
keeps that check available across sessions; it never authors its claimed side.

The default open set comes from GitHub. --open-set-capture replays an independent
JSON list of issue numbers offline, including in every committed control case.
Claims come only from --claimed-file (default: docs/slate-lanes.json).
Exit 0 means clean, 1 means findings, and 2 means required evidence is unknown.
Unreadable populations and unevaluable finding counts are printed as unknown,
never zero. DUPLICATE is checked even when the open-set source is unusable.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path

#: NEGATIVE-CONTROL: controls/slate-reconcile
#: ADR 0008: an operator may trust this verdict without rechecking membership.
#: Offline captures keep both input origins explicit and controls reproducible.

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_UNKNOWN = 2
DEFAULT_CLAIMED = Path(__file__).resolve().parents[1] / "docs" / "slate-lanes.json"
OPEN_LIMIT = 1_000_000  # Override gh's small default; refuse a possibly capped set.


def issue_list(value: object) -> list[int]:
    """Reject booleans too: JSON true is not an issue number."""
    if not isinstance(value, list) or any(type(number) is not int for number in value):
        raise ValueError("expected a list of integers")
    return value


def read_claims(path: Path) -> dict[int, list[str]]:
    """Read declarations only; notes never influence a verdict."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("missing claimed file") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("malformed claimed file: cannot read JSON") from exc
    try:
        if not isinstance(data, dict):
            raise ValueError("expected an object with lanes and buckets")
        memberships = defaultdict(list)
        for section in ("lanes", "buckets"):
            if section not in data or not isinstance(data[section], dict):
                raise ValueError(f"{section} must be an object")
            for name, numbers in data[section].items():
                try:
                    numbers = issue_list(numbers)
                except ValueError as exc:
                    raise ValueError(f"{section}.{name} must be a list of integers") from exc
                for number in numbers:
                    memberships[number].append(f"{section}.{name}")
        return dict(memberships)
    except ValueError as exc:
        raise ValueError(f"malformed claimed file: {exc}") from exc


def read_open_set(capture: Path | None) -> set[int]:
    if capture is not None:
        try:
            return set(issue_list(json.loads(capture.read_text(encoding="utf-8"))))
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError("unusable open-set source: cannot read capture as a list of integers") from exc
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", "cooneycw/claude-power-pack",
             "--state", "open", "--json", "number", "--limit", str(OPEN_LIMIT)],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("unusable open-set source: gh timed out") from exc
    except (OSError, UnicodeError) as exc:
        raise ValueError("unusable open-set source: cannot run gh") from exc
    if result.returncode:
        raise ValueError(f"unusable open-set source: gh exited {result.returncode}")
    try:
        rows = json.loads(result.stdout)
        if not isinstance(rows, list) or any(not isinstance(row, dict) or "number" not in row for row in rows):
            raise ValueError("expected issue objects")
        numbers = issue_list([row["number"] for row in rows])
    except ValueError as exc:
        raise ValueError("unusable open-set source: malformed gh output") from exc
    if len(numbers) >= OPEN_LIMIT:
        raise ValueError("unusable open-set source: gh result reached its limit; completeness unknown")
    return set(numbers)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--claimed-file", type=Path, default=DEFAULT_CLAIMED,
                        help="hand-maintained claims (default: repository docs/slate-lanes.json)")
    parser.add_argument("--open-set-capture", type=Path,
                        help="offline JSON list of open issue numbers; otherwise query GitHub with gh")
    args = parser.parse_args(argv)

    errors = []
    claimed = opened = None
    try:
        claimed = read_claims(args.claimed_file)
    except ValueError as exc:
        errors.append(str(exc))
    try:
        opened = read_open_set(args.open_set_capture)
    except ValueError as exc:
        errors.append(str(exc))

    for error in errors:
        print(f"SLATE-UNKNOWN: {error}")
    duplicates = None if claimed is None else sorted(n for n, places in claimed.items() if len(places) > 1)
    unaccounted = phantom = None
    if opened is not None and claimed is not None:
        unaccounted = sorted(opened - claimed.keys())
        phantom = sorted(claimed.keys() - opened)
    # PHANTOM and DUPLICATE are only ever non-empty when `claimed` parsed
    # successfully (see the guards above), so this fallback is never actually
    # indexed on a real finding - it exists to give mypy a concrete type
    # rather than `dict[int, list[str]] | None`, without re-deriving the
    # guard's own logic a second time.
    claimed_locations = claimed or {}
    for kind, numbers in (("UNACCOUNTED", unaccounted), ("PHANTOM", phantom), ("DUPLICATE", duplicates)):
        for number in numbers or []:
            locations = "" if kind == "UNACCOUNTED" else " in " + ", ".join(claimed_locations[number])
            print(f"SLATE-FINDING: {kind} #{number}{locations}")

    has_findings = bool(unaccounted or phantom or duplicates)
    verdict = "UNKNOWN" if errors else "FINDING" if has_findings else "OK"

    def count(value):
        return "unknown" if value is None else len(value)

    print(f"SLATE-{verdict}: open={count(opened)} claimed={count(claimed)} "
          f"UNACCOUNTED={count(unaccounted)} PHANTOM={count(phantom)} DUPLICATE={count(duplicates)}")
    return EXIT_UNKNOWN if errors else EXIT_FINDING if has_findings else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
