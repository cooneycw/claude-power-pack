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
# Make THIS directory a genuinely shallow checkout whose receipt names a commit the
# checkout does not contain - which is what CI is on every run (`--depth=1`).
rm -rf .git docs
mkdir src && ( cd src && git init -q -b master . && git config user.email c@c && git config user.name c \
  && git config commit.gpgsign false && echo one > a.txt && git add -A && git commit -qm one )
FIRST=$( cd src && git rev-parse HEAD )
( cd src && echo two > b.txt && git add -A && git commit -qm two )
git clone --quiet --depth=1 "file://$PWD/src" shallow
mv shallow/.git .
rm -rf shallow src
git config user.email c@c; git config user.name c
# The receipt names the FIRST commit, which the depth-1 clone does not carry.
write_receipt "$FIRST" ran
