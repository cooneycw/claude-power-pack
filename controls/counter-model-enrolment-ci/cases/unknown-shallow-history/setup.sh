#!/usr/bin/env bash
. "$(dirname "$0")/common.sh" 2>/dev/null || . ./common.sh
# What CI is on every run before the step deepens it: a depth-1 clone whose
# receipt names a commit the clone does not carry. Undecidable - and in this
# mode undecidable must NEVER exit ok.
rm -rf .git
mkdir src && ( cd src && git init -q -b master . && git config user.email c@c && git config user.name c \
  && git config commit.gpgsign false && echo one > a.txt && git add -A && git commit -qm one )
FIRST=$( cd src && git rev-parse HEAD )
( cd src && echo two > b.txt && git add -A && git commit -qm two )
git clone --quiet --depth=1 "file://$PWD/src" shallow
mv shallow/.git .; rm -rf shallow src
git config user.email c@c; git config user.name c
git checkout -q --detach HEAD
write_receipt "$FIRST" ran issue-9-pr
