#!/usr/bin/env bash
# flow-worktree-claim.sh - Cross-session ownership claim on a flow worktree
# (issue #597).
#
# Motivation: nothing stopped two concurrent /flow sessions from operating on
# the same repo, or the same worktree. The #503 live-driver guard protects
# RESUMING into an active worktree; it does not protect an active worktree from
# being REMOVED by someone else, and it has no notion of an owner, so it cannot
# tell "another session is driving this" from "someone left files dirty". The
# observed cost was silent data loss: a sibling session's Step-7 cleanup removed
# a live session's worktree by name, destroying uncommitted work.
#
# This helper makes ownership explicit and machine-checkable by riding git's own
# worktree lock. `git worktree lock --reason <text>` already makes
# `git worktree remove --force` refuse (it demands `-f -f`), so a claim is a
# real barrier rather than an advisory note, and the reason text is readable
# from `git worktree list --porcelain`. The reason we write is a single line:
#
#   flow-claim issue=<N> pid=<PID> session=<SID> host=<HOST> ts=<EPOCH>
#
# Liveness: the owning session is alive when `kill -0 <pid>` succeeds AND the
# recorded host matches this one (a pid from another machine says nothing about
# a pid here). A claim whose owner is gone is STALE and may be taken over, so
# the mechanism can never permanently wedge a repo. A lock this script did not
# write (no `flow-claim` prefix) is FOREIGN and is never stolen - someone locked
# that worktree deliberately.
#
# It is FAIL-OPEN by design: anything it cannot determine (not a worktree, git
# too old, lock unsupported on the primary checkout) reports and exits 0 rather
# than blocking a flow run. The one non-zero exit is the case it exists for -
# `claim` losing to a LIVE foreign owner.
#
# Usage:
#   flow-worktree-claim.sh claim   <WORKTREE_PATH> --issue <N> [--steal]
#   flow-worktree-claim.sh check   <WORKTREE_PATH>
#   flow-worktree-claim.sh check   --issue <N> [--repo <PATH>]
#   flow-worktree-claim.sh release <WORKTREE_PATH> [--force]
#
#   claim    Acquire the claim. Re-claiming a self-owned worktree refreshes the
#            timestamp (idempotent). A STALE claim is taken over automatically.
#            A LIVE foreign claim exits 1 unless --steal is passed.
#   check    Report the claim state without changing it. Always exits 0 unless
#            --exit-code is passed, which returns 1 for a held claim.
#   release  Drop a self-owned (or stale) claim. A foreign live claim is left
#            alone unless --force. Never fails the caller.
#
# Output ends with a machine-readable verdict line:
#   FLOW_CLAIM: free | self | held | stale | foreign | unsupported | unknown
# preceded by owner detail lines (FLOW_CLAIM_OWNER_PID=, ..._SESSION=, ..._HOST=,
# ..._TS=, ..._AGE_MIN=, FLOW_CLAIM_PATH=), each '-' when not applicable.
#
# Env:
#   CLAUDE_PID              owning process id (Claude Code sets it); falls back
#                           to $PPID
#   CLAUDE_CODE_SESSION_ID  owning session id; falls back to '-'
#   FLOW_CLAIM_MAX_AGE_HOURS  a claim from ANOTHER host older than this is
#                           treated as stale (default 24) - cross-host liveness
#                           cannot be probed, so age is the only safety valve
# Env (test hooks - unset in normal use):
#   FLOW_CLAIM_GIT          override the `git` binary
#   FLOW_CLAIM_NOW          override "now" as epoch seconds
#   FLOW_CLAIM_HOST         override this host's name
#   FLOW_CLAIM_LIVE_PIDS    ':'-separated pids to treat as alive (bypasses
#                           kill -0, so a test can simulate a live sibling)

set -uo pipefail

GIT="${FLOW_CLAIM_GIT:-git}"
MAX_AGE_HOURS="${FLOW_CLAIM_MAX_AGE_HOURS:-24}"
SELF_PID="${CLAUDE_PID:-$PPID}"
SELF_SESSION="${CLAUDE_CODE_SESSION_ID:-}"
SELF_HOST="${FLOW_CLAIM_HOST:-${HOSTNAME:-$(hostname 2>/dev/null || echo unknown)}}"
NOW="${FLOW_CLAIM_NOW:-$(date +%s)}"

