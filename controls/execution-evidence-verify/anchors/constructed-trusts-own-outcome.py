#!/usr/bin/env python3
"""CONSTRUCTED anchor for controls/execution-evidence-verify (issue #1366).

The plausible weaker reader: trust the record's OWN summary. A known schema, a
terminal event and `outcome: completed` and it says supported. It catches a
missing terminal event and a record that admits failure - and is blind to every
fact the record cannot vouch for about itself: a tree edited after the run, a
record copied under another name, and a summary that claims `completed` over a
gate that never ran. Same CLI and markers as scripts/execution-evidence-verify.py.
"""

import json
import sys

try:
    record = json.loads(open(sys.argv[1], encoding="utf-8").read())
except (OSError, ValueError, IndexError):
    print("EXECUTION_EVIDENCE: unknown")
    sys.exit(4)
if record.get("schema") != "cpp.execution-evidence/v1":
    print("EXECUTION_EVIDENCE: unknown")
    sys.exit(4)
if record.get("terminal") and record.get("outcome") == "completed":
    print("EXECUTION_EVIDENCE: supported")
    sys.exit(0)
print("EXECUTION_EVIDENCE: not-supported")
sys.exit(3)
