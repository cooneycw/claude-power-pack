#!/usr/bin/env python3
"""CONSTRUCTED BLIND ANCHOR: fixed helper list, prose membership, unchecked waivers.

Intentionally omits all plan-record verbs and any newly invented helper.
It also trusts waiver metadata without checking its reason, issue or citation.
This is not historical source and must never replace the real checker.
"""
import argparse
import json
from pathlib import Path

HELPERS = {
    "check-ignored-additions.sh", "codex-skill-resync.sh", "counter-model-receipt.py",
    "flow-ci-status.sh", "flow-finish-gate.sh", "flow-live-driver-guard.sh",
    "flow-stale-check.sh", "flow-start-resolve.sh",
    "flow-worktree-claim.sh", "flow-worktree-guard.sh", "friction-log.sh",
    "gh-pr-merge.sh", "nit-store-resolve.sh", "speckit-context.py", "worktree-remove.sh",
}
p = argparse.ArgumentParser()
p.add_argument("--root", type=Path, required=True)
a = p.parse_args()
table = json.loads((a.root / "docs/agents/driver-parity.json").read_text())["entries"]
missing = []
for driver in ("codex", "qwen", "gemma"):
    text = (a.root / f".claude/commands/{driver}/auto.md").read_text()
    for helper in HELPERS:
        waived = any(e.get("driver") == driver and e.get("gate") == helper and e.get("disposition") in {"equivalent", "exempt"} for e in table)
        if helper not in text and not waived:
            missing.append((driver, helper))
print("DRIVER_PARITY: fail" if missing else "DRIVER_PARITY: ok")
raise SystemExit(1 if missing else 0)
