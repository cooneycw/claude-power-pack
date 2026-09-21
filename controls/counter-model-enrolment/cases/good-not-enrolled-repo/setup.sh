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
# A repository that does not participate: no receipts directory at all. This
# helper is installed globally and /flow:auto runs it in other repositories,
# which have never run a counter-model review. They must not red.
