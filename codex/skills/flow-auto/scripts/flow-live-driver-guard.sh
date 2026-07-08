#!/usr/bin/env bash
# flow-live-driver-guard.sh - Warn when a worktree looks like ANOTHER live
# session is mid-implementation in it, before /flow:auto's resume path enters
# it (issue #503).
#
# Motivation: on a box running 3+ concurrent Claude sessions against one repo,
# `/flow:auto <N>` can be invoked while a DIFFERENT live session is already
# driving the issue-N worktree. If the resume path enters it anyway, two drivers
# fight over one checkout and the second driver's Step-7 cleanup can delete the
# first driver's cwd out from under it. The flow:auto #478 run only dodged this
# via an ad-hoc "were files touched in the last few minutes?" check and stood
# down. This guard makes that instinct a reusable, testable check.
#
# What it does: given a worktree path, it inspects the mtimes of every dirty
# file there (tracked-modified + untracked; deleted paths skipped). If ANY was
# modified within the freshness threshold (default 30 minutes), a live driver is
# SUSPECTED - the caller should require explicit confirmation before entering.
# It COMPLEMENTS `gh pr list --head <branch>` (an already-shipped branch is the
# other resume hazard); this guard only speaks to local freshness.
#
# It is ADVISORY and FAIL-OPEN: it never blocks the flow (exit 0) unless
# --exit-code is passed, and a missing path / not-a-repo / stat failure is
# reported and shrugged off, never fatal.
#
# Usage:
#   flow-live-driver-guard.sh [WORKTREE_PATH] [--threshold-minutes N] [--exit-code]
#
#   WORKTREE_PATH        Worktree to inspect (default: current directory).
#   --threshold-minutes N  Freshness window in minutes (default: 30). Alias: --minutes.
#   --exit-code          Return non-zero (1) when a live driver is SUSPECTED;
#                        still 0 for "clear" and "unknown". Default is always-0.
#
# Output ends with a machine-readable verdict line:
#   FLOW_LIVE_DRIVER: clear | suspected | unknown
#
# Env (test hooks - unset in normal use):
#   FLOW_LIVE_DRIVER_NOW   override "now" as epoch seconds (default: date +%s)
#   FLOW_LIVE_DRIVER_GIT   override the `git` binary (default: git)

set -uo pipefail

GIT="${FLOW_LIVE_DRIVER_GIT:-git}"
THRESHOLD_MIN=30
WANT_EXIT_CODE=0
TARGET=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --threshold-minutes|--minutes)
      shift
      if [ "$#" -eq 0 ] || ! printf '%s' "$1" | grep -qE '^[0-9]+$'; then
        echo "flow-live-driver-guard: --threshold-minutes needs a non-negative integer" >&2
        exit 2
      fi
      THRESHOLD_MIN="$1"
      ;;
    --exit-code) WANT_EXIT_CODE=1 ;;
    --help|-h)
      sed -n '2,44p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    --*)
      echo "flow-live-driver-guard: unknown option: $1" >&2
      exit 2
      ;;
    *)
      if [ -z "$TARGET" ]; then
        TARGET="$1"
      else
        echo "flow-live-driver-guard: unexpected argument: $1" >&2
        exit 2
      fi
      ;;
  esac
  shift
done

TARGET="${TARGET:-.}"
verdict() { echo "FLOW_LIVE_DRIVER: $1"; }

# --- Fail-open guards -------------------------------------------------------
if [ ! -d "$TARGET" ]; then
  echo "flow-live-driver-guard: '$TARGET' is not a directory - skipping (advisory)." >&2
  verdict unknown
  exit 0
fi
if ! "$GIT" -C "$TARGET" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "flow-live-driver-guard: '$TARGET' is not a git work tree - skipping (advisory)." >&2
  verdict unknown
  exit 0
fi

ROOT="$("$GIT" -C "$TARGET" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$ROOT" ]; then
  verdict unknown
  exit 0
fi

NOW="${FLOW_LIVE_DRIVER_NOW:-$(date +%s)}"
THRESHOLD_SEC=$((THRESHOLD_MIN * 60))

# Portable mtime-in-epoch for a file: GNU stat first, then BSD/macOS stat.
mtime_of() {
  stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo ""
}

# Collect dirty file paths (tracked-modified + untracked) via NUL-delimited
# porcelain so paths with spaces are safe. For rename/copy entries (R*/C*) the
# porcelain emits "XY new\0old" - the NEW path (what a live driver just wrote)
# is in the current record; the following record is the source, which we skip.
fresh=()
fresh_ages=()
oldest_fresh_min=""
pending_skip=0
while IFS= read -r -d '' entry; do
  if [ "$pending_skip" -eq 1 ]; then
    pending_skip=0   # this record is a rename/copy source path - ignore it.
    continue
  fi
  status="${entry:0:2}"
  path="${entry:3}"
  [ -n "$path" ] || continue
  case "$status" in
    R*|C*) pending_skip=1 ;;   # next record is the source path.
  esac
  # Deleted files cannot be stat'd; a live driver is signalled by writes, not
  # deletions, so skip anything not present on disk.
  f="$ROOT/$path"
  [ -e "$f" ] || continue
  mt="$(mtime_of "$f")"
  [ -n "$mt" ] || continue
  age=$((NOW - mt))
  # Guard against clock skew (negative age) - treat as fresh (just written).
  if [ "$age" -lt 0 ]; then age=0; fi
  if [ "$age" -le "$THRESHOLD_SEC" ]; then
    age_min=$((age / 60))
    fresh+=("$path")
    fresh_ages+=("$age_min")
    if [ -z "$oldest_fresh_min" ] || [ "$age_min" -gt "$oldest_fresh_min" ]; then
      oldest_fresh_min="$age_min"
    fi
  fi
done < <("$GIT" -C "$TARGET" status --porcelain --untracked-files=all -z 2>/dev/null)

if [ "${#fresh[@]}" -eq 0 ]; then
  echo "flow-live-driver-guard: no dirty file in '$ROOT' modified within ${THRESHOLD_MIN}m - clear."
  verdict clear
  exit 0
fi

echo "flow-live-driver-guard: LIVE DRIVER SUSPECTED in '$ROOT'." >&2
echo "  ${#fresh[@]} dirty file(s) modified within the last ${THRESHOLD_MIN}m:" >&2
i=0
max=20
while [ "$i" -lt "${#fresh[@]}" ] && [ "$i" -lt "$max" ]; do
  echo "  - ${fresh[$i]}  (~${fresh_ages[$i]}m ago)" >&2
  i=$((i + 1))
done
if [ "${#fresh[@]}" -gt "$max" ]; then
  echo "  ... and $(( ${#fresh[@]} - max )) more" >&2
fi
echo "" >&2
echo "  Another session may be mid-implementation in this worktree (issue #503)." >&2
echo "  Entering it now risks two drivers fighting over one checkout - the Step-7" >&2
echo "  cleanup can delete the other driver's cwd. Before proceeding:" >&2
echo "    1. Confirm no other live session owns this worktree (ask, or check the mtimes)." >&2
echo "    2. gh pr list --head <branch>   # already-shipped branch is the other hazard." >&2
echo "  Only enter after explicit confirmation." >&2

if [ "$WANT_EXIT_CODE" -eq 1 ]; then
  verdict suspected
  exit 1
fi
verdict suspected
exit 0
