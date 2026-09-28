#!/bin/sh
# Case runner for controls/flow-worktree-guard (#1014).
#
# Builds a real repository with a linked worktree in a temp dir, and runs the
# gate from the place the case's `scenario` names:
#   clean-linked   the worktree, main clean              -> the gate LOOKED
#   main-checkout  the main checkout itself              -> nothing to examine
#   git-fails      the worktree, with a git that cannot resolve its own
#                  git dir (FLOW_WORKTREE_GIT)          -> the gate COULD NOT look
#
# THE FINDING IS "the gate did not report a clean look". The pre-#1014 guard
# exited 0, silently, in all three - a clean pass, a not-applicable run and a
# blind run were byte-identical - so the historical anchor misses both BAD
# cases and agrees on the GOOD one. The fixed gate exits non-zero (unknown 4,
# not-applicable 5) on the two BAD cases.
set -u
case_dir="$1"
gate="$2"
command -v git >/dev/null 2>&1 || { echo "FLOW_WORKTREE_GUARD_CONTROL: unavailable - git is not installed"; exit 3; }
command -v bash >/dev/null 2>&1 || { echo "FLOW_WORKTREE_GUARD_CONTROL: unavailable - bash is not installed"; exit 3; }
scenario=$(cat "$case_dir/scenario") || exit 3
gate_abs=$(cd "$(dirname "$gate")" && pwd)/$(basename "$gate")
# A gate that sources gate-lib.sh finds it beside itself; a historical anchor
# runs from controls/, so offer the library next to a COPY of the gate.
T=$(mktemp -d) || { echo "FLOW_WORKTREE_GUARD_CONTROL: unavailable - no tmpdir"; exit 3; }
trap 'rm -rf "$T"' EXIT
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
cp "$gate_abs" "$T/guard.sh" && cp "$repo_root/scripts/gate-lib.sh" "$T/gate-lib.sh" || exit 3

git init -q -b main "$T/main" || exit 3
printf 'a\n' > "$T/main/a.txt"
git -C "$T/main" add a.txt && git -C "$T/main" -c user.email=t@t -c user.name=t commit -q -m base || exit 3
git -C "$T/main" worktree add -q -b issue-1-x "$T/wt" || exit 3

case "$scenario" in
  clean-linked)  (cd "$T/wt" && bash "$T/guard.sh" --strict) >"$T/out" 2>&1; rc=$? ;;
  main-checkout) (cd "$T/main" && bash "$T/guard.sh" --strict) >"$T/out" 2>&1; rc=$? ;;
  git-fails)
    printf '#!/usr/bin/env bash\ncase "$*" in *--is-inside-work-tree*) exit 0 ;; esac\nexit 128\n' > "$T/git"
    chmod +x "$T/git"
    (cd "$T/wt" && FLOW_WORKTREE_GIT="$T/git" bash "$T/guard.sh" --strict) >"$T/out" 2>&1; rc=$? ;;
  *) echo "FLOW_WORKTREE_GUARD_CONTROL: unavailable - unknown scenario '$scenario'"; exit 3 ;;
esac

if [ "$rc" -eq 0 ]; then
  echo "FLOW_WORKTREE_GUARD_CONTROL: clean-look (gate exit 0)"
  exit 0
fi
echo "FLOW_WORKTREE_GUARD_CONTROL: finding - gate exit $rc: $(grep '^FLOW_WORKTREE_GUARD:' "$T/out" | head -1)"
exit 1
