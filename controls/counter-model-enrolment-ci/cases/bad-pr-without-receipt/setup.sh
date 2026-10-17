#!/usr/bin/env bash
. "$(dirname "$0")/common.sh" 2>/dev/null || . ./common.sh
init_repo
# A receipt exists - for ANOTHER branch. The PR's own branch has none.
write_receipt "$(git rev-parse HEAD)" ran issue-8-other
git add -A; git commit -qm "other branch's receipt"
echo change > change.txt; git add -A; git commit -qm "the PR's change"
git checkout -q --detach HEAD
