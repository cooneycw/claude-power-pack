#!/usr/bin/env bash
. "$(dirname "$0")/common.sh" 2>/dev/null || . ./common.sh
init_repo
# Reachable by ancestry, but recorded for a different branch: without --branch a
# detached CI checkout would accept it, which is why the step names the branch.
write_receipt "$(git rev-parse HEAD)" ran issue-8-other
echo change > change.txt; git add -A; git commit -qm "the PR's change"
git checkout -q --detach HEAD