CLAIM_PREFIX="flow-claim"

usage_fail() { echo "flow-worktree-claim: $1" >&2; exit 2; }

# Emit the owner detail block + verdict. All args default to '-'.
emit() {
  echo "FLOW_CLAIM_PATH=${O_PATH:--}"
  echo "FLOW_CLAIM_OWNER_PID=${O_PID:--}"
  echo "FLOW_CLAIM_OWNER_SESSION=${O_SESSION:--}"
  echo "FLOW_CLAIM_OWNER_HOST=${O_HOST:--}"
  echo "FLOW_CLAIM_TS=${O_TS:--}"
  echo "FLOW_CLAIM_AGE_MIN=${O_AGE_MIN:--}"
  echo "FLOW_CLAIM_ISSUE=${O_ISSUE:--}"
  echo "FLOW_CLAIM: $1"
}

# Absolute, symlink-resolved path (git's porcelain prints resolved paths, so
# both sides of the comparison must be normalized the same way).
abspath() {
  if [ -d "$1" ]; then (cd "$1" 2>/dev/null && pwd -P); else echo "$1"; fi
}

# is_alive PID HOST -> 0 when the owning session is still running here.
is_alive() {
  local pid="$1" host="$2"
  [ -n "$pid" ] && [ "$pid" != "-" ] || return 1
  # A pid only means something on the machine that recorded it.
  [ "$host" = "$SELF_HOST" ] || return 1
  if [ -n "${FLOW_CLAIM_LIVE_PIDS:-}" ]; then
    case ":$FLOW_CLAIM_LIVE_PIDS:" in
      *":$pid:"*) return 0 ;;
      *) return 1 ;;
    esac
  fi
  kill -0 "$pid" 2>/dev/null
}

# Parse a claim reason string into the O_* globals. Returns 1 when the reason
# is not one of ours (a foreign lock).
O_PATH=""; O_PID=""; O_SESSION=""; O_HOST=""; O_TS=""; O_AGE_MIN=""; O_ISSUE=""
parse_reason() {
  local reason="$1" field
  case "$reason" in
    "$CLAIM_PREFIX "*) : ;;
    *) return 1 ;;
  esac
  for field in $reason; do
    case "$field" in
      issue=*) O_ISSUE="${field#issue=}" ;;
      pid=*) O_PID="${field#pid=}" ;;
      session=*) O_SESSION="${field#session=}" ;;
      host=*) O_HOST="${field#host=}" ;;
      ts=*) O_TS="${field#ts=}" ;;
    esac
  done
  if [ -n "$O_TS" ] && printf '%s' "$O_TS" | grep -qE '^[0-9]+$'; then
    local age=$((NOW - O_TS))
    [ "$age" -lt 0 ] && age=0
    O_AGE_MIN=$((age / 60))
  fi
  return 0
}

# lock_reason_for PATH - print the lock reason for a worktree ('' when
# unlocked). Locked-with-no-reason prints the sentinel '(no reason)'.
lock_reason_for() {
  local want cur="" locked_line=""
  want="$(abspath "$1")"
  while IFS= read -r line; do
    case "$line" in
      "worktree "*) cur="$(abspath "${line#worktree }")"; locked_line="" ;;
      "locked "*)
        [ "$cur" = "$want" ] && { printf '%s' "${line#locked }"; return 0; }
        ;;
      "locked")
        [ "$cur" = "$want" ] && { printf '%s' "(no reason)"; return 0; }
        ;;
    esac
  done < <("$GIT" -C "$want" worktree list --porcelain 2>/dev/null)
  return 0
}

