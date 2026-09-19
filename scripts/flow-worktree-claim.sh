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
#   flow-claim issue=<N> pid=<PID> session=<SID> host=<HOST> ts=<EPOCH> start=<TICKS>
#
# Liveness: the owning session is alive when the recorded host matches this one
# (a pid from another machine says nothing about a pid here) AND the pid both
# EXISTS and is still the SAME PROCESS that wrote the claim.
#
# EXISTS IS NOT IDENTITY (issue #1032). `kill -0 <pid>` answers "some process
# has this number", and Linux recycles pids - on a busy host the whole space
# wraps in hours. A claim read through `kill -0` alone therefore reports a
# long-dead session as LIVE, which is the unsafe direction here: it is the
# reading that BLOCKS recovery, so the worktree becomes permanently
# unreclaimable and `--steal` - the deliberate override for a genuinely live
# owner - becomes the only way to clean up after a dead one. Once the safe path
# and the override are the same flag, the override has stopped meaning what it
# says.
#
# So the claim records an identity WITNESS the pid alone cannot forge: `start=`,
# field 22 of /proc/<pid>/stat, the boot-relative tick at which that process
# began. A pid can be reused; a pid paired with its start instant cannot be.
# Three readings, and the difference between the last two is the whole point:
#
#   matched     pid exists and its start-time equals the witness -> ALIVE
#   mismatched  pid exists but started at a different instant    -> NOT alive,
#               it is a DIFFERENT process wearing a recycled number
#   absent |    no witness recorded (a claim written before #1032), or /proc is
#   unreadable  unreadable (not Linux) -> identity CANNOT be established
#
# An unverifiable claim falls back to `kill -0`, but is then BOUNDED by
# FLOW_CLAIM_MAX_AGE_HOURS, which until #1032 gated only the cross-host branch.
# That bound is what guarantees no claim can wedge a repo forever. It is applied
# ONLY where identity could not be established: a claim whose witness MATCHES is
# never aged out, however long its session has been running, so a legitimately
# long-lived run cannot be evicted by the clock. The two-sidedness is deliberate
# and the asymmetry is the safety: age is a weak signal used only where the
# strong one is unavailable.
#
# The witness can only ever DEMOTE held -> stale on a positively read
# CONFLICTING value. `absent` and `unreadable` never produce `stale` on their
# own - a check that cannot read identity must not claim to have disproved it.
#
# A claim whose owner is gone is STALE and may be taken over, so the mechanism
# can never permanently wedge a repo. A lock this script did not write (no
# `flow-claim` prefix) is FOREIGN and is never stolen - someone locked that
# worktree deliberately.
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
# ..._TS=, ..._AGE_MIN=, ..._WITNESS=, FLOW_CLAIM_PATH=), each '-' when not
# applicable.
#
# FLOW_CLAIM_OWNER_WITNESS reports HOW liveness was decided, not merely what it
# decided (issue #1032): matched | mismatched | absent | unreadable | -. A caller
# that prints only the verdict cannot tell "the owner exited" from "this pid
# belongs to somebody else now", and those want different words in front of a
# user about to lose work.
#
# Env:
#   CLAUDE_PID              owning process id (Claude Code sets it); falls back
#                           to $PPID
#   CLAUDE_CODE_SESSION_ID  owning session id; falls back to '-'
#   FLOW_CLAIM_MAX_AGE_HOURS  a claim whose process identity could NOT be
#                           established - another host, or no readable witness -
#                           is treated as stale once older than this (default
#                           24). A claim with a MATCHING witness is never aged
#                           out: age is the fallback signal, used only where the
#                           identity check could not answer (issue #1032).
# Env (test hooks - unset in normal use):
#   FLOW_CLAIM_GIT          override the `git` binary
#   FLOW_CLAIM_NOW          override "now" as epoch seconds
#   FLOW_CLAIM_HOST         override this host's name
#   FLOW_CLAIM_LIVE_PIDS    ':'-separated pids to treat as alive (bypasses
#                           kill -0, so a test can simulate a live sibling)
#   FLOW_CLAIM_PROC_ROOT    override /proc for the start-time witness. A test
#                           seam, not a knob: it exists so BOTH witness lanes -
#                           readable and unreadable - are reachable on a host
#                           whose /proc works, which is every host the suite
#                           runs on.

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
  echo "FLOW_CLAIM_OWNER_WITNESS=${O_WITNESS:--}"
  echo "FLOW_CLAIM_STALE_REASON=${O_STALE_REASON:--}"
  echo "FLOW_CLAIM: $1"
}

