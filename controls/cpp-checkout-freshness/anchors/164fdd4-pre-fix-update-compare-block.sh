#!/usr/bin/env bash
# ANCHOR for controls/cpp-checkout-freshness (issue #1282). NOT a gate - a vendored
# blind artifact the control must fail against.
#
# Lines 148-166 of .claude/commands/cpp/update.md at 164fdd4 are reproduced BYTE
# FOR BYTE between the markers below. The only constructed part is this preamble,
# which gives the markdown block the same calling convention as the gate
# (`--path <checkout>`) and the two variables /cpp:update set before it
# (`cd "$CPP_DIR"`, CURRENT_BRANCH). On an unreachable origin the unchecked fetch
# fails, the stale remote-tracking ref still matches HEAD, and the block prints
# "Already up to date!" with exit 0 - an unknown rendered as clean.
[ "${1:-}" = "--path" ] && [ -n "${2:-}" ] || { echo "usage: $0 --path <checkout>" >&2; exit 2; }
cd "$2" || exit 2
CURRENT_BRANCH=$(git branch --show-current)
# --- BEGIN verbatim .claude/commands/cpp/update.md@164fdd4 lines 148-166 ---
# Fetch latest from origin
echo ""
echo "Fetching latest from origin..."
git fetch origin 2>&1

# Compare with remote
BEHIND=$(git rev-list HEAD..origin/$CURRENT_BRANCH --count 2>/dev/null || echo "0")
AHEAD=$(git rev-list origin/$CURRENT_BRANCH..HEAD --count 2>/dev/null || echo "0")

if [ "$BEHIND" -eq 0 ]; then
  echo ""
  echo "Already up to date!"
else
  echo ""
  echo "$BEHIND commit(s) behind origin/$CURRENT_BRANCH"
  echo ""
  echo "New changes:"
  git log --oneline HEAD..origin/$CURRENT_BRANCH
fi
# --- END verbatim ---
