#!/bin/sh
# Case runner for controls/flow-worktree-guard-leak (issue #1726).
#
#   run-case.sh <case-dir> <gate>
#
# Builds a repository with a linked worktree in a temp dir and runs the guard
# from the worktree, with `--strict`, in the state the case's `scenario` names:
#   fresh-leak     this run edited a.txt, and a.txt was ALSO just changed in the
#                  main checkout                       -> an edit leaked into main
#   clean          main is clean                       -> nothing leaked
#   stale-overlap  the same overlap, but main's change is years old
#                                                      -> pre-existing dirt, not this run's
#
# THE FINDING IS the `leak` verdict (exit 3): the reason the guard exists. Its
# other control (controls/flow-worktree-guard) covers the could-not-look and
# nothing-to-look-at verdicts, and cannot hold this case: its historical
# anchor already caught a real leak, and an anchor that catches a known-bad
# case scores a control INERT.
set -u
case_dir="$1"
gate="$2"
command -v git >/dev/null 2>&1 || { echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: unavailable - git is not installed"; exit 3; }
command -v bash >/dev/null 2>&1 || { echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: unavailable - bash is not installed"; exit 3; }
scenario=$(cat "$case_dir/scenario" 2>/dev/null) || { echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: cannot-run - no scenario"; exit 2; }
gate_abs=$(cd "$(dirname "$gate")" && pwd)/$(basename "$gate")

raw=$(mktemp -d) || { echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: unavailable - no tmpdir"; exit 3; }
T=$(cd "$raw" && pwd -P) || { echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: cannot-run - tmpdir unreadable"; exit 2; }
trap 'rm -rf "$T"' EXIT
mkdir "$T/home" "$T/tmp" "$T/no-template"
# EVERYTHING THIS RUNNER STARTS GETS AN ENVIRONMENT BUILT FROM NOTHING.
# Git and bash are steered by their environment: GIT_DIR or GIT_INDEX_FILE
# makes `git -C <fixture>` act on the caller's repository, GIT_CONFIG_COUNT
# runs somebody's hooks, the helpers read their own FLOW_* overrides, and
# bash sources $BASH_ENV when the gate starts and can put any of it back.
# Three review passes each found one more name a list had missed. So nothing
# is inherited but PATH: HOME and TMPDIR are inside this runner's directory,
# configuration is confined, hooks are off, and a variable reaches the gate
# only by being written on the line that starts it.
clean() {
  env -i PATH="$PATH" HOME="$T/home" TMPDIR="$T/tmp" LC_ALL=C \
      GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_NOSYSTEM=1 \
      GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null \
      "$@"
}
G() { clean git -c user.email=fixture@example.invalid -c user.name=fixture -c commit.gpgsign=false "$@"; }
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
# The guard sources gate-lib.sh from beside itself; an anchor runs from
# controls/, so both are offered next to a COPY of whichever gate is under test.
if ! { cp "$gate_abs" "$T/guard.sh" && cp "$repo_root/scripts/gate-lib.sh" "$T/gate-lib.sh"; }; then
  echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: cannot-run - could not stage the gate"; exit 2
fi
{
  G init -q -b main --template="$T/no-template" "$T/main" &&
  printf 'a\n' > "$T/main/a.txt" &&
  G -C "$T/main" add a.txt && G -C "$T/main" commit -q -m base &&
  G -C "$T/main" worktree add -q -b issue-1-x "$T/wt"
} >/dev/null 2>&1 || { echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: cannot-run - could not build the fixture"; exit 2; }

case "$scenario" in
  clean) : ;;
  fresh-leak)
    printf 'worktree edit\n' > "$T/wt/a.txt"
    printf 'leaked edit\n' > "$T/main/a.txt" ;;
  stale-overlap)
    printf 'worktree edit\n' > "$T/wt/a.txt"
    printf 'old main dirt\n' > "$T/main/a.txt"
    touch -t 202001010000 "$T/main/a.txt" || { echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: cannot-run - touch -t"; exit 2; } ;;
  *) echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: cannot-run - unknown scenario '$scenario'"; exit 2 ;;
esac

(cd "$T/wt" && clean FLOW_LEAK_FRESH_MIN=30 bash "$T/guard.sh" --strict) >"$T/out" 2>&1
rc=$?
cat "$T/out"
marker=$(grep -E '^FLOW_WORKTREE_GUARD: ' "$T/out" | head -1)
# A CRASH IS NOT A VERDICT: the exit code counts only beside the verdict line
# that goes with it.
case "$rc:$marker" in
  3:"FLOW_WORKTREE_GUARD: leak"*)
    echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: finding - $marker"; exit 1 ;;
  0:"FLOW_WORKTREE_GUARD: no-leak"*)
    echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: no-finding - $marker"; exit 0 ;;
  *)
    echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: cannot-run - gate exit $rc with verdict '${marker:-none}'"; exit 2 ;;
esac
