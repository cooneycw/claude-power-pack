#!/usr/bin/env bash
. "$(dirname "$0")/common.sh" 2>/dev/null || . ./common.sh
init_repo
write_receipt "$(git rev-parse HEAD)" ran issue-9-pr
git add -A; git commit -qm "receipt"
echo after > after.txt; git add -A; git commit -qm "after review"
git checkout -q --detach HEAD