# Absolute, symlink-resolved path (git's porcelain prints resolved paths, so
# both sides of the comparison must be normalized the same way).
abspath() {
  if [ -d "$1" ]; then (cd "$1" 2>/dev/null && pwd -P); else echo "$1"; fi
}

PROC_ROOT="${FLOW_CLAIM_PROC_ROOT:-/proc}"

# start_time_of PID - print the process's start instant, or nothing when it
# cannot be read (no such process, or no readable /proc on this host).
#
# Field 22 of /proc/<pid>/stat. Fields 1 and 2 are the pid and the comm, and
# comm is the one field that can contain spaces AND parentheses - it is the
# executable name, which the process itself controls. Splitting the whole line
# on whitespace therefore shifts every later field by however many spaces the
# name happens to hold, silently, which would make an honest witness compare
# unequal to itself. So consume through the LAST ') ' first (greedy ##, not the
# first match), after which field 20 of the remainder is field 22 of the line.
start_time_of() {
  local pid="$1" line rest
  [ -n "$pid" ] && [ "$pid" != "-" ] || return 0
  case "$pid" in *[!0-9]* | "") return 0 ;; esac
  line="$(cat "$PROC_ROOT/$pid/stat" 2>/dev/null)" || return 0
  [ -n "$line" ] || return 0
  case "$line" in *") "*) : ;; *) return 0 ;; esac
  rest="${line##*) }"
  # shellcheck disable=SC2086
  set -- $rest
  [ "$#" -ge 20 ] || return 0
  printf '%s' "${20}" 2>/dev/null || true
}

# witness_state PID WITNESS -> prints matched | mismatched | absent | unreadable
#
# The four are kept apart because only ONE of them is entitled to demote a claim
# (issue #1032). A check that cannot read identity has not disproved it, so
# `absent` and `unreadable` must never be rendered as `mismatched` downstream.
witness_state() {
  local pid="$1" want="$2" have
  if [ -z "$want" ] || [ "$want" = "-" ]; then printf 'absent'; return 0; fi
  # The process must be readable at all before its start-time can be compared.
  if [ ! -r "$PROC_ROOT/$pid/stat" ]; then printf 'unreadable'; return 0; fi
  have="$(start_time_of "$pid")"
  if [ -z "$have" ]; then printf 'unreadable'; return 0; fi
  if [ "$have" = "$want" ]; then printf 'matched'; else printf 'mismatched'; fi
}

# pid_exists PID -> 0 when SOME process holds this number (identity not asked).
pid_exists() {
  local pid="$1"
  [ -n "$pid" ] && [ "$pid" != "-" ] || return 1
  if [ -n "${FLOW_CLAIM_LIVE_PIDS:-}" ]; then
    case ":$FLOW_CLAIM_LIVE_PIDS:" in
      *":$pid:"*) return 0 ;;
      *) return 1 ;;
    esac
  fi
  kill -0 "$pid" 2>/dev/null
}

