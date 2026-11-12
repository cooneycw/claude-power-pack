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
T=$(mktemp -d) || { echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: unavailable - no tmpdir"; exit 3; }
trap 'rm -rf "$T"' EXIT
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
# The guard sources gate-lib.sh from beside itself; an anchor runs from
# controls/, so both are offered next to a COPY of whichever gate is under test.
if ! { cp "$gate_abs" "$T/guard.sh" && cp "$repo_root/scripts/gate-lib.sh" "$T/gate-lib.sh"; }; then
  echo "FLOW_WORKTREE_GUARD_LEAK_CONTROL: cannot-run - could not stage the gate"; exit 2
fi
G() { git -c user.email=fixture@example.invalid -c user.name=fixture -c commit.gpgsign=false "$@"; }
{
  G init -q -b main "$T/main" &&
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

(cd "$T/wt" && env -u FLOW_WORKTREE_GIT FLOW_LEAK_FRESH_MIN=30 bash "$T/guard.sh" --strict) >"$T/out" 2>&1
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
