#!/usr/bin/env python3
"""THE BLIND ANCHOR for controls/bandit-audit: codex-power-pack's own one-liner.

This is NOT a strawman written to fail. It is a faithful implementation of the
command issue #962 exists to reject, which CxPP runs today:

    bandit -r lib scripts -ll --quiet --skip B104,B108,B310,B602

Everything the real gate adds is absent here, and each absence is one of the
known-bad cases it therefore misses:

  * the skip list is APPLIED, so a B602 in a file nothing accounts for is
    dropped before the verdict. Measured on CPP's tree at adoption: 10 of 11
    MEDIUM+ findings disappear this way.
  * there is NO allowlist, so a suppression that has outlived its finding
    cannot be noticed - a `--skip` has nothing to go stale.
  * `metrics._totals.skipped_tests` is never read, so a skip list arriving by
    any route is invisible.
  * per-file `nosec` is never read, so an inline `# nosec` deletes a finding
    from the report and nothing says so.

It ACCEPTS the real gate's argv - `--from-capture`, `--allow-file`, `--root` -
because check-negative-controls.py invokes the anchor with the manifest's
invocation, substituting the anchor for `{gate}`. `--allow-file` is accepted and
then ignored, which is precisely the blindness under test rather than an
oversight in the fixture.

It PRINTS `BANDIT-FINDING:` when it does report, so that an anchor which
unexpectedly CAUGHT a known-bad input is scored INERT (a real alarm about this
control) rather than UNRESOLVED (a crash). Issue #946's distinction, held on the
anchor side.

FROZEN. Never edited to satisfy a linter or a refactor - its bytes are the
evidence, and `controls/*/anchors` is excluded from ruff and mypy for that
reason. If the real gate's argv changes, this file is REPLACED and its sha256
re-recorded, not patched.
"""

from __future__ import annotations

import argparse
import json
import sys

CXPP_SKIP = {"B104", "B108", "B310", "B602"}
GATED = {"MEDIUM", "HIGH"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--allow-file", default=None)
    parser.add_argument("--from-capture", default=None)
    parser.add_argument("--capture", default=None)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if not args.from_capture:
        print("BANDIT-UNKNOWN: this anchor only replays a capture", file=sys.stderr)
        return 2
    try:
        with open(args.from_capture, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"BANDIT-UNKNOWN: capture unreadable: {exc}", file=sys.stderr)
        return 2

    results = payload.get("report", {}).get("results", []) or []
    kept = [
        r for r in results
        if str(r.get("issue_severity", "")).upper() in GATED
        and str(r.get("test_id", "")) not in CXPP_SKIP
    ]
    for finding in kept:
        print(
            f"BANDIT-FINDING: {finding.get('filename')}:{finding.get('line_number')} "
            f"{finding.get('test_id')} ({finding.get('issue_severity')})",
            file=sys.stderr,
        )
    print(f"bandit-audit: {len(kept)} finding(s) at -ll after --skip {','.join(sorted(CXPP_SKIP))}")
    return 1 if kept else 0


if __name__ == "__main__":
    sys.exit(main())