# is_alive PID HOST WITNESS -> 0 when the owning SESSION is still running here.
# Sets O_WITNESS to how identity was decided, which classify() then uses to pick
# between the decisive and the bounded lane.
is_alive() {
  local pid="$1" host="$2" witness="${3:-}"
  O_WITNESS="-"
  [ -n "$pid" ] && [ "$pid" != "-" ] || return 1
  # A pid only means something on the machine that recorded it.
  [ "$host" = "$SELF_HOST" ] || return 1
  pid_exists "$pid" || return 1
  O_WITNESS="$(witness_state "$pid" "$witness")"
  case "$O_WITNESS" in
    # The pid exists and started when the claim says it did: this IS the owner.
    matched) return 0 ;;
    # The pid exists but is a DIFFERENT process wearing a recycled number. This
    # is the one reading that may contradict `kill -0`, and it is the whole of
    # specimen #3: without it, a dead session reads as live forever.
    mismatched) return 1 ;;
    # Identity could not be established either way. Fall back to existence, as
    # before #1032 - classify() then applies the age bound so this lane cannot
    # wedge a repo permanently.
    *) return 0 ;;
  esac
}

# aged_out -> 0 when the claim is older than the configured bound.
#
# A claim with no readable timestamp is NOT aged out: an unreadable age is not
# an old one, and inventing staleness from a missing field is how a guard starts
# releasing live worktrees.
aged_out() {
  [ -n "$O_AGE_MIN" ] || return 1
  case "$O_AGE_MIN" in *[!0-9]* | "") return 1 ;; esac
  [ "$O_AGE_MIN" -gt $((MAX_AGE_HOURS * 60)) ]
}

# Parse a claim reason string into the O_* globals. Returns 1 when the reason
# is not one of ours (a foreign lock).
O_PATH=""; O_PID=""; O_SESSION=""; O_HOST=""; O_TS=""; O_AGE_MIN=""; O_ISSUE=""
O_START=""; O_WITNESS=""; O_STALE_REASON=""
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
      start=*) O_START="${field#start=}" ;;
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
  O_START=""; O_WITNESS=""; O_STALE_REASON=""

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
  # Matching on the pid ALONE is the same pid-identity mistake this issue is
  # about, pointed at ourselves: a recycled pid can land on OUR number while the
  # claim belongs to a session that has since died. Session id is authoritative
  # above; here the witness has to agree before a bare pid match may claim
  # ownership. Left unguarded this was the worse half of the bug, because
  # `self` ALSO makes worktree-remove.sh skip its independent occupancy check -
  # so a false `self` removes a guard rather than merely misreporting a state.
  if [ "$O_HOST" = "$SELF_HOST" ] && [ "$O_PID" = "$SELF_PID" ]; then
    if [ "$(witness_state "$O_PID" "$O_START")" != mismatched ]; then
      STATE=self; return 0
    fi
  fi
  if is_alive "$O_PID" "$O_HOST" "$O_START"; then
    # Alive. Whether that reading is DECISIVE depends on how it was reached
    # (issue #1032). A matching start-time witness identifies the process, so
    # the claim is held outright and no clock may evict it - a session may
    # legitimately work one worktree for days. An unverifiable reading is only
    # "some process holds this number", so it is bounded by age: that bound is
    # the guarantee that no claim wedges a repo forever, and it is applied HERE
    # rather than to every same-host claim precisely so a verified owner is
    # never its victim.
    case "$O_WITNESS" in
      matched) STATE=held; return 0 ;;
    esac
    if aged_out; then
      # Still running, but we could not confirm it is the SAME process and the
      # claim has outlived the bound. That is expiry, NOT a death - saying
      # otherwise would assert a fact this path never established.
      O_STALE_REASON=aged-out-unverified; STATE=stale; return 0
    fi
    STATE=held; return 0
  fi
  # Not alive. Same host is decisively stale, but for one of two different
  # reasons, and only the witness distinguishes them.
  if [ "$O_HOST" = "$SELF_HOST" ]; then
    if [ "$O_WITNESS" = mismatched ]; then
      O_STALE_REASON=recycled-pid
    else
      O_STALE_REASON=owner-exited
    fi
    STATE=stale; return 0
  fi
  # A claim from another host cannot be probed at all, so age is its only valve.
  if aged_out; then O_STALE_REASON=aged-out-remote-host; STATE=stale; return 0; fi
  STATE=held
}

# ---- argument parsing -------------------------------------------------------
VERB="${1:-}"
[ -n "$VERB" ] || usage_fail "usage: flow-worktree-claim.sh claim|check|release <WORKTREE_PATH> [options]"
shift

