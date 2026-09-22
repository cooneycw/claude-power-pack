#!/usr/bin/env bash
# The state #1083 replaces: NO GUARD AT ALL.
#
# Before this change nothing enforced #775. `.claude/hooks.json` carried one
# SessionStart notice and two PostToolUse output masks; that was the whole file.
# This anchor is that absence made runnable, so the control can demonstrate that
# the known-bad inputs were ALLOWED before the guard existed - which is what
# makes the post-fix red mean something.
exit 0
