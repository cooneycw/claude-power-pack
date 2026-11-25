#!/usr/bin/env python3
"""Fixture-only discover/refresh/verify/report entry for the neutral host core.

Production adapters and host-global discovery are not shipped by delivery A.
Every destination is explicitly supplied under a marked disposable fixture.
"""
#: NEGATIVE-CONTROL: controls/host-update-core

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent.parent))

from lib.host_update.driver import run  # noqa: E402
from lib.host_update.fixture import load_fixture  # noqa: E402
from lib.host_update.models import Request  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("verify", "refresh"))
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--lock-timeout", type=float, default=5.0)
    parser.add_argument("--selected", choices=("auto", "yes", "no"), default="auto")
    parser.add_argument("--adopt", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        adapters, revision = load_fixture(args.fixture_root.absolute())
    except Exception as exc:
        print(f"HOST_UPDATE: invalid fixture ({type(exc).__name__})", file=sys.stderr)
        return 2
    selection = None if args.selected == "auto" else args.selected == "yes"
    request = Request(revision, selection, args.lock_timeout, tuple(args.adopt))
    report = run(adapters, request, verify_only=args.operation == "verify")
    state = {0: "current", 1: "failure", 4: "unknown", 5: "not-applicable"}[report.exit_code]
    print(f"HOST_UPDATE: {state} (fixture-only; {sum(row.selected for row in report.results)} selected adapters)",
          file=sys.stderr)
    if args.json:
        print(json.dumps(asdict(report), sort_keys=True, indent=2))
    else:
        for row in report.results:
            print(f"{row.harness}: {row.before.state} -> {row.after.state}; "
                  f"{row.action}; exit {row.exit_code}; {row.reason}")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