# Classify the current state of WORKTREE_PATH, setting the O_* owner globals
# and STATE. Deliberately NOT a value-returning function: the owner detail has
# to survive into emit(), and command substitution would run this in a subshell
# and discard every assignment.
classify() {
  local path="$1" reason
  O_PATH="$path"; O_PID=""; O_SESSION=""; O_HOST=""; O_TS=""; O_AGE_MIN=""; O_ISSUE=""

  if [ ! -d "$path" ]; then STATE=unknown; return 0; fi
  if ! "$GIT" -C "$path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    STATE=unknown; return 0
  fi
  # The primary checkout cannot be locked by git at all; a run on the
  # current-branch lane therefore has no claim to make.
  if [ ! -f "$path/.git" ]; then STATE=unsupported; return 0; fi

  reason="$(lock_reason_for "$path")"
  if [ -z "$reason" ]; then STATE=free; return 0; fi
  if ! parse_reason "$reason"; then STATE=foreign; return 0; fi

  if [ -n "$SELF_SESSION" ] && [ "$O_SESSION" = "$SELF_SESSION" ]; then
    STATE=self; return 0
  fi
  if [ "$O_HOST" = "$SELF_HOST" ] && [ "$O_PID" = "$SELF_PID" ]; then
    STATE=self; return 0
  fi
  if is_alive "$O_PID" "$O_HOST"; then STATE=held; return 0; fi
  # Not provably alive. Same host + dead pid is decisively stale; a claim from
  # another host is only stale once it has aged out.
  if [ "$O_HOST" = "$SELF_HOST" ]; then STATE=stale; return 0; fi
  if [ -n "$O_AGE_MIN" ] && [ "$O_AGE_MIN" -gt $((MAX_AGE_HOURS * 60)) ]; then
    STATE=stale; return 0
  fi
  STATE=held
}

# ---- argument parsing -------------------------------------------------------
VERB="${1:-}"
[ -n "$VERB" ] || usage_fail "usage: flow-worktree-claim.sh claim|check|release <WORKTREE_PATH> [options]"
shift

case "$VERB" in
  claim | check | release) : ;;
  --help | -h)
    sed -n '2,70p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *) usage_fail "unknown verb: $VERB (expected claim, check or release)" ;;
esac

WT=""
ISSUE_NUM=""
REPO=""
STEAL=0
FORCE=0
WANT_EXIT_CODE=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --issue)
      [ "$#" -ge 2 ] || usage_fail "--issue requires a number"
      ISSUE_NUM="$2"; shift
      ;;
    --issue=*) ISSUE_NUM="${1#--issue=}" ;;
    --repo)
      [ "$#" -ge 2 ] || usage_fail "--repo requires a path"
      REPO="$2"; shift
      ;;
    --repo=*) REPO="${1#--repo=}" ;;
    --steal) STEAL=1 ;;
    --force) FORCE=1 ;;
    --exit-code) WANT_EXIT_CODE=1 ;;
    --*) usage_fail "unknown option: $1" ;;
    *)
      [ -z "$WT" ] || usage_fail "unexpected argument: $1"
      WT="$1"
      ;;
  esac
  shift
done

if [ -n "$ISSUE_NUM" ]; then
  printf '%s' "$ISSUE_NUM" | grep -qE '^[0-9]+$' ||
    usage_fail "--issue must be a number, got: $ISSUE_NUM"
fi

# `check --issue N` resolves the worktree by branch, so a session can ask
# "does anyone hold issue N?" before it has a path of its own (issue #597,
# the cross-session claim check).
if [ -z "$WT" ] && [ -n "$ISSUE_NUM" ] && [ "$VERB" = check ]; then
  REPO="${REPO:-.}"
  cur=""
  while IFS= read -r line; do
    case "$line" in
      "worktree "*) cur="${line#worktree }" ;;
      "branch refs/heads/issue-${ISSUE_NUM}-"*) WT="$cur" ;;
    esac
  done < <("$GIT" -C "$REPO" worktree list --porcelain 2>/dev/null)
  if [ -z "$WT" ]; then
    O_PATH="-"
    emit free
    exit 0
  fi
fi

[ -n "$WT" ] || usage_fail "$VERB requires a worktree path"
WT="$(abspath "$WT")"

STATE=unknown
classify "$WT"

