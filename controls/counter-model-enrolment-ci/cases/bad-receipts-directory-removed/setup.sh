#!/usr/bin/env bash
. "$(dirname "$0")/common.sh" 2>/dev/null || . ./common.sh
init_repo
# The PR deleted the receipts directory: the participation marker is gone, so
# finish mode would call this repository not-enrolled and let it through.
echo change > change.txt; git add -A; git commit -qm "the PR's change"
git checkout -q --detach HEAD
