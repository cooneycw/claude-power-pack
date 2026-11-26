#!/usr/bin/env python3
"""Build/check self-contained topic copies in an explicit generated directory."""
#: NEGATIVE-CONTROL: controls/antigravity-skill-build
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent.parent))

from lib.antigravity_skills import BuildAdapter  # noqa: E402
from lib.host_update.driver import _source_git, run  # noqa: E402
from lib.host_update.models import Request, Revision  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).absolute().parent.parent)
    parser.add_argument("--revision")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    source = args.source_root.absolute()
    revision = args.revision
    if revision is None:
        result = _source_git(Revision("", source), ["rev-parse", "HEAD"])
        revision = result.stdout.decode().strip() if result.returncode == 0 else "unavailable"
    output = (args.output_root or source / "antigravity/skills").absolute()
    report = run([BuildAdapter(output)], Request(Revision(revision, source), selected=True),
                 verify_only=not args.write)
    report = replace(report, coverage="antigravity-topic-build-only")
    print("AGY_SKILLS: " + {0: "current", 1: "failure", 4: "unknown", 5: "not-applicable"}[report.exit_code],
          file=sys.stderr)
    if args.json:
        print(json.dumps(asdict(report), sort_keys=True, indent=2))
    else:
        for row in report.results:
            print(f"{row.harness}: {row.after.state}; expected={row.after.expected_packages}; {row.reason}")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