case "$VERB" in
  check)
    emit "$STATE"
    if [ "$WANT_EXIT_CODE" -eq 1 ] && [ "$STATE" = held ]; then exit 1; fi
    exit 0
    ;;

  release)
    case "$STATE" in
      self | stale)
        if "$GIT" -C "$WT" worktree unlock "$WT" >/dev/null 2>&1; then
          echo "flow-worktree-claim: released claim on '$WT'." >&2
        fi
        O_PID=""; O_SESSION=""; O_HOST=""; O_TS=""; O_AGE_MIN=""; O_ISSUE=""
        emit free
        ;;
      held | foreign)
        if [ "$FORCE" -eq 1 ]; then
          "$GIT" -C "$WT" worktree unlock "$WT" >/dev/null 2>&1
          echo "flow-worktree-claim: FORCE-released a $STATE claim on '$WT' (owner pid ${O_PID:--})." >&2
          emit free
        else
          echo "flow-worktree-claim: '$WT' is claimed by another session (pid ${O_PID:--}, session ${O_SESSION:--}) - not releasing. Pass --force to override." >&2
          emit "$STATE"
        fi
        ;;
      *) emit "$STATE" ;;
    esac
    exit 0
    ;;

  claim)
    [ -n "$ISSUE_NUM" ] || usage_fail "claim requires --issue <N>"
    case "$STATE" in
      held)
        if [ "$STEAL" -eq 0 ]; then
          echo "flow-worktree-claim: '$WT' is CLAIMED by a live session (pid ${O_PID:--}, session ${O_SESSION:--}, host ${O_HOST:--}, ~${O_AGE_MIN:-?}m ago)." >&2
          echo "  Another /flow run is driving this worktree right now (issue #597). Working here would race it:" >&2
          echo "  its cleanup can delete this checkout, and yours can delete theirs." >&2
          echo "  Either wait for that session to finish, or - if you are certain it is gone - re-run with --steal." >&2
          emit held
          exit 1
        fi
        echo "flow-worktree-claim: stealing a live claim on '$WT' (--steal; previous owner pid ${O_PID:--})." >&2
        "$GIT" -C "$WT" worktree unlock "$WT" >/dev/null 2>&1
        ;;
      foreign)
        # Someone locked this worktree for their own reasons. Never steal it,
        # but do not fail the run either - report and move on (fail-open).
        echo "flow-worktree-claim: '$WT' carries a non-flow lock; leaving it untouched and claiming nothing." >&2
        emit foreign
        exit 0
        ;;
      stale)
        echo "flow-worktree-claim: taking over a stale claim on '$WT' (owner pid ${O_PID:--} is gone)." >&2
        "$GIT" -C "$WT" worktree unlock "$WT" >/dev/null 2>&1
        ;;
      self)
        # Idempotent refresh: drop our own lock so the new timestamp lands.
        "$GIT" -C "$WT" worktree unlock "$WT" >/dev/null 2>&1
        ;;
      unsupported | unknown)
        echo "flow-worktree-claim: '$WT' cannot hold a claim ($STATE) - continuing unclaimed (advisory)." >&2
        emit "$STATE"
        exit 0
        ;;
    esac

    REASON="$CLAIM_PREFIX issue=$ISSUE_NUM pid=$SELF_PID session=${SELF_SESSION:--} host=$SELF_HOST ts=$NOW"
    if ! "$GIT" -C "$WT" worktree lock --reason "$REASON" "$WT" >/dev/null 2>&1; then
      echo "flow-worktree-claim: could not lock '$WT' (git too old, or lock unsupported) - continuing unclaimed (advisory)." >&2
      O_PID=""; O_SESSION=""; O_HOST=""; O_TS=""; O_AGE_MIN=""; O_ISSUE=""
      emit unsupported
      exit 0
    fi
    O_PID="$SELF_PID"; O_SESSION="${SELF_SESSION:--}"; O_HOST="$SELF_HOST"
    O_TS="$NOW"; O_AGE_MIN=0; O_ISSUE="$ISSUE_NUM"
    echo "flow-worktree-claim: claimed '$WT' for issue #$ISSUE_NUM (pid $SELF_PID)." >&2
    emit self
    exit 0
    ;;
esac
