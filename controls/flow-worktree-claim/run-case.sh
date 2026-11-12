#!/bin/sh
# Case runner for controls/flow-worktree-claim (issue #1726).
#
#   run-case.sh <case-dir> <gate>
#
# Builds a repository with one linked worktree in a temp dir, locks the
# worktree with a flow claim whose OWNER is in the state the case names, and
# asks the gate (`check`) what it makes of that claim, as another session.
#
#   owner=live      the owning process exists and is the one that claimed
#   owner=recycled  the pid exists, but it is a DIFFERENT process (its start
#                   time is not the one the claim recorded)
#   owner=zombie    the pid exists and has exited; nobody has reaped it
#   owner=none      the worktree carries no claim
#
# THE FINDING IS "this claim's owner is provably gone". A helper that reads
# liveness as "some process has this number" calls both the recycled and the
# zombie owner live, and the worktree is then removable only with --steal -
# the override that is supposed to mean a genuinely live owner is being
# overridden. The process table is a fixture (FLOW_CLAIM_PROC_ROOT), so no
# case depends on a pid that happens to exist on this host.
set -u
case_dir="$1"
gate="$2"
case "$gate" in /*) ;; *) gate="$PWD/$gate" ;; esac
command -v git >/dev/null 2>&1 || { echo "FLOW_CLAIM_CONTROL: unavailable - git is not installed"; exit 3; }
command -v bash >/dev/null 2>&1 || { echo "FLOW_CLAIM_CONTROL: unavailable - bash is not installed"; exit 3; }
owner=$(sed -n 's/^owner=//p' "$case_dir/facts.txt" 2>/dev/null | head -1)
case "$owner" in live|recycled|zombie|none) ;; *) echo "FLOW_CLAIM_CONTROL: cannot-run - bad owner '$owner'"; exit 2 ;; esac

# GIT IS TOLD ABOUT ITS REPOSITORY BY PATH AND BY NOTHING ELSE. A caller's
# GIT_DIR, GIT_WORK_TREE or GIT_INDEX_FILE would make `git -C <fixture>` act on
# the CALLER's repository and commit its staged changes; an inherited
# GIT_CONFIG_COUNT or GIT_TEMPLATE_DIR would run somebody's hooks on the
# fixture's commits. So every GIT_* variable is dropped, by pattern and not by
# a list of the ones thought of, configuration is confined to what follows,
# and hooks are off for the fixture and for the gate alike.
for inherited in $(env | sed -n 's/^\(GIT_[A-Za-z0-9_]*\)=.*/\1/p'); do unset "$inherited"; done
GIT_CONFIG_GLOBAL=/dev/null
GIT_CONFIG_SYSTEM=/dev/null
GIT_CONFIG_NOSYSTEM=1
GIT_CONFIG_COUNT=1
GIT_CONFIG_KEY_0=core.hooksPath
GIT_CONFIG_VALUE_0=/dev/null
export GIT_CONFIG_GLOBAL GIT_CONFIG_SYSTEM GIT_CONFIG_NOSYSTEM GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0

T=$(mktemp -d) || { echo "FLOW_CLAIM_CONTROL: unavailable - no tmpdir"; exit 3; }
trap 'rm -rf "$T"' EXIT
G() { git -c user.email=fixture@example.invalid -c user.name=fixture -c commit.gpgsign=false "$@"; }
mkdir "$T/no-template"
{
  G init -q -b main --template="$T/no-template" "$T/main" &&
  G -C "$T/main" commit -q --allow-empty -m base &&
  G -C "$T/main" worktree add -q -b issue-42-fixture "$T/wt"
} >/dev/null 2>&1 || { echo "FLOW_CLAIM_CONTROL: cannot-run - could not build the fixture repository"; exit 2; }

# The owner: pid 9999 on host `controlhost`, recorded as started at tick 111.
# After the comm, the stat fields are: state, ppid, ... thread count (18th),
# ... start time (20th).
stat_line() { printf '9999 (owner) %s 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 %s\n' "$1" "$2"; }
mkdir -p "$T/proc/9999"
case "$owner" in
  live)     stat_line S 111 > "$T/proc/9999/stat" ;;
  recycled) stat_line S 999 > "$T/proc/9999/stat" ;;
  zombie)   stat_line Z 111 > "$T/proc/9999/stat" ;;
esac
if [ "$owner" != none ]; then
  G -C "$T/main" worktree lock --reason \
    "flow-claim issue=42 pid=9999 session=owner host=controlhost ts=$(date +%s) start=111" "$T/wt" \
    >/dev/null 2>&1 || { echo "FLOW_CLAIM_CONTROL: cannot-run - could not lock the worktree"; exit 2; }
fi

out=$(env CLAUDE_PID=4242 CLAUDE_CODE_SESSION_ID=observer FLOW_CLAIM_HOST=controlhost \
          FLOW_CLAIM_LIVE_PIDS=9999 FLOW_CLAIM_PROC_ROOT="$T/proc" \
          bash "$gate" check "$T/wt" 2>&1)
rc=$?
printf '%s\n' "$out"
verdict=$(printf '%s\n' "$out" | sed -n 's/^FLOW_CLAIM: //p' | tail -1)
# A CRASH IS NOT A VERDICT: no FLOW_CLAIM line, or a non-zero exit from a
# read-only check, is reported as cannot-run and never scored as either side.
if [ "$rc" -ne 0 ] || [ -z "$verdict" ]; then
  echo "FLOW_CLAIM_CONTROL: cannot-run - check exited $rc with verdict '${verdict:-none}'"
  exit 2
fi
case "$verdict" in
  stale)     echo "FLOW_CLAIM_CONTROL: finding - the claim's owner is gone ($verdict)"; exit 1 ;;
  held|free) echo "FLOW_CLAIM_CONTROL: no-finding - $verdict"; exit 0 ;;
  *)         echo "FLOW_CLAIM_CONTROL: cannot-run - unexpected verdict '$verdict'"; exit 2 ;;
esac
