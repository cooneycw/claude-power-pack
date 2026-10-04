#!/usr/bin/env python3
"""execution-evidence-verify.py - read a durable execution-evidence record (issue #1366).

Prints the one claim a `cpp.execution-evidence/v1` record supports, or why it
supports none. The record is written by the CPP runner when
`CPP_EXECUTION_EVIDENCE=<skill>` is set (`/flow:check` sets `flow-check`); see
docs/agents/execution-evidence.md.

Usage:
  execution-evidence-verify.py <record.json> [--path <checkout>] [--no-current]
  execution-evidence-verify.py latest <skill> [--path <checkout>]

Output ends with `EXECUTION_EVIDENCE: supported | not-supported | unknown`:

  supported      0  terminal, completed, every gate passed, bound to the CURRENT
                    HEAD and working-tree content (unless --no-current)
  not-supported  3  failed / stopped / interrupted / no terminal event / a gate
                    skipped, not run or examining nothing / stale HEAD or tree /
                    replayed or duplicate invocation
  unknown        4  unreadable record, unknown schema, or the current tree could
                    not be identified to compare against

`supported` is a claim about what the helper OBSERVED, not tamper-proof
attestation: the record is a writable local file. Consumers that must rely on a
fact re-derive it under their own authority (skillc #249, CI).

Stdlib only: it imports lib.cicd.evidence, which needs no third-party package, so
it runs with a bare python3 beside the CPP checkout.
"""

#: NEGATIVE-CONTROL: controls/execution-evidence-verify

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.cicd.evidence import cli  # noqa: E402


def main(argv: list[str]) -> int:
    if argv[:1] == ["latest"]:
        return cli(argv)
    if argv[:1] in (["-h"], ["--help"]) or not argv:
        print(__doc__)
        return 0 if argv else 2
    return cli(["verify", *argv])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
