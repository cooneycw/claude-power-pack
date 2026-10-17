#!/usr/bin/env bash
. "$(dirname "$0")/common.sh" 2>/dev/null || . ./common.sh
init_repo
# The PR's own receipt for its branch, at an ancestor - but recorded with no
# `scope`, so it says nothing about what the reviewer could see (issue #1461).
NO_SCOPE=1 write_receipt "$(git rev-parse HEAD)" ran issue-9-pr
git add -A; git commit -qm "receipt without scope"
git checkout -q --detach HEAD
