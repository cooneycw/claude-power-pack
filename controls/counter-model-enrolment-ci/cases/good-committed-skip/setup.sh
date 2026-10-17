#!/usr/bin/env bash
. "$(dirname "$0")/common.sh" 2>/dev/null || . ./common.sh
init_repo
write_receipt "$(git rev-parse HEAD)" skipped issue-9-pr codex-absent
git add -A; git commit -qm "skip receipt"
git checkout -q --detach HEAD
