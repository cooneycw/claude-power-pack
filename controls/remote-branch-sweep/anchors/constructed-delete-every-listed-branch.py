#!/usr/bin/env python3
"""CONSTRUCTED blind anchor for scripts/remote-branch-sweep.py (issue #1262).

A sweeper that trusts the branch list: every branch it can see, it plans to
delete. It never reads a PR, a push time, a merge commit or a worktree, so it
MISSES every registered BAD case - moved after merge, merge commit off the
default branch, open PR, pushed within 24h, closed unmerged, never had a PR -
and AGREES with the real gate on the one GOOD case. That is the failure the
real gate exists to prevent: an orphan-branch cleanup that deletes someone's
only copy because it was on the list.
"""

import argparse
import json
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("mode")
ap.add_argument("--repo", required=True)
ap.add_argument("--api-fixture", type=Path, required=True)
ap.add_argument("--now")
args = ap.parse_args()
table = json.loads(args.api_fixture.read_text(encoding="utf-8"))
branches = table.get(f"repos/{args.repo}/branches?per_page=100") or []
for b in branches:
    print(f"SWEEP_DELETE: {b['name']} {b['commit']['sha']} - listed")
print(f"SWEEP: plan examined={len(branches)} delete={len(branches)} refused=0")
sys.exit(0)
