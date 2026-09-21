#!/usr/bin/env bash
# Build the case tree. Runs INSIDE the copied temp dir, so nothing here touches
# the repository under test.
set -eu
# Pin the branch: `git init` without -b takes init.defaultBranch from the
# HOST, so on a box configured for `main` these fixtures wrote receipts for
# a branch that did not exist and the control's verdict became a property of
# the host rather than of the instrument (counter-model review, MEDIUM).
git init -q -b master .
git config user.email c@c; git config user.name c
git config commit.gpgsign false
echo base > base.txt; git add -A; git commit -qm base
write_receipt() { # $1 head  $2 status  $3 skip_reason
  mkdir -p docs/measurements/counter-model
  python3 - "$@" <<PYEOF
import json, sys, pathlib
head, status = sys.argv[1], sys.argv[2]
r = {"schema": 1, "recorded_at": "2026-09-21T12:00:00Z", "issue": "1171",
     "branch": "master", "head": head, "status": status,
     "reviewer": None if status == "skipped" else "codex/gpt-6-astra",
     "implementer": "claude/claude-opus-5"}
if status == "skipped":
    r["skip_reason"] = sys.argv[3]
pathlib.Path("docs/measurements/counter-model/receipt.json").write_text(json.dumps(r, indent=2))
PYEOF
}

# THE ANCESTRY RULE. The review was taken, then the branch advanced - which is
# exactly what auto.md does between :1021 and :1240. Strict head equality reds
# here; this must pass.
write_receipt "$(git rev-parse HEAD)" ran
echo more > more.txt; git add -A; git commit -qm after-review
echo again > again.txt; git add -A; git commit -qm merge-like