case "$VERB" in
  claim | check | release) : ;;
  --help | -h)
    # Derive the header's extent rather than hardcoding it: a fixed range
    # silently truncates --help the moment the header grows, and nothing
    # reports that (issue #1032 grew it past the old '2,70p').
    sed -n '2,/^[^#]/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
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
        O_START=""; O_WITNESS=""; O_STALE_REASON=""
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
          echo "flow-worktree-claim: '$WT' is CLAIMED by a live session (pid ${O_PID:--}, session ${O_SESSION:--}, host ${O_HOST:--}, ~${O_AGE_MIN:-?}m ago, identity ${O_WITNESS:--})." >&2
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
        # Name the two staleness causes apart (issue #1032). "gone" and "that
        # number belongs to someone else now" are different facts about the
        # world, and the second is the one a reader will not otherwise guess.
        case "$O_STALE_REASON" in
          recycled-pid)
            echo "flow-worktree-claim: taking over a stale claim on '$WT' (pid ${O_PID:--} exists but is a DIFFERENT process - the owner's pid was recycled)." >&2
            ;;
          aged-out-unverified)
            # Do NOT say "gone": the pid is still running. What expired is our
            # willingness to believe an ownership record we cannot verify.
            echo "flow-worktree-claim: taking over an EXPIRED claim on '$WT' (pid ${O_PID:--} still exists, but the claim records no verifiable process identity and is ~${O_AGE_MIN:-?}m old, past the ${MAX_AGE_HOURS}h bound)." >&2
            ;;
          aged-out-remote-host)
            echo "flow-worktree-claim: taking over an EXPIRED claim on '$WT' (owner is on host ${O_HOST:--}, whose liveness cannot be probed from here; ~${O_AGE_MIN:-?}m old, past the ${MAX_AGE_HOURS}h bound)." >&2
            ;;
          *)
            echo "flow-worktree-claim: taking over a stale claim on '$WT' (owner pid ${O_PID:--} is gone)." >&2
            ;;
        esac
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

    # Record the identity witness beside the pid (issue #1032). An empty one is
    # written as '-' rather than omitted, so a reader can tell "this version
    # recorded no witness" from "an older version had no such field" - and so
    # the field count of the reason line never varies.
    SELF_START="$(start_time_of "$SELF_PID")"
    REASON="$CLAIM_PREFIX issue=$ISSUE_NUM pid=$SELF_PID session=${SELF_SESSION:--} host=$SELF_HOST ts=$NOW start=${SELF_START:--}"
    if ! "$GIT" -C "$WT" worktree lock --reason "$REASON" "$WT" >/dev/null 2>&1; then
      echo "flow-worktree-claim: could not lock '$WT' (git too old, or lock unsupported) - continuing unclaimed (advisory)." >&2
      O_PID=""; O_SESSION=""; O_HOST=""; O_TS=""; O_AGE_MIN=""; O_ISSUE=""
      O_START=""; O_WITNESS=""; O_STALE_REASON=""
      emit unsupported
      exit 0
    fi
    O_PID="$SELF_PID"; O_SESSION="${SELF_SESSION:--}"; O_HOST="$SELF_HOST"
    O_TS="$NOW"; O_AGE_MIN=0; O_ISSUE="$ISSUE_NUM"
    O_START="${SELF_START:--}"
    O_WITNESS="$([ -n "$SELF_START" ] && echo matched || echo unreadable)"
    # Clear the PREVIOUS claim's staleness reason. This block describes the
    # claim just acquired, and carrying `aged-out-unverified` out beside
    # `FLOW_CLAIM: self` would attribute the old owner's expiry to the new
    # owner - a record asserting something that is not true of what it names,
    # which is the exact failure class this issue exists to remove.
    O_STALE_REASON=""
    echo "flow-worktree-claim: claimed '$WT' for issue #$ISSUE_NUM (pid $SELF_PID)." >&2
    emit self
    exit 0
    ;;
esac
